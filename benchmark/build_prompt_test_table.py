"""Build a side-by-side comparison table for the prompt-bias hypothesis test.

Rows: Upstage I+T (tf457), Upstage I+T (image_first),
      Qwen OCR I+T (tf457), Qwen OCR I+T (image_first).
Cols: per-dataset EM + macro avg + Δ vs Upstage I+T tf457 baseline.

The Upstage tf457 baseline is read from results/v12_on_visrag/today/
{dataset}_parsed_visual_top1_first100.json (= "Image+Text (Upstage)" in tf457.md).
Other cells come from results/prompt_test/.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROMPT_TEST = ROOT / "results" / "prompt_test"
USER_RESULTS = ROOT / "results" / "v12_on_visrag" / "today"

DATASETS = ["InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA"]


def load_accuracy(path: Path) -> float | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)["summary"]["accuracy"]


def fmt(v: float | None) -> str:
    return f"{v:.4f}" if v is not None else "—"


CELLS = [
    # (label, lookup function) — all 4 cells re-run locally on transformers 4.57.6
    (
        "Image+Text (Upstage) — prompt=tf457",
        lambda ds: load_accuracy(PROMPT_TEST / f"{ds}_upstage_text_image_tf457.json"),
    ),
    (
        "Image+Text (Upstage) — prompt=image_first",
        lambda ds: load_accuracy(PROMPT_TEST / f"{ds}_upstage_text_image_image_first.json"),
    ),
    (
        "Image+Text (Qwen OCR) — prompt=tf457",
        lambda ds: load_accuracy(PROMPT_TEST / f"{ds}_qwen_ocr_text_image_tf457.json"),
    ),
    (
        "Image+Text (Qwen OCR) — prompt=image_first",
        lambda ds: load_accuracy(PROMPT_TEST / f"{ds}_qwen_ocr_text_image_image_first.json"),
    ),
]


def main() -> None:
    accs = {label: {ds: getter(ds) for ds in DATASETS} for label, getter in CELLS}
    base = accs[CELLS[0][0]]

    lines = [
        "# Prompt-bias hypothesis test (Image+Text cells)",
        "",
        "Generator: Qwen2-VL-7B-Instruct (NF4 4-bit) | Metric: Relaxed Exact Match",
        "Samples: Chaemin first100 (oracle qrels, topk=1) | DocVQA == MP-DocVQA",
        "Environment: transformers 4.57.6 (vision-bug-free); local RTX 4060 8GB.",
        "",
        "All 4 cells were re-run end-to-end on the same machine and same",
        "transformers version, so prompt-variant deltas are within-config and free",
        "of the 4.51 vision-encoder bug that depressed tf451 numbers.",
        "",
        "| Method | Prompt | InfoVQA | ChartQA | MP-DocVQA | SlideVQA | Macro | Δ vs row 1 |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, _ in CELLS:
        row = accs[label]
        per_ds = [row[ds] for ds in DATASETS]
        macro = sum(v for v in per_ds if v is not None) / sum(1 for v in per_ds if v is not None) if any(v is not None for v in per_ds) else None
        base_per_ds = [base[ds] for ds in DATASETS]
        deltas = [a - b for a, b in zip(per_ds, base_per_ds) if a is not None and b is not None]
        delta_macro = (sum(deltas) / len(deltas) * 100) if len(deltas) == len(DATASETS) else None

        method = label.split(" — prompt=")[0]
        prompt = label.split(" — prompt=")[1] if " — prompt=" in label else "?"
        delta_str = f"{delta_macro:+.2f}%p" if delta_macro is not None else "—"
        if label == CELLS[0][0]:
            delta_str = "— (baseline)"
        lines.append(
            f"| {method} | {prompt} | "
            + " | ".join(fmt(row[ds]) for ds in DATASETS)
            + f" | {fmt(macro)} | {delta_str} |"
        )

    lines.append("")
    lines.append("## tf457 reference (different hardware, copied verbatim)")
    lines.append("")
    lines.append("| Method | Prompt | InfoVQA | ChartQA | MP-DocVQA | SlideVQA |")
    lines.append("|---|---|---:|---:|---:|---:|")
    lines.append("| Image+Text (Qwen OCR) | tf457 | 0.7300 | 0.6667 | 0.8200 | 0.5800 |")
    lines.append("| Image+Text (Upstage)  | tf457 | 0.5400 | 0.5079 | 0.8000 | 0.5200 |")

    md = "\n".join(lines) + "\n"
    out_path = PROMPT_TEST / "table.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding="utf-8")
    print(md)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
