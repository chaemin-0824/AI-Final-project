"""Stage 7: 검색된 페이지 이미지를 Gemini 3.1 Pro에 전달하여 답변 생성."""

from __future__ import annotations

import base64
import io
import sys
import time
from pathlib import Path

import fitz  # PyMuPDF
import google.generativeai as genai
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent.parent))
import config

GEMINI_MODEL = "models/gemini-3.1-pro-preview"

# Gemini 이미지 크기 제한: 개별 이미지 ~4MB, 총 요청 ~20MB
# 200 DPI 기준 A4 ≈ 1654×2339 ≈ 1~2MB (JPEG 75%)
# 15페이지 × 2MB = ~30MB → 150 DPI로 낮추거나 JPEG 압축
MAX_IMAGE_PAGES = 15
TARGET_DPI = 150  # 200 DPI에서 크기 초과 시 150으로 조정
JPEG_QUALITY = 80
MAX_IMAGE_BYTES = 3_500_000  # 3.5MB per image safety limit

VISUAL_PROMPT_TEMPLATE = """당신은 교량 정밀안전진단 보고서를 분석하는 전문가입니다.

위 이미지들은 보고서에서 질문과 관련된 페이지의 원본 스캔입니다.
아래 텍스트는 같은 페이지에서 OCR로 추출한 텍스트와 표 마크다운입니다.

[지시사항]
1. 이미지와 텍스트를 함께 참조하세요. 이미지에서 표의 셀 값을 직접 읽고,
   텍스트에서 맥락과 전후 관계를 파악하세요.
2. 수치를 인용할 때는 해당 표 번호와 페이지를 명시하세요.
3. "정보 없음"이라고 답하기 전에 이미지의 모든 표와 텍스트를 재확인하세요.
4. 질문에서 요구한 정보에만 답변하세요.

{text_context}

[질문]
{question}
"""


def render_pdf_pages(
    pdf_path: str | Path,
    pages: list[int],
    dpi: int = TARGET_DPI,
) -> list[dict]:
    """PDF 페이지를 JPEG 이미지로 렌더링한다.

    Args:
        pdf_path: PDF 파일 경로.
        pages: 1-based 페이지 번호 리스트.
        dpi: 렌더링 해상도.

    Returns:
        [{"page": int, "image_bytes": bytes, "mime_type": str}, ...]
    """
    doc = fitz.open(str(pdf_path))
    results = []
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    for page_num in pages[:MAX_IMAGE_PAGES]:
        page_idx = page_num - 1  # fitz는 0-based
        if page_idx < 0 or page_idx >= len(doc):
            continue

        page = doc[page_idx]
        pix = page.get_pixmap(matrix=matrix)

        # PIL Image로 변환 후 JPEG 압축
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=JPEG_QUALITY)
        img_bytes = buf.getvalue()

        # 크기 초과 시 품질 낮춰 재압축
        if len(img_bytes) > MAX_IMAGE_BYTES:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=60)
            img_bytes = buf.getvalue()

        # 그래도 초과면 해상도 낮춤
        if len(img_bytes) > MAX_IMAGE_BYTES:
            lower_zoom = 100 / 72.0
            pix2 = page.get_pixmap(matrix=fitz.Matrix(lower_zoom, lower_zoom))
            img2 = Image.frombytes("RGB", [pix2.width, pix2.height], pix2.samples)
            buf = io.BytesIO()
            img2.save(buf, format="JPEG", quality=70)
            img_bytes = buf.getvalue()

        results.append({
            "page": page_num,
            "image_bytes": img_bytes,
            "mime_type": "image/jpeg",
            "size_kb": len(img_bytes) / 1024,
        })

    doc.close()
    return results


def generate_visual_answer(
    question: str,
    page_images: list[dict],
    text_context: str = "",
) -> dict:
    """이미지 + 텍스트 context + 질문을 Gemini 3.1 Pro에 전달하여 답변을 생성한다.

    Args:
        question: 질문 텍스트.
        page_images: render_pdf_pages()의 반환값.
        text_context: v10r 검색에서 추출한 마크다운 텍스트 context.

    Returns:
        {"answer": str, "elapsed_sec": float, "input_tokens": int, "output_tokens": int}
    """
    genai.configure(api_key=config.GOOGLE_API_KEY)
    model = genai.GenerativeModel(GEMINI_MODEL)

    # Content 구성: [이미지1, 이미지2, ..., 텍스트 프롬프트]
    content_parts = []
    for img_info in page_images:
        b64 = base64.b64encode(img_info["image_bytes"]).decode("utf-8")
        content_parts.append({
            "inline_data": {
                "mime_type": img_info["mime_type"],
                "data": b64,
            }
        })

    # 텍스트 context 포맷팅
    if text_context:
        text_section = f"[OCR 추출 텍스트]\n{text_context}\n[OCR 추출 텍스트 끝]"
    else:
        text_section = ""

    prompt_text = VISUAL_PROMPT_TEMPLATE.format(
        question=question,
        text_context=text_section,
    )
    content_parts.append(prompt_text)

    t0 = time.time()
    response = model.generate_content(
        content_parts,
        generation_config=genai.GenerationConfig(
            temperature=0,
            max_output_tokens=4096,
        ),
    )
    elapsed = time.time() - t0

    answer = response.text if response.text else ""
    usage = getattr(response, "usage_metadata", None)
    input_tokens = getattr(usage, "prompt_token_count", 0) if usage else 0
    output_tokens = getattr(usage, "candidates_token_count", 0) if usage else 0

    return {
        "answer": answer,
        "elapsed_sec": round(elapsed, 2),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
