"""PDF에서 텍스트와 표를 추출하는 모듈.

스캔본 PDF: pdf2image + Google Cloud Vision OCR
디지털본 PDF: PyMuPDF(fitz) 직접 추출
표 추출: Camelot (lattice 우선, 실패 시 stream)
"""

import json
import os
import re
from pathlib import Path
from typing import Optional

import fitz
from langchain_core.documents import Document
from pdf2image import convert_from_path
from tqdm import tqdm

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def _extract_printed_page_number(text: str) -> Optional[str]:
    """텍스트에서 인쇄된 페이지 번호를 추출한다.

    패턴: VI-281, IV-142, -142-, 단독 숫자 등.
    """
    patterns = [
        r'[IVX]+-\d+',        # VI-281, IV-142
        r'-\s*(\d+)\s*-',     # -142-
        r'^\s*(\d+)\s*$',     # 단독 숫자 (줄 끝)
    ]
    lines = text.strip().split('\n')
    candidates = []
    for line in lines[-5:]:
        for pattern in patterns:
            match = re.search(pattern, line.strip())
            if match:
                candidates.append(match.group(0).strip())
    if not candidates and lines:
        for line in lines[:3]:
            for pattern in patterns:
                match = re.search(pattern, line.strip())
                if match:
                    candidates.append(match.group(0).strip())
    return candidates[-1] if candidates else None


def _ocr_with_vision(image, credentials_path: str) -> str:
    """Google Cloud Vision API로 이미지 OCR을 수행한다."""
    from google.cloud import vision
    import io

    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
    client = vision.ImageAnnotatorClient()

    img_byte_arr = io.BytesIO()
    image.save(img_byte_arr, format='PNG')
    img_bytes = img_byte_arr.getvalue()

    gv_image = vision.Image(content=img_bytes)
    response = client.text_detection(image=gv_image)

    if response.error.message:
        raise Exception(f"Vision API 오류: {response.error.message}")

    texts = response.text_annotations
    if texts:
        return texts[0].description
    return ""


