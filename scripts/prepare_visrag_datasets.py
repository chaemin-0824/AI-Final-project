from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def repo_name(dataset: str) -> str:
    return f"openbmb/VisRAG-Ret-Test-{dataset}"


def inspect_dataset(dataset: str, cache_dir: str | None = None) -> dict[str, Any]:
    try:
        from datasets import load_dataset
    except ImportError as exc:
        raise SystemExit("datasets is required: pip install datasets") from exc

    name = repo_name(dataset)
    result: dict[str, Any] = {"dataset": dataset, "repo": name, "splits": {}}
    for subset in ("queries", "corpus", "qrels"):
        ds = load_dataset(name, name=subset, split="train", cache_dir=cache_dir)
        row = ds[0] if len(ds) else {}
        result["splits"][subset] = {
            "num_rows": len(ds),
            "columns": list(ds.column_names),
            "sample_keys": list(row.keys()) if isinstance(row, dict) else [],
        }
    return result


PPT_DATASETS = ["InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA"]
ALL_PAPER_DATASETS = ["ArxivQA", "ChartQA", "MP-DocVQA", "InfoVQA", "PlotQA", "SlideVQA"]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download/inspect VisRAG paper benchmark datasets from Hugging Face. "
        "Default subset matches docs/VisRAG Multi Page Compression.pptx (InfoVQA, ChartQA, MP-DocVQA, SlideVQA).",
    )
    parser.add_argument("--datasets", nargs="+", default=PPT_DATASETS)
    parser.add_argument("--all-paper", action="store_true", help="Use the full 6-dataset paper set instead of the PPT subset.")
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--output", default="data/visrag_dataset_manifest.json")
    args = parser.parse_args()
    if args.all_paper:
        args.datasets = ALL_PAPER_DATASETS

    manifest = [inspect_dataset(name, args.cache_dir) for name in args.datasets]
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {out} ({len(manifest)} datasets)")


if __name__ == "__main__":
    main()
