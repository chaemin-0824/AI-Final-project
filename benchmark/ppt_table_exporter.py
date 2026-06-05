"""Render v12-general + VisRAG results in the PPT layout from
docs/VisRAG Multi Page Compression.pptx (slide 10).

PPT main table is:
    Method | InfoVQA | ChartQA | DocVQA | SlideVQA | 평균 Δ vs Baseline

DocVQA in the PPT corresponds to MP-DocVQA in the official VisRAG repo.

Inputs are the per-(dataset, method) JSON files written by
benchmark/v12_on_visrag.py (and, optionally, VisRAG history JSONLs from the
official generate.py).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.compare_results import summarize_v12_json, summarize_visrag_history  # noqa: E402
from benchmark.metrics import write_json  # noqa: E402

PPT_DATASETS = ["InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA"]
PPT_DATASET_DISPLAY = {
    "InfoVQA": "InfoVQA",
    "ChartQA": "ChartQA",
    "MP-DocVQA": "DocVQA",
    "SlideVQA": "SlideVQA",
}

METHOD_TO_DEFAULT_LABEL = {
    "image_only": "Baseline (순수 VisRAG, v12_on_visrag image_only)",
    "parsed_text_only": "Parsed-Text Only (ablation)",
    "parsed_visual": "Parsed-Visual RAG (v12-general)",
}


def _macro(row: dict[str, float | None]) -> float | None:
    vals = [v for v in row.values() if v is not None]
    return mean(vals) if vals else None


def _delta_pp(method_macro: float | None, baseline_macro: float | None) -> str:
    if method_macro is None or baseline_macro is None:
        return "n/a"
    delta = (method_macro - baseline_macro) * 100.0
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.2f}%p"


def _coerce_dataset(value: str | None, hint_from_path: str | None) -> str | None:
    if value in PPT_DATASETS:
        return value
    if hint_from_path:
        for ds in PPT_DATASETS:
            if ds.lower() in hint_from_path.lower():
                return ds
    return None


def gather_rows(
    v12_paths: list[Path],
    visrag_paths: list[Path],
    visrag_label: str,
    label_overrides: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    """Return (entries, method_label_by_key, dataset_by_entry).

    entries each carry: dataset (official VisRAG name), method_key, accuracy.
    method_label_by_key keeps the display label per method_key in insertion order.
    """
    method_labels: dict[str, str] = {}
    entries: list[dict[str, Any]] = []

    for path in v12_paths:
        entry = summarize_v12_json(path)
        ds = _coerce_dataset(entry.get("dataset"), str(path))
        method = entry.get("method")
        if ds is None or method not in METHOD_TO_DEFAULT_LABEL:
            continue
        if method not in method_labels:
            method_labels[method] = label_overrides.get(method, METHOD_TO_DEFAULT_LABEL[method])
        entries.append({
            "dataset": ds,
            "method_key": method,
            "accuracy": entry.get("accuracy"),
            "source_path": str(path),
            "total": entry.get("total"),
            "correct": entry.get("correct"),
        })

    if visrag_paths:
        method_labels["visrag_official"] = visrag_label
        for path in visrag_paths:
            entry = summarize_visrag_history(path)
            ds = _coerce_dataset(entry.get("dataset"), str(path))
            if ds is None:
                continue
            entries.append({
                "dataset": ds,
                "method_key": "visrag_official",
                "accuracy": entry.get("accuracy"),
                "source_path": str(path),
                "total": entry.get("total"),
                "correct": entry.get("correct"),
            })

    return entries, method_labels


def _build_grid(entries: list[dict[str, Any]], method_keys: list[str]) -> dict[str, dict[str, float | None]]:
    grid: dict[str, dict[str, float | None]] = {k: {ds: None for ds in PPT_DATASETS} for k in method_keys}
    for e in entries:
        if e["method_key"] not in grid or e["dataset"] not in PPT_DATASETS:
            continue
        if e["accuracy"] is None:
            continue
        grid[e["method_key"]][e["dataset"]] = float(e["accuracy"])
    return grid


def render_markdown(
    entries: list[dict[str, Any]],
    method_labels: dict[str, str],
    baseline_key: str,
) -> str:
    method_keys = [baseline_key] + [k for k in method_labels if k != baseline_key]
    grid = _build_grid(entries, method_keys)
    macro = {k: _macro(grid[k]) for k in method_keys}
    baseline_macro = macro.get(baseline_key)

    header = ["Method"] + [PPT_DATASET_DISPLAY[d] for d in PPT_DATASETS] + ["평균 Δ vs Baseline"]
    sep = ["---"] + ["---:"] * len(PPT_DATASETS) + ["---:"]
    lines = [
        "# Results (PPT slide-10 layout)",
        "",
        "Dataset columns match `docs/VisRAG Multi Page Compression.pptx` slide 10.",
        "DocVQA == MP-DocVQA (`openbmb/VisRAG-Ret-Test-MP-DocVQA`).",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "|".join(sep) + "|",
    ]
    for k in method_keys:
        label = method_labels[k]
        delta = "—" if k == baseline_key else _delta_pp(macro[k], baseline_macro)
        cells = [label]
        for ds in PPT_DATASETS:
            v = grid[k][ds]
            cells.append("n/a" if v is None else f"{v:.4f}")
        cells.append(delta)
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    lines.append("## Macro averages")
    lines.append("")
    lines.append("| Method | Macro acc | Δ vs Baseline |")
    lines.append("|---|---:|---:|")
    for k in method_keys:
        m = macro[k]
        m_str = "n/a" if m is None else f"{m:.4f}"
        delta = "—" if k == baseline_key else _delta_pp(m, baseline_macro)
        lines.append(f"| {method_labels[k]} | {m_str} | {delta} |")
    lines.append("")
    return "\n".join(lines)


def render_csv(
    entries: list[dict[str, Any]],
    method_labels: dict[str, str],
    baseline_key: str,
) -> str:
    method_keys = [baseline_key] + [k for k in method_labels if k != baseline_key]
    grid = _build_grid(entries, method_keys)
    macro = {k: _macro(grid[k]) for k in method_keys}
    baseline_macro = macro.get(baseline_key)
    header = ["Method"] + [PPT_DATASET_DISPLAY[d] for d in PPT_DATASETS] + ["macro_acc", "delta_vs_baseline_pp"]
    out = [",".join(header)]
    for k in method_keys:
        cells = [method_labels[k]]
        for ds in PPT_DATASETS:
            v = grid[k][ds]
            cells.append("" if v is None else f"{v:.6f}")
        m = macro[k]
        cells.append("" if m is None else f"{m:.6f}")
        if k == baseline_key or m is None or baseline_macro is None:
            cells.append("")
        else:
            cells.append(f"{(m - baseline_macro) * 100.0:.4f}")
        out.append(",".join(cells))
    return "\n".join(out) + "\n"


def render_json(
    entries: list[dict[str, Any]],
    method_labels: dict[str, str],
    baseline_key: str,
) -> dict[str, Any]:
    method_keys = [baseline_key] + [k for k in method_labels if k != baseline_key]
    grid = _build_grid(entries, method_keys)
    macro = {k: _macro(grid[k]) for k in method_keys}
    baseline_macro = macro.get(baseline_key)
    return {
        "layout_source": "docs/VisRAG Multi Page Compression.pptx slide 10",
        "datasets_display": [PPT_DATASET_DISPLAY[d] for d in PPT_DATASETS],
        "datasets_official": PPT_DATASETS,
        "baseline_method_key": baseline_key,
        "baseline_label": method_labels[baseline_key],
        "rows": [
            {
                "method_key": k,
                "method_label": method_labels[k],
                "by_dataset": {PPT_DATASET_DISPLAY[d]: grid[k][d] for d in PPT_DATASETS},
                "macro_accuracy": macro[k],
                "delta_vs_baseline_pp": None
                if (k == baseline_key or macro[k] is None or baseline_macro is None)
                else (macro[k] - baseline_macro) * 100.0,
            }
            for k in method_keys
        ],
        "source_entries": entries,
    }


def _parse_label_override(values: list[str]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    for item in values:
        if "=" not in item:
            raise SystemExit(f"--label expects method=label, got: {item}")
        method, label = item.split("=", 1)
        overrides[method.strip()] = label.strip()
    return overrides


def main() -> int:
    parser = argparse.ArgumentParser(description="Render v12 + VisRAG results in the PPT slide-10 layout.")
    parser.add_argument("--v12-json", action="extend", nargs="+", default=[],
                        help="JSON files from benchmark/v12_on_visrag.py. May be repeated.")
    parser.add_argument("--visrag-history", action="extend", nargs="+", default=[],
                        help="JSONL history files from visrag generate.py (one per dataset). May be repeated.")
    parser.add_argument("--visrag-baseline-label", default="Baseline (순수 VisRAG, official)",
                        help="Label for the VisRAG official-script baseline row.")
    parser.add_argument("--label", action="append", default=[],
                        help="Override method label, e.g. --label parsed_visual='Parsed-Visual RAG (ours)'.")
    parser.add_argument("--baseline-method",
                        choices=["image_only", "visrag_official", "parsed_text_only", "parsed_visual"],
                        default=None,
                        help="Which method is treated as Baseline for Δ. "
                             "Default: visrag_official if --visrag-history given, else image_only.")
    parser.add_argument("--output-markdown", default="results/ppt_format/results_table.md")
    parser.add_argument("--output-csv", default="results/ppt_format/results_table.csv")
    parser.add_argument("--output-json", default="results/ppt_format/results_table.json")
    args = parser.parse_args()

    label_overrides = _parse_label_override(args.label)
    entries, method_labels = gather_rows(
        [Path(p) for p in args.v12_json],
        [Path(p) for p in args.visrag_history],
        args.visrag_baseline_label,
        label_overrides,
    )

    if not entries:
        print("No usable entries found. Provide --v12-json and/or --visrag-history.", file=sys.stderr)
        return 1

    if args.baseline_method:
        baseline_key = args.baseline_method
    elif "visrag_official" in method_labels:
        baseline_key = "visrag_official"
    elif "image_only" in method_labels:
        baseline_key = "image_only"
    else:
        baseline_key = next(iter(method_labels))

    if baseline_key not in method_labels:
        print(f"Baseline method {baseline_key} has no entries.", file=sys.stderr)
        return 1

    md = render_markdown(entries, method_labels, baseline_key)
    csv = render_csv(entries, method_labels, baseline_key)
    js = render_json(entries, method_labels, baseline_key)

    out_md = Path(args.output_markdown)
    out_csv = Path(args.output_csv)
    out_js = Path(args.output_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md, encoding="utf-8")
    out_csv.write_text(csv, encoding="utf-8")
    write_json(out_js, js)
    print(md)
    print(f"\nwrote {out_md}\nwrote {out_csv}\nwrote {out_js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
