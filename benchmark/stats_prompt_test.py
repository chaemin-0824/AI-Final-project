"""Per-query paired statistics for the prompt-test results.

Computes:
  - Per-query EM under the relaxed-EM metric for each (dataset, cell).
  - Paired sign / McNemar test for the key cell comparisons.
  - 95% bootstrap CI on macro accuracy for each cell.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Iterable

from benchmark.metrics import relaxed_exact_match

ROOT = Path(__file__).resolve().parents[1]
PROMPT_TEST = ROOT / "results" / "prompt_test"

DATASETS = ["InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA"]
CELLS = {
    "upstage_tf457": "upstage_text_image_tf457",
    "upstage_image_first": "upstage_text_image_image_first",
    "upstage_tf457_norm": "upstage_text_image_tf457_norm",
    "qwen_ocr_tf457": "qwen_ocr_text_image_tf457",
    "qwen_ocr_image_first": "qwen_ocr_text_image_image_first",
}


def load_rows(cell_token: str) -> dict[tuple[str, str], bool]:
    out: dict[tuple[str, str], bool] = {}
    for ds in DATASETS:
        path = PROMPT_TEST / f"{ds}_{cell_token}.json"
        payload = json.load(open(path, encoding="utf-8"))
        for r in payload["rows"]:
            qid = r["qid"]
            em = relaxed_exact_match(str(r.get("prediction", "")), str(r["answer"]))
            out[(ds, qid)] = em
    return out


def macro_accuracy(em_map: dict[tuple[str, str], bool]) -> float:
    per_ds = {}
    for (ds, _qid), em in em_map.items():
        per_ds.setdefault(ds, []).append(em)
    accs = [sum(v) / len(v) for v in per_ds.values()]
    return sum(accs) / len(accs)


def bootstrap_ci(em_map: dict[tuple[str, str], bool], n_iters: int = 2000, alpha: float = 0.05, seed: int = 0) -> tuple[float, float, float]:
    rng = random.Random(seed)
    per_ds: dict[str, list[bool]] = {}
    for (ds, _qid), em in em_map.items():
        per_ds.setdefault(ds, []).append(em)
    boots = []
    ds_keys = list(per_ds.keys())
    for _ in range(n_iters):
        per_ds_accs = []
        for ds in ds_keys:
            xs = per_ds[ds]
            n = len(xs)
            sample = [xs[rng.randrange(n)] for _ in range(n)]
            per_ds_accs.append(sum(sample) / n)
        boots.append(sum(per_ds_accs) / len(per_ds_accs))
    boots.sort()
    lo = boots[int(alpha / 2 * n_iters)]
    hi = boots[int((1 - alpha / 2) * n_iters)]
    point = macro_accuracy(em_map)
    return point, lo, hi


def mcnemar(a: dict[tuple[str, str], bool], b: dict[tuple[str, str], bool]) -> dict:
    keys = sorted(set(a) & set(b))
    a_only = sum(1 for k in keys if a[k] and not b[k])
    b_only = sum(1 for k in keys if b[k] and not a[k])
    both_correct = sum(1 for k in keys if a[k] and b[k])
    both_wrong = sum(1 for k in keys if not a[k] and not b[k])
    n_disc = a_only + b_only
    # McNemar with continuity correction
    if n_disc == 0:
        chi2 = 0.0
        p = 1.0
    else:
        chi2 = (abs(a_only - b_only) - 1) ** 2 / n_disc
        # Chi-square 1-df survival function via erfc
        p = math.erfc(math.sqrt(chi2 / 2.0))
    # Exact two-sided sign test on discordant pairs (binomial 0.5)
    def binom_pmf(k: int, n: int) -> float:
        # log-space for stability
        from math import lgamma, exp
        return exp(lgamma(n + 1) - lgamma(k + 1) - lgamma(n - k + 1) - n * math.log(2.0))
    if n_disc == 0:
        p_sign = 1.0
    else:
        k_smaller = min(a_only, b_only)
        cum = sum(binom_pmf(i, n_disc) for i in range(k_smaller + 1))
        p_sign = min(1.0, 2 * cum)
    return {
        "n": len(keys),
        "a_unique_correct": a_only,
        "b_unique_correct": b_only,
        "both_correct": both_correct,
        "both_wrong": both_wrong,
        "n_discordant": n_disc,
        "mcnemar_chi2": chi2,
        "mcnemar_p_continuity": p,
        "sign_test_p_exact": p_sign,
    }


def per_dataset_acc(em_map: dict[tuple[str, str], bool]) -> dict[str, float]:
    per_ds: dict[str, list[bool]] = {}
    for (ds, _qid), em in em_map.items():
        per_ds.setdefault(ds, []).append(em)
    return {ds: sum(v) / len(v) for ds, v in per_ds.items()}


def main() -> None:
    cells = {name: load_rows(token) for name, token in CELLS.items()}

    # Per-cell macro accuracy + bootstrap CI
    print("=== Macro accuracy with 95% bootstrap CI (n=2000) ===")
    for name, em in cells.items():
        point, lo, hi = bootstrap_ci(em)
        per_ds = per_dataset_acc(em)
        per_ds_str = " / ".join(f"{ds}: {per_ds[ds]:.3f}" for ds in DATASETS)
        print(f"  {name:24s} macro={point:.4f} [{lo:.4f}, {hi:.4f}]   per-ds: {per_ds_str}")

    # Paired comparisons
    paired = [
        ("upstage_tf457", "qwen_ocr_tf457",        "Upstage I+T vs self-OCR I+T (original prompt)"),
        ("upstage_image_first", "qwen_ocr_image_first", "Upstage I+T vs self-OCR I+T (image-first prompt)"),
        ("upstage_tf457", "upstage_image_first",   "Upstage I+T: image-first vs original prompt"),
        ("qwen_ocr_tf457", "qwen_ocr_image_first", "self-OCR I+T: image-first vs original prompt"),
        ("upstage_tf457", "upstage_tf457_norm",    "Upstage I+T: normalised vs original text (same prompt)"),
    ]
    print()
    print("=== Paired McNemar / sign tests ===")
    for a, b, desc in paired:
        res = mcnemar(cells[a], cells[b])
        print(f"  {desc}")
        print(f"    {a} (a) vs {b} (b)")
        print(
            f"    a-only: {res['a_unique_correct']}, b-only: {res['b_unique_correct']}, both correct: {res['both_correct']}, both wrong: {res['both_wrong']}"
        )
        print(
            f"    n_disc: {res['n_discordant']}, McNemar chi2: {res['mcnemar_chi2']:.3f}, p(cont): {res['mcnemar_p_continuity']:.4f}, sign-test p: {res['sign_test_p_exact']:.4f}"
        )
        print()


if __name__ == "__main__":
    main()
