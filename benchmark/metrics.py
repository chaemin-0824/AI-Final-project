from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Iterable

_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?")


def _numbers(text: str) -> list[float]:
    return [float(x) for x in _NUMBER.findall(text.replace(",", ""))]


def relaxed_exact_match(prediction: str, answer: str, tolerance: float = 0.05) -> bool:
    """VisRAG-style relaxed exact match.

    Text answers are compared case-insensitively after whitespace normalization.
    If both strings contain numbers, each gold number must be matched by at least
    one predicted number within the given relative tolerance.
    """
    pred = " ".join(str(prediction).strip().lower().split())
    gold = " ".join(str(answer).strip().lower().split())
    if pred == gold:
        return True

    gold_nums = _numbers(gold)
    pred_nums = _numbers(pred)
    if gold_nums and pred_nums:
        for g in gold_nums:
            matched = False
            for p in pred_nums:
                denom = max(abs(g), 1e-12)
                if math.isclose(p, g, rel_tol=tolerance, abs_tol=tolerance if abs(g) < 1 else 0.0):
                    matched = True
                    break
                if abs(p - g) / denom <= tolerance:
                    matched = True
                    break
            if not matched:
                return False
        return True
    return pred in gold or gold in pred


def accuracy(rows: Iterable[dict], pred_key: str = "prediction", answer_key: str = "answer", tolerance: float = 0.05) -> dict:
    total = 0
    correct = 0
    for row in rows:
        if answer_key not in row:
            continue
        total += 1
        correct += int(relaxed_exact_match(str(row.get(pred_key, "")), str(row[answer_key]), tolerance))
    return {"total": total, "correct": correct, "accuracy": (correct / total if total else None)}


def mrr_at_k(run: dict[str, list[str]], qrels: dict[str, set[str]], k: int = 10) -> float:
    if not qrels:
        return 0.0
    total = 0.0
    for qid, relevant in qrels.items():
        reciprocal = 0.0
        for rank, docid in enumerate(run.get(qid, [])[:k], start=1):
            if docid in relevant:
                reciprocal = 1.0 / rank
                break
        total += reciprocal
    return total / len(qrels)


def recall_at_k(run: dict[str, list[str]], qrels: dict[str, set[str]], k: int = 10) -> float:
    if not qrels:
        return 0.0
    total = 0.0
    for qid, relevant in qrels.items():
        if not relevant:
            continue
        retrieved = set(run.get(qid, [])[:k])
        total += len(retrieved.intersection(relevant)) / len(relevant)
    return total / len(qrels)


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: str | Path, payload: object) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
