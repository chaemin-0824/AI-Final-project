from __future__ import annotations

import json
from pathlib import Path

from benchmark.ppt_table_exporter import (
    METHOD_TO_DEFAULT_LABEL,
    PPT_DATASETS,
    gather_rows,
    render_csv,
    render_json,
    render_markdown,
)


def _write_v12_json(path: Path, dataset: str, method: str, accuracy: float, total: int = 10) -> None:
    """Write a synthetic v12 result JSON.

    summarize_v12_json recomputes accuracy from row predictions, so we have to
    encode the desired hit rate by making `correct` rows predict the gold answer
    and the rest predict something different.
    """
    correct = round(accuracy * total)
    rows: list[dict] = []
    for i in range(total):
        is_hit = i < correct
        # relaxed_exact_match falls back to substring containment for text answers,
        # so we use disjoint strings to avoid accidental matches.
        rows.append({
            "dataset": dataset,
            "method": method,
            "topk": 1,
            "prediction": "alpha" if is_hit else "zzzzz",
            "answer": "alpha",
        })
    payload = {"summary": {"total": total, "correct": correct, "accuracy": accuracy}, "rows": rows}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_gather_rows_keeps_only_ppt_datasets_and_known_methods(tmp_path: Path) -> None:
    good = tmp_path / "ChartQA_image_only_top1.json"
    skipped_dataset = tmp_path / "ArxivQA_image_only_top1.json"  # not in PPT 4-set
    skipped_method = tmp_path / "ChartQA_unknown_top1.json"
    _write_v12_json(good, "ChartQA", "image_only", 0.5)
    _write_v12_json(skipped_dataset, "ArxivQA", "image_only", 0.4)
    _write_v12_json(skipped_method, "ChartQA", "weird_mode", 0.3)

    entries, method_labels = gather_rows([good, skipped_dataset, skipped_method], [], "VisRAG label", {})

    assert len(entries) == 1
    assert entries[0]["dataset"] == "ChartQA"
    assert entries[0]["method_key"] == "image_only"
    assert method_labels["image_only"] == METHOD_TO_DEFAULT_LABEL["image_only"]


def test_render_markdown_marks_baseline_and_delta(tmp_path: Path) -> None:
    paths: list[Path] = []
    for ds, acc_image, acc_pv in [
        ("InfoVQA", 0.5, 0.6),
        ("ChartQA", 0.4, 0.5),
        ("MP-DocVQA", 0.6, 0.7),
        ("SlideVQA", 0.5, 0.6),
    ]:
        a = tmp_path / f"{ds}_image_only_top1.json"
        b = tmp_path / f"{ds}_parsed_visual_top1.json"
        _write_v12_json(a, ds, "image_only", acc_image)
        _write_v12_json(b, ds, "parsed_visual", acc_pv)
        paths.extend([a, b])

    entries, method_labels = gather_rows(paths, [], "VisRAG label", {"parsed_visual": "Ours"})
    md = render_markdown(entries, method_labels, baseline_key="image_only")

    assert "DocVQA" in md
    assert "InfoVQA" in md
    assert "Ours" in md
    # Baseline row has em-dash, our method has signed delta.
    assert "| — |" in md
    assert "+10.00%p" in md  # macro went from 0.5 to 0.6.


def test_render_csv_and_json_round_trip(tmp_path: Path) -> None:
    a = tmp_path / "ChartQA_image_only_top1.json"
    b = tmp_path / "ChartQA_parsed_visual_top1.json"
    _write_v12_json(a, "ChartQA", "image_only", 0.4)
    _write_v12_json(b, "ChartQA", "parsed_visual", 0.5)
    entries, method_labels = gather_rows([a, b], [], "VisRAG label", {})

    csv_text = render_csv(entries, method_labels, baseline_key="image_only")
    js = render_json(entries, method_labels, baseline_key="image_only")

    assert csv_text.splitlines()[0] == "Method,InfoVQA,ChartQA,DocVQA,SlideVQA,macro_acc,delta_vs_baseline_pp"
    assert js["datasets_official"] == PPT_DATASETS
    assert js["baseline_method_key"] == "image_only"
    assert js["rows"][0]["method_key"] == "image_only"
    assert abs(js["rows"][1]["delta_vs_baseline_pp"] - 10.0) < 1e-6  # 0.5 - 0.4 = 0.1 -> 10pp on single dataset.
