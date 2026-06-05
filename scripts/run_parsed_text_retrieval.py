from __future__ import annotations

import argparse
import sys
from pathlib import Path

from datasets import load_dataset

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.parse_cache import load_parse_cache
from benchmark.text_retrieval import build_bm25_index, format_trec_rows, retrieve


def main() -> int:
    parser = argparse.ArgumentParser(description="Run BM25 retrieval over Upstage parsed VisRAG evidence and write TREC output.")
    parser.add_argument("--dataset", required=True, choices=["ArxivQA", "ChartQA", "MP-DocVQA", "InfoVQA", "PlotQA", "SlideVQA"])
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--parse-cache", required=True)
    parser.add_argument("--topk", type=int, default=10)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    dataset_path = args.dataset_path or f"openbmb/VisRAG-Ret-Test-{args.dataset}"
    cache = load_parse_cache(args.parse_cache)
    docs = [doc for doc in cache.values() if doc.dataset == args.dataset]
    if not docs:
        print(f"No parsed documents found for {args.dataset} in {args.parse_cache}", file=sys.stderr)
        return 1
    index = build_bm25_index(docs)
    queries = load_dataset(dataset_path, name="queries", split="train", cache_dir=args.cache_dir)

    rows: list[str] = []
    count = 0
    for example in queries:
        qid = str(example["query-id"])
        query = str(example["query"])
        hits = retrieve(index, query, topk=args.topk)
        rows.extend(format_trec_rows(qid, hits))
        count += 1
        if args.limit is not None and count >= args.limit:
            break

    output = Path(args.output or ROOT / "results" / "parsed_text_retrieval" / args.dataset / "test.trec")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(rows) + ("\n" if rows else ""), encoding="utf-8")
    print(f"queries={count} rows={len(rows)} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
