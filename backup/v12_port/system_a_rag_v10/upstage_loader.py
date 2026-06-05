"""Upstage parse cache loader for RAG v10."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def load_upstage_parse_pages(bridge_name: str) -> tuple[list[dict], list[int]]:
    """Load successful Upstage parse pages and unresolved failed page ids."""
    cache_path = Path(config.PROJECT_ROOT) / "data" / bridge_name / "upstage_parse_cache.json"
    if not cache_path.exists():
        raise FileNotFoundError(f"Upstage cache not found: {cache_path}")

    data = json.loads(cache_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        pages = [item for item in data if isinstance(item, dict) and isinstance(item.get("page"), int)]
        failed_pages: list[int] = []
    elif isinstance(data, dict):
        pages = [
            item for item in data.get("pages", [])
            if isinstance(item, dict) and isinstance(item.get("page"), int)
        ]
        failed_pages = [
            item["page"] for item in data.get("failed_pages", [])
            if isinstance(item, dict) and isinstance(item.get("page"), int)
        ]
    else:
        raise RuntimeError(f"Unsupported Upstage cache format: {cache_path}")

    pages.sort(key=lambda item: item["page"])
    return pages, failed_pages
