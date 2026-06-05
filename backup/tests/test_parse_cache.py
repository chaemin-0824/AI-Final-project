from __future__ import annotations

from benchmark.parse_cache import ParsedDocument, append_parse_cache, cache_key, evidence_text, load_parse_cache


def test_cache_key_uses_dataset_and_corpus_id() -> None:
    assert cache_key("ChartQA", "3960.png") == "ChartQA:3960.png"


def test_jsonl_cache_round_trips_unicode_and_table_markdown(tmp_path) -> None:
    path = tmp_path / "cache.jsonl"
    doc = ParsedDocument(
        dataset="ChartQA",
        corpus_id="3960.png",
        text="교량 점검 표와 Chart label",
        tables_markdown=["| 항목 | 값 |\n|---|---|\n| 균열 | 0.3mm |"],
        table_descriptions=["균열 폭을 정리한 표"],
        raw_upstage={"content": {"markdown": "본문"}},
    )

    append_parse_cache(path, doc)
    loaded = load_parse_cache(path)

    assert loaded["ChartQA:3960.png"] == doc
    assert "교량 점검" in evidence_text(doc)
    assert "| 균열 | 0.3mm |" in evidence_text(doc)
    assert "균열 폭을 정리한 표" in evidence_text(doc)


def test_failed_parse_rows_are_preserved(tmp_path) -> None:
    path = tmp_path / "cache.jsonl"
    failed = ParsedDocument(
        dataset="PlotQA",
        corpus_id="plot-1",
        parse_status="failed",
        error="rate limited",
    )

    append_parse_cache(path, failed)
    loaded = load_parse_cache(path)

    assert loaded["PlotQA:plot-1"].parse_status == "failed"
    assert loaded["PlotQA:plot-1"].error == "rate limited"
    assert evidence_text(loaded["PlotQA:plot-1"]) == ""
