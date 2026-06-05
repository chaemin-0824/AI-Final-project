from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from datasets import load_dataset
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmark.metrics import accuracy, write_json  # noqa: E402
from benchmark.parse_cache import cache_key, evidence_text, load_parse_cache  # noqa: E402

MODES = ("image_only", "parsed_text_only", "parsed_visual")
# Generators chosen to match docs/VisRAG Multi Page Compression.pptx slide 10 baseline.
#   - qwen2vl7b: teammate-aligned baseline (Qwen2-VL-7B-Instruct, bf16). Default model_id.
#   - qwen2vl7b_bnb4: same weights loaded with bitsandbytes 4-bit (~5-6 GB VRAM).
#                     We dropped AWQ because AutoAWQ's triton kernel breaks on torch>=2.4.
#   - minicpmv26: VisRAG paper-aligned alternative.
#   - gpt4o: paper API fallback (no local GPU).
GENERATOR_BACKENDS = ("qwen2vl7b", "qwen2vl7b_bnb4", "minicpmv26", "gpt4o")
DEFAULT_BACKEND = "qwen2vl7b_bnb4"
_MODEL_CACHE: dict[tuple[str, str], tuple[Any, Any]] = {}


def default_model_for_backend(backend: str) -> str:
    """답변 생성 백엔드별 기본 모델 이름을 돌려준다.

    backend는 qwen2vl7b / qwen2vl7b_bnb4 / minicpmv26 / gpt4o 중 하나이며,
    반환값은 실제 호출에 사용할 모델 경로/이름이다.
    예: default_model_for_backend("qwen2vl7b_bnb4").
    """
    defaults = {
        "qwen2vl7b": "Qwen/Qwen2-VL-7B-Instruct",
        "qwen2vl7b_bnb4": "Qwen/Qwen2-VL-7B-Instruct",  # base weights, quantised on load
        "minicpmv26": "openbmb/MiniCPM-V-2_6",
        "gpt4o": "gpt-4o",
    }
    return defaults[backend]


def load_trec(path: str | Path) -> dict[str, list[tuple[str, float]]]:
    run: dict[str, list[tuple[int, str, float]]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 6:
                continue
            qid, docid, rank, score = parts[0], parts[2], int(parts[3]), float(parts[4])
            run.setdefault(qid, []).append((rank, docid, score))
    return {qid: [(docid, score) for rank, docid, score in sorted(items)] for qid, items in run.items()}


def load_qrels(dataset: str, dataset_path: str, cache_dir: str | None = None) -> dict[str, list[str]]:
    ds = load_dataset(dataset_path, name="qrels", split="train", cache_dir=cache_dir)
    qrels: dict[str, list[str]] = {}
    for row in ds:
        if float(row.get("score", 1)) <= 0:
            continue
        qrels.setdefault(str(row["query-id"]), []).append(str(row["corpus-id"]))
    return qrels


def positive_docids(dataset_name: str, qid: str) -> list[str]:
    # Same convention used by openbmb/visrag generate.py.
    if dataset_name == "SlideVQA":
        return [docid for docid in qid.split("query_number")[0].split("tcy6") if docid]
    return [qid[: -1 - len(qid.split("-")[-1])]]


def pil_to_part(img: Image.Image) -> dict[str, str]:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=85)
    return {"mime_type": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode("ascii")}


def build_prompt(query: str, parsed_context: str, mode: str) -> str:
    if mode == "image_only":
        evidence_instruction = "Use only the provided document page image(s)."
        context_block = "(not provided)"
    elif mode == "parsed_text_only":
        evidence_instruction = "Use only the parsed text/table evidence. No images are provided."
        context_block = parsed_context or "(not provided)"
    else:
        evidence_instruction = "Use parsed text/table evidence for exact labels and values, and use images to verify visual/layout evidence."
        context_block = parsed_context or "(not provided)"

    return f"""You are evaluating a document QA method on the VisRAG benchmark.
{evidence_instruction}
Answer only the final answer. For numeric answers, return the exact visible value when possible.
If the evidence is insufficient, answer: insufficient to answer.

[Parsed text/table evidence]
{context_block}

[Question]
{query}
"""


def build_minicpm_messages(prompt: str, images: list[Image.Image]) -> list[dict[str, Any]]:
    """MiniCPM-V 2.6의 chat 입력 메시지를 만든다.

    prompt는 질문과 증거 지시문이고, images는 VLM이 함께 볼 페이지 이미지 목록이다.
    이미지가 있으면 논문 코드처럼 `[이미지..., 텍스트]` 형태로 넣고, 이미지가 없으면
    텍스트만 넣는다. 예: build_minicpm_messages("Q?", [img]).
    """
    content: Any = images + [prompt] if images else prompt
    return [{"role": "user", "content": content}]


