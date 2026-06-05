"""Human-LLM Agreement 검증 모듈.

논문에서 "LLM-as-Judge 신뢰성 검증"으로 사용.
Cohen's Kappa와 Pearson Correlation으로 사람-LLM 채점 일치도를 측정한다.
"""

import json
import random
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd
from scipy.stats import pearsonr
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).parent.parent))
import config
from questions import CATEGORIES

# 카테고리별 샘플 수 (총 10개)
CATEGORY_SAMPLE = {
    "성능변화": 3,
    "중대결함": 3,
    "C등급관리": 2,
    "등급통계": 2,
}


def generate_human_scoring_sheet(
    bridge_name: str, system_name: str, sample_n: int = 10
) -> str:
    """사람 채점용 엑셀 시트를 생성한다.

    Args:
        bridge_name: 교량 이름.
        system_name: 시스템 이름 ("rag" 또는 "llm").
        sample_n: 샘플 수 (기본 10).

    Returns:
        생성된 엑셀 파일 경로.
    """
    results_path = (
        Path(config.RESULTS_DIR) / f"{bridge_name}_{system_name}_results.json"
    )
    with open(results_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    results = data.get("results", data) if isinstance(data, dict) else data

    # 카테고리별 균등 추출
    by_category = defaultdict(list)
    for item in results:
        cat = item.get("category", item.get("question_type", "기타"))
        by_category[cat].append(item)

    sampled = []
    for cat, count in CATEGORY_SAMPLE.items():
        pool = by_category.get(cat, [])
        n = min(count, len(pool))
        sampled.extend(random.sample(pool, n))

    # 부족하면 나머지에서 랜덤 추가
    remaining = sample_n - len(sampled)
    if remaining > 0:
        sampled_ids = {s.get("question_id") for s in sampled}
        pool = [r for r in results if r.get("question_id") not in sampled_ids]
        sampled.extend(random.sample(pool, min(remaining, len(pool))))

    # 엑셀 생성
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Human Scoring"

    headers = [
        "question_id",
        "category",
        "question",
        "answer",
        "human_accuracy_score",
        "human_faithfulness",
        "human_answer_relevance",
        "human_completeness",
        "human_reason",
    ]
    ws.append(headers)

    # 헤더 스타일
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = openpyxl.styles.Font(bold=True)

    for item in sampled:
        ws.append(
            [
                item.get("question_id", ""),
                item.get("category", item.get("question_type", "")),
                item.get("question", ""),
                item.get("answer", ""),
                None,  # human_accuracy_score
                None,  # human_faithfulness
                None,  # human_answer_relevance
                None,  # human_completeness
                None,  # human_reason
            ]
        )

    # 열 너비 조정
    ws.column_dimensions["C"].width = 60
    ws.column_dimensions["D"].width = 80
    ws.column_dimensions["I"].width = 40

    output_path = (
        Path(config.RESULTS_DIR)
        / f"human_scoring_{bridge_name}_{system_name}.xlsx"
    )
    wb.save(str(output_path))

    print(f"📝 사람 채점 시트 생성: {output_path}")
    return str(output_path)


def compute_agreement(bridge_name: str, system_name: str) -> dict:
    """사람 채점과 LLM Judge 채점 간의 일치도를 계산한다.

    Args:
        bridge_name: 교량 이름.
        system_name: 시스템 이름 ("rag" 또는 "llm").

    Returns:
        일치도 지표 딕셔너리.
    """
    # 사람 채점 엑셀 로드
    human_path = (
        Path(config.RESULTS_DIR)
        / f"human_scoring_{bridge_name}_{system_name}.xlsx"
    )
    df_human = pd.read_excel(str(human_path))

    # LLM 채점 JSON 로드
    judged_path = (
        Path(config.RESULTS_DIR) / f"{bridge_name}_{system_name}_judged.json"
    )
    with open(judged_path, "r", encoding="utf-8") as f:
        llm_judged = json.load(f)

    llm_by_qid = {item["question_id"]: item for item in llm_judged}

    # 매칭된 쌍만 추출
    human_acc, llm_acc = [], []
    human_faith, llm_faith = [], []
    human_rel, llm_rel = [], []
    human_comp, llm_comp = [], []
    human_pass, llm_pass = [], []

    for _, row in df_human.iterrows():
        qid = row["question_id"]
        if qid not in llm_by_qid:
            continue

        llm_item = llm_by_qid[qid]

        # NaN 체크 — 사람이 채점하지 않은 행 건너뛰기
        if pd.isna(row.get("human_accuracy_score")):
            continue

        h_acc = int(row["human_accuracy_score"])
        l_acc = int(llm_item["accuracy_score"])
        human_acc.append(h_acc)
        llm_acc.append(l_acc)

        human_pass.append(1 if h_acc >= 80 else 0)
        llm_pass.append(1 if l_acc >= 80 else 0)

        human_faith.append(int(row["human_faithfulness"]))
        llm_faith.append(int(llm_item["faithfulness"]))

        human_rel.append(int(row["human_answer_relevance"]))
        llm_rel.append(int(llm_item["answer_relevance"]))

        human_comp.append(int(row["human_completeness"]))
        llm_comp.append(int(llm_item["completeness"]))

    sample_size = len(human_acc)

    # Pearson Correlation (accuracy_score — 연속형)
    if sample_size >= 3:
        acc_corr, _ = pearsonr(human_acc, llm_acc)
    else:
        acc_corr = float("nan")

    # Cohen's Kappa (이진형)
    faith_kappa = _safe_kappa(human_faith, llm_faith)
    rel_kappa = _safe_kappa(human_rel, llm_rel)
    comp_kappa = _safe_kappa(human_comp, llm_comp)

    # Pass/Fail 일치율
    if sample_size > 0:
        matches = sum(1 for h, l in zip(human_pass, llm_pass) if h == l)
        pf_agreement = matches / sample_size * 100
    else:
        pf_agreement = 0.0

    result = {
        "bridge": bridge_name,
        "system": system_name,
        "sample_size": sample_size,
        "accuracy_correlation": round(acc_corr, 4),
        "faithfulness_kappa": round(faith_kappa, 4),
        "relevance_kappa": round(rel_kappa, 4),
        "completeness_kappa": round(comp_kappa, 4),
        "pass_fail_agreement": round(pf_agreement, 2),
    }

    print(f"\n📊 Human-LLM Agreement ({bridge_name} / {system_name})")
    print(f"  샘플 수: {sample_size}")
    print(f"  Accuracy Correlation: {result['accuracy_correlation']}")
    print(f"  Faithfulness Kappa:   {result['faithfulness_kappa']}")
    print(f"  Relevance Kappa:      {result['relevance_kappa']}")
    print(f"  Completeness Kappa:   {result['completeness_kappa']}")
    print(f"  Pass/Fail 일치율:     {result['pass_fail_agreement']}%")

    return result


def _safe_kappa(y1: list, y2: list) -> float:
    """Cohen's Kappa 안전 계산. 데이터 부족 시 NaN 반환."""
    if len(y1) < 2:
        return float("nan")
    # 모든 값이 동일하면 kappa 계산 불가
    if len(set(y1)) == 1 and len(set(y2)) == 1:
        return 1.0 if y1[0] == y2[0] else 0.0
    try:
        return cohen_kappa_score(y1, y2)
    except Exception:
        return float("nan")


# ── 하위 호환: __init__.py에서 import하는 이름 유지 ──

def compute_cohens_kappa(
    human_scores: list[dict],
    llm_scores: list[dict],
    metric: str = "faithfulness",
) -> float:
    """사람 채점과 LLM 채점 간 Cohen's Kappa를 계산한다."""
    h = [s[metric] for s in human_scores]
    l = [s[metric] for s in llm_scores]
    return _safe_kappa(h, l)


def validate_agreement(
    human_scores: list[dict],
    llm_scores: list[dict],
) -> dict:
    """전체 메트릭에 대해 Human-LLM Agreement를 검증한다."""
    faith_kappa = compute_cohens_kappa(human_scores, llm_scores, "faithfulness")
    rel_kappa = compute_cohens_kappa(human_scores, llm_scores, "answer_relevance")
    comp_kappa = compute_cohens_kappa(human_scores, llm_scores, "completeness")

    h_acc = [s["accuracy_score"] for s in human_scores]
    l_acc = [s["accuracy_score"] for s in llm_scores]
    if len(h_acc) >= 3:
        acc_corr, _ = pearsonr(h_acc, l_acc)
    else:
        acc_corr = float("nan")

    # Pass/Fail 일치율
    h_pass = [1 if s["accuracy_score"] >= 80 else 0 for s in human_scores]
    l_pass = [1 if s["accuracy_score"] >= 80 else 0 for s in llm_scores]
    if len(h_pass) > 0:
        matches = sum(1 for h, l in zip(h_pass, l_pass) if h == l)
        overall = f"{matches / len(h_pass) * 100:.1f}%"
    else:
        overall = "N/A"

    return {
        "faithfulness_kappa": round(faith_kappa, 4),
        "answer_relevance_kappa": round(rel_kappa, 4),
        "completeness_kappa": round(comp_kappa, 4),
        "accuracy_correlation": round(acc_corr, 4),
        "overall_agreement": overall,
    }


def load_human_scores(file_path: str) -> list[dict]:
    """사람 채점 결과 파일을 로드한다."""
    path = Path(file_path)
    if path.suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    elif path.suffix in (".xlsx", ".xls"):
        df = pd.read_excel(str(path))
        records = []
        for _, row in df.iterrows():
            if pd.isna(row.get("human_accuracy_score")):
                continue
            records.append(
                {
                    "question_id": row["question_id"],
                    "accuracy_score": int(row["human_accuracy_score"]),
                    "faithfulness": int(row["human_faithfulness"]),
                    "answer_relevance": int(row["human_answer_relevance"]),
                    "completeness": int(row["human_completeness"]),
                    "reason": row.get("human_reason", ""),
                }
            )
        return records
    else:
        raise ValueError(f"지원하지 않는 파일 형식: {path.suffix}")
