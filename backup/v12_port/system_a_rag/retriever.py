"""질문 유형 분류 + 적응형 검색 + GPT-5.4 답변 생성 모듈.

1. classify_question: 키워드 기반 질문 유형 분류
2. generate_prompt: 유형별 전문가 프롬프트 생성
3. rag_answer: 검색 + 재랭킹 + LLM 답변 생성
"""

import re
import sys
import time
from pathlib import Path

from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


# 유형별 키워드 매핑
CATEGORY_KEYWORDS = {
    "성능변화": ["변화", "추이", "이전", "과거", "비교", "악화", "개선", "직전", "보수", "보강", "상승", "하락", "이력"],
    "중대결함": ["손상", "균열", "박락", "철근", "누수", "결함", "파손", "부식", "면적", "개소", "박리", "오염", "강도"],
    "C등급관리": ["C등급", "방치", "관리", "임계", "D등급", "C등급 이하"],
    "등급통계": ["등급", "점수", "안전율", "결함도", "환산", "가중치", "S.F", "종합"],
}


def classify_question(question: str) -> str:
    """키워드 기반으로 질문 유형을 분류한다.

    Args:
        question: 질문 텍스트.

    Returns:
        "성능변화", "중대결함", "C등급관리", "등급통계" 중 하나.
    """
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in question)
        scores[category] = score

    # C등급관리를 우선 체크 (더 구체적인 패턴)
    if scores["C등급관리"] >= 1:
        return "C등급관리"

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        return best

    return "등급통계"


def generate_prompt(question: str, context: str, question_type: str) -> str:
    """질문 유형에 맞는 전문가 프롬프트를 생성한다.

    Args:
        question: 질문 텍스트.
        context: 검색된 문서 컨텍스트.
        question_type: classify_question의 반환값.

    Returns:
        LLM에 전달할 프롬프트 문자열.
    """
    base_instruction = (
        "당신은 20년 경력의 교량 정밀안전진단 전문가입니다.\n"
        "반드시 근거 페이지를 [p.XX] 또는 [페이지 XX, 표 X.X] 형식으로 명시하세요.\n"
        "보고서에 없는 내용은 절대 지어내지 말고 '해당 정보 없음'으로 답하세요.\n"
        "핵심 요약을 맨 처음 한 문장으로 제시하세요."
    )

    type_instructions = {
        "중대결함": (
            "\n\n[추가 지시]\n"
            "구조물 코드(S1~S3, P1~P2, A1~A2)별로 손상 유형, 면적(㎡), 개소를 정확히 기술하세요."
        ),
        "등급통계": (
            "\n\n[추가 지시]\n"
            "수치는 소수점까지 정확히 표기하세요. 예: 결함도 0.239, 안전율 1.697"
        ),
        "성능변화": (
            "\n\n[추가 지시]\n"
            "이전 vs 금회를 표(Markdown Table)로 비교 정리하세요."
        ),
    }

    extra = type_instructions.get(question_type, "")

    prompt = (
        f"{base_instruction}{extra}\n\n"
        f"--- 참고 자료 ---\n{context}\n--- 참고 자료 끝 ---\n\n"
        f"질문: {question}\n\n답변:"
    )

    return prompt


def _rerank_documents(
    docs: list[Document],
    question_type: str,
) -> list[Document]:
    """질문 유형에 따라 검색 결과를 재랭킹한다.

    Args:
        docs: 검색된 Document 리스트.
        question_type: 질문 유형.

    Returns:
        재랭킹된 Document 리스트.
    """
    if question_type == "중대결함":
        # critical_damage 또는 table_data(damage) 우선
        priority = []
        normal = []
        for doc in docs:
            chunk_type = doc.metadata.get("chunk_type", "")
            table_type = doc.metadata.get("table_type", "")
            if chunk_type == "critical_damage" or table_type == "damage":
                priority.append(doc)
            else:
                normal.append(doc)
        return priority + normal

    elif question_type == "등급통계":
        # 수치 패턴 포함 문서 우선
        num_pattern = re.compile(r'\d+\.\d+|결함도|안전율|S\.F|가중치')
        priority = []
        normal = []
        for doc in docs:
            if num_pattern.search(doc.page_content):
                priority.append(doc)
            else:
                normal.append(doc)
        return priority + normal

    elif question_type == "성능변화":
        # evaluation 타입 표 우선
        priority = []
        normal = []
        for doc in docs:
            table_type = doc.metadata.get("table_type", "")
            if table_type == "evaluation":
                priority.append(doc)
            else:
                normal.append(doc)
        return priority + normal

    elif question_type == "C등급관리":
        # evaluation 표 + 등급 관련 문서 우선
        priority = []
        normal = []
        for doc in docs:
            table_type = doc.metadata.get("table_type", "")
            has_grade = "C등급" in doc.page_content or "등급" in doc.page_content
            if table_type == "evaluation" or has_grade:
                priority.append(doc)
            else:
                normal.append(doc)
        return priority + normal

    return docs


def rag_answer(
    question: str,
    vectorstore: FAISS,
    bridge_name: str,
    question_id: str = "",
) -> dict:
    """질문에 대해 RAG 기반 답변을 생성한다.

    Args:
        question: 질문 텍스트.
        vectorstore: FAISS 벡터스토어 객체.
        bridge_name: 교량 이름.
        question_id: 질문 ID (예: "Q01").

    Returns:
        {
            "question_id": str,
            "question": str,
            "answer": str,
            "question_type": str,
            "retrieved_pages": list[int],
            "bridge": str,
            "system": "rag",
        }
    """
    # 1. 질문 유형 분류
    question_type = classify_question(question)

    # 2. 벡터 검색 (k=20)
    retrieved_docs = vectorstore.similarity_search(question, k=20)

    # 3. 유형별 재랭킹
    reranked_docs = _rerank_documents(retrieved_docs, question_type)

    # 4. 상위 10개로 context 구성
    top_docs = reranked_docs[:10]
    context_parts = []
    for doc in top_docs:
        page = doc.metadata.get("page", "?")
        doc_page = doc.metadata.get("document_page", "")
        page_info = f"[페이지 {page}"
        if doc_page:
            page_info += f" ({doc_page})"
        page_info += "]"
        context_parts.append(f"{page_info}\n{doc.page_content}")
    context = "\n\n".join(context_parts)

    # 5. 프롬프트 생성
    prompt = generate_prompt(question, context, question_type)

    # 6. LLM 답변 생성
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

    # 7. 검색된 페이지 번호 수집
    retrieved_pages = []
    for doc in top_docs:
        page = doc.metadata.get("page")
        if page and page not in retrieved_pages:
            retrieved_pages.append(page)

    return {
        "question_id": question_id,
        "question": question,
        "answer": answer,
        "question_type": question_type,
        "retrieved_pages": retrieved_pages,
        "bridge": bridge_name,
        "system": "rag",
        "elapsed_sec": round(elapsed, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
