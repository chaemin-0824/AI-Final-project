"""결과 분석 + 통계 + 엑셀 리포트 모듈.

G-Eval 1~5 Likert 척도 기반 3차원(accuracy, completeness, faithfulness) 평가.
구형식(0-100 accuracy_score) 결과도 자동 변환하여 호환 처리.
"""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from questions import CATEGORIES

SYSTEMS = ["rag", "rag_v2", "rag_v3", "llm", "proposed"]
DIMENSIONS = ["accuracy", "completeness", "faithfulness"]


def _normalize_result(r: dict) -> dict:
    """구형식(0-100) 결과를 신형식(1-5 Likert)으로 변환한다."""
    if "accuracy_score" in r and "accuracy" not in r:
        r["accuracy"] = max(1, min(5, round(r["accuracy_score"] / 20)))
    if "accuracy" not in r:
        r["accuracy"] = 1
    if "completeness" not in r or isinstance(r.get("completeness"), bool) or r.get("completeness") in (0, 1):
        r["completeness"] = 5 if r.get("completeness", 0) else 1
    if "faithfulness" not in r or isinstance(r.get("faithfulness"), bool) or r.get("faithfulness") in (0, 1):
        r["faithfulness"] = 5 if r.get("faithfulness", 0) else 1
    # errors 필드 통합
    if "errors_found" in r and "errors" not in r:
        r["errors"] = r["errors_found"]
    return r


def _mean_field(results: list[dict], field: str) -> float:
    vals = [r.get(field, 1) for r in results]
    return float(np.mean(vals)) if vals else 0


def _load_judged(bridge_name: str, system_name: str) -> list[dict]:
    path = Path(config.RESULTS_DIR) / f"{bridge_name}_{system_name}_judged.json"
    with open(path, "r", encoding="utf-8") as f:
        results = json.load(f)
    return [_normalize_result(r) for r in results]


def _available_systems(bridge_name: str) -> list[str]:
    """채점 결과가 존재하는 시스템 목록을 반환한다."""
    available = []
    for sys_name in SYSTEMS:
        path = Path(config.RESULTS_DIR) / f"{bridge_name}_{sys_name}_judged.json"
        if path.exists():
            available.append(sys_name)
    return available


def analyze_single(bridge_name: str, system_name: str) -> dict:
    """단일 시스템의 채점 결과를 분석한다."""
    results = _load_judged(bridge_name, system_name)
    total = len(results)

    # 차원별 통계
    dim_stats = {}
    for dim in DIMENSIONS:
        scores = [r.get(dim, 1) for r in results]
        dim_stats[f"avg_{dim}"] = round(float(np.mean(scores)), 2) if scores else 0
        dim_stats[f"std_{dim}"] = round(float(np.std(scores, ddof=1)) if len(scores) > 1 else 0, 2)

    # 종합 평균 (3차원 평균)
    all_avgs = [dim_stats[f"avg_{d}"] for d in DIMENSIONS]
    avg_overall = round(float(np.mean(all_avgs)), 2)

    # 카테고리별 accuracy 평균
    category_scores = {}
    by_cat = defaultdict(list)
    for r in results:
        cat = r.get("category", r.get("question_type", "기타"))
        by_cat[cat].append(r.get("accuracy", 1))
    for cat, cat_scores in by_cat.items():
        category_scores[cat] = round(float(np.mean(cat_scores)), 2)

    # 오류 유형별 빈도
    error_types = Counter()
    for r in results:
        for err in r.get("errors", r.get("errors_found", [])):
            error_types[err] += 1

    return {
        "bridge": bridge_name,
        "system": system_name,
        "total_questions": total,
        **dim_stats,
        "avg_overall": avg_overall,
        "category_scores": category_scores,
        "error_types": dict(error_types),
    }


