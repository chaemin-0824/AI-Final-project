"""Smart chunking over Upstage parse cache."""

from __future__ import annotations

import re
from typing import Iterable

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


TEXT_CATEGORIES = {"paragraph", "list"}
SKIP_CATEGORIES = {"header", "footer", "figure", "image"}

CHAPTER_RE = re.compile(r"제\s*(\d+)\s*장")
SECTION_RE = re.compile(r"(?<!\d)(\d+(?:\.\d+)+)")
TABLE_ID_RE = re.compile(r"표\s*([0-9]+(?:\.[0-9]+)+)")


def _element_text(element: dict) -> str:
    content = element.get("content") or {}
    text = content.get("markdown") or content.get("text") or content.get("html") or ""
    return str(text).strip()


def _strip_heading_marks(text: str) -> str:
    return re.sub(r"^\s*#+\s*", "", text).strip()


def _detect_structure(text: str, current_chapter: int | None, current_section: str | None) -> tuple[int | None, str | None]:
    cleaned = _strip_heading_marks(text)
    chapter = current_chapter
    section = current_section

    chapter_match = CHAPTER_RE.search(cleaned)
    if chapter_match:
        parsed_chapter = int(chapter_match.group(1))
        if 1 <= parsed_chapter <= 9:
            chapter = parsed_chapter
            section = None

    section_match = SECTION_RE.search(cleaned)
    if section_match:
        parsed_section = section_match.group(1)
        parsed_chapter = int(parsed_section.split(".")[0])
        if 1 <= parsed_chapter <= 9:
            section = parsed_section
            chapter = parsed_chapter

    return chapter, section


def _extract_table_id(*texts: str) -> str | None:
    for text in texts:
        if not text:
            continue
        match = TABLE_ID_RE.search(_strip_heading_marks(text))
        if match:
            return f"표 {match.group(1)}"
    return None


def _build_prefix(page: int, chapter: int | None, section: str | None, element_type: str, table_id: str | None = None) -> str:
    parts = [f"[페이지 {page}]"]
    if chapter is not None:
        parts.append(f"[제{chapter}장]")
    if section:
        parts.append(f"[절 {section}]")
    parts.append(f"[유형 {element_type}]")
    if table_id:
        parts.append(f"[{table_id}]")
    return " ".join(parts)


def _flush_text_buffer(
    docs: list[Document],
    splitter: RecursiveCharacterTextSplitter,
    page: int,
    chapter: int | None,
    section: str | None,
    text_buffer: list[str],
) -> None:
    joined = "\n\n".join(part for part in text_buffer if part).strip()
    if not joined:
        return

    seeded = f"{_build_prefix(page, chapter, section, 'text')}\n{joined}"
    seed_doc = Document(
        page_content=seeded,
        metadata={
            "page": page,
            "chapter": f"제{chapter}장" if chapter is not None else None,
            "chapter_no": chapter,
            "section": section,
            "element_type": "text",
            "table_id": None,
        },
    )
    docs.extend(splitter.split_documents([seed_doc]))


def build_smart_chunks(page_records: Iterable[dict]) -> list[Document]:
    """Build smart chunks from Upstage page records."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=3000,
        chunk_overlap=1000,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    docs: list[Document] = []
    current_chapter: int | None = None
    current_section: str | None = None

    for page_record in page_records:
        page = page_record["page"]
        elements = page_record.get("elements", [])
        text_buffer: list[str] = []
        consumed_text_indices: set[int] = set()

        for idx, element in enumerate(elements):
            category = str(element.get("category") or "").lower()
            text = _element_text(element)

            if not text or category in SKIP_CATEGORIES:
                continue

            if category == "header":
                current_chapter, current_section = _detect_structure(text, current_chapter, current_section)
                continue

            if category.startswith("heading"):
                _flush_text_buffer(docs, splitter, page, current_chapter, current_section, text_buffer)
                text_buffer = []
                current_chapter, current_section = _detect_structure(text, current_chapter, current_section)
                continue

            if category == "table":
                _flush_text_buffer(docs, splitter, page, current_chapter, current_section, text_buffer)
                text_buffer = []

                prev_caption = ""
                if idx > 0 and str(elements[idx - 1].get("category") or "").lower() == "caption":
                    prev_caption = _element_text(elements[idx - 1])

                next_paragraph = ""
                if idx + 1 < len(elements):
                    next_category = str(elements[idx + 1].get("category") or "").lower()
                    if next_category in TEXT_CATEGORIES:
                        next_paragraph = _element_text(elements[idx + 1])
                        consumed_text_indices.add(idx + 1)

                table_id = _extract_table_id(prev_caption, text)
                chunk_body = "\n\n".join(part for part in [prev_caption, text, next_paragraph] if part).strip()
                seeded = f"{_build_prefix(page, current_chapter, current_section, 'table', table_id)}\n{chunk_body}"
                docs.append(
                    Document(
                        page_content=seeded,
                        metadata={
                            "page": page,
                            "chapter": f"제{current_chapter}장" if current_chapter is not None else None,
                            "chapter_no": current_chapter,
                            "section": current_section,
                            "element_type": "table",
                            "table_id": table_id,
                        },
                    )
                )
                continue

            if category in TEXT_CATEGORIES and idx not in consumed_text_indices:
                text_buffer.append(text)

        _flush_text_buffer(docs, splitter, page, current_chapter, current_section, text_buffer)

    return docs
