"""Retriever and answer generation for RAG v10."""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import faiss
import google.generativeai as genai
import numpy as np
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI
from rank_bm25 import BM25Okapi

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from system_a_rag.retriever import classify_question, generate_prompt, _rerank_documents
from system_a_rag_v5.query_decomposer import decompose_query


# Default fallback (used only when dynamic extraction fails)
_DEFAULT_CHAPTER_PROMPT = (
    "교량 점검보고서 구조: 1장-개요, 2장-현황/이력, 3장-현장조사/시험, "
    "4장-상태평가, 5장-안전성평가, 6장-내하력/내진, 7장-종합평가, "
    "8장-보수보강방안, 9장-결론. 해당 장 번호만 출력 (쉼표 구분).\n\n"
    "질문: {question}"
)

# Cache for dynamically extracted chapter structures per bridge
_chapter_structure_cache: dict[str, str] = {}


def _extract_chapter_structure(bridge_name: str) -> str | None:
    """upstage_parse_cache.json에서 실제 장 제목을 추출한다."""
    if bridge_name in _chapter_structure_cache:
        return _chapter_structure_cache[bridge_name]

    cache_path = Path(config.PROJECT_ROOT) / "data" / bridge_name / "upstage_parse_cache.json"
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        pages = data.get("pages", [])

        chapters: dict[int, str] = {}
        for page_data in pages:
            for elem in page_data.get("elements", []):
                cat = elem.get("category", "")
                if cat not in ("heading1", "header", "paragraph"):
                    continue
                content = elem.get("content", {})
                text = content.get("text", "") or content.get("markdown", "").replace("#", "").strip()
                m = re.match(r"제\s*(\d+)\s*장\s*(.*)", text)
                if m:
                    ch_no = int(m.group(1))
                    ch_title = m.group(2).strip()
                    if ch_no not in chapters and ch_title:
                        chapters[ch_no] = ch_title

        if not chapters:
            return None

        parts = [f"{no}장-{title}" for no, title in sorted(chapters.items())]
        structure = "이 교량 보고서의 장 구조: " + ", ".join(parts)
        _chapter_structure_cache[bridge_name] = structure
        return structure
    except Exception:
        return None


def _build_chapter_prompt(question: str, bridge_name: str = "") -> str:
    """보고서의 실제 장 구조를 반영한 장 라우팅 프롬프트를 생성한다."""
    structure = _extract_chapter_structure(bridge_name) if bridge_name else None
    if structure:
        return (
            f"{structure}\n"
            "질문과 관련된 장 번호만 출력하세요 (쉼표 구분). 여러 장에 걸칠 수 있으면 모두 출력.\n\n"
            f"질문: {question}"
        )
    return _DEFAULT_CHAPTER_PROMPT.format(question=question)

MAX_CONTEXT_CHUNKS = 20
HISTORY_QUERY_KEYWORDS = (
    "비교", "변화", "추이", "장기간", "지속", "계속", "이전", "과거", "기 점검", "전검", "이력",
)
HISTORY_TABLE_KEYWORDS = (
    "비교", "변화", "추이", "기 점검", "전검", "이력", "종합평가", "안전등급", "상태평가",
)
DAMAGE_KEYWORDS = (
    "망상균열", "망상 균열", "균열", "누수", "백태", "박리", "박락", "철근노출",
    "파손", "재료분리", "소성변형", "들뜸", "마모",
)
ATTRIBUTE_KEYWORDS = (
    "원인", "면적", "물량", "개소", "수량", "등급", "비교", "변화", "이력", "추이", "기간",
)
COMPONENT_KEYWORDS = (
    "바닥판", "거더", "가로보", "교면포장", "포장", "신축이음", "교대", "교각", "받침", "배수시설", "기초",
)


