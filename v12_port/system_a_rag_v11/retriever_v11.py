"""RAG v11 orchestrator: v10r retrieval + visual (image-based) generation."""

from __future__ import annotations

import sys
import time
from pathlib import Path

from langchain_core.documents import Document

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

# v10r 검색 파이프라인 재사용
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

# v11 이미지 기반 생성
from system_a_rag_v11.visual_generator import render_pdf_pages, generate_visual_answer


def rag_answer_v11(
    question: str,
    retriever: ChapterHybridRetriever,
    all_docs: list[Document],
    bridge_name: str,
    question_id: str = "",
) -> dict:
    """v10r 검색 + 이미지 기반 Gemini 답변 생성.

    Stage 1~6: v10r과 동일한 검색 파이프라인.
    Stage 7: 검색된 페이지를 PDF 이미지로 렌더링 → Gemini 3.1 Pro에 전달.
    """
    # ── Stage 1~3: 질문 분류, 장 필터링, 쿼리 분해 ──
    question_type = classify_question(question)
    predicted_chapters = infer_target_chapters(
        question, question_type, bridge_name=bridge_name
    )
    subqueries = decompose_query(question)

    # ── Stage 4~5: 하이브리드 검색 + 리랭킹 + 보충 ──
    merged_docs = _multi_query_search(
        retriever, question, subqueries, predicted_chapters, k=20
    )
    reranked_docs = _rerank_documents(merged_docs, question_type)
    top_docs = reranked_docs[:10]
    top_docs = _supplement_history_docs(
        top_docs=top_docs,
        all_docs=all_docs,
        question=question,
        subqueries=subqueries,
        chapters=predicted_chapters,
    )
    top_docs = _supplement_damage_docs(
        top_docs=top_docs,
        all_docs=all_docs,
        question=question,
        question_type=question_type,
        chapters=predicted_chapters,
    )

    # ── Stage 6: 인접 페이지 확장 ──
    expanded_docs = _expand_neighbor_pages(top_docs, all_docs, page_window=1)

    # 검색 메타데이터 추출
    retrieved_pages: list[int] = []
    used_table_chunks = []
    seen_table_ids: set[tuple] = set()

    for doc in expanded_docs:
        page = doc.metadata.get("page", None)
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

    # ── Stage 7: 이미지만으로 답변 생성 ──
    pdf_path = config.BRIDGES[bridge_name]["pdf_path"]

    # 페이지 정렬 (번호순)
    image_pages = sorted(retrieved_pages)[:15]

    page_images = render_pdf_pages(pdf_path, image_pages)
    n_image_pages = len(page_images)
    total_image_kb = sum(img["size_kb"] for img in page_images)

    gen = generate_visual_answer(question, page_images)

    return {
        "question_id": question_id,
        "question": question,
        "answer": gen["answer"],
        "question_type": question_type,
        "category": "",  # 호출 측에서 설정
        "predicted_chapters": predicted_chapters,
        "subqueries": subqueries,
        "retrieved_pages": retrieved_pages,
        "image_pages": image_pages,
        "n_image_pages": n_image_pages,
        "total_image_kb": round(total_image_kb, 1),
        "used_table_chunks": used_table_chunks,
        "bridge": bridge_name,
        "system": "rag_v11",
        "elapsed_sec": gen["elapsed_sec"],
        "input_tokens": gen["input_tokens"],
        "output_tokens": gen["output_tokens"],
    }
