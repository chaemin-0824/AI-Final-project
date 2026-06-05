"""RAG v12 orchestrator: v10r retrieval + image + text context → Gemini 3.1 Pro."""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_core.documents import Document

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

from system_a_rag.retriever import classify_question, _rerank_documents
from system_a_rag_v5.query_decomposer import decompose_query
from system_a_rag_v10.retriever_v10 import (
    ChapterHybridRetriever,
    infer_target_chapters,
    _multi_query_search,
    _supplement_history_docs,
    _supplement_damage_docs,
    _expand_neighbor_pages,
)
from system_a_rag_v11.visual_generator import render_pdf_pages, generate_visual_answer


def rag_answer_v12(
    question: str,
    retriever: ChapterHybridRetriever,
    all_docs: list[Document],
    bridge_name: str,
    question_id: str = "",
) -> dict:
    """v10r 검색 + PDF 이미지 + OCR 텍스트 context → Gemini 3.1 Pro 답변 생성."""

    # ── Stage 1~6: v10r 검색 파이프라인 ──
    question_type = classify_question(question)
    predicted_chapters = infer_target_chapters(
        question, question_type, bridge_name=bridge_name
    )
    subqueries = decompose_query(question)

    merged_docs = _multi_query_search(
        retriever, question, subqueries, predicted_chapters, k=20
    )
    reranked_docs = _rerank_documents(merged_docs, question_type)
    top_docs = reranked_docs[:10]
    top_docs = _supplement_history_docs(
        top_docs=top_docs, all_docs=all_docs, question=question,
        subqueries=subqueries, chapters=predicted_chapters,
    )
    top_docs = _supplement_damage_docs(
        top_docs=top_docs, all_docs=all_docs, question=question,
        question_type=question_type, chapters=predicted_chapters,
    )
    expanded_docs = _expand_neighbor_pages(top_docs, all_docs, page_window=1)

    # 검색 메타데이터 + 텍스트 context 추출
    retrieved_pages: list[int] = []
    retrieved_contexts: list[str] = []
    used_table_chunks = []
    seen_table_ids: set[tuple] = set()

    for doc in expanded_docs:
        page = doc.metadata.get("page", None)
        retrieved_contexts.append(f"[페이지 {page}]\n{doc.page_content}")
        if isinstance(page, int) and page not in retrieved_pages:
            retrieved_pages.append(page)
        if doc.metadata.get("element_type") == "table":
            key = (doc.metadata.get("page"), doc.metadata.get("table_id"))
            if key not in seen_table_ids:
                seen_table_ids.add(key)
                used_table_chunks.append({
                    "page": doc.metadata.get("page"),
                    "chapter": doc.metadata.get("chapter"),
                    "section": doc.metadata.get("section"),
                    "table_id": doc.metadata.get("table_id"),
                })

    text_context = "\n\n".join(retrieved_contexts)

    # ── Stage 7: 이미지 + 텍스트 → Gemini 답변 생성 ──
    pdf_path = config.BRIDGES[bridge_name]["pdf_path"]
    image_pages = sorted(retrieved_pages)[:15]

    page_images = render_pdf_pages(pdf_path, image_pages)
    n_image_pages = len(page_images)
    total_image_kb = sum(img["size_kb"] for img in page_images)

    gen = generate_visual_answer(question, page_images, text_context=text_context)

    return {
        "question_id": question_id,
        "question": question,
        "answer": gen["answer"],
        "question_type": question_type,
        "category": "",
        "predicted_chapters": predicted_chapters,
        "subqueries": subqueries,
        "retrieved_pages": retrieved_pages,
        "image_pages": image_pages,
        "n_image_pages": n_image_pages,
        "total_image_kb": round(total_image_kb, 1),
        "used_table_chunks": used_table_chunks,
        "bridge": bridge_name,
        "system": "rag_v12",
        "elapsed_sec": gen["elapsed_sec"],
        "input_tokens": gen["input_tokens"],
        "output_tokens": gen["output_tokens"],
    }