def compare_systems(bridge_name: str) -> dict:
    """모든 시스템의 결과를 비교 분석한다."""
    available = _available_systems(bridge_name)
    if len(available) < 2:
        raise FileNotFoundError(
            f"{bridge_name}: 비교할 시스템이 2개 이상 필요 (발견: {available})"
        )

    # 각 시스템 분석
    analyses = {}
    judged_data = {}
    for sys_name in available:
        analyses[sys_name] = analyze_single(bridge_name, sys_name)
        judged_data[sys_name] = _load_judged(bridge_name, sys_name)

    # 시스템 쌍별 통계적 유의성 검정
    stat_test = {}
    sys_pairs = [(a, b) for i, a in enumerate(available) for b in available[i + 1:]]
    for sys_a, sys_b in sys_pairs:
        pair_key = f"{sys_a}_vs_{sys_b}"
        for dim in DIMENSIONS:
            vals_a = [r.get(dim, 1) for r in judged_data[sys_a]]
            vals_b = [r.get(dim, 1) for r in judged_data[sys_b]]
            p_val, significant = _wilcoxon_test(vals_a, vals_b)
            stat_test[f"{pair_key}_{dim}_p_value"] = p_val
            stat_test[f"{pair_key}_{dim}_significant"] = significant

    # 카테고리별 우세 판정 (최고 accuracy 시스템)
    category_winner = {}
    for cat in CATEGORIES:
        scores = {s: analyses[s]["category_scores"].get(cat, 0) for s in available}
        max_score = max(scores.values())
        winners = [s for s, v in scores.items() if v == max_score]
        category_winner[cat] = winners[0] if len(winners) == 1 else "tie"

    result = {
        "bridge": bridge_name,
        "systems": available,
        "statistical_test": stat_test,
        "category_winner": category_winner,
    }
    for sys_name in available:
        result[sys_name] = analyses[sys_name]
    return result


def generate_final_report() -> None:
    """모든 교량의 결과를 통합하여 최종 리포트를 생성한다."""
    bridges = list(config.BRIDGES.keys())
    all_comparisons = {}

    for bridge in bridges:
        try:
            all_comparisons[bridge] = compare_systems(bridge)
        except FileNotFoundError as e:
            print(f"  ⚠️ {bridge} 결과 파일 없음: {e}")
            continue

    if not all_comparisons:
        print("  ❌ 분석할 결과가 없습니다.")
        return

    # JSON 저장
    json_path = Path(config.RESULTS_DIR) / "final_comparison.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_comparisons, f, ensure_ascii=False, indent=2)

    # 엑셀 리포트 생성
    excel_path = Path(config.RESULTS_DIR) / "final_comparison.xlsx"
    with pd.ExcelWriter(str(excel_path), engine="openpyxl") as writer:
        _write_summary_sheet(writer, all_comparisons)
        _write_category_sheet(writer, all_comparisons)
        _write_error_sheet(writer, all_comparisons)
        _write_scan_vs_digital_sheet(writer, all_comparisons)
        _write_stat_sheet(writer, all_comparisons)
        _write_detail_sheet(writer, bridges)
        _write_cost_speed_sheet(writer, bridges)
        _write_routing_sheet(writer, bridges)

    print(f"\n📊 최종 리포트 생성 완료")
    print(f"  📄 {excel_path}")
    print(f"  📄 {json_path}")

    # 콘솔 요약
    _print_summary(all_comparisons)


# ── 엑셀 시트 작성 헬퍼 ──


def _write_summary_sheet(writer, comparisons: dict) -> None:
    """Sheet 1: 전체요약"""
    rows = []
    for bridge, comp in comparisons.items():
        for sys_name in comp.get("systems", ["rag", "llm"]):
            s = comp[sys_name]
            rows.append(
                {
                    "교량": bridge,
                    "시스템": sys_name.upper(),
                    "Accuracy": s["avg_accuracy"],
                    "Completeness": s["avg_completeness"],
                    "Faithfulness": s["avg_faithfulness"],
                    "종합평균": s["avg_overall"],
                }
            )
    pd.DataFrame(rows).to_excel(writer, sheet_name="전체요약", index=False)


def _write_category_sheet(writer, comparisons: dict) -> None:
    """Sheet 2: 카테고리별"""
    rows = []
    for bridge, comp in comparisons.items():
        systems = comp.get("systems", ["rag", "llm"])
        for cat in CATEGORIES:
            row = {"교량": bridge, "카테고리": cat}
            for sys_name in systems:
                row[f"{sys_name.upper()} Accuracy"] = comp[sys_name]["category_scores"].get(cat, 0)
            row["우세"] = comp["category_winner"].get(cat, "N/A")
            rows.append(row)
    pd.DataFrame(rows).to_excel(writer, sheet_name="카테고리별", index=False)


def _write_error_sheet(writer, comparisons: dict) -> None:
    """Sheet 3: 오류분석"""
    all_errors = set()
    for comp in comparisons.values():
        for sys_name in comp.get("systems", ["rag", "llm"]):
            all_errors.update(comp[sys_name]["error_types"].keys())

    rows = []
    for error_type in sorted(all_errors):
        row = {"오류유형": error_type}
        for bridge, comp in comparisons.items():
            for sys_name in comp.get("systems", ["rag", "llm"]):
                row[f"{bridge}_{sys_name.upper()}"] = comp[sys_name]["error_types"].get(error_type, 0)
        rows.append(row)
    pd.DataFrame(rows).to_excel(writer, sheet_name="오류분석", index=False)