def _infer_llm_target_chapters(question: str, max_retries: int = 3, bridge_name: str = "") -> list[int]:
    """Infer candidate chapters with Gemini Flash-Lite."""
    if not config.GOOGLE_API_KEY:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    genai.configure(api_key=config.GOOGLE_API_KEY)
    model = genai.GenerativeModel(config.VLM_TABLE_MODEL)
    prompt = _build_chapter_prompt(question, bridge_name)

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = getattr(response, "text", "").strip()
            chapters = sorted({int(x) for x in re.findall(r"\d+", text) if 1 <= int(x) <= 9})
            if chapters:
                return chapters
            return []
        except Exception as exc:  # noqa: BLE001
            wait_sec = 30 if ("429" in str(exc) or "RESOURCE_EXHAUSTED" in str(exc)) else 10
            if attempt < max_retries - 1:
                time.sleep(wait_sec)
                continue
            return []

    return []


def _infer_rule_based_chapters(question: str, question_type: str) -> list[int]:
    text = question.replace(" ", "")
    chapters = set()

    if question_type == "성능변화":
        chapters.add(4)
        if any(keyword in text for keyword in ("안전등급", "종합평가", "상태등급", "상승", "하락")):
            chapters.add(7)
        if any(keyword in text for keyword in ("보수보강", "보수·보강", "공사이후", "개략공사비", "우선순위")):
            chapters.add(8)

    if question_type == "중대결함":
        chapters.add(3)
        if any(keyword in text for keyword in ("원인", "분석", "왜")):
            chapters.add(2)

    if question_type == "C등급관리":
        chapters.update({4, 7})
        if any(keyword in text for keyword in ("보수보강", "보수·보강", "조치", "방안")):
            chapters.add(8)

    if any(keyword in text for keyword in ("결함도", "상태평가", "상태등급", "c등급")):
        chapters.add(4)
    if any(keyword in text for keyword in ("안전등급", "종합평가")):
        chapters.add(7)
    if any(keyword in text for keyword in ("보수보강", "보수·보강", "개략공사비", "우선순위", "공사이후")):
        chapters.add(8)
    if any(keyword in text for keyword in ("이력", "연혁", "과거")):
        chapters.add(2)
    # 안전성평가/안전율은 보고서마다 5장 또는 6장에 있음 → 둘 다 포함
    if any(keyword in text for keyword in ("안전성평가", "안전성 평가", "안전율", "S.F", "구조검토", "구조 검토")):
        chapters.update({5, 6})

    return sorted(ch for ch in chapters if 1 <= ch <= 9)


def infer_target_chapters(question: str, question_type: str, max_retries: int = 3, bridge_name: str = "") -> list[int]:
    llm_chapters = _infer_llm_target_chapters(question, max_retries=max_retries, bridge_name=bridge_name)
    rule_chapters = _infer_rule_based_chapters(question, question_type)
    combined = sorted(set(llm_chapters) | set(rule_chapters))
    return combined or list(range(1, 10))


