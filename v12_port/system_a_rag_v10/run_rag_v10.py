"""Run RAG v10 with Upstage smart chunking and chapter-filtered hybrid retrieval."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
from langchain_core.documents import Document

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from evaluation.judge import judge_all_results
from questions import QUESTIONS
from system_a_rag_v10.chunker import build_smart_chunks
from system_a_rag_v10.embeddings import GeminiEmbeddings
from system_a_rag_v10.retriever_v10 import ChapterHybridRetriever, rag_answer_v10
from system_a_rag_v10.upstage_loader import load_upstage_parse_pages


TEST_QIDS = ["Q03", "Q06", "Q09", "Q18", "Q29"]


def _serialize_docs(docs: list[Document]) -> list[dict]:
    return [
        {
            "page_content": doc.page_content,
            "metadata": doc.metadata,
        }
        for doc in docs
    ]


def _save_chunk_cache(bridge_name: str, docs: list[Document]) -> Path:
    cache_path = Path(config.PROJECT_ROOT) / "data" / bridge_name / "upstage_v10_chunks.json"
    cache_path.write_text(
        json.dumps(_serialize_docs(docs), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return cache_path


def _load_judged_subset(path: Path, qids: list[str]) -> dict[str, dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["question_id"]: item
        for item in data
        if item.get("question_id") in qids
    }


def _build_comparison_markdown(bridge_name: str, v10_results: dict, judged_v10_path: Path, qids: list[str]) -> str:
    judged_paths = {
        "v1": Path(config.RESULTS_DIR) / f"{bridge_name}_rag_judged.json",
        "v3": Path(config.RESULTS_DIR) / f"{bridge_name}_rag_v3_judged.json",
        "v5": Path(config.RESULTS_DIR) / f"{bridge_name}_rag_v5_judged.json",
        "v10": judged_v10_path,
    }
    judged = {name: _load_judged_subset(path, qids) for name, path in judged_paths.items()}

    header = "| Version | Q03 | Q06 | Q09 | Q18 | Q29 | Avg Accuracy | Avg Completeness | Avg Faithfulness |\n"
    header += "|---|---:|---:|---:|---:|---:|---:|---:|---:|\n"
    lines = [header]

    for version in ["v1", "v3", "v5", "v10"]:
        subset = judged[version]
        acc_avg = sum(subset[q]["accuracy"] for q in qids) / len(qids)
        comp_avg = sum(subset[q]["completeness"] for q in qids) / len(qids)
        faith_avg = sum(subset[q]["faithfulness"] for q in qids) / len(qids)
        lines.append(
            "| {version} | {q03} | {q06} | {q09} | {q18} | {q29} | {acc:.2f} | {comp:.2f} | {faith:.2f} |\n".format(
                version=version,
                q03=subset["Q03"]["accuracy"],
                q06=subset["Q06"]["accuracy"],
                q09=subset["Q09"]["accuracy"],
                q18=subset["Q18"]["accuracy"],
                q29=subset["Q29"]["accuracy"],
                acc=acc_avg,
                comp=comp_avg,
                faith=faith_avg,
            )
        )

    lines.append("\n## v10 Retrieval Details\n\n")
    lines.append("| QID | Chapters | Retrieved Pages | Used Table Chunks |\n")
    lines.append("|---|---|---|---|\n")

    results_by_qid = {
        item["question_id"]: item
        for item in v10_results["results"]
        if item.get("question_id") in qids
    }
    for qid in qids:
        item = results_by_qid[qid]
        chapters = ", ".join(str(ch) for ch in item.get("predicted_chapters", []))
        pages = ", ".join(str(p) for p in item.get("retrieved_pages", []))
        tables = ", ".join(
            f"{table.get('table_id') or '-'}@p.{table.get('page')}"
            for table in item.get("used_table_chunks", [])
        ) or "-"
        lines.append(f"| {qid} | {chapters or '-'} | {pages or '-'} | {tables} |\n")

    return "".join(lines)


def run_rag_v10_pipeline(bridge_name: str = "대안천교", question_ids: list[str] | None = None) -> dict:
    if not config.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set")
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not set")

    active_questions = [q for q in QUESTIONS if q["id"] in (question_ids or TEST_QIDS)]
    results_dir = Path(config.RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)

    output_path = results_dir / f"{bridge_name}_rag_v10_5q_results.json"
    comparison_path = results_dir / f"{bridge_name}_rag_v10_5q_comparison.md"

    start = time.time()
    print(f"\n🚀 [RAG v10] {bridge_name} 시작 ({len(active_questions)}문항)")

    upstage_pages, failed_pages = load_upstage_parse_pages(bridge_name)
    print(f"📄 Upstage pages: success={len(upstage_pages)}, failed={len(failed_pages)}")
    if failed_pages:
        print(f"⚠️ Upstage failed pages: {failed_pages}")

    docs = build_smart_chunks(upstage_pages)
    chunk_cache_path = _save_chunk_cache(bridge_name, docs)
    print(f"🧩 Smart chunks: {len(docs)}개")
    print(f"💾 Chunk cache: {chunk_cache_path}")

    embedder = GeminiEmbeddings()
    texts = [doc.page_content for doc in docs]
    vectors = np.array(embedder.embed_documents(texts), dtype="float32")
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    vectors = vectors / norms
    print(f"🔢 Gemini embeddings: {vectors.shape}")

    retriever = ChapterHybridRetriever(docs, vectors, embedder)

    answers = []
    for idx, question in enumerate(active_questions, 1):
        print(f"▶ {question['id']} ({idx}/{len(active_questions)})")
        answer_result = None
        for attempt in range(3):
            try:
                answer_result = rag_answer_v10(
                    question=question["text"],
                    retriever=retriever,
                    all_docs=docs,
                    bridge_name=bridge_name,
                    question_id=question["id"],
                )
                answer_result["category"] = question["category"]
                break
            except Exception as exc:  # noqa: BLE001
                wait_sec = 30 if "429" in str(exc) else 10
                if attempt < 2:
                    print(f"  ⚠️ 에러 (시도 {attempt + 1}/3): {exc}")
                    time.sleep(wait_sec)
                    continue
                answer_result = {
                    "question_id": question["id"],
                    "question": question["text"],
                    "answer": f"ERROR: {exc}",
                    "question_type": question["category"],
                    "category": question["category"],
                    "predicted_chapters": [],
                    "subqueries": [],
                    "retrieved_contexts": [],
                    "retrieved_pages": [],
                    "used_table_chunks": [],
                    "bridge": bridge_name,
                    "system": "rag_v10",
                    "elapsed_sec": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
        answers.append(answer_result)

        print(
            f"  chapters={answer_result.get('predicted_chapters', [])} | "
            f"pages={answer_result.get('retrieved_pages', [])} | "
            f"tables={answer_result.get('used_table_chunks', [])}"
        )
        if idx < len(active_questions):
            time.sleep(2)

    final_result = {
        "bridge": bridge_name,
        "system": "rag_v10",
        "model": config.RAG_LLM_MODEL,
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(answers),
        "results": answers,
    }
    output_path.write_text(json.dumps(final_result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"💾 Results: {output_path}")

    judge_all_results(bridge_name, str(output_path), "rag_v10_5q")
    judged_v10_path = results_dir / f"{bridge_name}_rag_v10_5q_judged.json"

    comparison_md = _build_comparison_markdown(bridge_name, final_result, judged_v10_path, [q["id"] for q in active_questions])
    comparison_path.write_text(comparison_md, encoding="utf-8")

    print("\n=== v1 / v3 / v5 / v10 비교표 ===")
    print(comparison_md)

    elapsed = time.time() - start
    print(f"✅ v10 완료: {int(elapsed // 60)}분 {int(elapsed % 60):02d}초")
    return final_result


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG v10")
    parser.add_argument("--bridge", type=str, default="대안천교")
    parser.add_argument("--question-ids", nargs="*", default=TEST_QIDS)
    args = parser.parse_args()

    run_rag_v10_pipeline(args.bridge, args.question_ids)


if __name__ == "__main__":
    main()
