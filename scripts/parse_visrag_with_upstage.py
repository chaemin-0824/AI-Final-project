from __future__ import annotations

import argparse
import json
import os
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from datasets import load_dataset
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.parse_cache import ParsedDocument, append_parse_cache, cache_key, load_parse_cache

API_URL = "https://api.upstage.ai/v1/document-ai/document-parse"
MAX_RETRIES = 3
RETRY_WAIT_SEC = 10
RATE_LIMIT_WAIT_SEC = 30


def image_to_png_bytes(image: Image.Image) -> bytes:
    buf = BytesIO()
    image.convert("RGB").save(buf, format="PNG")
    return buf.getvalue()


def extract_upstage_text_tables(payload: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    content = payload.get("content", {}) if isinstance(payload.get("content", {}), dict) else {}
    text_parts: list[str] = []
    table_markdown: list[str] = []
    table_descriptions: list[str] = []

    for key in ("markdown", "text", "html"):
        value = content.get(key)
        if isinstance(value, str) and value.strip():
            text_parts.append(value.strip())

    elements = payload.get("elements", []) if isinstance(payload.get("elements", []), list) else []
    for element in elements:
        if not isinstance(element, dict):
            continue
        category = str(element.get("category", element.get("type", ""))).lower()
        elem_content = element.get("content", {}) if isinstance(element.get("content", {}), dict) else {}
        md = element.get("markdown") or elem_content.get("markdown")
        text = element.get("text") or elem_content.get("text")
        html = element.get("html") or elem_content.get("html")
        if "table" in category:
            if isinstance(md, str) and md.strip():
                table_markdown.append(md.strip())
            elif isinstance(html, str) and html.strip():
                table_markdown.append(html.strip())
            if isinstance(text, str) and text.strip():
                table_descriptions.append(text.strip())
        elif isinstance(text, str) and text.strip():
            text_parts.append(text.strip())

    # Deduplicate while preserving order.
    def unique(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)
        return out

    return "\n\n".join(unique(text_parts)), unique(table_markdown), unique(table_descriptions)


def retry_wait(exc: Exception) -> int:
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        if exc.response.status_code in {429, 499, 500, 502, 503, 504}:
            return RATE_LIMIT_WAIT_SEC
    return RETRY_WAIT_SEC


def call_upstage(api_key: str, image_bytes: bytes, filename: str) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"document": (filename, image_bytes, "image/png")}
    data = {"output_formats": "['html', 'markdown']"}
    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.post(API_URL, headers=headers, files=files, data=data, timeout=120)
            response.raise_for_status()
            return response.json()
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt == MAX_RETRIES:
                break
            wait = retry_wait(exc)
            print(f"Upstage error attempt {attempt}/{MAX_RETRIES}: {type(exc).__name__}: {exc}; retrying in {wait}s", flush=True)
            time.sleep(wait)
    raise RuntimeError(f"Upstage parse failed after {MAX_RETRIES} attempts: {last_error}")


def parse_dataset(args: argparse.Namespace) -> int:
    api_key = os.environ.get("UPSTAGE_API_KEY", "")
    if not args.dry_run and not api_key:
        print("UPSTAGE_API_KEY is required unless --dry-run is set", file=sys.stderr)
        return 1

    dataset_path = args.dataset_path or f"openbmb/VisRAG-Ret-Test-{args.dataset}"
    corpus = load_dataset(dataset_path, name="corpus", split="train", cache_dir=args.cache_dir)
    target_docids: set[str] | None = None
    if args.qrels_for_first_queries is not None:
        queries = load_dataset(dataset_path, name="queries", split="train", cache_dir=args.cache_dir)
        qids = {str(row["query-id"]) for row in queries.select(range(min(args.qrels_for_first_queries, len(queries))))}
        qrels = load_dataset(dataset_path, name="qrels", split="train", cache_dir=args.cache_dir)
        target_docids = {
            str(row["corpus-id"])
            for row in qrels
            if str(row["query-id"]) in qids and float(row.get("score", 1)) > 0
        }
        print(f"target_docids_from_qrels={len(target_docids)}", flush=True)
    output = Path(args.output or ROOT / "data" / "parsed" / f"{args.dataset}_upstage.jsonl")
    existing = load_parse_cache(output)
    processed = 0

    for row in corpus:
        corpus_id = str(row["corpus-id"])
        if target_docids is not None and corpus_id not in target_docids:
            continue
        key = cache_key(args.dataset, corpus_id)
        if key in existing and not args.force:
            continue
        print(f"{args.dataset}:{corpus_id}", flush=True)
        if args.dry_run:
            processed += 1
            if args.limit is not None and processed >= args.limit:
                break
            continue
        try:
            image_bytes = image_to_png_bytes(row["image"])
            raw = call_upstage(api_key, image_bytes, f"{args.dataset}_{corpus_id}.png")
            text, tables, descriptions = extract_upstage_text_tables(raw)
            doc = ParsedDocument(
                dataset=args.dataset,
                corpus_id=corpus_id,
                text=text,
                tables_markdown=tables,
                table_descriptions=descriptions,
                parse_status="ok",
                raw_upstage=raw,
            )
        except Exception as exc:  # noqa: BLE001
            doc = ParsedDocument(
                dataset=args.dataset,
                corpus_id=corpus_id,
                parse_status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        append_parse_cache(output, doc)
        existing[key] = doc
        processed += 1
        if args.limit is not None and processed >= args.limit:
            break
        if args.delay_sec:
            time.sleep(args.delay_sec)

    print(f"processed={processed} output={output}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse VisRAG HF corpus images with Upstage Document Parse and cache JSONL evidence.")
    parser.add_argument("--dataset", required=True, choices=["ArxivQA", "ChartQA", "MP-DocVQA", "InfoVQA", "PlotQA", "SlideVQA"])
    parser.add_argument("--dataset-path", default=None)
    parser.add_argument("--cache-dir", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--qrels-for-first-queries", type=int, default=None, help="Parse only gold corpus pages for the first N evaluation queries.")
    parser.add_argument("--output", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay-sec", type=float, default=0.0)
    args = parser.parse_args()
    return parse_dataset(args)


if __name__ == "__main__":
    raise SystemExit(main())