class ChapterHybridRetriever:
    """Hybrid retriever with chapter-aware FAISS + BM25 search."""

    def __init__(self, documents: list[Document], vectors: np.ndarray, embedder):
        self.documents = documents
        self.vectors = vectors.astype("float32")
        self.embedder = embedder
        self.bm25 = BM25Okapi([doc.page_content.split() for doc in documents])

    def _filtered_indices(self, chapters: list[int] | None) -> list[int]:
        if not chapters:
            return list(range(len(self.documents)))

        filtered = [
            idx for idx, doc in enumerate(self.documents)
            if doc.metadata.get("chapter_no") in chapters
        ]
        return filtered or list(range(len(self.documents)))

    def _search_indices(self, query_vec: np.ndarray, indices: list[int], k: int, rrf_constant: int = 60) -> dict[int, float]:
        """Run hybrid (semantic + BM25) search on a subset of indices and return RRF scores."""
        if not indices:
            return {}

        subset_vectors = self.vectors[indices]
        dim = subset_vectors.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(subset_vectors)

        search_k = min(max(k, 20), len(indices))
        distances, local_indices = index.search(query_vec.reshape(1, -1), search_k)
        semantic_rank = [
            indices[local_idx]
            for local_idx in local_indices[0]
            if local_idx != -1
        ]

        bm25_scores = self.bm25.get_scores(query_vec._query_text.split()) if hasattr(query_vec, '_query_text') else self._last_bm25_scores
        bm25_rank = sorted(
            indices,
            key=lambda idx: bm25_scores[idx],
            reverse=True,
        )[:search_k]

        rrf_scores: dict[int, float] = {}
        for rank, idx in enumerate(semantic_rank):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (rank + rrf_constant)
        for rank, idx in enumerate(bm25_rank):
            rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (rank + rrf_constant)

        return rrf_scores

    def search(self, query: str, chapters: list[int] | None = None, k: int = 20, rrf_constant: int = 60) -> list[Document]:
        query_vec = np.array(self.embedder.embed_query(query), dtype="float32")
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            raise RuntimeError("Zero-norm query embedding")
        query_vec = query_vec / query_norm

        # Compute BM25 scores once for all indices
        bm25_scores = self.bm25.get_scores(query.split())

        all_indices = list(range(len(self.documents)))
        filtered_indices = self._filtered_indices(chapters)
        is_chapter_filtered = chapters and len(filtered_indices) < len(all_indices)

        def _rrf_search(indices: list[int], search_k: int) -> dict[int, float]:
            subset_vectors = self.vectors[indices]
            dim = subset_vectors.shape[1]
            idx_obj = faiss.IndexFlatIP(dim)
            idx_obj.add(subset_vectors)

            actual_k = min(max(search_k, 20), len(indices))
            distances, local_indices = idx_obj.search(query_vec.reshape(1, -1), actual_k)
            semantic_rank = [indices[li] for li in local_indices[0] if li != -1]

            bm25_rank = sorted(indices, key=lambda i: bm25_scores[i], reverse=True)[:actual_k]

            scores: dict[int, float] = {}
            for rank, i in enumerate(semantic_rank):
                scores[i] = scores.get(i, 0.0) + 1.0 / (rank + rrf_constant)
            for rank, i in enumerate(bm25_rank):
                scores[i] = scores.get(i, 0.0) + 1.0 / (rank + rrf_constant)
            return scores

        if is_chapter_filtered:
            # 1) Chapter-filtered search with 1.5x weight boost
            chapter_scores = _rrf_search(filtered_indices, k)
            boosted = {idx: score * 1.5 for idx, score in chapter_scores.items()}

            # 2) Full search (safety net)
            global_scores = _rrf_search(all_indices, k)

            # 3) Merge: chapter results get 1.5x, global results add base score
            merged: dict[int, float] = {}
            for idx, score in boosted.items():
                merged[idx] = merged.get(idx, 0.0) + score
            for idx, score in global_scores.items():
                merged[idx] = merged.get(idx, 0.0) + score

            final_indices = sorted(merged, key=merged.get, reverse=True)[:k]
        else:
            scores = _rrf_search(filtered_indices, k)
            final_indices = sorted(scores, key=scores.get, reverse=True)[:k]

        return [self.documents[idx] for idx in final_indices]


def _multi_query_search(
    retriever: ChapterHybridRetriever,
    question: str,
    subqueries: list[str],
    chapters: list[int],
    k: int = 20,
) -> list[Document]:
    def dedupe_keep_order(values: list[str]) -> list[str]:
        seen = set()
        output = []
        for value in values:
            normalized = " ".join(value.split())
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            output.append(normalized)
        return output

    def extract_keywords(text: str, candidates: tuple[str, ...]) -> list[str]:
        found = []
        normalized = text.replace("망상 균열", "망상균열")
        for keyword in candidates:
            key = keyword.replace("망상 균열", "망상균열")
            if key in normalized and key not in found:
                found.append(key)
        return found

    queries = [question, *subqueries]
    damage_terms = extract_keywords(question, DAMAGE_KEYWORDS)
    attr_terms = extract_keywords(question, ATTRIBUTE_KEYWORDS)
    component_terms = extract_keywords(question, COMPONENT_KEYWORDS)

    if damage_terms and attr_terms:
        queries.append(" ".join([*component_terms, *damage_terms, *attr_terms]))
        queries.append(" ".join([*damage_terms, *attr_terms]))

    queries.extend(query.replace(" ", "") for query in queries if " " in query)
    queries = dedupe_keep_order(queries)

    seen_ids = set()
    merged_docs: list[Document] = []
    for query in queries:
        results = retriever.search(query, chapters=chapters, k=k)
        for doc in results:
            doc_id = f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}"
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                merged_docs.append(doc)
    return merged_docs


