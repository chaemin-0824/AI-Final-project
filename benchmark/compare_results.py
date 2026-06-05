from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.metrics import accuracy, load_jsonl, write_json


def summarize_visrag_history(path: Path) -> dict:
    rows = load_jsonl(path)
    normalized = []
    for row in rows:
        normalized.append({
            "qid": row.get("qid"),
            "prediction": row.get("preprocessed_responds", row.get("original_responds", "")),
            "answer": row.get("preprocessed_answer", row.get("original_answer", "")),
        })
    summary = accuracy(normalized)
    return {"path": str(path), "system": "visrag", "rows": len(rows), **summary}


def summarize_v12_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("rows", data if isinstance(data, list) else [])
    summary = accuracy(rows)
    dataset = rows[0].get("dataset") if rows else data.get("dataset")
    method = rows[0].get("method") if rows else data.get("method")
    topk = rows[0].get("topk") if rows else data.get("topk")
    return {
        "path": str(path),
        "system": "v12-general",
        "dataset": dataset,
        "method": method,
        "topk": topk,
        "rows": len(rows),
        **summary,
    }


def grouped_averages(items: list[dict]) -> dict:
    by_method: dict[str, list[float]] = defaultdict(list)
    by_dataset: dict[str, list[float]] = defaultdict(list)
    for item in items:
        acc = item.get("accuracy")
        if acc is None:
            continue
        if item.get("method"):
            by_method[str(item["method"])].append(float(acc))
        if item.get("dataset"):
            by_dataset[str(item["dataset"])].append(float(acc))
    return {
        "macro_by_method": {key: mean(vals) for key, vals in sorted(by_method.items())},
        "macro_by_dataset": {key: mean(vals) for key, vals in sorted(by_dataset.items())},
        "overall_macro_accuracy": mean([float(i["accuracy"]) for i in items if i.get("accuracy") is not None]) if any(i.get("accuracy") is not None for i in items) else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a compact comparison report for VisRAG and v12-general outputs.")
    parser.add_argument("--visrag-history", nargs="*", default=[])
    parser.add_argument("--v12-json", nargs="*", default=[])
    parser.add_argument("--output", default="results/comparison_summary.json")
    args = parser.parse_args()

    visrag = [summarize_visrag_history(Path(p)) for p in args.visrag_history]
    v12 = [summarize_v12_json(Path(p)) for p in args.v12_json]
    report = {
        "metric": "VisRAG paper generation Accuracy with relaxed exact match (5% numeric tolerance)",
        "visrag": visrag,
        "v12": v12,
        "v12_averages": grouped_averages(v12),
    }
    write_json(args.output, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
