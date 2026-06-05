"""LLM-as-Judge 채점 모듈.

Gemini 2.5 Pro를 Judge로 사용하여 6개 메트릭을 동시 평가한다.
Judge는 PDF 보고서 원문을 캐싱한 상태에서 원문 대조 채점을 수행한다.
"""

import datetime
import json
import re
import sys
import time
from pathlib import Path

import google.generativeai as genai
from google.generativeai import caching

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from metrics import JUDGE_PROMPT_TEMPLATE

JUDGE_SYSTEM_INSTRUCTION = (
    "너는 교량 정밀안전진단 보고서의 정합성을 검증하는 AI 감사관이다.\n"
    "현재 보고 있는 보고서 원문을 기준으로 시스템 답변을 엄격하게 평가하라."
)

SKIP_PREFIXES = ("ERROR", "BLOCKED")
SKIP_RESULT = {
    "accuracy": 1,
    "completeness": 1,
    "faithfulness": 1,
    "errors": ["시스템 오류로 답변 미생성"],
    "reason": "시스템 오류",
}
PARSE_FAIL_RESULT = {
    "accuracy": 1,
    "completeness": 1,
    "faithfulness": 1,
    "errors": ["JSON 파싱 실패"],
    "reason": "파싱 실패",
}


def create_judge_session(bridge_name: str):
    """PDF를 캐싱한 Judge 세션을 생성한다.

    Returns:
        (judge_model, cache) 튜플.
    """
    genai.configure(api_key=config.GOOGLE_API_KEY)

    bridge_info = config.BRIDGES[bridge_name]
    pdf_path = bridge_info["pdf_path"]
    filename = Path(pdf_path).name

    print(f"⏳ [Judge] PDF 업로드 중: {filename}")
    pdf_file = genai.upload_file(path=pdf_path)

    while pdf_file.state.name == "PROCESSING":
        time.sleep(2)
        pdf_file = genai.get_file(pdf_file.name)

    if pdf_file.state.name == "FAILED":
        raise ValueError(f"파일 처리 실패: {pdf_file.state.name}")

    print(f"▶ [Judge] 파일 준비 완료")

    cache = caching.CachedContent.create(
        model=config.JUDGE_MODEL,
        display_name=f"judge_{bridge_name}",
        system_instruction=JUDGE_SYSTEM_INSTRUCTION,
        contents=[pdf_file],
        ttl=datetime.timedelta(minutes=config.CACHE_TTL_MINUTES),
    )

    print(f"✅ [Judge] 캐싱 완료! (Cache: {cache.name})")
    print("⏳ 캐시 안정화 대기 (10초)...")
    time.sleep(10)

    judge_model = genai.GenerativeModel.from_cached_content(cache)
    return judge_model, cache


def _clamp(value: int, lo: int = 1, hi: int = 5) -> int:
    """값을 lo~hi 범위로 클램핑한다."""
    return max(lo, min(hi, value))