def _needs_history_boost(question: str, subqueries: list[str]) -> bool:
    query_text = " ".join([question, *subqueries])
    return any(keyword in query_text for keyword in HISTORY_QUERY_KEYWORDS)


def _supplement_history_docs(
    top_docs: list[Document],
    all_docs: list[Document],
    question: str,
    subqueries: list[str],
    chapters: list[int],
    max_additional: int = 3,
) -> list[Document]:
    if not _needs_history_boost(question, subqueries):
        return top_docs

    seen_ids = {
        f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}"
        for doc in top_docs
    }
    query_text = " ".join([question, *subqueries])
    candidates = []

    for doc in all_docs:
        if doc.metadata.get("element_type") != "table":
            continue
        if chapters and doc.metadata.get("chapter_no") not in chapters:
            continue

        doc_id = f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}"
        if doc_id in seen_ids:
            continue

        score = 0
        content = doc.page_content
        section = str(doc.metadata.get("section") or "")
        table_id = str(doc.metadata.get("table_id") or "")
        meta_text = " ".join([content, section, table_id])

        for keyword in HISTORY_TABLE_KEYWORDS:
            if keyword in meta_text:
                score += 3
        for keyword in HISTORY_QUERY_KEYWORDS:
            if keyword in query_text and keyword in meta_text:
                score += 2

        if re.fullmatch(r"\d+\.3(\.\d+)?", section):
            score += 2
        if "c등급" in query_text.lower() and " c " in f" {content.lower()} ":
            score += 1

        if score > 0:
            candidates.append((score, doc))

    candidates.sort(key=lambda item: (-item[0], item[1].metadata.get("page", 999)))
    selected = [doc for _, doc in candidates[:max_additional]]
    return selected + list(top_docs)


def _supplement_damage_docs(
    top_docs: list[Document],
    all_docs: list[Document],
    question: str,
    question_type: str,
    chapters: list[int],
    max_additional: int = 3,
) -> list[Document]:
    if question_type != "중대결함":
        return top_docs

    damage_terms = [term for term in DAMAGE_KEYWORDS if term.replace(" ", "") in question.replace(" ", "")]
    attr_terms = [term for term in ATTRIBUTE_KEYWORDS if term.replace(" ", "") in question.replace(" ", "")]
    if not damage_terms or not any(term in attr_terms for term in ("원인", "면적", "물량", "개소", "수량")):
        return top_docs

    seen_ids = {
        f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}"
        for doc in top_docs
    }
    candidates = []
    for doc in all_docs:
        if doc.metadata.get("element_type") != "table":
            continue
        if chapters and doc.metadata.get("chapter_no") not in chapters:
            continue

        doc_id = f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}"
        if doc_id in seen_ids:
            continue

        content = doc.page_content.replace(" ", "")
        score = 0
        for term in damage_terms:
            if term.replace(" ", "") in content:
                score += 4
        for term in attr_terms:
            if term.replace(" ", "") in content:
                score += 3
        if "손상물량" in content or "물량표" in content or "집계표" in content:
            score += 3
        if any(token in content for token in ("원인", "단위", "m2", "개소")):
            score += 2
        if re.search(r"\d+\.\d+", content):
            score += 1

        if score > 0:
            candidates.append((score, doc))

    candidates.sort(key=lambda item: (-item[0], item[1].metadata.get("page", 999)))
    supplemented = list(top_docs)
    for _, doc in candidates[:max_additional]:
        supplemented.append(doc)
    return supplemented


