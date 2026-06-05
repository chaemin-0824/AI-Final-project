"""Query Decomposition 모듈 — 질문을 서브쿼리로 분해.

Gemini Flash-Lite를 사용하여 복합 질문을 2~3개의 구체적 서브쿼리로 분해한다.
"""

import sys
import time
from pathlib import Path

import google.generativeai as genai

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

DECOMPOSE_PROMPT = """아래 질문을 검색에 적합한 2~3개의 구체적인 서브쿼리로 분해하세요.
각 서브쿼리는 하나의 정보만 묻는 짧은 질문이어야 합니다.

질문: {question}

[1] 서브쿼리1
[2] 서브쿼리2
[3] 서브쿼리3"""


def decompose_query(question: str, max_retries: int = 3) -> list[str]:
    """질문을 2~3개의 서브쿼리로 분해한다.

    Args:
        question: 원본 질문 텍스트.
        max_retries: 최대 재시도 횟수.

    Returns:
        서브쿼리 리스트 (원본 질문 미포함).
    """
    genai.configure(api_key=config.GOOGLE_API_KEY)
    model = genai.GenerativeModel(config.VLM_TABLE_MODEL)

    prompt = DECOMPOSE_PROMPT.format(question=question)

    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            text = response.text.strip()
            return _parse_subqueries(text)
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                time.sleep(30 * (attempt + 1))
            elif attempt < max_retries - 1:
                time.sleep(5)
            else:
                print(f"    ⚠️ Query decomposition 실패: {error_str[:100]}")
                return []

    return []


def _parse_subqueries(text: str) -> list[str]:
    """LLM 응답에서 서브쿼리를 파싱한다."""
    subqueries = []
    for i in range(1, 4):
        marker = f"[{i}]"
        next_marker = f"[{i + 1}]"
        start = text.find(marker)
        if start == -1:
            continue
        start += len(marker)
        end = text.find(next_marker, start) if i < 3 else len(text)
        if end == -1:
            end = len(text)
        sq = text[start:end].strip()
        if sq:
            subqueries.append(sq)
    return subqueries
