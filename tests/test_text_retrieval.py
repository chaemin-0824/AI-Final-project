from __future__ import annotations

from benchmark.parse_cache import ParsedDocument
from benchmark.text_retrieval import build_bm25_index, format_trec_rows, retrieve


def test_retrieve_ranks_matching_evidence_first() -> None:
    docs = [
        ParsedDocument(dataset="ChartQA", corpus_id="a", text="apple revenue chart"),
        ParsedDocument(dataset="ChartQA", corpus_id="b", text="bridge crack table"),
    ]
    index = build_bm25_index(docs)

    hits = retrieve(index, "crack table", topk=2)

    assert hits[0].corpus_id == "b"
    assert len(hits) == 2


def test_format_trec_rows_uses_expected_columns() -> None:
    docs = [ParsedDocument(dataset="ChartQA", corpus_id="doc1", text="alpha beta")]
    index = build_bm25_index(docs)
    hits = retrieve(index, "alpha", topk=1)

    rows = format_trec_rows("qid1", hits, run_name="parsed_text_bm25")

    assert rows[0].startswith("qid1 Q0 doc1 1 ")
    assert rows[0].endswith(" parsed_text_bm25")