def call_minicpmv26(query: str, images: list[Image.Image], parsed_context: str, model_name: str, mode: str, max_new_tokens: int) -> dict[str, Any]:
    """MiniCPM-V 2.6으로 답변을 생성한다.

    query는 질문, images는 원본 페이지 이미지, parsed_context는 Upstage가 뽑은 텍스트/표 증거다.
    출력은 prediction과 token placeholder를 담은 dict다. 예: call_minicpmv26(...).
    """
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "MiniCPM-V 2.6 실행에는 torch와 transformers가 필요합니다. "
            "VisRAG 전체 의존성을 설치하거나 --generator-backend gpt4o(논문 fallback)를 사용하세요."
        ) from exc

    cache_key_model = ("minicpmv26", model_name)
    if cache_key_model in _MODEL_CACHE:
        model, tokenizer = _MODEL_CACHE[cache_key_model]
    else:
        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        model = AutoModel.from_pretrained(model_name, trust_remote_code=True, torch_dtype=dtype)
        model = model.eval()
        if torch.cuda.is_available():
            model = model.cuda()
        _MODEL_CACHE[cache_key_model] = (model, tokenizer)

    prompt = build_prompt(query, parsed_context, mode)
    msgs = build_minicpm_messages(prompt, images if mode in {"image_only", "parsed_visual"} else [])
    start = time.time()
    response = model.chat(
        image=None,
        msgs=msgs,
        tokenizer=tokenizer,
        sampling=False,
        max_new_tokens=max_new_tokens,
    )
    return {
        "prediction": response if isinstance(response, str) else str(response),
        "elapsed_sec": round(time.time() - start, 3),
        "input_tokens": 0,
        "output_tokens": 0,
    }


def call_gpt4o(query: str, images: list[Image.Image], parsed_context: str, model_name: str, mode: str, max_new_tokens: int) -> dict[str, Any]:
    """GPT-4o로 동일한 증거 입력 조건의 답변을 생성한다.

    query는 질문, images는 이미지 증거, parsed_context는 텍스트/표 증거다. 논문에서
    GPT-4o도 사용되므로 GPU가 없을 때의 paper-aligned 대안이다.
    """
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --generator-backend gpt4o")
    client = OpenAI(api_key=api_key)
    content: list[dict[str, Any]] = [{"type": "text", "text": build_prompt(query, parsed_context, mode)}]
    if mode in {"image_only", "parsed_visual"}:
        for image in images:
            encoded = pil_to_part(image)["data"]
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}"}})
    start = time.time()
    response = client.chat.completions.create(
        model=model_name,
        messages=[{"role": "user", "content": content}],
        max_tokens=max_new_tokens,
    )
    usage = getattr(response, "usage", None)
    return {
        "prediction": response.choices[0].message.content or "",
        "elapsed_sec": round(time.time() - start, 3),
        "input_tokens": getattr(usage, "prompt_tokens", 0) if usage else 0,
        "output_tokens": getattr(usage, "completion_tokens", 0) if usage else 0,
    }


def build_qwen2vl_messages(prompt: str, images: list[Image.Image]) -> list[dict[str, Any]]:
    """Qwen2-VL chat 메시지 포맷.

    Qwen2-VL은 OpenAI-style multipart content를 사용한다: 이미지마다
    `{"type": "image", "image": <PIL.Image>}`, 텍스트는
    `{"type": "text", "text": ...}`. images가 비어 있으면 텍스트만.
    """
    parts: list[dict[str, Any]] = []
    for img in images:
        parts.append({"type": "image", "image": img})
    parts.append({"type": "text", "text": prompt})
    return [{"role": "user", "content": parts}]