def _write_scan_vs_digital_sheet(writer, comparisons: dict) -> None:
    """Sheet 4: 스캔vs디지털"""
    rows = []
    bridges = list(comparisons.keys())
    scan_bridge = next((b for b in bridges if "대안천" in b), None)
    digital_bridge = next((b for b in bridges if "송정" in b), None)

    all_systems = set()
    for comp in comparisons.values():
        all_systems.update(comp.get("systems", ["rag", "llm"]))

    metrics = [f"avg_{d}" for d in DIMENSIONS] + ["avg_overall"]

    for sys_name in sorted(all_systems):
        for metric in metrics:
            row = {"시스템": sys_name.upper(), "메트릭": metric}
            if scan_bridge and scan_bridge in comparisons and sys_name in comparisons[scan_bridge].get("systems", []):
                row["스캔(대안천교)"] = comparisons[scan_bridge][sys_name].get(metric, 0)
            if digital_bridge and digital_bridge in comparisons and sys_name in comparisons[digital_bridge].get("systems", []):
                row["디지털(송정교)"] = comparisons[digital_bridge][sys_name].get(metric, 0)
            if "스캔(대안천교)" in row and "디지털(송정교)" in row:
                scan_val = row["스캔(대안천교)"]
                dig_val = row["디지털(송정교)"]
                row["차이"] = round(dig_val - scan_val, 4) if isinstance(scan_val, (int, float)) else "N/A"
            rows.append(row)

    pd.DataFrame(rows).to_excel(writer, sheet_name="스캔vs디지털", index=False)


def _write_stat_sheet(writer, comparisons: dict) -> None:
    """Sheet 5: 통계검증"""
    rows = []
    for bridge, comp in comparisons.items():
        st = comp["statistical_test"]
        systems = comp.get("systems", ["rag", "llm"])
        sys_pairs = [(a, b) for i, a in enumerate(systems) for b in systems[i + 1:]]
        for sys_a, sys_b in sys_pairs:
            pair_key = f"{sys_a}_vs_{sys_b}"
            for dim in DIMENSIONS:
                rows.append(
                    {
                        "교량": bridge,
                        "비교": f"{sys_a.upper()} vs {sys_b.upper()}",
                        "메트릭": dim,
                        "p-value": st.get(f"{pair_key}_{dim}_p_value", "N/A"),
                        "유의(p<0.05)": st.get(f"{pair_key}_{dim}_significant", "N/A"),
                    }
                )
    pd.DataFrame(rows).to_excel(writer, sheet_name="통계검증", index=False)


def _write_detail_sheet(writer, bridges: list) -> None:
    """Sheet 6: 개별문항"""
    rows = []
    for bridge in bridges:
        sys_judged = {}
        for sys_name in SYSTEMS:
            try:
                sys_judged[sys_name] = _load_judged(bridge, sys_name)
            except FileNotFoundError:
                continue

        if not sys_judged:
            continue

        by_qid = {}
        for sys_name, judged in sys_judged.items():
            for r in judged:
                qid = r.get("question_id", "")
                if qid not in by_qid:
                    by_qid[qid] = {"question": r.get("question", "")}
                by_qid[qid][sys_name] = r

        for qid in sorted(by_qid.keys()):
            data = by_qid[qid]
            row = {"교량": bridge, "question_id": qid, "question": data["question"]}
            for sys_name in SYSTEMS:
                if sys_name in data:
                    r = data[sys_name]
                    row[f"{sys_name}_answer"] = r.get("answer", "")
                    row[f"{sys_name}_accuracy"] = r.get("accuracy", 1)
                    row[f"{sys_name}_completeness"] = r.get("completeness", 1)
                    row[f"{sys_name}_faithfulness"] = r.get("faithfulness", 1)
            rows.append(row)

    pd.DataFrame(rows).to_excel(writer, sheet_name="개별문항", index=False)


def _load_results(bridge_name: str, system_name: str) -> list[dict]:
    """결과 JSON(답변 원본)을 로드한다."""
    path = Path(config.RESULTS_DIR) / f"{bridge_name}_{system_name}_results.json"
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("results", data) if isinstance(data, dict) else data


def _get_model_for_system(system_name: str) -> str:
    """시스템명에 대응하는 모델명을 반환한다."""
    if system_name in ("rag", "rag_v2", "rag_v3"):
        return config.RAG_LLM_MODEL
    if system_name == "proposed":
        return "proposed_mixed"
    return "gemini-3.1-pro-preview"


