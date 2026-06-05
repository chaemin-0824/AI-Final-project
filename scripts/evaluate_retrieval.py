from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.metrics import mrr_at_k, recall_at_k, write_json
from benchmark.text_retrieval import parse_trec


def load_hf_qrels(dataset: str, dataset_path: str | None = None, cache_dir: str | None = None) -> dict[str, set[str]]:
    path = dataset_path or f"openbmb/VisRAG-Ret-Test-{dataset}"
    ds = load_dataset(path, name="qrels", split="train", cache_dir=cache_dir)
    qrels: dict[str, set[str]] = {}
    for row in ds:
        if float(row.get("score", 1)) <= 0:
            continue
        qrels.setdefault(str(row["query-id"]), set()).add(str(row["corpus-id"]))
    return qrels


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a TREC run with VisRAG retrieval metrics.")
    parser.add_argument("--dataset", required=True, choices=["ArxivQA", "ChartQA", "MP-DocVQA", "InfoVQA", "PlotQA", "SlideVQA"])
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--trec", required=True)
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    run = parse_trec(args.trec)
    qrels = load_hf_qrels(args.dataset, args.dataset_path, args.cache_dir)
    result = {
        "dataset": args.dataset,
        "trec": args.trec,
        "k": args.k,
        "num_queries": len(qrels),
        "MRR@10" if args.k == 10 else f"MRR@{args.k}": mrr_at_k(run, qrels, k=args.k),
        "Recall@10" if args.k == 10 else f"Recall@{args.k}": recall_at_k(run, qrels, k=args.k),
    }
    if args.output:
        write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
