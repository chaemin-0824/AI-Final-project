from __future__ import annotations

import re
from dataclasses import dataclass

from rank_bm25 import BM25Okapi

from benchmark.parse_cache import ParsedDocument, evidence_text

_TOKEN_RE = re.compile(r"[\w가-힣]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass
class Bm25Index:
    docs: list[ParsedDocument]
    tokenized: list[list[str]]
    bm25: BM25Okapi


@dataclass
class RetrievalHit:
    corpus_id: str
    score: float
    rank: int


def build_bm25_index(docs: list[ParsedDocument]) -> Bm25Index:
    ok_docs = [doc for doc in docs if doc.parse_status == "ok"]
    if not ok_docs:
        raise ValueError("No successfully parsed documents are available for BM25 indexing")
    tokenized = [tokenize(evidence_text(doc) or doc.text) for doc in ok_docs]
    # rank_bm25 expects at least one token per document.
    tokenized = [tokens if tokens else ["__empty__"] for tokens in tokenized]
    return Bm25Index(docs=ok_docs, tokenized=tokenized, bm25=BM25Okapi(tokenized))


def retrieve(index: Bm25Index, query: str, topk: int = 10) -> list[RetrievalHit]:
    q_tokens = tokenize(query) or ["__empty__"]
    q_set = set(q_tokens)
    scores = index.bm25.get_scores(q_tokens)

    def sort_key(item: tuple[int, float]) -> tuple[float, int]:
        doc_idx, score = item
        overlap = len(q_set.intersection(index.tokenized[doc_idx]))
        return float(score), overlap

    ranked = sorted(enumerate(scores), key=sort_key, reverse=True)[:topk]
    return [
        RetrievalHit(corpus_id=index.docs[i].corpus_id, score=float(score), rank=rank)
        for rank, (i, score) in enumerate(ranked, start=1)
    ]


def format_trec_rows(qid: str, hits: list[RetrievalHit], run_name: str = "parsed_text_bm25") -> list[str]:
    return [f"{qid} Q0 {hit.corpus_id} {hit.rank} {hit.score:.8f} {run_name}" for hit in hits]


def parse_trec(path: str) -> dict[str, list[str]]:
    run: dict[str, list[tuple[int, str]]] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) < 6:
                continue
            qid, docid, rank = parts[0], parts[2], int(parts[3])
            run.setdefault(qid, []).append((rank, docid))
    return {qid: [docid for _, docid in sorted(items)] for qid, items in run.items()}