def _compute_proposed_cost(results: list[dict]) -> float:
    """proposed 시스템의 혼합 비용을 계산한다."""
    rag_cost_info = config.MODEL_COSTS.get(config.RAG_LLM_MODEL, {"input": 0, "output": 0})
    llm_cost_info = config.MODEL_COSTS.get("gemini-3.1-pro-preview", {"input": 0, "output": 0})

    total_cost = 0.0
    for r in results:
        routed = r.get("routed_to", "llm")
        inp = r.get("input_tokens", 0)
        out = r.get("output_tokens", 0)
        if routed == "rag_v3":
            total_cost += inp * rag_cost_info["input"] / 1_000_000
            total_cost += out * rag_cost_info["output"] / 1_000_000
        else:
            total_cost += inp * llm_cost_info["input"] / 1_000_000
            total_cost += out * llm_cost_info["output"] / 1_000_000
    return total_cost


def _write_cost_speed_sheet(writer, bridges: list) -> None:
    """Sheet 7: 비용속도"""
    rows = []
    for bridge in bridges:
        for sys_name in SYSTEMS:
            results = _load_results(bridge, sys_name)
            if not results:
                continue

            total_elapsed = sum(r.get("elapsed_sec", 0) for r in results)
            total_input = sum(r.get("input_tokens", 0) for r in results)
            total_output = sum(r.get("output_tokens", 0) for r in results)
            total_tokens = total_input + total_output
            n = len(results)

            if sys_name == "proposed":
                model = f"{config.RAG_LLM_MODEL} + gemini-3.1-pro"
                total_cost = _compute_proposed_cost(results)
            else:
                model = _get_model_for_system(sys_name)
                cost_info = config.MODEL_COSTS.get(model, {"input": 0, "output": 0})
                total_cost = (
                    total_input * cost_info["input"] / 1_000_000
                    + total_output * cost_info["output"] / 1_000_000
                )

            rows.append({
                "교량": bridge,
                "시스템": sys_name.upper(),
                "모델": model,
                "문항수": n,
                "총 시간(분)": round(total_elapsed / 60, 1),
                "문항당 평균(초)": round(total_elapsed / n, 1) if n else 0,
                "총 입력토큰": total_input,
                "총 출력토큰": total_output,
                "총 토큰": total_tokens,
                "총 비용($)": round(total_cost, 4),
                "문항당 비용($)": round(total_cost / n, 4) if n else 0,
            })

    pd.DataFrame(rows).to_excel(writer, sheet_name="비용속도", index=False)


def _write_routing_sheet(writer, bridges: list) -> None:
    """Sheet 8: 라우팅분석 — Proposed 시스템의 질문별 라우팅 결과."""
    rows = []
    for bridge in bridges:
        # proposed 결과 로드
        proposed_results = _load_results(bridge, "proposed")
        if not proposed_results:
            continue

        # proposed 채점 결과 로드
        proposed_judged = {}
        try:
            judged = _load_judged(bridge, "proposed")
            proposed_judged = {r.get("question_id"): r for r in judged}
        except FileNotFoundError:
            pass

        for r in proposed_results:
            qid = r.get("question_id", "")
            j = proposed_judged.get(qid, {})
            rows.append({
                "교량": bridge,
                "question_id": qid,
                "question": r.get("question", "")[:80],
                "classification": r.get("classification", ""),
                "routed_to": r.get("routed_to", ""),
                "accuracy": j.get("accuracy", ""),
                "completeness": j.get("completeness", ""),
                "faithfulness": j.get("faithfulness", ""),
                "elapsed_sec": r.get("elapsed_sec", 0),
            })

    if rows:
        pd.DataFrame(rows).to_excel(writer, sheet_name="라우팅분석", index=False)


# ── 유틸리티 ──


def _wilcoxon_test(a: list, b: list) -> tuple[float, bool]:
    """Wilcoxon signed-rank test. 차이가 없으면 p=1.0 반환."""
    diffs = [x - y for x, y in zip(a, b)]
    if all(d == 0 for d in diffs):
        return 1.0, False
    try:
        stat, p_val = wilcoxon(a, b)
        return round(p_val, 6), bool(p_val < 0.05)
    except Exception:
        return 1.0, False


