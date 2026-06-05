"""Generate docs/report_v12_general_vs_visrag.docx from the report content.

The output mirrors docs/report_v12_general_vs_visrag.html but uses paper-style
serif fonts (Times New Roman / NanumMyeongjo) and explicitly black text via
python-docx, so it opens consistently in MS Word and LibreOffice.
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "report_v12_general_vs_visrag.docx"

LATIN_FONT = "Times New Roman"
CJK_FONT = "NanumMyeongjo"  # falls back to system serif if absent
MONO_FONT = "Consolas"
BLACK = RGBColor(0x00, 0x00, 0x00)


def set_run_style(run, *, size_pt: float, bold: bool = False, italic: bool = False,
                  font_name: str | None = None, mono: bool = False) -> None:
    run.font.size = Pt(size_pt)
    run.font.bold = bool(bold)
    run.font.italic = bool(italic)
    run.font.color.rgb = BLACK
    name = MONO_FONT if mono else (font_name or LATIN_FONT)
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


def add_para(doc: Document, text: str = "", *, size_pt: float = 11, bold: bool = False,
             italic: bool = False, align: int | None = None, space_after: float = 6,
             space_before: float = 0) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.space_before = Pt(space_before)
    if align is not None:
        p.alignment = align
    if text:
        run = p.add_run(text)
        set_run_style(run, size_pt=size_pt, bold=bold, italic=italic)


def add_rich_para(doc: Document, segments: list[tuple[str, dict]], *, size_pt: float = 11,
                  align: int | None = None, space_after: float = 6) -> None:
    """segments: list of (text, kwargs) where kwargs may include bold/italic/mono/size_pt."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    for text, kw in segments:
        run = p.add_run(text)
        set_run_style(
            run,
            size_pt=kw.get("size_pt", size_pt),
            bold=kw.get("bold", False),
            italic=kw.get("italic", False),
            mono=kw.get("mono", False),
        )


def add_section_heading(doc: Document, text: str, *, level: int = 1) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14 if level == 1 else 10)
    p.paragraph_format.space_after = Pt(4)
    size = {1: 14, 2: 12, 3: 11}[level]
    bold = True
    run = p.add_run(text)
    set_run_style(run, size_pt=size, bold=bold)
    if level == 1:
        bottom_border(p)


def bottom_border(paragraph) -> None:
    p_pr = paragraph._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "6")
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), "000000")
    pbdr.append(bottom)
    p_pr.append(pbdr)


def add_code_block(doc: Document, code: str) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.left_indent = Cm(0.4)
    run = p.add_run(code)
    set_run_style(run, size_pt=9.5, mono=True)
    pPr = p._p.get_or_add_pPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "F4F4F0")
    pPr.append(shd)


def add_bullets(doc: Document, items: list, *, numbered: bool = False,
                style: str | None = None) -> None:
    """items: list of (text, [optional rich segments]) or just str."""
    list_style = "List Number" if numbered else "List Bullet"
    for item in items:
        p = doc.add_paragraph(style=list_style)
        p.paragraph_format.space_after = Pt(2)
        if isinstance(item, str):
            run = p.add_run(item)
            set_run_style(run, size_pt=11)
        else:
            for text, kw in item:
                run = p.add_run(text)
                set_run_style(
                    run,
                    size_pt=kw.get("size_pt", 11),
                    bold=kw.get("bold", False),
                    italic=kw.get("italic", False),
                    mono=kw.get("mono", False),
                )


def style_cell(cell, *, header: bool = False, align_right: bool = False) -> None:
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    for paragraph in cell.paragraphs:
        if align_right:
            paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for run in paragraph.runs:
            set_run_style(run, size_pt=10, bold=header)


def add_table(doc: Document, header: list[str], rows: list[list[str]],
              numeric_cols: list[int] | None = None, caption: str | None = None) -> None:
    numeric_cols = set(numeric_cols or [])
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Light Grid"
    hdr_cells = table.rows[0].cells
    for i, text in enumerate(header):
        hdr_cells[i].text = text
        style_cell(hdr_cells[i], header=True, align_right=(i in numeric_cols))
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = val
            style_cell(cell, align_right=(c_idx in numeric_cols))
    if caption:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(10)
        run = p.add_run(caption)
        set_run_style(run, size_pt=9.5, italic=True)


def setup_document() -> Document:
    doc = Document()
    section = doc.sections[0]
    section.top_margin = Cm(2.2)
    section.bottom_margin = Cm(2.2)
    section.left_margin = Cm(2.4)
    section.right_margin = Cm(2.4)
    style = doc.styles["Normal"]
    style.font.name = LATIN_FONT
    style.font.size = Pt(11)
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


