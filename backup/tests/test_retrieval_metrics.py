from __future__ import annotations

from benchmark.metrics import mrr_at_k, recall_at_k


def test_mrr_at_k_scores_first_relevant_rank() -> None:
    run = {"q1": ["d2", "d1"], "q2": ["d3"], "q3": ["d9"]}
    qrels = {"q1": {"d1"}, "q2": {"d3"}, "q3": {"d4"}}

    assert mrr_at_k(run, qrels, k=2) == (1 / 2 + 1 + 0) / 3


def test_recall_at_k_averages_per_query_recall() -> None:
    run = {"q1": ["d1", "d2"], "q2": ["d3"], "q3": []}
    qrels = {"q1": {"d1", "d9"}, "q2": {"d3"}, "q3": {"d4"}}

    assert recall_at_k(run, qrels, k=2) == (1 / 2 + 1 + 0) / 3