def call_qwen2vl(query: str, images: list[Image.Image], parsed_context: str, model_name: str, mode: str, max_new_tokens: int, use_bnb4: bool) -> dict[str, Any]:
    """Qwen2-VL-7B-Instruct로 답변을 생성한다.

    use_bnb4=True면 bitsandbytes 4-bit NF4 quantisation으로 8 GB-class GPU에서도
    동작하도록 한다. bf16은 ~14 GB, NF4는 ~5-6 GB.
    """
    try:
        import torch
        from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2VLForConditionalGeneration
    except ImportError as exc:
        raise RuntimeError(
            "Qwen2-VL 실행에는 torch와 transformers>=4.45가 필요합니다. "
            "pip install 'transformers>=4.51,<4.52' 'qwen-vl-utils' 'accelerate' && "
            "(4-bit 사용 시) pip install bitsandbytes"
        ) from exc
    try:
        from qwen_vl_utils import process_vision_info
    except ImportError as exc:
        raise RuntimeError(
            "Qwen2-VL은 qwen-vl-utils가 필요합니다. pip install qwen-vl-utils"
        ) from exc

    cache_key_model = ("qwen2vl7b_bnb4" if use_bnb4 else "qwen2vl7b", model_name)
    if cache_key_model in _MODEL_CACHE:
        model, processor = _MODEL_CACHE[cache_key_model]
    else:
        kwargs: dict[str, Any] = {"trust_remote_code": True}
        if use_bnb4:
            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )
            kwargs["torch_dtype"] = torch.float16
        else:
            kwargs["torch_dtype"] = torch.bfloat16 if torch.cuda.is_available() else torch.float32
        if torch.cuda.is_available():
            kwargs["device_map"] = "auto"
        model = Qwen2VLForConditionalGeneration.from_pretrained(model_name, **kwargs).eval()
        processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True, use_fast=True)
        # Cap image patches so InfoVQA-style tall infographics don't generate 20k+
        # vision tokens. 1024×1280 ≈ 1.3M pixels ≈ ~1700 tokens after 28×28 patching.
        # Env override: QWEN_MAX_PIXELS / QWEN_MIN_PIXELS in case a future dataset
        # needs more resolution.
        max_pixels = int(os.environ.get("QWEN_MAX_PIXELS", str(1280 * 1024)))
        min_pixels = int(os.environ.get("QWEN_MIN_PIXELS", str(256 * 256)))
        if hasattr(processor, "image_processor"):
            processor.image_processor.max_pixels = max_pixels
            processor.image_processor.min_pixels = min_pixels
        # Drop sampling-only knobs from the generation_config so do_sample=False
        # doesn't trigger noisy warnings on every call.
        if hasattr(model, "generation_config") and model.generation_config is not None:
            for k in ("temperature", "top_p", "top_k"):
                if hasattr(model.generation_config, k):
                    setattr(model.generation_config, k, None)
        _MODEL_CACHE[cache_key_model] = (model, processor)

    prompt = build_prompt(query, parsed_context, mode)
    msgs = build_qwen2vl_messages(prompt, images if mode in {"image_only", "parsed_visual"} else [])
    text = processor.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    image_inputs, video_inputs = process_vision_info(msgs)
    inputs = processor(
        text=[text],
        images=image_inputs,
        videos=video_inputs,
        padding=True,
        return_tensors="pt",
    )
    if torch.cuda.is_available():
        inputs = inputs.to("cuda")
    start = time.time()
    with torch.no_grad():
        generated = model.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    trimmed = [out[len(inp):] for inp, out in zip(inputs.input_ids, generated)]
    out_text = processor.batch_decode(trimmed, skip_special_tokens=True, clean_up_tokenization_spaces=False)[0]
    in_tokens = int(inputs.input_ids.numel())
    out_tokens = int(sum(t.numel() for t in trimmed))
    return {
        "prediction": out_text.strip(),
        "elapsed_sec": round(time.time() - start, 3),
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    }


def call_generator(backend: str, query: str, images: list[Image.Image], parsed_context: str, model_name: str, mode: str, max_new_tokens: int) -> dict[str, Any]:
    """선택된 생성기 백엔드로 답변 생성을 위임한다.

    backend는 qwen2vl7b / qwen2vl7b_bnb4 / minicpmv26 / gpt4o 중 하나.
    나머지 입력은 같은 질문·같은 증거. 예: call_generator("qwen2vl7b_bnb4", ...).
    """
    if backend in {"qwen2vl7b", "qwen2vl7b_bnb4"}:
        return call_qwen2vl(query, images, parsed_context, model_name, mode, max_new_tokens, use_bnb4=(backend == "qwen2vl7b_bnb4"))
    if backend == "minicpmv26":
        return call_minicpmv26(query, images, parsed_context, model_name, mode, max_new_tokens)
    if backend == "gpt4o":
        return call_gpt4o(query, images, parsed_context, model_name, mode, max_new_tokens)
    raise ValueError(f"Unsupported generator backend: {backend}")


def build_parsed_context(dataset: str, docids: list[str], parse_cache_path: str | None) -> tuple[str, bool, list[str]]:
    if not parse_cache_path:
        return "", False, []
    cache = load_parse_cache(parse_cache_path)
    contexts: list[str] = []
    available_docids: list[str] = []
    for docid in docids:
        doc = cache.get(cache_key(dataset, docid))
        if not doc:
            continue
        text = evidence_text(doc)
        if text:
            contexts.append(f"[Document {docid}]\n{text}")
            available_docids.append(docid)
    return "\n\n".join(contexts), bool(contexts), available_docids


