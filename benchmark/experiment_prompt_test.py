"""Prompt-bias hypothesis test on the tf457 Image+Text cells.

Hypothesis (user, 2026-06-11):
    "Image+Text (Upstage)" underperforms "Image+Text (Qwen OCR)" because the
    answer prompt biases the model toward text ("Use parsed text/table evidence
    for exact labels and values, and use images to verify visual/layout
    evidence."). When Upstage parsed text is clean, the model relies on it and
    barely consults the image.

Test:
    Same conditions as tf457 (Qwen2-VL-7B-Instruct NF4, oracle qrels topk=1,
    first 100 queries per dataset). Two prompt variants × two text sources:

      - prompt=tf457        : original "text-first, image-verify" instruction
      - prompt=image_first  : "image-primary, text-supportive" instruction

      - mode=upstage_text_image  : Upstage parsed text + page image(s)
      - mode=qwen_ocr_text_image : Qwen2-VL self-OCR text + page image(s)

Outputs:
    results/prompt_test/{dataset}_{mode}_{prompt}.json
    results/prompt_test/ocr_cache/{dataset}.jsonl  (shared Qwen OCR cache)

The Qwen OCR_PROMPT is ported verbatim from the team's run_comparison_v2.py
(visrag_research/src/) so the OCR engine matches tf457's "Image+Text (Qwen OCR)"
row.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.metrics import accuracy, write_json  # noqa: E402
from benchmark.v12_on_visrag import (  # noqa: E402
    _MODEL_CACHE,
    build_qwen2vl_messages,
    default_model_for_backend,
)

MODES = ("upstage_text_image", "qwen_ocr_text_image")
PROMPT_VARIANTS = ("tf457", "image_first")

DATASETS = ("InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA")

# Verbatim from visrag_research/src/run_comparison_v2.py (team OCR engine).
OCR_PROMPT = (
    "Extract all text content from this document image. "
    "Preserve the structure: use headings, bullet points, and paragraphs as in the original. "
    "Output only the extracted text — no explanations or commentary."
)

# Answer-prompt evidence instructions.
EVIDENCE_INSTRUCTION = {
    # tf457: ported verbatim from benchmark/v12_on_visrag.py (parsed_visual branch).
    "tf457": "Use parsed text/table evidence for exact labels and values, and use images to verify visual/layout evidence.",
    # image_first: invert the bias — image is the primary evidence, parsed
    # text is only a secondary cross-check.
    "image_first": "Use the document page image(s) as the primary evidence. Read directly from the image. Use the parsed text/table only as a secondary cross-check for ambiguous labels or numeric values.",
}


def build_answer_prompt(query: str, parsed_context: str, variant: str) -> str:
    instruction = EVIDENCE_INSTRUCTION[variant]
    context = parsed_context or "(not provided)"
    return f"""You are evaluating a document QA method on the VisRAG benchmark.
{instruction}
Answer only the final answer. For numeric answers, return the exact visible value when possible.
If the evidence is insufficient, answer: insufficient to answer.

[Parsed text/table evidence]
{context}