def _print_summary(comparisons: dict) -> None:
    """콘솔에 요약 테이블을 출력한다."""
    print("\n" + "=" * 70)
    print("📊 최종 비교 요약 (G-Eval 1~5 Likert)")
    print("=" * 70)
    header = f"{'교량':<10} {'시스템':<8} {'Acc':>5} {'Comp':>5} {'Faith':>5} {'Avg':>5}"
    print(header)
    print("-" * 70)
    for bridge, comp in comparisons.items():
        for sys_name in comp.get("systems", ["rag", "llm"]):
            s = comp[sys_name]
            print(
                f"{bridge:<10} {sys_name.upper():<8} "
                f"{s['avg_accuracy']:>5.2f} "
                f"{s['avg_completeness']:>5.2f} "
                f"{s['avg_faithfulness']:>5.2f} "
                f"{s['avg_overall']:>5.2f}"
            )
    print("=" * 70)

    # 통계 검정 요약
    for bridge, comp in comparisons.items():
        st = comp["statistical_test"]
        systems = comp.get("systems", ["rag", "llm"])
        sys_pairs = [(a, b) for i, a in enumerate(systems) for b in systems[i + 1:]]
        for sys_a, sys_b in sys_pairs:
            pair_key = f"{sys_a}_vs_{sys_b}"
            p = st.get(f"{pair_key}_accuracy_p_value", "N/A")
            sig = "유의" if st.get(f"{pair_key}_accuracy_significant") else "비유의"
            print(f"  {bridge}: {sys_a.upper()} vs {sys_b.upper()} accuracy p={p} ({sig})")


# ── 하위 호환 ──


def analyze_results(rag_results: list[dict], llm_results: list[dict]) -> dict:
    """RAG와 LLM 결과를 비교 분석한다 (리스트 직접 입력 버전)."""
    rag_results = [_normalize_result(r) for r in rag_results]
    llm_results = [_normalize_result(r) for r in llm_results]

    overall = {
        "rag": _compute_stats(rag_results),
        "llm": _compute_stats(llm_results),
    }

    by_category = {}
    for cat in CATEGORIES:
        rag_cat = [r for r in rag_results if r.get("category", r.get("question_type")) == cat]
        llm_cat = [r for r in llm_results if r.get("category", r.get("question_type")) == cat]
        by_category[cat] = {
            "rag": _compute_stats(rag_cat),
            "llm": _compute_stats(llm_cat),
        }

    rag_acc = [r.get("accuracy", 1) for r in rag_results]
    llm_acc = [r.get("accuracy", 1) for r in llm_results]
    stat_tests = run_statistical_tests(rag_acc, llm_acc)

    return {
        "overall": overall,
        "by_category": by_category,
        "statistical_tests": stat_tests,
    }


def compute_category_stats(results: list[dict], categories: dict) -> dict:
    """카테고리별 통계를 계산한다."""
    results = [_normalize_result(r) for r in results]
    out = {}
    for cat in categories:
        cat_results = [
            r for r in results
            if r.get("category", r.get("question_type")) == cat
        ]
        out[cat] = _compute_stats(cat_results)
    return out


def run_statistical_tests(a_scores: list[float], b_scores: list[float]) -> dict:
    """두 시스템 점수 간 통계 검정을 수행한다."""
    p_val, sig = _wilcoxon_test(a_scores, b_scores)
    return {
        "wilcoxon": {"p_value": p_val, "significant": sig},
    }


def generate_excel_report(analysis: dict, output_path: str) -> None:
    """분석 결과를 엑셀 리포트로 생성한다."""
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        rows = []
        for sys_name in ["rag", "llm"]:
            s = analysis["overall"][sys_name]
            s_row = {"시스템": sys_name.upper()}
            s_row.update(s)
            rows.append(s_row)
        pd.DataFrame(rows).to_excel(writer, sheet_name="전체요약", index=False)

        cat_rows = []
        for cat, data in analysis.get("by_category", {}).items():
            for sys_name in ["rag", "llm"]:
                row = {"카테고리": cat, "시스템": sys_name.upper()}
                row.update(data[sys_name])
                cat_rows.append(row)
        pd.DataFrame(cat_rows).to_excel(writer, sheet_name="카테고리별", index=False)

    print(f"📄 엑셀 리포트 저장: {output_path}")


def _compute_stats(results: list[dict]) -> dict:
    """결과 리스트에서 통계를 계산한다."""
    if not results:
        return {
            "avg_accuracy": 0, "avg_completeness": 0, "avg_faithfulness": 0,
            "avg_overall": 0, "count": 0,
        }
    stats = {}
    for dim in DIMENSIONS:
        scores = [r.get(dim, 1) for r in results]
        stats[f"avg_{dim}"] = round(float(np.mean(scores)), 2)
    all_avgs = [stats[f"avg_{d}"] for d in DIMENSIONS]
    stats["avg_overall"] = round(float(np.mean(all_avgs)), 2)
    stats["count"] = len(results)
    return stats