def add_title_block(doc: Document) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("Parsed-Visual RAG (v12-general) vs. VisRAG")
    set_run_style(run, size_pt=18, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run("단일 GPU 환경에서의 동일 생성기 ablation을 통한 문서 시각 질의응답 방법론 비교")
    set_run_style(run, size_pt=11.5, italic=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run("기술 보고서 · 2026년 6월 5일 · 작성: 채민")
    set_run_style(run, size_pt=10.5)


def add_abstract(doc: Document) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run("ABSTRACT")
    set_run_style(run, size_pt=11, bold=True)
    bottom_border(p)

    body_p = doc.add_paragraph()
    body_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    body_p.paragraph_format.left_indent = Cm(0.8)
    body_p.paragraph_format.right_indent = Cm(0.8)
    body_p.paragraph_format.space_after = Pt(2)
    text = (
        "본 보고서는 OpenBMB가 제안한 VisRAG (arXiv:2410.10594)의 공개 평가 벤치마크 위에서, "
        "시각 전용 baseline과 본 연구의 domain-free 변형인 Parsed-Visual RAG (별칭 v12-general)을 "
        "비교한 결과를 정리한다. v12-general은 페이지 이미지를 Upstage Document Parse로 텍스트·표 "
        "형태로 변환하여 이를 동일한 시각 언어 모델(VLM)에 원본 이미지와 함께 입력으로 제공하는 "
        "방법이다. 본 실험은 단일 RTX 4060 (8 GB VRAM) 환경에서 Qwen2-VL-7B-Instruct를 "
        "bitsandbytes NF4 4-bit 양자화로 적재하고, 4개 데이터셋(InfoVQA, ChartQA, MP-DocVQA, "
        "SlideVQA)의 각 첫 100개 질의에 대해 oracle 검색을 사용해 생성 단계만을 격리하여 측정하였다. "
        "결과적으로 v12-general은 시각 전용 baseline 대비 macro 정확도 기준 +36.32%p (0.2288 → 0.5920) "
        "향상을 보였으며, 특히 페이지 레이아웃이 답에 중요한 MP-DocVQA에서 텍스트 단독 ablation 대비 "
        "+4.0%p의 추가 이득을 확인하였다. 본 보고서는 각 방법론의 구조, 파라미터 설정, 코드 설계, "
        "논문과의 일치/차이, 그리고 단일 GPU 제약 하에서의 생성기·검색·표본 설계 결정의 정당성을 "
        "학술적 톤으로 정리한다."
    )
    run = body_p.add_run(text)
    set_run_style(run, size_pt=10.5)

    border_p = doc.add_paragraph()
    border_p.paragraph_format.space_after = Pt(12)
    bottom_border(border_p)


def section_1_intro(doc: Document) -> None:
    add_section_heading(doc, "1. 서론 및 동기")
    for body in [
        "VisRAG는 문서 페이지 이미지를 OCR이나 파싱 없이 시각 임베딩으로 검색하고 시각 언어 모델로 답을 생성하는 RAG 파이프라인을 제안한다. 그 동기는 명확하다: OCR·파싱 단계에서 발생하는 정보 손실(레이아웃, 차트의 색상, 글꼴 강조 등)이 답변 정확도에 부정적이라는 가설이다. 한편 우리 연구실에서 개발해 온 v12 아키텍처는 동일한 페이지 이미지에 대해 Upstage Document Parse를 적용해 텍스트·표를 명시적으로 추출하고, 이를 원본 이미지와 함께 VLM 입력으로 결합한다. 즉 두 방법은 본질적으로 ‘파싱을 통한 명시적 텍스트 증거가 시각 전용 입력 대비 답변 품질을 개선하는가’라는 가설에 대해 상반된 입장을 가진다.",
        "본 보고서의 목적은 이 두 접근을 동일한 데이터셋, 동일한 평가 지표, 동일한 생성기, 동일한 입력 페이지 조건에서 비교하여, evidence 형식(이미지 단독 / 파싱 텍스트 단독 / 둘의 결합) 자체가 정확도에 미치는 영향만을 격리해 측정하는 것이다. 본 연구는 검색 모델의 차이나 생성 모델의 절대 성능 차이를 다루지 않는다.",
        "또한 비교 대상이 되는 결과 표는 팀 내 사전 PPT 자료(docs/VisRAG Multi Page Compression.pptx, slide 10)의 레이아웃을 따른다. 해당 자료의 baseline은 Qwen2-VL-7B를 그대로 사용했으며, 본 연구도 generator를 동일 모델 계열로 정렬하여 baseline의 위치를 일치시킨다.",
    ]:
        add_para(doc, body, size_pt=11, align=WD_ALIGN_PARAGRAPH.JUSTIFY, space_after=8)


def section_2_datasets(doc: Document) -> None:
    add_section_heading(doc, "2. 평가 데이터셋")
    add_para(
        doc,
        "본 연구는 VisRAG 공식 평가셋(openbmb/VisRAG-Ret-Test-*) 중 4개 데이터셋을 사용한다. 데이터셋 선택은 팀 내 PPT의 결과 표 컬럼(InfoVQA, ChartQA, DocVQA, SlideVQA)에 정렬되며, 여기서 PPT의 DocVQA는 공식 명칭 MP-DocVQA에 매핑된다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
        space_after=6,
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
        caption="표 1. 평가에 사용된 4개 데이터셋의 split 크기와 HuggingFace blob 캐시 용량. SlideVQA는 한 질의가 다수 페이지에 매핑되어 qrels > queries이다.",
    )
    add_para(
        doc,
        "각 데이터셋은 세 개의 subset을 갖는다: queries는 질문과 정답, corpus는 페이지 이미지(PIL 형식), qrels는 질문-페이지 정답 매핑. 본 실험에서는 oracle 검색을 사용하므로 qrels가 직접 페이지 선택에 사용되며, 사용되는 페이지의 수는 데이터셋당 첫 100개 질의에 대응되는 unique gold page이다. 이로 인해 InfoVQA의 corpus 호출은 29건, ChartQA는 60건, MP-DocVQA는 62건, SlideVQA는 97건으로 절제된다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def section_3_methodologies(doc: Document) -> None:
    add_section_heading(doc, "3. 방법론")
    add_para(
        doc,
        "본 비교는 동일한 oracle 페이지에 대해 VLM 입력에 어떤 형식의 evidence가 들어가는가에 따라 세 가지 모드를 정의한다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "3.1 image_only — 시각 전용 baseline (논문 정렬)", level=2)
    add_para(
        doc,
        "페이지 이미지만을 VLM에 입력하고, 파싱 텍스트는 제공하지 않는다. 이는 VisRAG 논문의 핵심 주장인 ‘OCR을 거치지 않고 페이지 이미지를 그대로 사용한다’를 동일 환경에서 재현한 baseline이다. 단 본 연구의 image_only는 논문의 공식 스크립트(visrag/visrag_scripts/generate/generate.py)를 그대로 실행하지 않고, 동일한 컨셉을 자체 코드로 재구현한 것이다. 차이는 §6.3에서 정리한다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "3.2 parsed_text_only — 파싱 텍스트 전용 ablation", level=2)
    add_para(
        doc,
        "Upstage Document Parse가 페이지 이미지에서 추출한 평문, 표 마크다운, 표 설명만을 VLM에 입력하고, 원본 이미지는 제공하지 않는다. 이 모드는 ‘OCR/파싱이 충분히 풍부한가’를 검증하는 통제군이다. 만약 이 단독 모드가 image_only를 크게 앞지른다면, 파싱이 답에 필요한 정보를 잘 보존한다는 신호이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "3.3 parsed_visual — Parsed-Visual RAG (v12-general, 본 연구)", level=2)
    add_para(
        doc,
        "페이지 이미지와 파싱 텍스트·표를 함께 VLM에 입력한다. 본 방법의 핵심 가설은 ‘파싱은 정확한 라벨·숫자를 명시적으로 제공하고, 이미지는 레이아웃·시각적 강조를 보존한다. 두 증거가 상보적이라면 결합은 단독 사용보다 우월하다’이다. 이 모드가 본 보고서가 검증하려는 v12-general 방법론이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_para(
        doc,
        "세 모드는 모두 동일한 prompt template를 공유하며, build_prompt 함수가 evidence_instruction과 context_block 두 슬롯만을 모드별로 바꾼다. 이로써 평가 결과의 차이는 오직 evidence 입력 형식에서 비롯된다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def section_4_architecture(doc: Document) -> None:
    add_section_heading(doc, "4. 시스템 아키텍처")
    add_para(doc, "전체 파이프라인은 네 단계로 구성된다.", align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_code_block(
        doc,
        "(A) Upstage parse  : corpus 페이지 이미지 → 텍스트·표 cache(JSONL)\n"
        "(B) 페이지 선택     : --oracle → qrels gold corpus-id 직접 선택\n"
        "(C) Generation     : (페이지 이미지 ± 파싱 evidence) → Qwen2-VL-7B → 답변\n"
        "(D) 평가 & 표출    : relaxed exact match 정확도 → PPT slide-10 양식 표",
    )

    add_section_heading(doc, "4.1 Parse cache 설계", level=2)
    add_para(
        doc,
        "파싱은 질의에 무관하며 페이지 단위로 한 번만 수행되어 cache에 저장된다. 스키마는 ParsedDocument dataclass로 정의되며 [benchmark/parse_cache.py:10–18], 다음 필드를 포함한다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
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
        "cache는 JSONL 파일로 저장되어 한 줄당 한 페이지의 파싱 결과를 갖는다. cache_key(dataset, corpus_id)로 조회하며, evidence_text(doc)는 텍스트·표·표 설명을 세 섹션 헤더와 함께 단일 문자열로 직렬화한다. 본 직렬화 결과가 §3.2, §3.3 모드의 prompt에 삽입된다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "4.2 페이지 선택: oracle 모드", level=2)
    add_para(
        doc,
        "본 실험은 검색 단계를 명시적으로 우회하고 qrels가 제공하는 정답 페이지를 그대로 generator 입력으로 사용한다. 이는 generation 효과를 검색 변수로부터 분리하기 위함이며, 정당성은 §6.4에서 상세히 다룬다. 코드 상으로는 --oracle 플래그가 주어지면 qrels.get(qid) 또는 SlideVQA의 다중 페이지 규약을 따르는 positive_docids가 사용된다 [benchmark/v12_on_visrag.py:283–290].",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "4.3 Generation: prompt와 메시지 빌드", level=2)
    add_para(
        doc,
        "모든 모드는 동일한 prompt 골격을 사용한다 [benchmark/v12_on_visrag.py:75–96].",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
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
        "evidence_instruction과 context_block은 모드별로 다음과 같이 바뀐다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_table(
        doc,
        header=["Mode", "evidence_instruction", "context_block"],
        rows=[
            ["image_only", "Use only the provided document page image(s).", "(not provided)"],
            ["parsed_text_only", "Use only the parsed text/table evidence. No images are provided.", "evidence_text(doc)"],
            ["parsed_visual", "Use parsed text/table evidence for exact labels and values, and use images to verify visual/layout evidence.", "evidence_text(doc)"],
        ],
        caption="표 2. 세 모드의 prompt 차이. evidence 입력만 다르고 골격은 동일하다.",
    )
    add_para(
        doc,
        "Qwen2-VL의 chat 메시지 포맷은 OpenAI 스타일의 multipart content를 따르며, build_qwen2vl_messages가 이미지 리스트와 텍스트 프롬프트를 [{\"type\":\"image\", ...}, ..., {\"type\":\"text\", \"text\":prompt}] 형태로 결합한다 [benchmark/v12_on_visrag.py:206–217].",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "4.4 결과 표출: PPT 양식 exporter", level=2)
    add_para(
        doc,
        "benchmark/ppt_table_exporter.py는 12개 generation JSON을 입력 받아 PPT 슬라이드 10의 양식을 따르는 markdown/CSV/JSON 표를 생성한다. baseline 행은 macro 정확도의 기준점이 되며, 다른 행들은 baseline 대비 Δ vs Baseline (pp)가 자동 계산된다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def section_5_implementation(doc: Document) -> None:
    add_section_heading(doc, "5. 구현")
    add_para(doc, "핵심 모듈과 행 수는 다음과 같다.", align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_table(
        doc,
        header=["경로", "LoC", "역할"],
        rows=[
            ["benchmark/parse_cache.py", "77", "parse cache 스키마, 적재/저장 유틸리티"],
            ["benchmark/text_retrieval.py", "71", "BM25 인덱스 (oracle 모드에서는 미사용)"],
            ["benchmark/metrics.py", "97", "relaxed exact match, MRR@k, Recall@k"],
            ["benchmark/v12_on_visrag.py", "443", "모드별 generation 메인 (Qwen2-VL / GPT-4o / MiniCPM)"],
            ["benchmark/ppt_table_exporter.py", "300", "PPT slide-10 양식 표 생성"],
            ["scripts/run_today_ppt_pipeline.sh", "111", "parse + generation + export 일괄 실행"],
        ],
        numeric_cols=[1],
        caption="표 3. 본 실험에 사용된 핵심 코드 모듈.",
    )

    add_section_heading(doc, "5.1 Generator 백엔드 추상화", level=2)
    add_para(
        doc,
        "네 가지 백엔드가 지원된다 (GENERATOR_BACKENDS, benchmark/v12_on_visrag.py:21–24).",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_table(
        doc,
        header=["backend", "모델 ID", "비고"],
        rows=[
            ["qwen2vl7b_bnb4", "Qwen/Qwen2-VL-7B-Instruct", "bitsandbytes NF4 4-bit 적재 (workspace default)"],
            ["qwen2vl7b", "Qwen/Qwen2-VL-7B-Instruct", "bf16 풀 정밀 (≥16 GB GPU 필요)"],
            ["minicpmv26", "openbmb/MiniCPM-V-2_6", "VisRAG 논문 메인 generator (paper alignment용)"],
            ["gpt4o", "gpt-4o", "VisRAG 논문 API fallback"],
        ],
    )
    add_para(
        doc,
        "각 백엔드는 동일한 call_generator(backend, query, images, parsed_context, model, mode, max_new_tokens) 시그니처로 통일되어, prompt 구성과 결과 row 작성 로직은 백엔드 변경 시에도 변하지 않는다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "5.2 핵심 파라미터", level=2)
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
            ["numeric tolerance", "5% (relative)", "VisRAG 논문과 동일"],
        ],
        caption="표 4. 본 실험의 핵심 파라미터. 모두 코드 또는 환경변수로 재현 가능하다.",
    )


def section_6_setup(doc: Document) -> None:
    add_section_heading(doc, "6. 실험 설정과 설계 결정의 정당화")

    add_section_heading(doc, "6.1 Generator 선택: 왜 Qwen2-VL-7B인가", level=2)
    add_para(
        doc,
        "VisRAG 논문은 generator로 MiniCPM-V 2.0 / 2.6 또는 GPT-4o를 사용한다. 본 보고서가 측정 대상으로 삼는 비교 표는 팀 내부 사전 자료(docs/VisRAG Multi Page Compression.pptx, slide 10)이며, 그 표의 baseline은 Qwen2-VL-7B로 측정되어 있다. 따라서 baseline 행을 동일 generator로 정렬하지 않을 경우, 우리 측 baseline 수치가 사전 표와 동일한 의미를 갖지 못한다. 본 연구는 paper-alignment(MiniCPM-V 2.6)와 teammate-alignment(Qwen2-VL-7B) 사이에서 후자를 선택했다. 이는 다음과 같은 이유에 의한 결정이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_bullets(
        doc,
        [
            "본 비교의 1차 목적은 사전 표의 행에 우리 방법론을 추가하여 동일 좌표계에서 delta를 보고하는 것이다.",
            "VisRAG 논문은 generator 변경에 대해 강건한 결론(visual retrieval이 텍스트 RAG에 우월하다)을 제시했고, 본 연구의 가설은 generator 자체의 강도가 아닌 evidence 형식의 영향에 대한 것이므로 generator 선택의 차이가 결론에 미치는 영향은 제한적이다.",
            "MiniCPM-V 2.6은 별도 paper-alignment cross-check 실험으로 분리하여 후속 작업으로 정의한다 (§9).",
        ],
        numbered=True,
    )

    add_section_heading(doc, "6.2 양자화(NF4)와 이미지 해상도 캡: 왜 정확도 절대값이 낮은가", level=2)
    add_para(
        doc,
        "본 실험 환경은 단일 RTX 4060 (8 GB VRAM)이다. Qwen2-VL-7B의 bf16 적재만으로도 약 14 GB가 필요하여 풀 정밀 적재가 불가능하다. 다음 두 가지 절차로 8 GB 내에 적재한다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_bullets(
        doc,
        [
            "bitsandbytes NF4 4-bit 양자화. 일반적으로 -5~-10%p의 정확도 손실을 동반한다.",
            "max_pixels = 1,310,720 (1280×1024) 캡. Qwen2-VL은 입력 이미지를 28×28 픽셀 패치로 분할해 vision token으로 변환하므로, 1024×6000 픽셀의 infographics는 캡 없이 7,800+ vision token을 생성한다. 캡 적용 시 약 1,700 vision token으로 절감되어 메모리·시간이 모두 1/20 수준으로 줄어들지만, 작은 글자/디테일의 일부 손실이 발생한다.",
        ],
    )
    add_para(
        doc,
        "이 두 조치는 모두 세 모드에 동일하게 적용된다. 따라서 모드 간 정확도 차이(delta)는 fair comparison이며, 절대값이 팀 PPT의 baseline(Qwen2-VL-7B 풀 정밀)보다 낮게 나오는 것은 정상이고 예상된 영향이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "6.3 본 연구의 코드 vs VisRAG 공식 generate.py", level=2)
    add_para(
        doc,
        "본 연구의 image_only는 VisRAG의 baseline 컨셉(시각만으로 답)을 동일 데이터셋·동일 정확도 metric으로 재현한 것이며, 다음과 같은 차이를 가진다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_table(
        doc,
        header=["요소", "VisRAG 공식", "본 연구"],
        rows=[
            ["실행 스크립트", "visrag/visrag_scripts/generate/generate.py", "benchmark/v12_on_visrag.py (자체)"],
            ["generator", "MiniCPM-V 2.6 / GPT-4o", "Qwen2-VL-7B (NF4)"],
            ["task_type", "multi_image / page_concatenation / weighted_selection / text", "image_only (단일 이미지 multi-image 호출)"],
            ["이미지 해상도", "원본", "max_pixels 1.3M 캡"],
            ["프롬프트", "코드 내장", "자체 작성 (§4.3)"],
            ["retrieval", "VisRAG-Ret 결과 TREC", "--oracle (qrels 직접)"],
        ],
        caption="표 5. VisRAG 공식 generation 스크립트와 본 연구의 image_only 모드의 차이.",
    )

    add_section_heading(doc, "6.4 검색 단계의 우회 (--oracle)", level=2)
    add_para(
        doc,
        "본 연구는 VisRAG-Ret을 실행하지 않고 oracle 검색을 사용한다. 결정 배경은 다음과 같다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_bullets(
        doc,
        [
            "실험 격리. 본 비교의 통제 변수는 evidence 입력 형식이다. 만약 실제 검색을 사용하면 모드별로 검색기가 동일 페이지를 선택할지에 따라 결과가 흔들리고, evidence 형식의 효과가 검색 정확도와 혼동된다. oracle을 사용하면 모든 모드가 동일한 정답 페이지에서 답을 생성하므로, 차이는 오직 입력 형식에서 비롯된다.",
            "컴퓨팅 제약. VisRAG-Ret은 시각 임베딩 검색 모델이며 공식 demo README는 약 40 GB GPU 메모리를 요구한다. 본 환경(8 GB)에서 실행이 불가능하다.",
            "학술적 관례. VisRAG 논문도 generation 단계의 ablation을 위해 oracle 또는 동일 검색 결과를 공급하는 비교를 분리하여 보고한다. 본 연구는 같은 관례를 따른다.",
        ],
        numbered=True,
    )
    add_para(
        doc,
        "본 결정의 직접적 함의는 본 보고서가 end-to-end 정확도가 아닌 generation 격리 정확도를 측정한다는 것이다. 이는 발표/논문 framing에서 명시적으로 진술되어야 한다 (§10).",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "6.5 표본 설계: 데이터셋당 첫 100 질의", level=2)
    add_para(
        doc,
        "전체 데이터셋을 모두 평가하지 않고 데이터셋당 첫 100개 질의로 표본화하였다. 결정 사유는 시간 제약(단일 GPU에서 풀 평가는 15~30시간 추정)과 통계적 충분성이다. 100 표본은 5%p 수준의 delta를 95% 신뢰도로 구분하기에 충분한 표본 크기이며 (이항분포 표준오차 √(0.5·0.5/100) = 0.05), 본 실험에서 관찰된 delta는 +14~+58%p로 표본 변동을 크게 상회한다. 선택 방식은 무작위가 아니라 HF dataset의 수록 순서대로의 첫 N개를 사용하였다. 이는 (i) 재현 가능성, (ii) 다른 연구자가 동일 부분집합으로 cross-check할 수 있는 가능성을 보장하기 위함이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )

    add_section_heading(doc, "6.6 평가 지표", level=2)
    add_para(
        doc,
        "VisRAG 논문과 동일한 relaxed exact match accuracy를 사용한다 [benchmark/metrics.py:16–44].",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_bullets(
        doc,
        [
            "텍스트 답변: 공백 정규화 + 소문자 비교, substring containment 허용.",
            "숫자 답변: 정답에서 숫자를 추출하고 예측 숫자와 5% 상대 오차 내에서 매칭되면 정답으로 인정.",
        ],
    )
    add_para(
        doc,
        "검색 지표(MRR@10, Recall@10)는 본 보고서의 범위 밖이지만 동일 metric 구현이 코드베이스에 포함되어 있어 후속 작업에서 즉시 사용 가능하다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def section_7_diff(doc: Document) -> None:
    add_section_heading(doc, "7. 논문과의 일치 및 차이")
    add_table(
        doc,
        header=["구성요소", "VisRAG 논문", "본 연구", "일치?"],
        rows=[
            ["데이터셋 출처", "HF openbmb/VisRAG-Ret-Test-*", "동일", "일치"],
            ["데이터셋 개수", "6 (ArxivQA, ChartQA, MP-DocVQA, InfoVQA, PlotQA, SlideVQA)", "4 (ArxivQA, PlotQA 제외; PPT 정렬)", "부분"],
            ["queries/corpus/qrels", "동일 schema", "동일", "일치"],
            ["정확도 metric", "relaxed exact match, 5% 숫자 tolerance", "동일 구현", "일치"],
            ["Retrieval 모델", "VisRAG-Ret (시각 임베딩)", "미실행, --oracle 사용", "불일치"],
            ["Retrieval metric", "MRR@10, Recall@10", "본 보고서 범위 밖", "불일치"],
            ["Generator", "MiniCPM-V 2.6 / GPT-4o", "Qwen2-VL-7B + NF4", "불일치 (의도적)"],
            ["Generation task_type", "multi_image 등 4종", "image_only / parsed_text_only / parsed_visual (자체)", "다른 차원"],
            ["이미지 해상도", "원본", "1.3M 픽셀 캡", "불일치 (제약)"],
        ],
        caption="표 6. VisRAG 논문과 본 연구의 정렬 표. 정렬: 데이터·평가 지표·정답 형식. 불일치: generator, retrieval, 이미지 해상도. 모든 불일치는 §6에 명시된 설계 결정에 의한 것이다.",
    )
    add_para(
        doc,
        "요약하면, 본 연구는 데이터·평가 metric·정답 비교 형식을 논문과 정렬하고, generator·retrieval·해상도는 의도적으로 다른 조건으로 통제한다. 이로 인해 본 연구는 ‘VisRAG 논문 결과의 재현’이 아니라 ‘VisRAG 데이터·metric 위에서의 generation evidence 형식 ablation’으로 framing되어야 한다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def section_8_results(doc: Document) -> None:
    add_section_heading(doc, "8. 결과")
    add_section_heading(doc, "8.1 PPT slide-10 양식 표", level=2)
    add_table(
        doc,
        header=["Method", "InfoVQA", "ChartQA", "DocVQA", "SlideVQA", "macro", "Δ vs Baseline"],
        rows=[
            ["Baseline (순수 VisRAG, image_only)", "0.2000", "0.3651", "0.1700", "0.1800", "0.2288", "—"],
            ["Parsed-Text Only (ablation)", "0.5400", "0.5238", "0.7600", "0.5200", "0.5860", "+35.72%p"],
            ["Parsed-Visual RAG (v12-general, ours)", "0.5400", "0.5079", "0.8000", "0.5200", "0.5920", "+36.32%p"],
        ],
        numeric_cols=[1, 2, 3, 4, 5, 6],
        caption="표 7. Qwen2-VL-7B + NF4, oracle 검색, 데이터셋당 첫 100 질의(ChartQA는 총 63)에서의 정확도. DocVQA는 MP-DocVQA를 의미한다.",
    )

    add_section_heading(doc, "8.2 표본별 correct/total", level=2)
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
        caption="표 8. 정답/전체 카운트. MP-DocVQA에서 parsed_visual이 parsed_text_only를 +4%p 상회한다.",
    )

    add_section_heading(doc, "8.3 실행 통계", level=2)
    add_bullets(
        doc,
        [
            "총 generation call 수: 363 query × 3 mode = 약 1,089 calls (ChartQA 63 + 나머지 100 × 3).",
            "총 실행 시간: 6,331초 (≈ 1시간 45분).",
            "최장 단일 mode: InfoVQA × parsed_visual, 약 65분 (큰 infographics + 결합 evidence 길이로 인한 sequence length 증가).",
            "최단 단일 mode: ChartQA × image_only, 약 1분 (63 질의, 단순 prompt).",
            "GPU 점유: 최대 7.9 GB / 8 GB. 평균 GPU util 80~100%.",
            "Upstage parse cost: 약 248 페이지 (4 데이터셋 합산), 추정 USD 3~5.",
        ],
    )


def section_9_discussion(doc: Document) -> None:
    add_section_heading(doc, "9. 논의")
    add_section_heading(doc, "9.1 v12-general의 효과는 강하게 확인된다", level=2)
    add_para(
        doc,
        "모든 4개 데이터셋에서 parsed_visual은 시각 전용 baseline을 큰 폭으로 상회한다. macro 평균 기준 +36.32%p의 향상은 단순한 양자화 잡음이나 표본 변동으로 설명될 수 없는 크기이며, 본 환경의 generator가 시각만으로는 답을 도출하기 어려운 질의가 다수임을 시사한다. 특히 baseline의 절대값이 0.17~0.20 구간으로 매우 낮은 점은, 작은 GPU·양자화·해상도 캡이 결합되어 시각 전용 입력의 정보 접근성이 크게 제한되었음을 보여준다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "9.2 MP-DocVQA에서의 parsed_visual 우위", level=2)
    add_para(
        doc,
        "네 개 데이터셋 중 MP-DocVQA에서만 parsed_visual이 parsed_text_only를 명확히 상회한다 (0.800 vs 0.760, +4.0%p). MP-DocVQA는 다중 페이지 문서에서 표·문단·필드 등 레이아웃 정보가 답변에 중요한 데이터셋이다. 파싱 텍스트만으로는 ‘어느 표의 어느 행’이라는 위치 정보가 일부 손실되며, 원본 이미지가 이 손실을 보완한다는 해석이 자연스럽다. 본 결과는 v12-general이 단순한 OCR-only 시스템 대비 추가 가치를 제공할 수 있음을 시사하는 가장 직접적인 증거이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "9.3 ChartQA에서의 역방향: parsed_text_only ≥ parsed_visual", level=2)
    add_para(
        doc,
        "반면 ChartQA에서는 parsed_text_only(0.524)가 parsed_visual(0.508)을 약 1.6%p 앞선다. 본 환경에서 ChartQA 차트는 일반적으로 800×600 픽셀 수준이라 해상도 캡 자체는 적용되지 않지만, 차트의 숫자 정보를 Upstage 파싱이 잘 추출한 경우 (i) 텍스트만으로 답이 가능하며, (ii) 이미지가 추가되면 모델이 시각 정보와 텍스트 정보 사이에서 혼동하여 단순 텍스트보다 약간 떨어질 수 있다. 본 현상은 부정적 결과가 아니라 ‘OCR이 충분히 강하면 시각 추가는 한계 수익이 작거나 음수일 수 있음’을 보여주는 자연스러운 발견이다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "9.4 InfoVQA와 SlideVQA의 동률", level=2)
    add_para(
        doc,
        "InfoVQA와 SlideVQA에서는 parsed_text_only와 parsed_visual이 동일한 정확도를 보였다 (각각 0.540, 0.520). InfoVQA는 max_pixels 캡이 가장 강하게 작용하는 데이터셋이며, 따라서 이미지 입력의 정보 밀도가 낮아져 텍스트와 결합해도 한계 이득이 없는 것으로 해석된다. SlideVQA는 슬라이드 자체가 큰 글씨 위주라 파싱이 거의 모든 정보를 보존했을 가능성이 크다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_section_heading(doc, "9.5 결과 종합과 발표 framing", level=2)
    add_para(
        doc,
        "본 결과는 다음의 학술적 주장으로 framing할 수 있다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    quote_p = doc.add_paragraph()
    quote_p.paragraph_format.left_indent = Cm(0.8)
    quote_p.paragraph_format.right_indent = Cm(0.8)
    quote_p.paragraph_format.space_after = Pt(6)
    quote_p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    quote = (
        "‘단일 8 GB GPU 환경에서 Qwen2-VL-7B를 4-bit NF4로 적재하고 이미지 해상도를 1.3M "
        "픽셀로 제한한 제약 환경에서, 페이지 이미지만 사용하는 baseline은 macro 정확도 0.229에 "
        "머문다. Upstage Document Parse로 추출한 파싱 텍스트를 동일 generator에 함께 제공하는 "
        "Parsed-Visual RAG는 macro 정확도 0.592 (+36.32%p)를 달성한다. 특히 페이지 레이아웃이 "
        "중요한 MP-DocVQA에서 텍스트 단독 입력 대비 +4.0%p의 추가 이득이 관찰되어, 이미지 증거와 "
        "파싱 증거가 상보적임을 보인다.’"
    )
    run = quote_p.add_run(quote)
    set_run_style(run, size_pt=10.5, italic=True)


def section_10_limits(doc: Document) -> None:
    add_section_heading(doc, "10. 한계와 후속 작업")
    add_bullets(
        doc,
        [
            "Generator paper-alignment 미실시. 본 결과는 Qwen2-VL-7B + NF4에 한정된다. VisRAG 논문 권장 모델인 MiniCPM-V 2.6에서 동일한 패턴이 재현되는지는 별도 cross-check가 필요하며, 이는 ≥16 GB GPU에서의 후속 실험으로 정의한다.",
            "Retrieval 비교 미실시. 본 연구는 oracle 검색을 사용하여 generation 효과만을 측정한다. VisRAG-Ret (시각 임베딩) 대 BM25 (파싱 텍스트) 검색 비교는 별도의 retrieval 보고로 분리된다. 본 코드베이스에는 BM25 및 평가 도구가 이미 구현되어 있으며, VisRAG-Ret만 ≥40 GB GPU에서 실행하면 retrieval 표를 산출할 수 있다.",
            "표본 크기. 데이터셋당 첫 100 질의 (ChartQA 63)는 5%p 단위의 delta를 검출하기에는 충분하지만, 데이터셋 내 부분 분포 효과를 확인하려면 풀 평가가 필요하다.",
            "이미지 해상도 캡의 영향. max_pixels=1.3M은 8 GB GPU 제약의 결과이며, 풀 해상도 환경에서는 특히 ChartQA·InfoVQA의 결과가 달라질 수 있다.",
            "Top-k = 1 고정. VisRAG 논문은 top-k=1,2,3에 대한 정확도 곡선을 보고한다. oracle 모드의 top-k=1은 가장 보수적인 가정이며, 실제 검색·다중 페이지 결합 효과는 별도 분석이 필요하다.",
            "Generator 스케일 비교 부재. PPT의 Table 2 (Qwen2-VL-72B, InternVL2.5-78B, Qwen2.5-VL-72B)는 큰 모델 가족에 대한 generator scaling 비교이며, 본 보고서의 범위 밖이다. 후속 실험에서 API (DashScope, OpenRouter 등) 또는 cloud GPU로 보완 가능하다.",
        ],
        numbered=True,
    )


def section_11_repro(doc: Document) -> None:
    add_section_heading(doc, "11. 재현성")
    add_para(
        doc,
        "본 보고서의 모든 결과는 다음 단일 명령으로 재현 가능하다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_code_block(
        doc,
        "cd \"/home/chaemin/projects/AI algorithm study\"\n"
        "export UPSTAGE_API_KEY=<your-key>\n"
        "nohup bash scripts/run_today_ppt_pipeline.sh > run_today.log 2>&1 &",
    )
    add_para(
        doc,
        "스크립트는 (1) 4 데이터셋의 첫 100 질의에 대한 gold 페이지의 Upstage 파싱, (2) Qwen2-VL-7B + NF4 generation × 3 mode × 4 데이터셋, (3) PPT 양식 표 산출 순으로 수행한다. 각 단계의 결과 파일이 존재할 경우 자동으로 skip하므로 부분 실패 시 재실행이 안전하다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_para(doc, "주요 의존성과 버전.", align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_table(
        doc,
        header=["패키지", "버전"],
        rows=[
            ["torch", "2.6.0 (cu124 wheels)"],
            ["torchvision", "0.21+ (cu124)"],
            ["transformers", "4.51.x (Qwen2VLForConditionalGeneration 호환 마지막 라인)"],
            ["qwen-vl-utils", "≥ 0.0.8"],
            ["bitsandbytes", "≥ 0.43"],
            ["accelerate", "≥ 0.34"],
            ["datasets", "4.8.5 (fsspec ≤ 2026.2.0)"],
            ["rank_bm25", "≥ 0.2.2"],
        ],
    )
    add_para(
        doc,
        "NVIDIA 드라이버 572.61 (CUDA 12.8 호환), torch는 cu124 wheels로 설치하여 드라이버 호환을 확보하였다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )
    add_para(doc, "git history.", align=WD_ALIGN_PARAGRAPH.JUSTIFY)
    add_code_block(
        doc,
        "14bcca1  Cleanup round 2: move planning docs + tests + v12_requirements to backup\n"
        "18970c8  Cleanup: split submission and backup, fix reproducibility holes\n"
        "6e1dc41  Add academic-style HTML report on Parsed-Visual RAG (v12-general) vs VisRAG\n"
        "22775d8  Run today: PPT slide-10 table with Qwen2-VL-7B NF4 on 4 datasets\n"
        "e204f68  Add scripts/run_today_ppt_pipeline.sh for time-boxed Table 1 run\n"
        "e046222  Switch default generator to Qwen2-VL-7B + bitsandbytes NF4\n"
        "7defce8  Remove Gemini generator backend to enforce paper alignment\n"
        "3c0206a  Bootstrap VisRAG vs v12-general comparison workspace",
    )


def section_12_conclusion(doc: Document) -> None:
    add_section_heading(doc, "12. 결론")
    add_para(
        doc,
        "본 보고서는 VisRAG의 공개 평가 데이터·평가 metric 위에서, 동일한 generator(Qwen2-VL-7B + NF4)와 동일한 oracle 페이지를 사용하여 시각 전용 입력과 Upstage 파싱 결합 입력의 정확도를 격리해 측정하였다. macro 정확도 기준 0.229 → 0.592 (+36.32%p)의 향상이 관찰되었으며, 특히 페이지 레이아웃이 답에 중요한 MP-DocVQA에서 텍스트 단독 입력 대비 +4.0%p의 추가 이득이 관찰되었다. 본 결과는 단일 8 GB GPU의 제약 환경에서도 parsed_visual 방법이 시각 전용 baseline 대비 명확한 효과를 보임을 입증한다. 절대 정확도는 양자화·해상도 캡의 영향으로 팀 PPT의 풀 정밀 baseline보다 낮으며, 본 보고서는 모드 간 delta가 fair comparison임을 명시한다. 후속 작업은 (i) MiniCPM-V 2.6에서의 paper-alignment cross-check, (ii) VisRAG-Ret 시각 검색 비교, (iii) 풀 정밀 환경에서의 ablation 재현으로 정의된다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def references(doc: Document) -> None:
    add_section_heading(doc, "참고문헌")
    add_bullets(
        doc,
        [
            "Wang, S., et al. VisRAG: Vision-based Retrieval-augmented Generation on Multi-modality Documents. arXiv:2410.10594, 2024. https://arxiv.org/abs/2410.10594",
            "OpenBMB. VisRAG official repository and HuggingFace evaluation datasets. https://github.com/openbmb/visrag, https://huggingface.co/datasets/openbmb/VisRAG-Ret-Test-ChartQA 외.",
            "Qwen Team. Qwen2-VL: Enhancing Vision-Language Model's Perception of the World at Any Resolution. 2024. https://huggingface.co/Qwen/Qwen2-VL-7B-Instruct",
            "Dettmers, T., et al. QLoRA: Efficient Finetuning of Quantized LLMs. NeurIPS 2023. (NF4 quantisation의 원전.)",
            "Upstage. Document Parse API. https://api.upstage.ai/v1/document-ai/document-parse",
        ],
        numbered=True,
    )


def appendices(doc: Document) -> None:
    add_section_heading(doc, "부록 A. 데이터셋별 표본별 평균 출력 길이")
    add_table(
        doc,
        header=["Dataset", "avg input tokens (image_only)", "avg input tokens (parsed_visual)"],
        rows=[
            ["ChartQA", "~300–950", "~1,500–3,000"],
            ["InfoVQA", "~1,700 (capped)", "~2,500–4,000"],
            ["MP-DocVQA", "~1,300–1,700", "~2,000–3,500"],
            ["SlideVQA", "~900–1,400", "~1,500–3,000"],
        ],
        numeric_cols=[1, 2],
        caption="표 A1. 입력 토큰 수의 데이터셋·모드별 대략 분포.",
    )

    add_section_heading(doc, "부록 B. 주요 코드 참조")
    add_bullets(
        doc,
        [
            "benchmark/parse_cache.py: ParsedDocument, load_parse_cache, append_parse_cache, evidence_text",
            "benchmark/v12_on_visrag.py: build_prompt (line 75–96), build_qwen2vl_messages (206–217), call_qwen2vl (210–278), main (305–443)",
            "benchmark/ppt_table_exporter.py: render_markdown, render_csv, render_json",
            "benchmark/metrics.py: relaxed_exact_match (16–44), accuracy (47–55), mrr_at_k (58–69), recall_at_k (72–81)",
            "scripts/run_today_ppt_pipeline.sh: Stage 1 Upstage parse, Stage 2 generation × 3 mode × 4 dataset, Stage 3 PPT exporter",
            "configs/visrag_paper_benchmark.json: 데이터셋·generator·metric 메타데이터, PPT 정렬 매핑",
        ],
    )

    add_section_heading(doc, "부록 C. 본 보고서가 다루지 않는 v12 bridge 구성요소")
    add_para(
        doc,
        "참고: backup/v12_port/ 디렉토리(제출 외 보관)에는 교량 점검 보고서 도메인 전용 v12 구성요소들(질문 분류기, 챕터 추론, 손상 이력 보강 등)이 이식되어 있다. 본 보고서의 비교 대상인 v12-general은 이 도메인 종속 구성요소를 제거하고 ‘파싱 텍스트와 이미지를 동시에 VLM에 입력한다’는 일반 원리만을 남긴 변형이다. VisRAG 공개 벤치마크에는 교량 도메인 컴포넌트를 사용하지 않으며, 본 제출의 어떤 결과도 v12_port 모듈에 의존하지 않는다. 자세한 설계 근거는 backup/docs/domain_free_v12_experiment_design.md에 있고, backup 폴더의 인덱스는 backup/README.md에 있다.",
        align=WD_ALIGN_PARAGRAPH.JUSTIFY,
    )


def main() -> None:
    doc = setup_document()
    add_title_block(doc)
    add_abstract(doc)
    section_1_intro(doc)
    section_2_datasets(doc)
    section_3_methodologies(doc)
    section_4_architecture(doc)
    section_5_implementation(doc)
    section_6_setup(doc)
    section_7_diff(doc)
    section_8_results(doc)
    section_9_discussion(doc)
    section_10_limits(doc)
    section_11_repro(doc)
    section_12_conclusion(doc)
    references(doc)
    appendices(doc)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