def _parse_judge_response(text: str) -> dict | None:
    """Judge 응답에서 JSON을 파싱한다 (G-Eval 1~5 Likert)."""
    # ```json 블록 제거
    cleaned = re.sub(r"```json\s*", "", text)
    cleaned = re.sub(r"```\s*", "", cleaned)
    cleaned = cleaned.strip()

    # json.loads 시도
    try:
        result = json.loads(cleaned)
        for key in ("accuracy", "completeness", "faithfulness"):
            if key in result:
                result[key] = _clamp(int(result[key]))
        return result
    except (json.JSONDecodeError, ValueError):
        pass

    # 정규식으로 각 필드 추출 시도
    try:
        extracted = {}
        for key in ("accuracy", "completeness", "faithfulness"):
            m = re.search(rf'"{key}"\s*:\s*(\d+)', text)
            extracted[key] = _clamp(int(m.group(1))) if m else 1

        errors_m = re.search(r'"errors"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if errors_m:
            extracted["errors"] = re.findall(r'"([^"]+)"', errors_m.group(1))
        else:
            extracted["errors"] = []

        reason_m = re.search(r'"reason"\s*:\s*"(.*?)"', text, re.DOTALL)
        extracted["reason"] = reason_m.group(1) if reason_m else ""

        # 최소한 하나의 점수가 1 이상이면 성공으로 간주
        if any(extracted[k] > 1 for k in ("accuracy", "completeness", "faithfulness")) or reason_m:
            return extracted
    except Exception:
        pass

    return None


def judge_answer(question: str, answer: str, judge_model) -> dict:
    """단일 답변을 Judge로 채점한다.

    Args:
        question: 질문 텍스트.
        answer: 채점할 답변 텍스트.
        judge_model: from_cached_content로 생성된 GenerativeModel.

    Returns:
        채점 결과 딕셔너리.
    """
    prompt = JUDGE_PROMPT_TEMPLATE.format(question=question, answer=answer)

    for attempt in range(3):
        try:
            response = judge_model.generate_content(prompt)
            result = _parse_judge_response(response.text)
            if result is not None:
                return result
            return dict(PARSE_FAIL_RESULT)

        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                if attempt < 2:
                    print(f"  ⚠️ 429 Rate Limit (시도 {attempt + 1}/3), 30초 대기...")
                    time.sleep(30)
                    continue
            if attempt < 2:
                print(f"  ⚠️ Judge 에러 (시도 {attempt + 1}/3): {error_str[:100]}")
                time.sleep(10)
                continue

            print(f"  ❌ Judge 3회 시도 실패: {error_str[:100]}")
            return dict(PARSE_FAIL_RESULT)

    return dict(PARSE_FAIL_RESULT)


def judge_all_results(
    bridge_name: str, results_file: str, system_name: str
) -> list[dict]:
    """전체 결과 파일을 Judge로 채점한다.

    Args:
        bridge_name: 교량 이름.
        results_file: 결과 JSON 파일 경로.
        system_name: 시스템 이름 ("rag" 또는 "llm").

    Returns:
        채점 결과가 추가된 리스트.
    """
    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", data) if isinstance(data, dict) else data

    print(f"\n⚖️ [{system_name}] {bridge_name} 채점 시작")

    judge_model, cache = create_judge_session(bridge_name)

    judged_results = []
    total = len(results)
    dim_sums = {"accuracy": 0, "completeness": 0, "faithfulness": 0}

    try:
        for i, item in enumerate(results, 1):
            question = item.get("question", "")
            answer = item.get("answer", "")
            qid = item.get("question_id", f"Q{i:02d}")

            # ERROR/BLOCKED 답변은 채점 건너뛰기
            if any(answer.startswith(prefix) for prefix in SKIP_PREFIXES):
                scores = dict(SKIP_RESULT)
                print(f"  ⏭️ {qid}/Q{total:02d} 건너뜀 (시스템 오류)")
            else:
                scores = judge_answer(question, answer, judge_model)
                acc = scores.get("accuracy", 1)
                comp = scores.get("completeness", 1)
                faith = scores.get("faithfulness", 1)
                print(f"  ▶ {qid}/Q{total:02d} 채점 중... 정확:{acc} 완전:{comp} 충실:{faith}")

            judged_item = {**item, **scores}
            judged_results.append(judged_item)

            for dim in dim_sums:
                dim_sums[dim] += scores.get(dim, 1)

            # 10문항마다 중간 저장
            if i % 10 == 0:
                _save_intermediate(bridge_name, system_name, judged_results)
                print(f"  💾 중간 저장 ({i}/{total})")

            # 질문 간 대기
            if i < total:
                time.sleep(3)

        # 최종 저장
        _save_intermediate(bridge_name, system_name, judged_results)

        avgs = {k: v / total for k, v in dim_sums.items()} if total > 0 else dim_sums
        print(f"  ✅ 채점 완료! 정확성: {avgs['accuracy']:.2f}, 완전성: {avgs['completeness']:.2f}, 충실성: {avgs['faithfulness']:.2f} (평균)")

    finally:
        try:
            cache.delete()
            print("  🗑️ Judge 캐시 삭제 완료")
        except Exception:
            pass

    return judged_results


def _save_intermediate(
    bridge_name: str, system_name: str, judged_results: list[dict]
) -> None:
    """중간 결과를 JSON으로 저장한다."""
    output_path = Path(config.RESULTS_DIR) / f"{bridge_name}_{system_name}_judged.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(judged_results, f, ensure_ascii=False, indent=2)
