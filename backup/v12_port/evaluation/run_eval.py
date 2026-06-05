"""평가 실행 스크립트.

사용법:
  python -m evaluation.run_eval --bridge 대안천교
  python -m evaluation.run_eval --bridge all
  python -m evaluation.run_eval --bridge all --skip-judge
  python -m evaluation.run_eval --bridge all --human-sheet
  python -m evaluation.run_eval --bridge all --human-agreement
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from evaluation.judge import judge_all_results
from evaluation.analyzer import analyze_single, compare_systems, generate_final_report
from evaluation.human_validation import generate_human_scoring_sheet, compute_agreement


def load_results(file_path: str) -> list[dict]:
    """결과 JSON 파일을 로드한다."""
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", data) if isinstance(data, dict) else data


SYSTEMS = ["rag", "rag_v2", "rag_v3", "llm", "proposed"]


def _check_results_exist(bridge_name: str) -> dict[str, str]:
    """RAG/RAG_v2/LLM 결과 파일 존재 확인. 경로 딕셔너리 반환."""
    paths = {}
    for sys_name in SYSTEMS:
        path = Path(config.RESULTS_DIR) / f"{bridge_name}_{sys_name}_results.json"
        if path.exists():
            paths[sys_name] = str(path)

    if not paths:
        raise FileNotFoundError(f"결과 파일 없음: {bridge_name}")

    return paths


def run_evaluation_pipeline(
    bridge_name: str,
    skip_judge: bool = False,
) -> dict:
    """지정된 교량에 대해 평가 파이프라인을 실행한다."""
    result_paths = _check_results_exist(bridge_name)

    if not skip_judge:
        for sys_name, path in result_paths.items():
            judge_all_results(bridge_name, path, sys_name)
    else:
        for sys_name in result_paths:
            judged = Path(config.RESULTS_DIR) / f"{bridge_name}_{sys_name}_judged.json"
            if not judged.exists():
                raise FileNotFoundError(f"채점 결과 파일 없음: {judged}")

    # 비교 분석
    comparison = compare_systems(bridge_name)
    return comparison


def main():
    parser = argparse.ArgumentParser(description="교량 QA 평가 시스템")
    parser.add_argument(
        "--bridge",
        type=str,
        required=True,
        help="교량 이름 (예: 대안천교, 송정교, all)",
    )
    parser.add_argument(
        "--skip-judge",
        action="store_true",
        help="채점 건너뛰고 기존 _judged.json으로 분석만 수행",
    )
    parser.add_argument(
        "--human-sheet",
        action="store_true",
        help="사람 채점용 엑셀 시트 생성",
    )
    parser.add_argument(
        "--human-agreement",
        action="store_true",
        help="사람-LLM 채점 일치도 계산",
    )
    args = parser.parse_args()

    # 대상 교량 결정
    if args.bridge == "all":
        bridges = list(config.BRIDGES.keys())
    else:
        if args.bridge not in config.BRIDGES:
            print(f"❌ 알 수 없는 교량: {args.bridge}")
            print(f"   사용 가능: {', '.join(config.BRIDGES.keys())}")
            sys.exit(1)
        bridges = [args.bridge]

    # ── Human Scoring Sheet 생성 모드 ──
    if args.human_sheet:
        for bridge in bridges:
            for sys_name in SYSTEMS:
                try:
                    generate_human_scoring_sheet(bridge, sys_name)
                except FileNotFoundError as e:
                    print(f"  ⚠️ {e}")
        print("✅ 사람 채점 시트 생성 완료!")
        return

    # ── Human Agreement 계산 모드 ──
    if args.human_agreement:
        for bridge in bridges:
            for sys_name in SYSTEMS:
                try:
                    compute_agreement(bridge, sys_name)
                except FileNotFoundError as e:
                    print(f"  ⚠️ {e}")
        print("✅ Human-LLM Agreement 계산 완료!")
        return

    # ── 메인 평가 파이프라인 ──
    print("⚖️ 평가 시작")

    for bridge in bridges:
        try:
            result_paths = _check_results_exist(bridge)
        except FileNotFoundError as e:
            print(f"  ⚠️ {bridge} 건너뜀: {e}")
            continue

        if not args.skip_judge:
            for sys_name, path in result_paths.items():
                print(f"  {bridge} {sys_name.upper()} 채점 중...")
                judge_all_results(bridge, path, sys_name)
        else:
            print(f"  {bridge} 채점 건너뜀 (--skip-judge)")

    # 비교 분석
    for bridge in bridges:
        try:
            comparison = compare_systems(bridge)
            # 개별 비교 결과 저장
            out_path = Path(config.RESULTS_DIR) / f"{bridge}_comparison.json"
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(comparison, f, ensure_ascii=False, indent=2)
        except FileNotFoundError as e:
            print(f"  ⚠️ {bridge} 비교 분석 실패: {e}")

    # all 모드: 최종 리포트 생성
    if args.bridge == "all":
        print("\n📊 최종 리포트 생성 중...")
        generate_final_report()

    print(f"\n✅ 완료! results/final_comparison.xlsx")


if __name__ == "__main__":
    main()
