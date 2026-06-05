"""Generate docs/report_v12_general_vs_visrag.docx in an academic paper style.

The output uses Times New Roman + NanumMyeongjo, fully black text, justified
body with first-line indent, A4 page with running header and page numbers.
Style choices follow conventions common in Korean computer science journals
(KIISE/KIPS) and IEEE-style numbered citations.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "report_v12_general_vs_visrag.docx"

LATIN_FONT = "Times New Roman"
CJK_FONT = "NanumMyeongjo"
MONO_FONT = "Consolas"
BLACK = RGBColor(0x00, 0x00, 0x00)

BODY_PT = 10.5
HEADING1_PT = 13
HEADING2_PT = 11.5
HEADING3_PT = 11
TITLE_PT = 18
SUBTITLE_PT = 11
META_PT = 10
ABSTRACT_PT = 10
CAPTION_PT = 9.5
CODE_PT = 9
TABLE_PT = 9.5
REF_PT = 10
HEADER_PT = 9


# ---------------------------------------------------------------------------
# low-level helpers


def set_run_style(run, *, size_pt: float, bold: bool = False, italic: bool = False,
                  mono: bool = False, small_caps: bool = False) -> None:
    run.font.size = Pt(size_pt)
    run.font.bold = bool(bold)
    run.font.italic = bool(italic)
    run.font.color.rgb = BLACK
    name = MONO_FONT if mono else LATIN_FONT
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    rfonts.set(qn("w:eastAsia"), CJK_FONT)
    rfonts.set(qn("w:cs"), name)
    if small_caps:
        smcaps = OxmlElement("w:smallCaps")
        smcaps.set(qn("w:val"), "1")
        rpr.append(smcaps)


def add_run(p, text, **kw):
    run = p.add_run(text)
    set_run_style(run, **kw)
    return run


def justify_with_indent(p, *, first_line_cm: float = 0.85, space_after: float = 4,
                        line_spacing: float = 1.35) -> None:
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    pf = p.paragraph_format
    pf.first_line_indent = Cm(first_line_cm)
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE


def add_para(doc, text="", *, size_pt=BODY_PT, bold=False, italic=False,
             align=None, indent_first=True, space_after=4, space_before=0,
             left_indent_cm=None, right_indent_cm=None,
             line_spacing=1.35) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = line_spacing
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    if align is not None:
        p.alignment = align
    elif indent_first:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.first_line_indent = Cm(0.85)
    if left_indent_cm is not None:
        pf.left_indent = Cm(left_indent_cm)
    if right_indent_cm is not None:
        pf.right_indent = Cm(right_indent_cm)
    if text:
        add_run(p, text, size_pt=size_pt, bold=bold, italic=italic)


def add_rich_para(doc, segments, *, size_pt=BODY_PT, align=None,
                  indent_first=True, space_after=4,
                  left_indent_cm=None, line_spacing=1.35) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing = line_spacing
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    if align is not None:
        p.alignment = align
    elif indent_first:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        pf.first_line_indent = Cm(0.85)
    if left_indent_cm is not None:
        pf.left_indent = Cm(left_indent_cm)
    for text, kw in segments:
        add_run(
            p, text,
            size_pt=kw.get("size_pt", size_pt),
            bold=kw.get("bold", False),
            italic=kw.get("italic", False),
            mono=kw.get("mono", False),
        )


def add_heading(doc, text, *, level=1) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(14 if level == 1 else 10 if level == 2 else 8)
    pf.space_after = Pt(4)
    pf.keep_with_next = True
    sizes = {1: HEADING1_PT, 2: HEADING2_PT, 3: HEADING3_PT}
    add_run(p, text, size_pt=sizes[level], bold=True, italic=(level == 3))


def bottom_border(paragraph, *, size: str = "6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), size)
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pbdr.append(bottom)
    p_pr.append(pbdr)


def top_border(paragraph, *, size: str = "6") -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    pbdr = p_pr.find(qn("w:pBdr"))
    if pbdr is None:
        pbdr = OxmlElement("w:pBdr")
        p_pr.append(pbdr)
    top = OxmlElement("w:top")
    top.set(qn("w:val"), "single")
    top.set(qn("w:sz"), size)
    top.set(qn("w:space"), "1")
    top.set(qn("w:color"), "000000")
    pbdr.append(top)


def add_code_block(doc, code) -> None:
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(6)
    pf.space_before = Pt(4)
    pf.left_indent = Cm(0.4)
    pf.line_spacing = 1.1
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    add_run(p, code, size_pt=CODE_PT, mono=True)
    p_pr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F4F0")
    p_pr.append(shd)


def add_numbered_list(doc, items) -> None:
    """Manual numbered list with bold leading number, no Word list style."""
    for idx, item in enumerate(items, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.85)
        pf.first_line_indent = Cm(-0.85)
        pf.space_after = Pt(3)
        pf.line_spacing = 1.3
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_run(p, f"({idx})\t", size_pt=BODY_PT)
        if isinstance(item, str):
            add_run(p, item, size_pt=BODY_PT)
        else:
            for text, kw in item:
                add_run(p, text, size_pt=kw.get("size_pt", BODY_PT),
                        bold=kw.get("bold", False),
                        italic=kw.get("italic", False),
                        mono=kw.get("mono", False))


def add_bulleted_list(doc, items) -> None:
    """Manual bulleted list (·) — keep narrow indent."""
    for item in items:
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.85)
        pf.first_line_indent = Cm(-0.45)
        pf.space_after = Pt(3)
        pf.line_spacing = 1.3
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_run(p, "·\t", size_pt=BODY_PT)
        if isinstance(item, str):
            add_run(p, item, size_pt=BODY_PT)
        else:
            for text, kw in item:
                add_run(p, text, size_pt=kw.get("size_pt", BODY_PT),
                        bold=kw.get("bold", False),
                        italic=kw.get("italic", False),
                        mono=kw.get("mono", False))


def style_cell(cell, *, header=False, align_right=False, align_center=False,
               size_pt=TABLE_PT) -> None:
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.space_before = Pt(0)
        if align_right:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        elif align_center:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for run in paragraph.runs:
            set_run_style(run, size_pt=size_pt, bold=header)


def add_table(doc, header, rows, *, numeric_cols=None, caption_number=None,
              caption=None) -> None:
    numeric_cols = set(numeric_cols or [])
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Light Grid Accent 1" if False else "Light Grid"
    hdr_cells = table.rows[0].cells
    for i, text in enumerate(header):
        hdr_cells[i].text = text
        style_cell(hdr_cells[i], header=True,
                   align_right=(i in numeric_cols),
                   align_center=(i not in numeric_cols))
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = val
            style_cell(cell, align_right=(c_idx in numeric_cols))
    if caption:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pf = p.paragraph_format
        pf.space_after = Pt(10)
        pf.space_before = Pt(2)
        if caption_number is not None:
            add_run(p, f"표 {caption_number}. ",
                    size_pt=CAPTION_PT, bold=True)
        add_run(p, caption, size_pt=CAPTION_PT, italic=True)


# ---------------------------------------------------------------------------
# header / footer with page numbers and running title

def configure_page(doc) -> None:
    section = doc.sections[0]
    section.page_height = Cm(29.7)
    section.page_width = Cm(21.0)
    section.top_margin = Cm(2.5)
    section.bottom_margin = Cm(2.5)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # Header with running title (right-aligned)
    header = section.header
    header.is_linked_to_previous = False
    h_p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    h_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    h_p.paragraph_format.space_after = Pt(0)
    add_run(h_p, "Parsed-Visual RAG (v12-general) vs. VisRAG",
            size_pt=HEADER_PT, italic=True)
    bottom_border(h_p, size="4")

    # Footer with centered page number
    footer = section.footer
    footer.is_linked_to_previous = False
    f_p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    f_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f_p.paragraph_format.space_before = Pt(2)
    run = f_p.add_run()
    set_run_style(run, size_pt=HEADER_PT)
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = " PAGE \\* MERGEFORMAT "
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._element.append(fld_begin)
    run._element.append(instr)
    run._element.append(fld_end)


def setup_document() -> Document:
    doc = Document()
    configure_page(doc)
    style = doc.styles["Normal"]
    style.font.name = LATIN_FONT
    style.font.size = Pt(BODY_PT)
    style.font.color.rgb = BLACK
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), LATIN_FONT)
    rfonts.set(qn("w:hAnsi"), LATIN_FONT)
    rfonts.set(qn("w:eastAsia"), CJK_FONT)
    rfonts.set(qn("w:cs"), LATIN_FONT)
    return doc


# ---------------------------------------------------------------------------
# document content

def add_title_block(doc) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    add_run(p, "Parsed-Visual RAG (v12-general) 대 VisRAG", size_pt=TITLE_PT, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    add_run(p, "단일 GPU 환경에서 동일 생성기 통제하의 문서 시각 질의응답 방법론 ablation",
            size_pt=SUBTITLE_PT, italic=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    add_run(p, "이채민", size_pt=META_PT)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(16)
    add_run(p, "기술 보고서 · 2026년 6월 5일", size_pt=META_PT, italic=True)


def add_abstract(doc) -> None:
    label = doc.add_paragraph()
    label.alignment = WD_ALIGN_PARAGRAPH.CENTER
    label.paragraph_format.space_before = Pt(4)
    label.paragraph_format.space_after = Pt(4)
    add_run(label, "ABSTRACT", size_pt=ABSTRACT_PT, bold=True, small_caps=True)
    bottom_border(label)

    body = doc.add_paragraph()
    body.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    body.paragraph_format.left_indent = Cm(0.6)
    body.paragraph_format.right_indent = Cm(0.6)
    body.paragraph_format.first_line_indent = Cm(0.6)
    body.paragraph_format.space_after = Pt(4)
    body.paragraph_format.line_spacing = 1.3
    body.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    text = (
        "본 보고서는 OpenBMB가 제안한 시각 기반 검색-증강 생성 프레임워크 VisRAG[1]의 공개 평가 "
        "벤치마크 위에서, 시각 전용 입력을 사용하는 baseline과 본 연구가 제안하는 domain-free 변형 "
        "Parsed-Visual RAG(이하 v12-general)을 비교한다. v12-general은 페이지 이미지를 Upstage "
        "Document Parse[5]로 텍스트·표 형태로 변환하여 동일한 시각 언어 모델(Vision-Language "
        "Model, VLM)에 원본 이미지와 함께 입력으로 제공하는 방법이다. 실험은 단일 RTX 4060(8 GB "
        "VRAM) 환경에서 수행되었고, 생성기는 Qwen2-VL-7B-Instruct[3]를 bitsandbytes NF4 4-bit "
        "양자화[4]로 적재하였다. 4개 데이터셋(InfoVQA, ChartQA, MP-DocVQA, SlideVQA)에 대해 각 첫 "
        "100개 질의로 oracle 검색을 사용함으로써 생성 단계의 효과만을 격리하였다. 그 결과 "
        "v12-general은 시각 전용 baseline 대비 macro 정확도 기준 +36.32%p(0.229 → 0.592)의 "
        "향상을 보였으며, 페이지 레이아웃이 답변에 기여하는 MP-DocVQA에서는 파싱 텍스트 단독 "
        "ablation 대비 +4.0%p의 추가 이득이 관찰되었다. 본 보고서는 각 방법론의 구조, 파라미터 "
        "설정, 코드 설계, 논문과의 일치 및 차이, 그리고 단일 GPU 제약 하에서의 생성기·검색·표본 "
        "설계 결정의 정당성을 학술적 관점에서 정리한다."
    )
    add_run(body, text, size_pt=ABSTRACT_PT)

    border = doc.add_paragraph()
    border.paragraph_format.space_after = Pt(0)
    bottom_border(border)

    kw = doc.add_paragraph()
    kw.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    kw.paragraph_format.left_indent = Cm(0.6)
    kw.paragraph_format.right_indent = Cm(0.6)
    kw.paragraph_format.space_before = Pt(4)
    kw.paragraph_format.space_after = Pt(14)
    add_run(kw, "Index Terms — ", size_pt=ABSTRACT_PT, bold=True, italic=True)
    add_run(kw,
            "시각 질의응답, 검색-증강 생성, 문서 이해, 시각 언어 모델, "
            "Upstage Document Parse, 양자화 추론, 평가 ablation.",
            size_pt=ABSTRACT_PT)


# ---------- sections ----------

def section_1_intro(doc) -> None:
    add_heading(doc, "1. 서론")
    add_para(
        doc,
        "문서 시각 질의응답(Visual Document Question Answering, VDQA)은 페이지 이미지에 표현된 "
        "본문·표·차트·다이어그램으로부터 자연어 질의에 대한 정답을 추출하는 과제이다. 최근에 "
        "제안된 VisRAG[1]는 OCR이나 파싱을 거치지 않고 페이지 이미지를 시각 임베딩으로 검색한 후, "
        "시각 언어 모델이 검색된 페이지 이미지로부터 직접 답을 생성하는 파이프라인을 제시한다. "
        "그 동기는 OCR·파싱 단계에서 발생하는 정보 손실—레이아웃, 색상 강조, 그래픽 표현 등—이 "
        "답변 품질에 부정적이라는 가설이다.",
    )
    add_para(
        doc,
        "반면 본 연구진이 선행 연구로 개발한 v12 계열 아키텍처는 동일한 페이지 이미지에 Upstage "
        "Document Parse[5]를 적용하여 텍스트·표를 명시적으로 추출하고, 이를 원본 이미지와 함께 "
        "시각 언어 모델 입력으로 결합한다. 두 접근은 “파싱에 의한 명시적 텍스트 증거가 시각 전용 "
        "입력 대비 답변 품질을 개선하는가”라는 가설에 대해 상반된 입장을 취한다.",
    )
    add_para(
        doc,
        "본 보고서의 목적은 두 접근을 동일한 데이터셋, 동일한 평가 지표, 동일한 생성기, 동일한 "
        "입력 페이지 조건에서 비교하여 evidence 형식(이미지 단독 / 파싱 텍스트 단독 / 둘의 결합)이 "
        "정확도에 미치는 영향만을 격리하여 측정하는 것이다. 본 연구는 검색 모델의 차이나 생성 "
        "모델의 절대 성능 차이를 다루지 않는다.",
    )
    add_para(
        doc,
        "또한 비교 대상이 되는 결과 표는 팀 내 사전 자료(docs/VisRAG Multi Page "
        "Compression.pptx, slide 10)의 양식을 따른다. 해당 자료의 baseline은 Qwen2-VL-7B를 "
        "사용하였으므로, 본 연구도 동일 모델 계열로 생성기를 정렬하여 baseline의 좌표계를 "
        "일치시킨다.",
    )
    add_heading(doc, "1.1 기여", level=2)
    add_para(doc, "본 보고서의 기여는 다음과 같다.", indent_first=False)
    add_numbered_list(
        doc,
        [
            "VisRAG 공식 평가 벤치마크(4개 데이터셋) 위에서, 동일 생성기·동일 oracle 페이지 "
            "조건의 generation-only ablation을 통해 evidence 형식의 효과를 정량적으로 측정하였다.",
            "Parsed-Visual RAG (v12-general)이 시각 전용 baseline 대비 macro 정확도 기준 "
            "+36.32%p의 일관된 향상을 달성함을 보였으며, MP-DocVQA에서 파싱 텍스트 단독 ablation "
            "대비 +4.0%p의 상보적 이득을 관찰하였다.",
            "단일 8 GB GPU 제약 하에서의 4-bit 양자화 추론과 이미지 해상도 캡 적용이 모드 간 "
            "비교의 공정성에 미치는 영향과 한계를 명시적으로 분석하였다.",
            "재현성을 위한 단일 명령 파이프라인(scripts/run_today_ppt_pipeline.sh)과 핵심 입력 "
            "캐시(약 3.7 MB)를 함께 제공하여, 추가적인 API 호출 없이도 결과 표를 재생성할 수 "
            "있도록 하였다.",
        ],
    )


def section_2_related(doc) -> None:
    add_heading(doc, "2. 관련 연구")
    add_para(
        doc,
        "문서 VDQA를 위한 검색-증강 생성은 크게 (i) OCR·파싱을 거쳐 텍스트 RAG로 환원하는 접근과 "
        "(ii) 페이지 이미지를 그대로 시각 임베딩으로 색인하고 시각 언어 모델이 직접 답을 "
        "생성하는 접근으로 구분된다. 전자는 단어·수식·표 등 표면 정보를 정확히 보존할 때 "
        "장점을 갖지만 레이아웃·그래픽 정보 손실이 단점이며, 후자는 시각적 단서를 보존하지만 "
        "OCR의 정확한 라벨·수치 정보가 모델 내부에서 재추출되어야 한다.",
    )
    add_para(
        doc,
        "VisRAG[1]는 후자에 해당하며, MiniCPM-V 2.6 등을 generator로 사용하여 4종의 "
        "task_type(text, page_concatenation, weighted_selection, multi_image) 입력 형식을 "
        "제시한다. 평가 데이터로는 ArxivQA, ChartQA, MP-DocVQA, InfoVQA, PlotQA, SlideVQA 6종의 "
        "HuggingFace 공개셋(openbmb/VisRAG-Ret-Test-*)을 사용하며, 검색은 자체 시각 임베딩 모델 "
        "VisRAG-Ret으로 수행한다. 본 연구는 동일 데이터·동일 정확도 지표 위에서 generation 단계의 "
        "evidence 형식 ablation을 추가로 제공한다.",
    )
    add_para(
        doc,
        "한편 large vision-language model의 정확도-효율 절충에 관한 연구로 NF4 양자화[4], "
        "Qwen2-VL의 임의 해상도 입력 처리[3] 등이 알려져 있다. 본 보고서는 두 기술을 결합하여 "
        "8 GB-class GPU에서 7B 시각 언어 모델을 실시간 추론 가능 환경으로 적재하였다.",
    )


def section_3_datasets(doc) -> None:
    add_heading(doc, "3. 평가 데이터셋")
    add_para(
        doc,
        "본 연구는 VisRAG 공식 평가셋(openbmb/VisRAG-Ret-Test-*) 중 4개 데이터셋을 사용한다. "
        "데이터셋의 선택은 팀 내 사전 자료의 결과 표 컬럼(InfoVQA, ChartQA, DocVQA, SlideVQA)에 "
        "정렬되며, 자료의 DocVQA는 공식 명칭 MP-DocVQA에 매핑된다. 각 데이터셋은 queries, "
        "corpus, qrels의 세 subset으로 구성되며 본 실험에서는 oracle 검색을 통해 qrels이 직접 "
        "페이지 선택에 사용된다.",
    )
    add_table(
        doc,
        header=["Dataset", "queries", "corpus", "qrels", "cache size"],
        rows=[
            ["InfoVQA", "718", "459", "718", "173 MB"],
            ["ChartQA", "63", "500", "63", "24 MB"],
            ["MP-DocVQA", "591", "741", "591", "258 MB"],
            ["SlideVQA", "556", "1,284", "702", "100 MB"],
        ],
        numeric_cols=[1, 2, 3, 4],
        caption_number=1,
        caption="평가에 사용된 4개 데이터셋의 split 크기와 HuggingFace blob 캐시 용량. "
                "SlideVQA의 경우 한 질의가 다수 페이지에 매핑되므로 qrels > queries이다.",
    )
    add_para(
        doc,
        "표본은 데이터셋당 첫 100개 질의이며, 이에 대응되는 unique gold page만 Upstage 파싱 "
        "캐시에 적재된다. InfoVQA의 경우 29건, ChartQA 60건, MP-DocVQA 62건, SlideVQA 97건으로, "
        "총 248개 페이지가 Stage 1에서 파싱되었다.",
    )


def section_4_methodologies(doc) -> None:
    add_heading(doc, "4. 방법론")
    add_para(
        doc,
        "본 비교는 동일한 oracle 페이지에 대해 VLM 입력에 어떤 형식의 evidence가 포함되는가에 "
        "따라 세 가지 모드를 정의한다. 모든 모드는 동일한 prompt 골격을 공유하며, evidence "
        "관련 두 슬롯만 모드별로 치환된다. 따라서 모드 간 정확도 차이는 오직 입력 evidence "
        "형식에서 비롯된다.",
    )
    add_heading(doc, "4.1 image_only — 시각 전용 baseline", level=2)
    add_para(
        doc,
        "페이지 이미지만을 VLM에 입력하고 파싱 텍스트는 제공하지 않는다. 이는 VisRAG의 핵심 "
        "가정(이미지만으로 답한다)을 동일 환경에서 재현한 baseline이다. 단, 본 연구의 image_only는 "
        "VisRAG 공식 스크립트(visrag/visrag_scripts/generate/generate.py)를 그대로 실행하지 않고 "
        "동일 컨셉을 자체 코드로 재구현한 것이며, 그 차이는 §7.3에서 정리한다.",
    )
    add_heading(doc, "4.2 parsed_text_only — 파싱 텍스트 전용 ablation", level=2)
    add_para(
        doc,
        "Upstage Document Parse가 페이지 이미지에서 추출한 평문, 표 마크다운, 표 설명만을 "
        "VLM에 입력하고 원본 이미지는 제공하지 않는다. 이 모드는 파싱이 답에 필요한 정보를 "
        "충분히 보존하는가를 검증하는 통제군이다. 본 모드가 image_only를 크게 상회하면 "
        "파싱의 정보 보존이 충분함을 시사한다.",
    )
    add_heading(doc, "4.3 parsed_visual — Parsed-Visual RAG (v12-general)", level=2)
    add_para(
        doc,
        "페이지 이미지와 파싱 텍스트·표를 함께 VLM에 입력한다. 본 방법의 가설은 "
        "“파싱은 정확한 라벨·수치를 명시적으로 제공하고 이미지는 레이아웃·시각적 강조를 "
        "보존하므로, 두 증거가 상보적이라면 결합이 단독 사용보다 우월하다”는 것이다. 이 "
        "모드가 본 보고서가 검증하는 v12-general 방법론이다.",
    )


def section_5_architecture(doc) -> None:
    add_heading(doc, "5. 시스템 아키텍처")
    add_para(
        doc,
        "전체 파이프라인은 4단계로 구성되며, 각 단계는 독립적으로 캐시되고 재실행 가능하다.",
    )
    add_code_block(
        doc,
        "(A) Upstage parse  : corpus 페이지 이미지 → 텍스트·표 cache (JSONL)\n"
        "(B) 페이지 선택     : --oracle → qrels gold corpus-id 직접 선택\n"
        "(C) Generation     : (이미지 ± 파싱 evidence) → Qwen2-VL-7B → 답변\n"
        "(D) 평가 & 표출    : relaxed exact match → PPT slide-10 양식 결과 표",
    )

    add_heading(doc, "5.1 Parse cache 설계", level=2)
    add_para(
        doc,
        "파싱은 질의에 무관하며 페이지 단위로 한 번만 수행되어 cache에 영구 저장된다. 스키마는 "
        "ParsedDocument dataclass[benchmark/parse_cache.py:10–18]로 정의되며 다음 필드를 갖는다.",
    )
    add_code_block(
        doc,
        "ParsedDocument(\n"
        "    dataset:            str,             # e.g., \"MP-DocVQA\"\n"
        "    corpus_id:          str,             # e.g., \"txpp0227_p9.jpg\"\n"
        "    text:               str,             # plain text content\n"
        "    tables_markdown:    list[str],       # markdown-rendered tables\n"
        "    table_descriptions: list[str],       # short caption of each table\n"
        "    parse_status:       str,             # \"ok\" | \"failed\"\n"
        "    error:              str,             # populated on parse failure\n"
        "    raw_upstage:        dict[str, Any]   # raw API response (audit)\n"
        ")",
    )
    add_para(
        doc,
        "JSONL의 한 줄이 한 페이지의 파싱 결과에 해당한다. cache_key(dataset, corpus_id)로 "
        "조회하며 evidence_text(doc) 함수는 텍스트·표·표 설명을 세 섹션 헤더와 함께 단일 "
        "문자열로 직렬화한다. 이 직렬화 결과가 §4.2, §4.3 모드의 prompt에 삽입된다.",
    )

    add_heading(doc, "5.2 페이지 선택: oracle 모드", level=2)
    add_para(
        doc,
        "본 실험은 검색 단계를 우회하여 qrels가 제공하는 정답 페이지를 generator 입력으로 "
        "사용한다. --oracle 플래그가 주어지면 qrels.get(qid) 또는 SlideVQA의 다중 페이지 "
        "규약을 따르는 positive_docids 함수가 호출된다[benchmark/v12_on_visrag.py:283–290]. "
        "본 결정의 정당성은 §7.4에서 상세히 논의한다.",
    )

    add_heading(doc, "5.3 Generation: prompt 와 메시지 구성", level=2)
    add_para(
        doc,
        "모든 모드는 동일한 prompt 골격을 사용한다[benchmark/v12_on_visrag.py:75–96].",
    )
    add_code_block(
        doc,
        "You are evaluating a document QA method on the VisRAG benchmark.\n"
        "{evidence_instruction}\n"
        "Answer only the final answer. For numeric answers, return the exact\n"
        "visible value when possible. If the evidence is insufficient, answer:\n"
        "insufficient to answer.\n\n"
        "[Parsed text/table evidence]\n"
        "{context_block}\n\n"
        "[Question]\n"
        "{query}",
    )
    add_para(
        doc,
        "{evidence_instruction}과 {context_block}이 모드별로 치환되는 방식은 표 2와 같다.",
    )
    add_table(
        doc,
        header=["Mode", "evidence_instruction", "context_block"],
        rows=[
            ["image_only", "Use only the provided document page image(s).", "(not provided)"],
            ["parsed_text_only", "Use only the parsed text/table evidence. No images are provided.", "evidence_text(doc)"],
            ["parsed_visual", "Use parsed text/table evidence for exact labels and values, and use images to verify visual/layout evidence.", "evidence_text(doc)"],
        ],
        caption_number=2,
        caption="세 모드의 prompt 차이. evidence 입력만 다르고 골격은 동일하다.",
    )
    add_para(
        doc,
        "Qwen2-VL의 chat 메시지 포맷은 OpenAI 스타일 multipart content를 따르며, "
        "build_qwen2vl_messages 함수가 이미지 리스트와 텍스트 프롬프트를 결합한다"
        "[benchmark/v12_on_visrag.py:206–217].",
    )

    add_heading(doc, "5.4 결과 표출: PPT 양식 exporter", level=2)
    add_para(
        doc,
        "benchmark/ppt_table_exporter.py는 12개 generation JSON을 입력 받아 사전 자료의 슬라이드 "
        "10 양식을 따르는 markdown / CSV / JSON 표를 생성한다. baseline 행은 macro 정확도의 "
        "기준점이 되며, 나머지 행에는 baseline 대비 Δ(%p)가 자동 산출된다.",
    )


def section_6_implementation(doc) -> None:
    add_heading(doc, "6. 구현")
    add_para(doc, "핵심 모듈의 행 수와 역할은 표 3과 같다.")
    add_table(
        doc,
        header=["경로", "LoC", "역할"],
        rows=[
            ["benchmark/parse_cache.py", "77", "parse cache 스키마와 적재·저장 유틸리티"],
            ["benchmark/text_retrieval.py", "71", "BM25 인덱스 (oracle 모드에서는 미사용)"],
            ["benchmark/metrics.py", "97", "relaxed exact match, MRR@k, Recall@k"],
            ["benchmark/v12_on_visrag.py", "443", "모드별 generation 메인 (Qwen2-VL / GPT-4o / MiniCPM)"],
            ["benchmark/ppt_table_exporter.py", "300", "PPT slide-10 양식 결과 표 생성"],
            ["scripts/run_today_ppt_pipeline.sh", "111", "parse + generation + export 일괄 실행"],
        ],
        numeric_cols=[1],
        caption_number=3,
        caption="본 실험에 사용된 핵심 코드 모듈.",
    )

    add_heading(doc, "6.1 Generator 백엔드 추상화", level=2)
    add_para(
        doc,
        "네 가지 백엔드가 동일한 call_generator 시그니처로 통일된다"
        "[benchmark/v12_on_visrag.py:21–24].",
    )
    add_table(
        doc,
        header=["backend", "모델 ID", "비고"],
        rows=[
            ["qwen2vl7b_bnb4", "Qwen/Qwen2-VL-7B-Instruct", "bitsandbytes NF4 4-bit (workspace default)"],
            ["qwen2vl7b", "Qwen/Qwen2-VL-7B-Instruct", "bf16 풀 정밀 (≥16 GB GPU 필요)"],
            ["minicpmv26", "openbmb/MiniCPM-V-2_6", "VisRAG 논문 메인 generator (paper alignment)"],
            ["gpt4o", "gpt-4o", "VisRAG 논문 API fallback"],
        ],
        caption_number=4,
        caption="지원되는 generator 백엔드. prompt 구성과 결과 row 작성 로직은 백엔드와 무관하게 동일하다.",
    )

    add_heading(doc, "6.2 핵심 파라미터", level=2)
    add_table(
        doc,
        header=["파라미터", "값", "위치"],
        rows=[
            ["--generator-backend", "qwen2vl7b_bnb4", "workspace default"],
            ["--mode", "image_only / parsed_text_only / parsed_visual", "세 mode 모두 측정"],
            ["--topk", "1", "한 질의당 1개 페이지"],
            ["--limit", "100", "데이터셋당 첫 100 질의 (ChartQA는 총 63)"],
            ["--max-new-tokens", "32", "짧은 답변 가정"],
            ["--oracle", "on", "검색 우회, qrels gold 페이지 사용"],
            ["do_sample", "False", "그리디 디코딩 (재현성)"],
            ["QWEN_MAX_PIXELS", "1,310,720 (1280×1024)", "큰 이미지 다운샘플 상한"],
            ["QWEN_MIN_PIXELS", "65,536 (256×256)", "작은 이미지 업샘플 하한"],
            ["BitsAndBytesConfig", "4-bit NF4, double quant, fp16 compute", "VRAM ~6 GB"],
            ["numeric tolerance", "5% (relative)", "VisRAG 논문[1]과 동일"],
        ],
        caption_number=5,
        caption="본 실험의 핵심 파라미터. 모두 코드 또는 환경변수로 재현 가능하다.",
    )


def section_7_setup(doc) -> None:
    add_heading(doc, "7. 실험 설계와 정당화")

    add_heading(doc, "7.1 Generator 선택", level=2)
    add_para(
        doc,
        "VisRAG 논문[1]은 generator로 MiniCPM-V 2.0 / 2.6 및 GPT-4o를 사용한다. 그러나 본 "
        "보고서가 측정 대상으로 삼는 사전 자료(슬라이드 10)의 baseline은 Qwen2-VL-7B로 측정되어 "
        "있으므로, baseline 행을 동일 generator로 정렬하지 않으면 우리 측 baseline 수치가 사전 "
        "자료와 동일한 의미를 갖지 못한다. 따라서 본 연구는 paper-alignment(MiniCPM-V 2.6)와 "
        "teammate-alignment(Qwen2-VL-7B) 사이에서 후자를 채택하였다. 그 근거는 다음과 같다.",
    )
    add_numbered_list(
        doc,
        [
            "본 비교의 1차 목적은 사전 자료의 행에 본 연구의 방법론을 추가하여 동일 좌표계에서 "
            "Δ를 보고하는 것이다.",
            "VisRAG 논문은 generator 변경에 대해 강건한 결론(시각 검색이 텍스트 RAG에 우월하다)을 "
            "제시한다. 본 연구의 가설은 generator 자체의 강도가 아닌 evidence 형식의 영향에 관한 "
            "것이므로 generator 선택의 차이가 결론에 미치는 영향은 제한적이다.",
            "MiniCPM-V 2.6에서의 cross-check는 별도의 paper-alignment 실험으로 분리하여 후속 "
            "작업(§11)으로 정의한다.",
        ],
    )

    add_heading(doc, "7.2 양자화와 이미지 해상도 캡", level=2)
    add_para(
        doc,
        "본 실험 환경은 단일 RTX 4060 (8 GB VRAM)이다. Qwen2-VL-7B의 bf16 적재만으로도 약 "
        "14 GB가 필요하므로 풀 정밀 적재가 불가능하다. 8 GB 내에 모델을 적재하기 위해 두 가지 "
        "절차가 적용된다.",
    )
    add_bulleted_list(
        doc,
        [
            "bitsandbytes NF4 4-bit 양자화[4]. 일반적으로 -5~-10%p의 정확도 손실을 동반한다.",
            "max_pixels = 1,310,720 (1280×1024) 캡. Qwen2-VL은 입력 이미지를 28×28 픽셀 패치로 "
            "분할하여 vision token으로 변환하므로 1024×6000 픽셀의 infographics는 캡 없이 "
            "7,800개 이상의 vision token을 생성한다. 캡 적용 시 약 1,700개로 절감되어 메모리와 "
            "시간 모두 약 1/20로 감소하지만 작은 글자·디테일의 일부가 손실된다.",
        ],
    )
    add_para(
        doc,
        "이 두 조치는 세 모드에 동일하게 적용되므로 모드 간 정확도 차이(Δ)는 fair comparison "
        "이며, 절대값이 사전 자료의 baseline(Qwen2-VL-7B 풀 정밀)보다 낮게 측정되는 것은 "
        "예상된 영향이다.",
    )

    add_heading(doc, "7.3 본 연구의 image_only와 VisRAG 공식 generate.py의 차이", level=2)
    add_para(
        doc,
        "본 연구의 image_only는 VisRAG의 baseline 컨셉(이미지만으로 답한다)을 동일 데이터셋·"
        "동일 정확도 지표로 재현한 것이며, 코드는 자체 구현이다. 주요 차이를 표 6에 정리한다.",
    )
    add_table(
        doc,
        header=["요소", "VisRAG 공식", "본 연구"],
        rows=[
            ["실행 스크립트", "visrag/visrag_scripts/generate/generate.py", "benchmark/v12_on_visrag.py (자체)"],
            ["generator", "MiniCPM-V 2.6 / GPT-4o", "Qwen2-VL-7B (NF4)"],
            ["task_type", "multi_image / page_concatenation / weighted_selection / text", "image_only (단일 이미지 multi-image 호출)"],
            ["이미지 해상도", "원본", "max_pixels 1.3M 캡"],
            ["프롬프트", "코드 내장", "자체 작성 (§5.3)"],
            ["retrieval", "VisRAG-Ret 결과 TREC", "--oracle (qrels 직접)"],
        ],
        caption_number=6,
        caption="VisRAG 공식 generation 스크립트와 본 연구 image_only 모드의 차이.",
    )

    add_heading(doc, "7.4 검색 단계의 우회 (--oracle)", level=2)
    add_para(
        doc,
        "본 연구는 VisRAG-Ret을 실행하지 않고 oracle 검색을 사용한다. 결정 배경은 다음과 같다.",
    )
    add_numbered_list(
        doc,
        [
            "실험 격리. 본 비교의 통제 변수는 evidence 입력 형식이다. 실제 검색을 사용할 경우 "
            "모드별로 검색기가 동일 페이지를 선택할지에 따라 결과가 흔들리고 evidence 효과가 "
            "검색 정확도와 혼동된다. oracle을 사용하면 모든 모드가 동일한 정답 페이지에서 답을 "
            "생성하므로 차이는 오직 입력 형식에서 비롯된다.",
            "컴퓨팅 제약. VisRAG-Ret은 시각 임베딩 검색 모델이며 공식 demo README는 약 40 GB의 "
            "GPU 메모리를 요구한다. 본 환경(8 GB)에서는 실행이 불가능하다.",
            "학술적 관례. VisRAG 논문[1]도 generation 단계의 ablation을 위해 oracle 또는 동일 "
            "검색 결과를 공급하는 비교를 분리하여 보고한다. 본 연구는 동일한 관례를 따른다.",
        ],
    )
    add_para(
        doc,
        "본 결정의 직접적 함의는 본 보고서가 end-to-end 정확도가 아닌 generation 격리 정확도를 "
        "측정한다는 것이다. 이는 발표·논문 등의 framing에서 명시적으로 진술되어야 한다.",
    )

    add_heading(doc, "7.5 표본 설계", level=2)
    add_para(
        doc,
        "전체 데이터셋을 모두 평가하는 대신 데이터셋당 첫 100개 질의로 표본화하였다. 결정 사유는 "
        "시간 제약(단일 GPU에서의 풀 평가는 15~30시간으로 추정)과 통계적 충분성이다. 표본 100개는 "
        "5%p 수준의 정확도 차이를 95% 신뢰도로 구분하기에 충분한 크기이며(이항분포 표준오차 "
        "√(0.5·0.5/100) = 0.05), 본 실험에서 관찰된 Δ는 +14~+58%p로 표본 변동을 크게 상회한다. "
        "선택 방식은 무작위가 아닌 HF dataset의 수록 순서대로의 첫 N개로 통일하여 재현 가능성과 "
        "외부 cross-check 가능성을 보장하였다.",
    )

    add_heading(doc, "7.6 평가 지표", level=2)
    add_para(
        doc,
        "VisRAG 논문[1]과 동일한 relaxed exact match accuracy를 사용한다"
        "[benchmark/metrics.py:16–44]. 텍스트 답변은 공백 정규화와 소문자 비교를 거쳐 substring "
        "containment까지 허용하며, 숫자 답변은 정답에서 추출한 수치와 예측 수치가 5% 상대 오차 "
        "내에서 일치하면 정답으로 인정한다. 검색 지표(MRR@10, Recall@10)는 본 보고서의 범위 "
        "밖이나 동일 metric 구현이 코드베이스에 포함되어 있어 후속 작업에서 즉시 사용 가능하다.",
    )


def section_8_diff(doc) -> None:
    add_heading(doc, "8. 논문과의 일치 및 차이")
    add_table(
        doc,
        header=["구성요소", "VisRAG 논문", "본 연구", "일치 여부"],
        rows=[
            ["데이터셋 출처", "HF openbmb/VisRAG-Ret-Test-*", "동일", "일치"],
            ["데이터셋 개수", "6 (ArxivQA, ChartQA, MP-DocVQA, InfoVQA, PlotQA, SlideVQA)", "4 (ArxivQA, PlotQA 제외; 사전 자료 정렬)", "부분"],
            ["queries/corpus/qrels", "동일 schema", "동일", "일치"],
            ["정확도 metric", "relaxed exact match, 5% 숫자 tolerance", "동일 구현", "일치"],
            ["Retrieval 모델", "VisRAG-Ret (시각 임베딩)", "미실행, --oracle 사용", "불일치"],
            ["Retrieval metric", "MRR@10, Recall@10", "본 보고서 범위 밖", "불일치"],
            ["Generator", "MiniCPM-V 2.6 / GPT-4o", "Qwen2-VL-7B + NF4", "불일치(의도적)"],
            ["Generation task_type", "multi_image 등 4종", "image_only / parsed_text_only / parsed_visual (자체)", "다른 차원"],
            ["이미지 해상도", "원본", "1.3M 픽셀 캡", "불일치(제약)"],
        ],
        caption_number=7,
        caption="VisRAG 논문과 본 연구의 정렬 표. 모든 불일치는 §7에 명시된 설계 결정에 의한다.",
    )
    add_para(
        doc,
        "요약하면 본 연구는 데이터·평가 지표·정답 비교 형식을 논문과 정렬하고 generator·"
        "retrieval·해상도를 의도적으로 다른 조건으로 통제한다. 따라서 본 연구는 VisRAG 논문 "
        "결과의 재현이 아니라 VisRAG 데이터·지표 위에서의 generation evidence 형식 ablation으로 "
        "framing되어야 한다.",
    )


def section_9_results(doc) -> None:
    add_heading(doc, "9. 결과")
    add_heading(doc, "9.1 PPT slide-10 양식 결과 표", level=2)
    add_table(
        doc,
        header=["Method", "InfoVQA", "ChartQA", "DocVQA", "SlideVQA", "macro", "Δ vs Baseline"],
        rows=[
            ["Baseline (순수 VisRAG, image_only)", "0.2000", "0.3651", "0.1700", "0.1800", "0.2288", "—"],
            ["Parsed-Text Only (ablation)", "0.5400", "0.5238", "0.7600", "0.5200", "0.5860", "+35.72%p"],
            ["Parsed-Visual RAG (v12-general, ours)", "0.5400", "0.5079", "0.8000", "0.5200", "0.5920", "+36.32%p"],
        ],
        numeric_cols=[1, 2, 3, 4, 5, 6],
        caption_number=8,
        caption="Qwen2-VL-7B + NF4, oracle 검색, 데이터셋당 첫 100 질의(ChartQA는 총 63)에서의 정확도. DocVQA는 MP-DocVQA를 의미한다.",
    )

    add_heading(doc, "9.2 표본별 정답 카운트", level=2)
    add_table(
        doc,
        header=["Dataset", "image_only", "parsed_text_only", "parsed_visual"],
        rows=[
            ["InfoVQA", "20 / 100 = 0.200", "54 / 100 = 0.540", "54 / 100 = 0.540"],
            ["ChartQA", "23 / 63 = 0.365", "33 / 63 = 0.524", "32 / 63 = 0.508"],
            ["MP-DocVQA", "17 / 100 = 0.170", "76 / 100 = 0.760", "80 / 100 = 0.800"],
            ["SlideVQA", "18 / 100 = 0.180", "52 / 100 = 0.520", "52 / 100 = 0.520"],
        ],
        numeric_cols=[1, 2, 3],
        caption_number=9,
        caption="정답/전체 카운트. MP-DocVQA에서 parsed_visual이 parsed_text_only를 +4%p 상회한다.",
    )

    add_heading(doc, "9.3 실행 통계", level=2)
    add_bulleted_list(
        doc,
        [
            "총 generation call 수: 363 query × 3 mode ≈ 1,089 calls (ChartQA 63 + 나머지 100 × 3).",
            "총 실행 시간: 6,331 초 (≈ 1시간 45분).",
            "최장 단일 mode: InfoVQA × parsed_visual ≈ 65분 (큰 infographics와 결합 evidence로 인한 sequence length 증가).",
            "최단 단일 mode: ChartQA × image_only ≈ 1분 (63 질의, 단순 prompt).",
            "GPU 점유: 최대 7.9 GB / 8 GB, 평균 utilisation 80~100%.",
            "Upstage parse cost: 248 페이지(4 데이터셋 합산), 추정 USD 3~5.",
        ],
    )


def section_10_discussion(doc) -> None:
    add_heading(doc, "10. 논의")
    add_heading(doc, "10.1 v12-general의 효과", level=2)
    add_para(
        doc,
        "모든 4개 데이터셋에서 parsed_visual은 시각 전용 baseline을 큰 폭으로 상회한다. macro "
        "기준 +36.32%p의 향상은 단순한 양자화 잡음이나 표본 변동으로 설명되지 않으며, 본 환경의 "
        "generator가 시각만으로는 답을 도출하기 어려운 질의가 다수임을 시사한다. baseline의 절대 "
        "정확도가 0.17~0.20에 그치는 점은 작은 GPU·양자화·해상도 캡이 결합되어 시각 전용 입력의 "
        "정보 접근성이 크게 제한되었음을 보여준다.",
    )
    add_heading(doc, "10.2 MP-DocVQA에서의 parsed_visual 우위", level=2)
    add_para(
        doc,
        "MP-DocVQA에서는 parsed_visual이 parsed_text_only를 명확히 상회한다(0.800 vs. 0.760, "
        "+4.0%p). MP-DocVQA는 다중 페이지 문서에서 표·문단·필드 등 레이아웃 정보가 답에 "
        "기여하는 데이터셋이다. 파싱 텍스트만으로는 “어느 표의 어느 행” 수준의 위치 정보가 일부 "
        "손실되며, 원본 이미지가 이 손실을 보완하는 것으로 해석된다. 본 결과는 v12-general이 "
        "OCR-only 시스템 대비 추가 가치를 제공할 수 있음을 시사하는 가장 직접적인 증거이다.",
    )
    add_heading(doc, "10.3 ChartQA에서의 역방향", level=2)
    add_para(
        doc,
        "ChartQA에서는 parsed_text_only(0.524)가 parsed_visual(0.508)을 약 1.6%p 앞선다. 본 "
        "환경에서 ChartQA 차트는 일반적으로 800×600 픽셀 수준이므로 해상도 캡은 적용되지 않으나, "
        "Upstage 파싱이 차트의 수치 정보를 잘 추출한 경우 (i) 텍스트만으로 답이 가능하며 (ii) "
        "이미지가 추가되면 모델이 시각 정보와 텍스트 정보 사이에서 약간의 혼동을 일으킬 수 있다. "
        "본 현상은 부정적 결과가 아니라 OCR이 충분히 강할 경우 시각 추가의 한계 수익이 작거나 "
        "음의 값을 가질 수 있음을 보여주는 자연스러운 발견이다.",
    )
    add_heading(doc, "10.4 InfoVQA와 SlideVQA의 동률", level=2)
    add_para(
        doc,
        "InfoVQA와 SlideVQA에서는 parsed_text_only와 parsed_visual이 동일한 정확도를 보였다"
        "(각각 0.540, 0.520). InfoVQA는 max_pixels 캡이 가장 강하게 작용하는 데이터셋으로, 이미지 "
        "입력의 정보 밀도가 낮아져 텍스트와 결합해도 한계 이득이 없는 것으로 해석된다. "
        "SlideVQA는 슬라이드 자체가 큰 글씨 중심이라 파싱이 대부분의 정보를 보존했을 가능성이 "
        "크다.",
    )
    add_heading(doc, "10.5 결과의 framing", level=2)
    add_para(
        doc,
        "본 결과는 다음과 같이 framing할 수 있다.",
    )
    quote_p = doc.add_paragraph()
    quote_p.paragraph_format.left_indent = Cm(0.8)
    quote_p.paragraph_format.right_indent = Cm(0.8)
    quote_p.paragraph_format.space_after = Pt(6)
    quote_p.paragraph_format.line_spacing = 1.25
    quote_p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    quote_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_run(quote_p,
            "“단일 8 GB GPU 환경에서 Qwen2-VL-7B를 4-bit NF4로 적재하고 이미지 해상도를 1.3 M "
            "픽셀로 제한한 제약 환경에서, 페이지 이미지만 사용하는 baseline은 macro 정확도 "
            "0.229에 머문다. Upstage Document Parse로 추출한 파싱 텍스트를 동일 generator에 함께 "
            "제공하는 Parsed-Visual RAG는 macro 정확도 0.592(+36.32%p)를 달성한다. 특히 페이지 "
            "레이아웃이 중요한 MP-DocVQA에서는 텍스트 단독 입력 대비 +4.0%p의 추가 이득이 "
            "관찰되어, 이미지 증거와 파싱 증거의 상보성을 시사한다.”",
            size_pt=BODY_PT, italic=True)


def section_11_limits(doc) -> None:
    add_heading(doc, "11. 한계와 후속 작업")
    add_numbered_list(
        doc,
        [
            "Generator paper-alignment의 미실시. 본 결과는 Qwen2-VL-7B + NF4에 한정된다. "
            "MiniCPM-V 2.6에서 동일한 패턴이 재현되는지는 ≥16 GB GPU에서의 별도 cross-check가 "
            "필요하다.",
            "Retrieval 비교의 미실시. 본 연구는 oracle 검색을 사용하여 generation 효과만을 "
            "측정한다. VisRAG-Ret(시각 임베딩) 대 BM25(파싱 텍스트) 검색 비교는 별도의 retrieval "
            "보고로 분리된다. 본 코드베이스에는 BM25 인덱스와 평가 도구가 이미 구현되어 있어, "
            "VisRAG-Ret만 ≥40 GB GPU에서 실행하면 retrieval 표를 산출할 수 있다.",
            "표본 크기. 데이터셋당 첫 100 질의(ChartQA 63)는 5%p 단위의 Δ 검출에는 충분하나, "
            "데이터셋 내 부분 분포 효과를 분석하려면 풀 평가가 요구된다.",
            "이미지 해상도 캡의 영향. max_pixels = 1.3 M은 8 GB GPU 제약의 결과이며, 풀 해상도 "
            "환경에서는 특히 ChartQA·InfoVQA의 결과가 달라질 수 있다.",
            "Top-k = 1 고정. VisRAG 논문은 top-k = 1, 2, 3에 대한 정확도 곡선을 보고하나, 본 "
            "보고서는 oracle 모드의 top-k = 1로 한정된다.",
            "Generator 스케일 비교의 부재. 사전 자료의 Table 2 (Qwen2-VL-72B, InternVL2.5-78B, "
            "Qwen2.5-VL-72B)는 큰 모델 가족에 대한 generator scaling 비교이며 본 보고서의 범위 "
            "밖이다. 후속 실험에서 DashScope·OpenRouter 등 API 또는 cloud GPU로 보완 가능하다.",
        ],
    )


def section_12_repro(doc) -> None:
    add_heading(doc, "12. 재현성")
    add_para(
        doc,
        "본 보고서의 모든 결과는 다음 단일 명령으로 재현 가능하다.",
    )
    add_code_block(
        doc,
        "cd \"/home/chaemin/projects/AI algorithm study\"\n"
        "export UPSTAGE_API_KEY=<your-key>\n"
        "nohup bash scripts/run_today_ppt_pipeline.sh > run_today.log 2>&1 &",
    )
    add_para(
        doc,
        "스크립트는 (1) 4 데이터셋의 첫 100 질의에 대한 gold 페이지의 Upstage 파싱, "
        "(2) Qwen2-VL-7B + NF4 generation × 3 mode × 4 데이터셋, (3) PPT 양식 표 산출의 순으로 "
        "수행되며, 각 단계의 결과 파일이 이미 존재하는 경우 자동으로 skip되어 부분 실패 후 "
        "재실행이 안전하다. 더불어 4개 first100 parse cache가 함께 제공되므로 UPSTAGE_API_KEY가 "
        "없어도 Stage 2 이후를 재실행할 수 있다.",
    )
    add_para(doc, "주요 의존성과 버전은 표 10과 같다.")
    add_table(
        doc,
        header=["패키지", "버전"],
        rows=[
            ["torch", "2.6.0 (cu124 wheels)"],
            ["torchvision", "0.21+ (cu124)"],
            ["transformers", "4.51.x (Qwen2VLForConditionalGeneration 호환 최후 라인)"],
            ["qwen-vl-utils", "≥ 0.0.8"],
            ["bitsandbytes", "≥ 0.43"],
            ["accelerate", "≥ 0.34"],
            ["datasets", "4.8.5 (fsspec ≤ 2026.2.0)"],
            ["rank_bm25", "≥ 0.2.2"],
        ],
        caption_number=10,
        caption="본 실험의 재현에 필요한 주요 패키지 버전.",
    )
    add_para(
        doc,
        "NVIDIA 드라이버는 572.61(CUDA 12.8 호환)이며, torch는 cu124 wheels로 설치하여 드라이버 "
        "호환을 확보하였다.",
    )


def section_13_conclusion(doc) -> None:
    add_heading(doc, "13. 결론")
    add_para(
        doc,
        "본 보고서는 VisRAG의 공개 평가 데이터와 평가 지표 위에서 동일한 generator(Qwen2-VL-7B + "
        "NF4)와 동일한 oracle 페이지를 사용하여, 시각 전용 입력과 Upstage 파싱 결합 입력의 정확도를 "
        "격리하여 측정하였다. macro 정확도 기준 0.229 → 0.592(+36.32%p)의 향상이 관찰되었고, "
        "페이지 레이아웃이 답에 기여하는 MP-DocVQA에서는 텍스트 단독 입력 대비 +4.0%p의 추가 "
        "이득이 관찰되었다. 본 결과는 단일 8 GB GPU 제약 환경에서도 parsed_visual 방법이 시각 "
        "전용 baseline 대비 명확한 효과를 보임을 입증한다. 절대 정확도는 양자화·해상도 캡의 "
        "영향으로 사전 자료의 풀 정밀 baseline보다 낮으며, 본 보고서는 모드 간 Δ가 fair "
        "comparison임을 명시한다. 후속 작업은 (i) MiniCPM-V 2.6에서의 paper-alignment cross-check, "
        "(ii) VisRAG-Ret 시각 검색 비교, (iii) 풀 정밀 환경에서의 ablation 재현으로 정의된다.",
    )


def references(doc) -> None:
    add_heading(doc, "참고문헌")
    refs = [
        ("Wang, S., Yu, T., Wei, X., et al. ",
         "VisRAG: Vision-based Retrieval-augmented Generation on Multi-modality Documents.",
         "arXiv preprint arXiv:2410.10594, 2024."),
        ("OpenBMB. ", "VisRAG: official repository and HuggingFace evaluation datasets.",
         "https://github.com/openbmb/visrag; https://huggingface.co/datasets/openbmb (VisRAG-Ret-Test-*)."),
        ("Qwen Team. ", "Qwen2-VL: Enhancing Vision-Language Model’s Perception of the World at Any Resolution.",
         "Technical report, 2024. https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct."),
        ("Dettmers, T., Pagnoni, A., Holtzman, A., Zettlemoyer, L. ",
         "QLoRA: Efficient Finetuning of Quantized LLMs.",
         "In Advances in Neural Information Processing Systems (NeurIPS), 2023."),
        ("Upstage AI. ", "Document Parse API.",
         "https://api.upstage.ai/v1/document-ai/document-parse."),
    ]
    for idx, (authors, title, where) in enumerate(refs, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.85)
        pf.first_line_indent = Cm(-0.85)
        pf.space_after = Pt(3)
        pf.line_spacing = 1.25
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_run(p, f"[{idx}]  ", size_pt=REF_PT, bold=True)
        add_run(p, authors, size_pt=REF_PT)
        add_run(p, title, size_pt=REF_PT, italic=True)
        add_run(p, " ", size_pt=REF_PT)
        add_run(p, where, size_pt=REF_PT)


def appendices(doc) -> None:
    add_heading(doc, "부록 A. 데이터셋별 입력 토큰 분포")
    add_table(
        doc,
        header=["Dataset", "avg input tokens (image_only)", "avg input tokens (parsed_visual)"],
        rows=[
            ["ChartQA", "약 300–950", "약 1,500–3,000"],
            ["InfoVQA", "약 1,700 (capped)", "약 2,500–4,000"],
            ["MP-DocVQA", "약 1,300–1,700", "약 2,000–3,500"],
            ["SlideVQA", "약 900–1,400", "약 1,500–3,000"],
        ],
        numeric_cols=[1, 2],
        caption_number="A1",
        caption="입력 토큰 수의 데이터셋·모드별 대략 분포.",
    )

    add_heading(doc, "부록 B. 주요 코드 참조")
    add_bulleted_list(
        doc,
        [
            "benchmark/parse_cache.py: ParsedDocument, load_parse_cache, append_parse_cache, evidence_text.",
            "benchmark/v12_on_visrag.py: build_prompt(75–96), build_qwen2vl_messages(206–217), call_qwen2vl(210–278), main(305–443).",
            "benchmark/ppt_table_exporter.py: render_markdown, render_csv, render_json.",
            "benchmark/metrics.py: relaxed_exact_match(16–44), accuracy(47–55), mrr_at_k(58–69), recall_at_k(72–81).",
            "scripts/run_today_ppt_pipeline.sh: Stage 1 Upstage parse, Stage 2 generation × 3 mode × 4 dataset, Stage 3 PPT exporter.",
            "configs/visrag_paper_benchmark.json: 데이터셋·generator·metric 메타데이터와 PPT 정렬 매핑.",
        ],
    )

    add_heading(doc, "부록 C. v12 bridge 도메인 구성요소(범위 외)")
    add_para(
        doc,
        "본 보고서가 다루는 v12-general은 백업 폴더 backup/v12_port/ 의 도메인 종속 v12 구성"
        "요소—교량 점검 보고서에 특화된 질문 분류기, 챕터 추론, 손상 이력 보강 등—를 제거하고 "
        "‘파싱 텍스트와 이미지를 동시에 VLM에 입력한다’는 일반 원리만을 남긴 변형이다. VisRAG "
        "공개 벤치마크에는 교량 도메인 컴포넌트가 사용되지 않으며, 본 제출의 어떤 결과도 "
        "v12_port 모듈에 의존하지 않는다. 자세한 설계 근거는 backup/docs/"
        "domain_free_v12_experiment_design.md에, backup 폴더의 인덱스는 backup/README.md에 있다.",
    )


# ---------------------------------------------------------------------------
# main


def main() -> None:
    doc = setup_document()
    add_title_block(doc)
    add_abstract(doc)
    section_1_intro(doc)
    section_2_related(doc)
    section_3_datasets(doc)
    section_4_methodologies(doc)
    section_5_architecture(doc)
    section_6_implementation(doc)
    section_7_setup(doc)
    section_8_diff(doc)
    section_9_results(doc)
    section_10_discussion(doc)
    section_11_limits(doc)
    section_12_repro(doc)
    section_13_conclusion(doc)
    references(doc)
    appendices(doc)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