def main() -> None:
    parser = argparse.ArgumentParser(description="Run domain-free Parsed-Visual RAG generation on VisRAG benchmark data.")
    parser.add_argument("--dataset", required=True, choices=["ArxivQA", "ChartQA", "MP-DocVQA", "InfoVQA", "PlotQA", "SlideVQA"])
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--trec", default=None, help="TREC run from retrieval. If absent, --oracle is required.")
    parser.add_argument("--oracle", action="store_true", help="Use gold positive document ids instead of retrieved docs.")
    parser.add_argument("--topk", type=int, default=1)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mode", choices=MODES, default="parsed_visual")
    parser.add_argument("--generator-backend", choices=GENERATOR_BACKENDS, default=DEFAULT_BACKEND,
                        help=f"Default: {DEFAULT_BACKEND} (teammate PPT baseline aligned).")
    parser.add_argument("--parse-cache", default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--max-new-tokens", type=int, default=20)
    parser.add_argument("--output", default=None)
    parser.add_argument("--dry-run", action="store_true", help="Validate loading and selection without calling the generator.")
    args = parser.parse_args()

    if args.mode in {"parsed_text_only", "parsed_visual"} and not args.parse_cache:
        raise SystemExit(f"--parse-cache is required for mode={args.mode}")
    if args.model is None:
        args.model = default_model_for_backend(args.generator_backend)

    dataset_path = args.dataset_path or f"openbmb/VisRAG-Ret-Test-{args.dataset}"
    queries = load_dataset(dataset_path, name="queries", split="train", cache_dir=args.cache_dir)
    run = load_trec(args.trec) if args.trec else {}
    qrels = load_qrels(args.dataset, dataset_path, args.cache_dir) if args.oracle else {}
    if not args.oracle and not run:
        raise SystemExit("Provide --trec or --oracle")

    # Pre-compute the set of corpus ids that will actually be needed so we can
    # load only those images. Loading the entire VisRAG corpus into memory OOMs
    # on large datasets (e.g. SlideVQA, MP-DocVQA).
    needed_corpus_ids: set[str] = set()
    if args.mode in {"image_only", "parsed_visual"} and not args.dry_run:
        count = 0
        for ex in queries:
            if args.limit is not None and count >= args.limit:
                break
            qid = str(ex["query-id"])
            if args.oracle:
                docids = (qrels.get(qid) or positive_docids(args.dataset, qid))[: args.topk]
            else:
                docids = [d for d, _ in run.get(qid, [])[: args.topk]]
            needed_corpus_ids.update(docids)
            count += 1

    corpus: dict[str, Image.Image] = {}
    if needed_corpus_ids:
        corpus_ds = load_dataset(dataset_path, name="corpus", split="train", cache_dir=args.cache_dir)
        for row in corpus_ds:
            cid = row["corpus-id"]
            if cid in needed_corpus_ids:
                corpus[cid] = row["image"].convert("RGB")
                if len(corpus) == len(needed_corpus_ids):
                    break

    rows: list[dict[str, Any]] = []
    for ex in queries:
        if args.limit is not None and len(rows) >= args.limit:
            break
        qid = str(ex["query-id"])
        query = str(ex["query"])
        answer = ex.get("answer")
        if args.oracle:
            docids = qrels.get(qid) or positive_docids(args.dataset, qid)
            docids = docids[: args.topk]
            scores = [1.0] * len(docids)
        else:
            ranked = run.get(qid, [])[: args.topk]
            docids = [d for d, _ in ranked]
            scores = [s for _, s in ranked]
        images = [corpus[d] for d in docids if d in corpus] if corpus else []
        parsed_context, context_available, parsed_docids = build_parsed_context(args.dataset, docids, args.parse_cache)
        row: dict[str, Any] = {
            "dataset": args.dataset,
            "qid": qid,
            "query": query,
            "answer": answer,
            "docids": docids,
            "scores": scores,
            "topk": args.topk,
            "method": args.mode,
            "generator_backend": args.generator_backend,
            "generator_model": args.model,
            "retrieval_source": "oracle_qrels" if args.oracle else "trec",
            "ocr_context_available": context_available,
            "parsed_docids": parsed_docids,
            "n_images": len(images),
        }
        if args.dry_run:
            row["prediction"] = "DRY_RUN"
        else:
            row.update(call_generator(
                args.generator_backend,
                query,
                images,
                parsed_context=parsed_context,
                model_name=args.model,
                mode=args.mode,
                max_new_tokens=args.max_new_tokens,
            ))
        rows.append(row)
        print(f"[{len(rows)}] {qid}: mode={args.mode} docs={len(docids)} images={len(images)} parsed={context_available} pred={row.get('prediction','')[:80]}")

    summary = accuracy(rows, pred_key="prediction", answer_key="answer")
    payload = {"summary": summary, "rows": rows}
    out = Path(args.output or ROOT / "results" / "v12_on_visrag" / f"{args.dataset}_{args.mode}_top{args.topk}.json")
    write_json(out, payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
