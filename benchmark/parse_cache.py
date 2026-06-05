from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(eq=True)
class ParsedDocument:
    dataset: str
    corpus_id: str
    text: str = ""
    tables_markdown: list[str] = field(default_factory=list)
    table_descriptions: list[str] = field(default_factory=list)
    parse_status: str = "ok"
    error: str = ""
    raw_upstage: dict[str, Any] = field(default_factory=dict)


def cache_key(dataset: str, corpus_id: str) -> str:
    return f"{dataset}:{corpus_id}"


def _from_dict(payload: dict[str, Any]) -> ParsedDocument:
    return ParsedDocument(
        dataset=str(payload.get("dataset", "")),
        corpus_id=str(payload.get("corpus_id", "")),
        text=str(payload.get("text", "") or ""),
        tables_markdown=[str(x) for x in payload.get("tables_markdown", []) or []],
        table_descriptions=[str(x) for x in payload.get("table_descriptions", []) or []],
        parse_status=str(payload.get("parse_status", "ok") or "ok"),
        error=str(payload.get("error", "") or ""),
        raw_upstage=payload.get("raw_upstage", {}) if isinstance(payload.get("raw_upstage", {}), dict) else {},
    )


def load_parse_cache(path: str | Path) -> dict[str, ParsedDocument]:
    p = Path(path)
    if not p.exists():
        return {}
    loaded: dict[str, ParsedDocument] = {}
    with p.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = _from_dict(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {p}:{line_no}") from exc
            loaded[cache_key(doc.dataset, doc.corpus_id)] = doc
    return loaded


def append_parse_cache(path: str | Path, doc: ParsedDocument) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(doc), ensure_ascii=False) + "\n")


def evidence_text(doc: ParsedDocument) -> str:
    if doc.parse_status != "ok":
        return ""
    sections: list[str] = []
    if doc.text.strip():
        sections.append("[TEXT]\n" + doc.text.strip())
    if doc.tables_markdown:
        tables = "\n\n".join(t.strip() for t in doc.tables_markdown if t.strip())
        if tables:
            sections.append("[TABLES]\n" + tables)
    if doc.table_descriptions:
        descriptions = "\n".join(d.strip() for d in doc.table_descriptions if d.strip())
        if descriptions:
            sections.append("[TABLE DESCRIPTIONS]\n" + descriptions)
    return "\n\n".join(sections)
