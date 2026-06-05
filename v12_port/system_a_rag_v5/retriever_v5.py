"""검색 + 답변 생성 v5 — Query Decomposition + Page-Level Context Expansion.

v3 대비 변경:
A) 검색 전: 질문을 서브쿼리 2~3개로 분해 → 원본+서브쿼리 모두 검색 → 결과 합침
B) 검색 후: top-k 페이지의 다른 청크도 보충 (상위 3~5 페이지 제한)
"""

import sys
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_openai import ChatOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from system_a_rag.retriever import classify_question, generate_prompt, _rerank_documents
from system_a_rag_v3.hybrid_retriever import HybridRetriever
from system_a_rag_v5.query_decomposer import decompose_query

MAX_PAGE_EXPANSION = 5  # 보충할 최대 페이지 수
MAX_EXPANDED_CHUNKS = 20  # 최종 context 최대 청크 수


def _multi_query_search(
    hybrid_retriever: HybridRetriever,
    original_query: str,
    subqueries: list[str],
    k: int = 20,
) -> list[Document]:
    """원본 쿼리 + 서브쿼리 결과를 합쳐 중복 제거한다."""
    all_queries = [original_query] + subqueries
    seen_ids = set()
    merged = []

    for query in all_queries:
        results = hybrid_retriever.search(query, k=k)
        for doc in results:
            doc_id = f"{doc.metadata.get('page', 0)}_{doc.page_content[:80]}"
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged.append(doc)

    return merged


def _expand_page_context(
    top_docs: list[Document],
    all_docs: list[Document],
    max_pages: int = MAX_PAGE_EXPANSION,
) -> list[Document]:
    """top-k 검색 결과의 페이지에 속하는 다른 청크를 보충한다.

    Args:
        top_docs: 재랭킹 후 상위 문서들.
        all_docs: 전체 문서 풀 (벡터스토어 구축에 사용된 모든 청크).
        max_pages: 보충할 최대 페이지 수.

    Returns:
        top_docs + 같은 페이지의 보충 청크 (중복 제거).
    """
    # 기존 검색 결과의 페이지 순서 (등장 순 상위 N개)
    page_order = []
    for doc in top_docs:
        page = doc.metadata.get("page")
        if page is not None and page not in page_order:
            page_order.append(page)
    target_pages = set(page_order[:max_pages])

    # 기존 검색 결과의 ID 집합
    existing_ids = set()
    for doc in top_docs:
        existing_ids.add(f"{doc.metadata.get('page', 0)}_{doc.page_content[:80]}")

    # 같은 페이지의 다른 청크 수집
    supplement = []
    for doc in all_docs:
        page = doc.metadata.get("page")
        if page in target_pages:
            doc_id = f"{page}_{doc.page_content[:80]}"
            if doc_id not in existing_ids:
                existing_ids.add(doc_id)
                supplement.append(doc)

    # 보충 청크를 페이지 순서대로 정렬
    page_rank = {p: i for i, p in enumerate(page_order)}
    supplement.sort(key=lambda d: page_rank.get(d.metadata.get("page"), 999))

    expanded = list(top_docs) + supplement
    return expanded[:MAX_EXPANDED_CHUNKS]


def rag_answer_v5(
    question: str,
    hybrid_retriever: HybridRetriever,
    all_docs: list[Document],
    bridge_name: str,
    question_id: str = "",
) -> dict:
    """질문에 대해 RAG v5 (Query Decomposition + Page Expansion) 기반 답변을 생성한다.

    Args:
        question: 질문 텍스트.
        hybrid_retriever: HybridRetriever 객체.
        all_docs: 전체 문서 풀 (page expansion용).
        bridge_name: 교량 이름.
        question_id: 질문 ID.

    Returns:
        답변 결과 딕셔너리.
    """
    # 1. 질문 유형 분류
    question_type = classify_question(question)

    # 2. Query Decomposition
    subqueries = decompose_query(question)
    if subqueries:
        print(f"    🔀 서브쿼리 {len(subqueries)}개: {[sq[:30] + '...' if len(sq) > 30 else sq for sq in subqueries]}")

    # 3. 멀티 쿼리 하이브리드 검색
    merged_docs = _multi_query_search(hybrid_retriever, question, subqueries, k=20)

    # 4. 유형별 재랭킹
    reranked_docs = _rerank_documents(merged_docs, question_type)

    # 5. 상위 10개 선택
    top_docs = reranked_docs[:10]

    # 6. Page-Level Context Expansion
    expanded_docs = _expand_page_context(top_docs, all_docs)
    n_expanded = len(expanded_docs) - len(top_docs)
    if n_expanded > 0:
        exp_pages = set()
        for doc in expanded_docs[len(top_docs):]:
            exp_pages.add(doc.metadata.get("page"))
        print(f"    📄 페이지 보충: +{n_expanded}청크 (pages: {sorted(exp_pages)})")

    # 7. Context 구성
    context_parts = []
    retrieved_contexts = []

    for doc in expanded_docs:
        page = doc.metadata.get("page", "?")
        doc_page = doc.metadata.get("document_page", "")
        page_info = f"[페이지 {page}"
        if doc_page:
            page_info += f" ({doc_page})"
        page_info += "]"
        context_parts.append(f"{page_info}\n{doc.page_content}")
        retrieved_contexts.append(doc.page_content)

    context = "\n\n".join(context_parts)

    # 8. 프롬프트 생성
    prompt = generate_prompt(question, context, question_type)

    # 9. LLM 답변 생성
    llm = ChatOpenAI(
        model=config.RAG_LLM_MODEL,
        temperature=0,
        openai_api_key=config.OPENAI_API_KEY,
    )
    t0 = time.time()
    response = llm.invoke(prompt)
    elapsed = time.time() - t0
    answer = response.content

    # 토큰 사용량 추출
    usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {}).get("token_usage", {})
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
        output_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
    else:
        input_tokens = getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0)

    # 10. 검색된 페이지 번호 수집
    retrieved_pages = []
    for doc in expanded_docs:
        page = doc.metadata.get("page")
        if page and page not in retrieved_pages:
            retrieved_pages.append(page)

    return {
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "question_type": question_type,
        "subqueries": subqueries,
        "n_retrieved_before_expansion": len(top_docs),
        "n_retrieved_after_expansion": len(expanded_docs),
        "retrieved_contexts": retrieved_contexts,
        "retrieved_pages": retrieved_pages,
        "bridge": bridge_name,
        "system": "rag_v5",
        "elapsed_sec": round(elapsed, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