def _expand_neighbor_pages(top_docs: list[Document], all_docs: list[Document], page_window: int = 1) -> list[Document]:
    if not top_docs:
        return []

    base_pages = []
    for doc in top_docs:
        page = doc.metadata.get("page")
        if isinstance(page, int) and page not in base_pages:
            base_pages.append(page)

    expanded_pages = set()
    for page in base_pages:
        for candidate in range(page - page_window, page + page_window + 1):
            if candidate >= 1:
                expanded_pages.add(candidate)

    seen = set()
    expanded_docs = list(top_docs)
    for doc in top_docs:
        seen.add(f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}")

    supplements = []
    for doc in all_docs:
        page = doc.metadata.get("page")
        if page not in expanded_pages:
            continue
        doc_id = f"{doc.metadata.get('page', 0)}_{doc.metadata.get('element_type')}_{doc.metadata.get('table_id')}_{doc.page_content[:80]}"
        if doc_id in seen:
            continue
        seen.add(doc_id)
        supplements.append(doc)

    def supplement_sort_key(doc: Document) -> tuple[int, int, int]:
        page = doc.metadata.get("page", 999)
        if isinstance(page, int) and base_pages:
            distance = min(abs(page - base_page) for base_page in base_pages)
        else:
            distance = 999
        table_priority = 0 if doc.metadata.get("element_type") == "table" else 1
        return (distance, table_priority, page if isinstance(page, int) else 999)

    supplements.sort(key=supplement_sort_key)
    expanded_docs.extend(supplements)
    return expanded_docs[:MAX_CONTEXT_CHUNKS]


def rag_answer_v10(
    question: str,
    retriever: ChapterHybridRetriever,
    all_docs: list[Document],
    bridge_name: str,
    question_id: str = "",
) -> dict:
    question_type = classify_question(question)
    predicted_chapters = infer_target_chapters(question, question_type, bridge_name=bridge_name)
    subqueries = decompose_query(question)

    merged_docs = _multi_query_search(retriever, question, subqueries, predicted_chapters, k=20)
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
    expanded_docs = _expand_neighbor_pages(top_docs, all_docs, page_window=1)

    context_parts = []
    retrieved_contexts = []
    retrieved_pages: list[int] = []
    used_table_chunks = []
    seen_table_ids = set()

    for doc in expanded_docs:
        page = doc.metadata.get("page", "?")
        context_parts.append(f"[페이지 {page}]\n{doc.page_content}")
        retrieved_contexts.append(doc.page_content)
        if isinstance(page, int) and page not in retrieved_pages:
            retrieved_pages.append(page)

        if doc.metadata.get("element_type") == "table":
            key = (doc.metadata.get("page"), doc.metadata.get("table_id"))
            if key not in seen_table_ids:
                seen_table_ids.add(key)
                used_table_chunks.append(
                    {
                        "page": doc.metadata.get("page"),
                        "chapter": doc.metadata.get("chapter"),
                        "section": doc.metadata.get("section"),
                        "table_id": doc.metadata.get("table_id"),
                    }
                )

    context = "\n\n".join(context_parts)
    prompt = generate_prompt(question, context, question_type)

    llm = ChatOpenAI(
        model=config.RAG_LLM_MODEL,
        temperature=0,
        openai_api_key=config.OPENAI_API_KEY,
    )
    t0 = time.time()
    response = llm.invoke(prompt)
    elapsed = time.time() - t0
    answer = response.content

    usage = getattr(response, "usage_metadata", None) or getattr(response, "response_metadata", {}).get("token_usage", {})
    if isinstance(usage, dict):
        input_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
        output_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
    else:
        input_tokens = getattr(usage, "input_tokens", 0) or getattr(usage, "prompt_tokens", 0)
        output_tokens = getattr(usage, "output_tokens", 0) or getattr(usage, "completion_tokens", 0)

    return {
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "question_type": question_type,
        "predicted_chapters": predicted_chapters,
        "subqueries": subqueries,
        "retrieved_contexts": retrieved_contexts,
        "retrieved_pages": retrieved_pages,
        "used_table_chunks": used_table_chunks,
        "bridge": bridge_name,
        "system": "rag_v10",
        "elapsed_sec": round(elapsed, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
