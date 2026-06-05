"""Local configuration for the v12 port inside AI algorithm study.

The port keeps code local, but reuses the existing bridge data by default so we do
not duplicate large PDFs/caches. Override paths with environment variables when
running an isolated experiment.
"""
from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_PROJECT_ROOT = Path(os.getenv("V12_SOURCE_PROJECT_ROOT", "/home/chaemin/projects/paper_visual_rag"))
DATA_ROOT = Path(os.getenv("V12_DATA_ROOT", str(SOURCE_PROJECT_ROOT / "data")))
RESULTS_DIR = str(Path(os.getenv("V12_RESULTS_DIR", str(PROJECT_ROOT / "results" / "v12_bridge"))))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
GOOGLE_VISION_CREDENTIALS = os.getenv(
    "GOOGLE_VISION_CREDENTIALS",
    str(SOURCE_PROJECT_ROOT / "google_vision_credentials.json"),
)

BRIDGES = {
    "대안천교": {
        "pdf_path": str(DATA_ROOT / "대안천교" / "대안천교_정밀안전진단_보고서.pdf"),
        "pdf_type": "scanned",
        "pages": 314,
        "description": "PSC거더교, B등급, 스캔본 PDF",
    },
    "송정교": {
        "pdf_path": str(DATA_ROOT / "송정교" / "4_송정교_정밀안전진단_보고서.pdf"),
        "pdf_type": "digital",
        "pages": 354,
        "description": "디지털본 PDF",
    },
    "사능철도육교": {
        "pdf_path": str(DATA_ROOT / "사능철도육교" / "3.본보고서.pdf"),
        "pdf_type": "digital",
        "pages": None,
        "description": "일반화 검증용 교량 보고서",
    },
}

FMS_EXCEL_PATH = str(DATA_ROOT / "04_FMS_점검진단실적_20251127.xlsx")

RAG_LLM_MODEL = os.getenv("V12_RAG_LLM_MODEL", "gpt-5.4")
RAG_EMBEDDING_MODEL = os.getenv("V12_RAG_EMBEDDING_MODEL", "text-embedding-3-small")
GEMINI_MODEL = os.getenv("V12_GEMINI_MODEL", "models/gemini-3.1-pro-preview")
VLM_TABLE_MODEL = os.getenv("V12_VLM_TABLE_MODEL", "models/gemini-3.1-flash-lite-preview")
JUDGE_MODEL = os.getenv("V12_JUDGE_MODEL", "models/gemini-3.1-pro-preview")
CACHE_TTL_MINUTES = int(os.getenv("V12_CACHE_TTL_MINUTES", "120"))

MODEL_COSTS = {
    "gpt-5.4": {"input": 2.50, "output": 15.00},
    "gpt-5.4-mini": {"input": 1.25, "output": 5.00},
    "gemini-3.1-pro-preview": {"input": 2.00, "output": 12.00},
}