def extract_all(bridge_name: str) -> list[Document]:
    """PDF에서 페이지별 텍스트를 추출하여 LangChain Document 리스트로 반환한다.

    Args:
        bridge_name: 교량 이름 (config.BRIDGES 키).

    Returns:
        LangChain Document 리스트. metadata에 page, document_page, source 포함.
    """
    bridge_info = config.BRIDGES[bridge_name]
    pdf_path = bridge_info["pdf_path"]
    pdf_type = bridge_info["pdf_type"]
    total_pages = bridge_info["pages"]

    cache_dir = Path(config.PROJECT_ROOT) / "data" / bridge_name
    cache_path = cache_dir / "ocr_cache.json"

    # 캐시 확인
    if cache_path.exists():
        print(f"📂 캐시 로드: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            cached_data = json.load(f)
        documents = []
        for item in cached_data:
            doc = Document(
                page_content=item["text"],
                metadata={
                    "page": item["page"],
                    "document_page": item.get("document_page"),
                    "source": pdf_path,
                    "bridge": bridge_name,
                },
            )
            documents.append(doc)
        print(f"📄 캐시에서 {len(documents)}개 문서 로드 완료")
        return documents

    documents = []
    cache_data = []

    if pdf_type == "scanned":
        # pdf2image로 PDF를 이미지로 변환 후 Google Vision OCR
        print(f"📄 스캔본 PDF OCR 시작: {pdf_path}")
        credentials_path = config.GOOGLE_VISION_CREDENTIALS

        images = convert_from_path(pdf_path, dpi=200)
        total = len(images)

        for i, image in enumerate(images):
            page_num = i + 1
            print(f"📄 페이지 {page_num}/{total} 처리 중...")

            try:
                text = _ocr_with_vision(image, credentials_path)
            except Exception as e:
                print(f"  ⚠️ OCR 실패 (페이지 {page_num}): {e}")
                text = ""

            printed_page = _extract_printed_page_number(text)

            doc = Document(
                page_content=text,
                metadata={
                    "page": page_num,
                    "document_page": printed_page,
                    "source": pdf_path,
                    "bridge": bridge_name,
                },
            )
            documents.append(doc)
            cache_data.append({
                "page": page_num,
                "document_page": printed_page,
                "text": text,
            })

    elif pdf_type == "digital":
        # PyMuPDF로 디지털 PDF 텍스트 추출
        print(f"📄 디지털 PDF 텍스트 추출 시작: {pdf_path}")

        pdf_doc = fitz.open(pdf_path)
        total = len(pdf_doc)

        for i in range(total):
            page_num = i + 1
            if page_num % 50 == 0 or page_num == 1:
                print(f"📄 페이지 {page_num}/{total} 처리 중...")

            page = pdf_doc[i]
            text = page.get_text("text")
            printed_page = _extract_printed_page_number(text)

            doc = Document(
                page_content=text,
                metadata={
                    "page": page_num,
                    "document_page": printed_page,
                    "source": pdf_path,
                    "bridge": bridge_name,
                },
            )
            documents.append(doc)
            cache_data.append({
                "page": page_num,
                "document_page": printed_page,
                "text": text,
            })

        pdf_doc.close()

    else:
        raise ValueError(f"지원하지 않는 pdf_type: {pdf_type}")

    # 캐시 저장
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    print(f"💾 캐시 저장: {cache_path}")
    print(f"📄 텍스트 추출 완료: {len(documents)}개 문서")

    return documents


def extract_tables(bridge_name: str) -> list[Document]:
    """PDF에서 표를 추출하여 LangChain Document 리스트로 반환한다.

    Camelot으로 표 추출 (lattice 우선, 실패 시 stream).
    추출된 표를 마크다운 형식으로 변환.

    Args:
        bridge_name: 교량 이름.

    Returns:
        LangChain Document 리스트. metadata에 chunk_type="table_data", table_type 포함.
    """
    bridge_info = config.BRIDGES[bridge_name]
    pdf_path = bridge_info["pdf_path"]

    cache_dir = Path(config.PROJECT_ROOT) / "data" / bridge_name
    cache_path = cache_dir / "table_cache.json"

    # 캐시 확인
    if cache_path.exists():
        print(f"📂 표 캐시 로드: {cache_path}")
        with open(cache_path, "r", encoding="utf-8") as f:
            cached_data = json.load(f)
        documents = []
        for item in cached_data:
            doc = Document(
                page_content=item["text"],
                metadata={
                    "page": item["page"],
                    "chunk_type": "table_data",
                    "table_type": item.get("table_type", "general"),
                    "source": pdf_path,
                    "bridge": bridge_name,
                },
            )
            documents.append(doc)
        print(f"📊 캐시에서 {len(documents)}개 표 로드 완료")
        return documents

    try:
        import camelot
    except ImportError:
        print("⚠️ camelot 패키지를 설치해 주세요: pip install camelot-py[cv]")
        return []

    documents = []
    cache_data = []

    print(f"📊 표 추출 시작: {pdf_path}")

    try:
        # lattice 방식 우선 시도
        tables = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
        if len(tables) == 0:
            raise ValueError("lattice 방식으로 표를 찾을 수 없음")
        print(f"  lattice 방식: {len(tables)}개 표 발견")
    except Exception as e:
        print(f"  ⚠️ lattice 실패 ({e}), stream 방식 시도 중...")
        try:
            tables = camelot.read_pdf(pdf_path, pages="all", flavor="stream")
            print(f"  stream 방식: {len(tables)}개 표 발견")
        except Exception as e2:
            print(f"  ⚠️ 표 추출 실패: {e2}")
            return []

    for i, table in enumerate(tables):
        df = table.df
        page_num = table.page

        # 마크다운 형식으로 변환
        md_lines = []
        headers = df.iloc[0].tolist()
        md_lines.append("| " + " | ".join(str(h) for h in headers) + " |")
        md_lines.append("| " + " | ".join("---" for _ in headers) + " |")
        for _, row in df.iloc[1:].iterrows():
            md_lines.append("| " + " | ".join(str(v) for v in row.tolist()) + " |")
        md_text = "\n".join(md_lines)

        # 표 유형 자동 분류
        table_type = _classify_table_type(md_text)

        doc = Document(
            page_content=md_text,
            metadata={
                "page": page_num,
                "chunk_type": "table_data",
                "table_type": table_type,
                "table_index": i,
                "source": pdf_path,
                "bridge": bridge_name,
            },
        )
        documents.append(doc)
        cache_data.append({
            "page": page_num,
            "table_type": table_type,
            "table_index": i,
            "text": md_text,
        })

    # 캐시 저장
    cache_dir.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, ensure_ascii=False, indent=2)
    print(f"💾 표 캐시 저장: {cache_path}")
    print(f"📊 표 추출 완료: {len(documents)}개 표")

    return documents


def _classify_table_type(text: str) -> str:
    """표 텍스트를 분석하여 유형을 분류한다.

    Returns:
        "damage", "evaluation", "priority", "general" 중 하나.
    """
    damage_keywords = ["손상", "물량", "㎡", "개소", "균열", "박락", "철근노출"]
    evaluation_keywords = ["등급", "평가", "결함도", "상태", "안전성"]
    priority_keywords = ["우선순위", "보수", "보강", "긴급"]

    damage_count = sum(1 for kw in damage_keywords if kw in text)
    eval_count = sum(1 for kw in evaluation_keywords if kw in text)
    priority_count = sum(1 for kw in priority_keywords if kw in text)

    if damage_count >= 2:
        return "damage"
    if eval_count >= 2:
        return "evaluation"
    if priority_count >= 2:
        return "priority"
    return "general"