[Question]
{query}
"""


# ---------------------------------------------------------------------------
# Lightweight wrapper around Qwen2-VL inference that shares the model cache
# with v12_on_visrag.call_qwen2vl. We need this because call_qwen2vl is
# hard-wired to build_prompt's 3-mode evidence string.
# ---------------------------------------------------------------------------

def _load_or_get_model(model_name: str, use_bnb4: bool = True):
    import torch
    from transformers import AutoProcessor, BitsAndBytesConfig, Qwen2VLForConditionalGeneration

    cache_key_model = ("qwen2vl7b_bnb4" if use_bnb4 else "qwen2vl7b", model_name)
    if cache_key_model in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key_model]

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
    max_pixels = int(os.environ.get("QWEN_MAX_PIXELS", str(1280 * 1024)))
    min_pixels = int(os.environ.get("QWEN_MIN_PIXELS", str(256 * 256)))
    if hasattr(processor, "image_processor"):
        processor.image_processor.max_pixels = max_pixels
        processor.image_processor.min_pixels = min_pixels
    if hasattr(model, "generation_config") and model.generation_config is not None:
        for k in ("temperature", "top_p", "top_k"):
            if hasattr(model.generation_config, k):
                setattr(model.generation_config, k, None)
    _MODEL_CACHE[cache_key_model] = (model, processor)
    return model, processor


def vlm_generate(prompt: str, images: list[Image.Image], model_name: str, max_new_tokens: int) -> dict[str, Any]:
    import torch
    from qwen_vl_utils import process_vision_info

    model, processor = _load_or_get_model(model_name, use_bnb4=True)
    msgs = build_qwen2vl_messages(prompt, images)
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
    elapsed = round(time.time() - start, 3)
    del inputs, generated, trimmed
    return {
        "text": out_text.strip(),
        "elapsed_sec": elapsed,
        "input_tokens": in_tokens,
        "output_tokens": out_tokens,
    }


# ---------------------------------------------------------------------------
# Caches
# ---------------------------------------------------------------------------

class JsonlCache:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, str] = {}
        if path.exists():
            with open(path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        row = json.loads(line)
                        self.data[row["key"]] = row["value"]

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def put(self, key: str, value: str) -> None:
        self.data[key] = value
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "value": value}, ensure_ascii=False) + "\n")


def load_upstage_text(dataset: str) -> dict[str, str]:
    path = ROOT / "data" / "parsed" / f"{dataset}_first100_qrels_upstage.jsonl"
    cache: dict[str, str] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            cache[row["corpus_id"]] = row.get("text", "")
    return cache


# Self-OCR alignment hypothesis test: rewrite Upstage's layout-preserving text
# so its surface form is closer to what Qwen2-VL would emit if it OCR'd the
# same page (continuous prose, no spurious bullet markers, single-line blocks).
# If the hypothesis is right, this should reduce the cross-modal-alignment cost
# at answer time and move Upstage I+T closer to Qwen OCR I+T.
_BULLET_LINE_RE = re.compile(r"^\s*[•●○■□▪▫\-\*•]+\s*$", re.MULTILINE)
_KOREAN_PARSE_MARKER_RE = re.compile(r"^\s*-\s*수집\s*$", re.MULTILINE)
_DASH_RULE_LINE_RE = re.compile(r"^\s*[-_=]{2,}\s*$", re.MULTILINE)


def normalize_upstage_text(text: str) -> str:
    text = _BULLET_LINE_RE.sub("", text)
    text = _KOREAN_PARSE_MARKER_RE.sub("", text)
    text = _DASH_RULE_LINE_RE.sub("", text)
    # Strip trailing spaces on each line + collapse intra-line whitespace.
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    # Join visual line-wraps: blank lines between a non-terminator end and a
    # continuation start (lowercase / conjunction) collapse to a single space.
    text = re.sub(
        r"(?<=[A-Za-z0-9,;:\-])\n\s*\n\s*(?=[a-z])",
        " ",
        text,
    )
    text = re.sub(r"(?<=[A-Za-z0-9,;:\-])\n(?=[a-z])", " ", text)
    # Collapse remaining 3+ newlines down to a single paragraph break.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def get_ocr_text(corpus_id: str, image: Image.Image, cache: JsonlCache, model_name: str) -> tuple[str, float]:
    cached = cache.get(corpus_id)
    if cached is not None:
        return cached, 0.0
    out = vlm_generate(OCR_PROMPT, [image], model_name, max_new_tokens=512)
    cache.put(corpus_id, out["text"])
    return out["text"], out["elapsed_sec"]


# ---------------------------------------------------------------------------
# Sample + image loading
# ---------------------------------------------------------------------------

def load_chaemin_samples(dataset: str, limit: int | None) -> list[dict[str, Any]]:
    """Reuse the exact (qid, query, answer, docids) tuples from the user's
    image_only first100 oracle run — same alignment as team tf457."""
    path = ROOT / "results" / "v12_on_visrag" / "today" / f"{dataset}_image_only_top1_first100.json"
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)
    rows = [
        {"qid": r["qid"], "query": r["query"], "answer": r["answer"], "docids": r["docids"]}
        for r in payload["rows"]
    ]
    if limit is not None:
        rows = rows[:limit]
    return rows


def load_corpus_images(dataset: str, needed: set[str]) -> dict[str, Image.Image]:
    """Reuse the user's HF-dataset-backed corpus loader so we do not depend on
    /data/jameskimh parquet paths from the team script."""
    from datasets import load_dataset

    dataset_path = f"openbmb/VisRAG-Ret-Test-{dataset}"
    corpus_ds = load_dataset(dataset_path, name="corpus", split="train")
    images: dict[str, Image.Image] = {}
    for row in corpus_ds:
        cid = row["corpus-id"]
        if cid in needed and cid not in images:
            images[cid] = row["image"].convert("RGB")
            if len(images) == len(needed):
                break
    missing = needed - set(images)
    if missing:
        raise RuntimeError(f"{dataset}: {len(missing)} corpus images missing, e.g. {sorted(missing)[:3]}")
    return images


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="tf457 prompt-bias hypothesis test.")
    parser.add_argument("--dataset", required=True, choices=list(DATASETS))
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--prompt", required=True, choices=PROMPT_VARIANTS)
    parser.add_argument("--limit", type=int, default=100, help="#samples (tf457 used 100).")
    parser.add_argument("--max-new-tokens", type=int, default=20)
    parser.add_argument("--model", default=None)
    parser.add_argument("--results-dir", default=None)
    parser.add_argument(
        "--upstage-normalize",
        action="store_true",
        help="Normalize Upstage text to Qwen-OCR-style (self-OCR alignment test).",
    )
    args = parser.parse_args()

    if args.model is None:
        args.model = default_model_for_backend("qwen2vl7b_bnb4")

    results_dir = Path(args.results_dir or ROOT / "results" / "prompt_test")
    results_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = results_dir / "ocr_cache"
    ocr_cache = JsonlCache(cache_dir / f"{args.dataset}.jsonl")

    samples = load_chaemin_samples(args.dataset, args.limit)
    needed = {d for s in samples for d in s["docids"]}
    print(f"[{args.dataset}/{args.mode}/{args.prompt}] {len(samples)} queries, {len(needed)} corpus images", flush=True)
    corpus = load_corpus_images(args.dataset, needed)

    upstage_text = load_upstage_text(args.dataset) if args.mode == "upstage_text_image" else {}

    rows: list[dict[str, Any]] = []
    for i, s in enumerate(samples):
        images = [corpus[d] for d in s["docids"]]
        ocr_sec = 0.0
        chunks: list[str] = []

        if args.mode == "upstage_text_image":
            for d in s["docids"]:
                t = upstage_text.get(d, "")
                if t and args.upstage_normalize:
                    t = normalize_upstage_text(t)
                if t:
                    chunks.append(f"[Document {d}]\n{t}")
        else:  # qwen_ocr_text_image
            for d, img in zip(s["docids"], images):
                t, sec = get_ocr_text(d, img, ocr_cache, args.model)
                ocr_sec += sec
                chunks.append(f"[Document {d}]\n{t}")

        context = "\n\n".join(chunks)
        prompt = build_answer_prompt(s["query"], context, args.prompt)
        out = vlm_generate(prompt, images, args.model, max_new_tokens=args.max_new_tokens)

        row: dict[str, Any] = {
            "dataset": args.dataset,
            "qid": s["qid"],
            "query": s["query"],
            "answer": s["answer"],
            "docids": s["docids"],
            "method": args.mode,
            "prompt_variant": args.prompt,
            "generator_backend": "qwen2vl7b_bnb4",
            "generator_model": args.model,
            "retrieval_source": "chaemin_first100_oracle",
            "prediction": out["text"],
            "elapsed_sec": out["elapsed_sec"],
            "ocr_elapsed_sec": round(ocr_sec, 3),
            "input_tokens": out["input_tokens"],
            "output_tokens": out["output_tokens"],
            "n_images": len(images),
            "context_available": bool(context.strip()),
        }
        rows.append(row)
        print(f"[{i + 1}/{len(samples)}] {s['qid']}: imgs={len(images)} pred={out['text'][:60]!r}", flush=True)

    summary = accuracy(rows, pred_key="prediction", answer_key="answer")
    payload = {"summary": summary, "rows": rows}
    suffix = "_norm" if args.upstage_normalize and args.mode == "upstage_text_image" else ""
    out_path = results_dir / f"{args.dataset}_{args.mode}_{args.prompt}{suffix}.json"
    write_json(out_path, payload)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"wrote {out_path}", flush=True)


if __name__ == "__main__":
    main()
