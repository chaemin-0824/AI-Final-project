"""RAG 파이프라인 실행 스크립트.

사용법:
  python -m system_a_rag.run_rag --bridge 대안천교
  python -m system_a_rag.run_rag --bridge 송정교
  python -m system_a_rag.run_rag --bridge all
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
from questions import QUESTIONS
from system_a_rag.extractor import extract_all, extract_tables
from system_a_rag.vectorstore import build_vectorstore, load_vectorstore
from system_a_rag.retriever import rag_answer


def run_rag_pipeline(bridge_name: str) -> dict:
    """지정된 교량에 대해 RAG 파이프라인을 실행한다.

    Args:
        bridge_name: 교량 이름.

    Returns:
        전체 결과 딕셔너리.
    """
    start_time = time.time()
    print(f"\n🚀 [RAG] {bridge_name} 분석 시작 (40문항)")

    results_dir = Path(config.RESULTS_DIR)
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / f"{bridge_name}_rag_results.json"

    # 1. PDF 텍스트 추출 (캐시 활용)
    text_docs = extract_all(bridge_name)
    print(f"📄 텍스트 추출 완료: {len(text_docs)}개 문서")

    # 2. 표 추출 (캐시 활용)
    table_docs = extract_tables(bridge_name)
    print(f"📊 표 추출 완료: {len(table_docs)}개 표")

    # 3. 텍스트 + 표 문서 합치기
    all_docs = text_docs + table_docs

    # 4. 벡터스토어 구축 또는 로드
    vectorstore = load_vectorstore(bridge_name)
    if vectorstore is None:
        print("🔨 벡터스토어 구축 중...")
        vectorstore = build_vectorstore(bridge_name, all_docs)
    else:
        print(f"🔍 벡터스토어 로드 완료")

    # 5. 40문항 순회 + 답변 생성
    answers = []
    total = len(QUESTIONS)

    for i, q in enumerate(QUESTIONS):
        q_num = i + 1
        print(f"▶ Q{q['id'][-2:]}/{total} 진행 중...")

        # API 에러 시 30초 대기 후 3회 재시도
        answer_result = None
        for attempt in range(3):
            try:
                answer_result = rag_answer(
                    question=q["text"],
                    vectorstore=vectorstore,
                    bridge_name=bridge_name,
                    question_id=q["id"],
                )
                break
            except Exception as e:
                if attempt < 2:
                    print(f"  ⚠️ API 에러 (시도 {attempt + 1}/3): {e}")
                    print(f"  ⏳ 30초 대기 후 재시도...")
                    time.sleep(30)
                else:
                    print(f"  ❌ 3회 시도 실패: {e}")
                    answer_result = {
                        "question_id": q["id"],
                        "question": q["text"],
                        "answer": f"ERROR: {str(e)}",
                        "question_type": q["category"],
                        "retrieved_pages": [],
                        "bridge": bridge_name,
                        "system": "rag",
                    }

        answers.append(answer_result)

        # 10문항마다 중간 저장
        if q_num % 10 == 0:
            _save_results(bridge_name, answers, output_path)
            print(f"💾 중간 저장 완료 ({q_num}/{total})")

        # Rate Limit 방지: 질문 간 2초 대기
        if q_num < total:
            time.sleep(2)

    # 6. 최종 저장
    final_result = _save_results(bridge_name, answers, output_path)

    elapsed = time.time() - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    print(f"✅ 완료! 소요 시간: {minutes}분 {seconds}초")

    return final_result


def _save_results(bridge_name: str, answers: list[dict], output_path: Path) -> dict:
    """결과를 JSON 파일로 저장한다."""
    result = {
        "bridge": bridge_name,
        "system": "rag",
        "model": config.RAG_LLM_MODEL,
        "timestamp": datetime.now().isoformat(),
        "total_questions": len(answers),
        "results": answers,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


def main():
    parser = argparse.ArgumentParser(description="RAG 파이프라인 실행")
    parser.add_argument(
        "--bridge",
        type=str,
        required=True,
        help="교량 이름 (대안천교, 송정교, all)",
    )
    args = parser.parse_args()

    if args.bridge == "all":
        bridges = list(config.BRIDGES.keys())
    else:
        if args.bridge not in config.BRIDGES:
            print(f"❌ 알 수 없는 교량: {args.bridge}")
            print(f"   사용 가능: {', '.join(config.BRIDGES.keys())}")
            sys.exit(1)
        bridges = [args.bridge]

    for bridge_name in bridges:
        run_rag_pipeline(bridge_name)


if __name__ == "__main__":
    main()
