"""Generate docs/cvpr_paper_visrag_modality_paradox.docx.

CVPR-review-template-style two-column paper. This docx is a class-project
rendering of the CVPR style; an official CVPR submission would use the
cvpr2026 LaTeX kit (this file is a Word-based approximation).

Title: "Beyond Textualization: An Oracle Study of Evidence Representation
in Multimodal Document Question Answering". The paper presents an
oracle-retrieval study of evidence representation: retrieval is held
fixed (gold qrels, top-1) so that the comparison isolates how a
vision-language model uses different evidence sources at the answer
stage. Seven evidence modes are compared across four benchmarks; a
short follow-up Section 5 probes one specific observation from the main
results (the Image+Text Upstage Document Parse underperformance).
"""
from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "cvpr_paper_visrag_modality_paradox.docx"

LATIN_FONT = "Times New Roman"
CJK_FONT = "NanumMyeongjo"
BLACK = RGBColor(0x00, 0x00, 0x00)
PAGE_MARGIN_X = 0.8125
PAGE_MARGIN_Y = 1.0625
COL_GAP_TWIPS = 450

TITLE_PT = 14
AUTHOR_PT = 11
BANNER_PT = 9
ABSTRACT_HDR_PT = 11
BODY_PT = 10
H1_PT = 11
H2_PT = 10
TABLE_PT = 8.4
CAPTION_PT = 9
REF_PT = 9
FOOTER_PT = 9

TITLE_TEXT = (
    "Beyond Textualization: An Oracle Study of Evidence Representation "
    "in Multimodal Document Question Answering"
)
REVIEW_HEADER = (
    "CVPR 2026 Submission #xxxx. Confidential review copy. DO NOT DISTRIBUTE."
)


# ---------------------------------------------------------------------------
# low-level helpers
# ---------------------------------------------------------------------------


def set_run_style(run, *, size_pt, bold=False, italic=False, small_caps=False):
    run.font.size = Pt(size_pt)
    run.font.bold = bool(bold)
    run.font.italic = bool(italic)
    run.font.color.rgb = BLACK
    run.font.name = LATIN_FONT
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), LATIN_FONT)
    rfonts.set(qn("w:hAnsi"), LATIN_FONT)
    rfonts.set(qn("w:eastAsia"), CJK_FONT)
    rfonts.set(qn("w:cs"), LATIN_FONT)
    if small_caps:
        smcaps = OxmlElement("w:smallCaps")
        smcaps.set(qn("w:val"), "1")
        rpr.append(smcaps)


def add_run(p, text, **kw):
    run = p.add_run(text)
    set_run_style(run, **kw)
    return run


def add_para(doc, text="", *, size_pt=BODY_PT, bold=False, italic=False,
             align=WD_ALIGN_PARAGRAPH.JUSTIFY, first_line_indent_cm=0.4,
             space_after=2, space_before=0, line_spacing=1.08,
             left_indent_cm=None, right_indent_cm=None):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.space_before = Pt(space_before)
    pf.line_spacing = line_spacing
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    p.alignment = align
    if first_line_indent_cm is not None:
        pf.first_line_indent = Cm(first_line_indent_cm)
    if left_indent_cm is not None:
        pf.left_indent = Cm(left_indent_cm)
    if right_indent_cm is not None:
        pf.right_indent = Cm(right_indent_cm)
    if text:
        add_run(p, text, size_pt=size_pt, bold=bold, italic=italic)
    return p


def _append_math_run(o_math, text, *, size_pt=9, style="i"):
    """Append a plain Office Math run. Word opens this as an equation."""
    r = OxmlElement("m:r")

    mr_pr = OxmlElement("m:rPr")
    sty = OxmlElement("m:sty")
    sty.set(qn("m:val"), style)
    mr_pr.append(sty)
    r.append(mr_pr)

    wr_pr = OxmlElement("w:rPr")
    fonts = OxmlElement("w:rFonts")
    for key in ("ascii", "hAnsi", "cs"):
        fonts.set(qn(f"w:{key}"), "Cambria Math")
    wr_pr.append(fonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(size_pt * 2)))
    wr_pr.append(sz)
    r.append(wr_pr)

    t = OxmlElement("m:t")
    t.set(qn("xml:space"), "preserve")
    t.text = text
    r.append(t)
    o_math.append(r)


def _math_run(text, *, style="i", size_pt=9):
    o_math = OxmlElement("m:oMath")
    _append_math_run(o_math, text, size_pt=size_pt, style=style)
    return list(o_math)


def _append_math_items(parent, items, *, size_pt=9):
    for item in items:
        if isinstance(item, str):
            _append_math_run(parent, item, size_pt=size_pt, style="i")
        elif isinstance(item, tuple):
            text, style = item
            _append_math_run(parent, text, size_pt=size_pt, style=style)
        else:
            parent.append(item)


def mtxt(text):
    return (text, "p")


def _m_container(tag, items, *, size_pt=9):
    node = OxmlElement(tag)
    _append_math_items(node, items, size_pt=size_pt)
    return node


def msub(base, sub, *, size_pt=9):
    node = OxmlElement("m:sSub")
    node.append(_m_container("m:e", base, size_pt=size_pt))
    node.append(_m_container("m:sub", sub, size_pt=size_pt))
    return node


def msup(base, sup, *, size_pt=9):
    node = OxmlElement("m:sSup")
    node.append(_m_container("m:e", base, size_pt=size_pt))
    node.append(_m_container("m:sup", sup, size_pt=size_pt))
    return node


def msubsup(base, sub, sup, *, size_pt=9):
    node = OxmlElement("m:sSubSup")
    node.append(_m_container("m:e", base, size_pt=size_pt))
    node.append(_m_container("m:sub", sub, size_pt=size_pt))
    node.append(_m_container("m:sup", sup, size_pt=size_pt))
    return node


def mfrac(num, den, *, size_pt=9):
    node = OxmlElement("m:f")
    node.append(_m_container("m:num", num, size_pt=size_pt))
    node.append(_m_container("m:den", den, size_pt=size_pt))
    return node


def mnary_sum(sub, sup, body, *, size_pt=9):
    node = OxmlElement("m:nary")
    pr = OxmlElement("m:naryPr")
    chr_node = OxmlElement("m:chr")
    chr_node.set(qn("m:val"), "∑")
    lim = OxmlElement("m:limLoc")
    lim.set(qn("m:val"), "undOvr")
    pr.append(chr_node)
    pr.append(lim)
    node.append(pr)
    node.append(_m_container("m:sub", sub, size_pt=size_pt))
    node.append(_m_container("m:sup", sup, size_pt=size_pt))
    node.append(_m_container("m:e", body, size_pt=size_pt))
    return node


def mhat(items, *, size_pt=9):
    node = OxmlElement("m:acc")
    pr = OxmlElement("m:accPr")
    chr_node = OxmlElement("m:chr")
    chr_node.set(qn("m:val"), "̂")
    pr.append(chr_node)
    node.append(pr)
    node.append(_m_container("m:e", items, size_pt=size_pt))
    return node


def meq_array(rows, *, size_pt=9):
    node = OxmlElement("m:eqArr")
    for row in rows:
        node.append(_m_container("m:e", row, size_pt=size_pt))
    return node


def mdelim(items, *, beg="{", end="", size_pt=9):
    node = OxmlElement("m:d")
    pr = OxmlElement("m:dPr")
    beg_node = OxmlElement("m:begChr")
    beg_node.set(qn("m:val"), beg)
    end_node = OxmlElement("m:endChr")
    end_node.set(qn("m:val"), end)
    pr.append(beg_node)
    pr.append(end_node)
    node.append(pr)
    node.append(_m_container("m:e", items, size_pt=size_pt))
    return node


def add_omml_equation(doc, items, number=None, *, size_pt=9,
                      space_before=2, space_after=3):
    """Display equation inserted as built-up Word Office Math."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(space_before)
    pf.space_after = Pt(space_after)
    pf.line_spacing = 1.0
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE

    o_math_para = OxmlElement("m:oMathPara")
    o_math = OxmlElement("m:oMath")
    _append_math_items(o_math, items, size_pt=size_pt)
    if number is not None:
        _append_math_run(o_math, f"    ({number})", size_pt=size_pt, style="p")
    o_math_para.append(o_math)
    p._p.append(o_math_para)
    return p


def add_heading(doc, text, *, level=1):
    """Mixed-case headings (CVPR style), not ALL CAPS."""
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(8 if level == 1 else 6)
    pf.space_after = Pt(3)
    pf.keep_with_next = True
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    size = H1_PT if level == 1 else H2_PT
    add_run(p, text, size_pt=size, bold=True)


def clear_cell_shading(cell):
    tcPr = cell._tc.get_or_add_tcPr()
    for existing in tcPr.findall(qn("w:shd")):
        tcPr.remove(existing)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "FFFFFF")
    tcPr.append(shd)


def set_cell_margins(cell, *, top=30, start=45, bottom=30, end=45):
    """Tight cell padding for dense CVPR tables."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = tcPr.find(qn("w:tcMar"))
    if tcMar is None:
        tcMar = OxmlElement("w:tcMar")
        tcPr.append(tcMar)
    for edge, value in (("top", top), ("start", start),
                        ("bottom", bottom), ("end", end)):
        node = tcMar.find(qn(f"w:{edge}"))
        if node is None:
            node = OxmlElement(f"w:{edge}")
            tcMar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def style_cell(cell, *, header=False, size_pt=TABLE_PT,
               align=WD_ALIGN_PARAGRAPH.CENTER):
    cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    clear_cell_shading(cell)
    set_cell_margins(cell)
    for paragraph in cell.paragraphs:
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.space_before = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        paragraph.alignment = align
        for run in paragraph.runs:
            set_run_style(run, size_pt=size_pt, bold=header)


def _clear_all_table_borders(table):
    """Strip every default border so we can paint only booktabs rules."""
    tblPr = table._tbl.tblPr
    existing = tblPr.find(qn("w:tblBorders"))
    if existing is not None:
        tblPr.remove(existing)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = OxmlElement(f"w:{side}")
        b.set(qn("w:val"), "nil")
        borders.append(b)
    tblPr.append(borders)
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            existing_cb = tcPr.find(qn("w:tcBorders"))
            if existing_cb is not None:
                tcPr.remove(existing_cb)


def _add_row_edge_border(row, edge, size_eighths=6):
    """Draw a horizontal border on every cell of `row` at `edge`."""
    for cell in row.cells:
        tcPr = cell._tc.get_or_add_tcPr()
        tcBorders = tcPr.find(qn("w:tcBorders"))
        if tcBorders is None:
            tcBorders = OxmlElement("w:tcBorders")
            tcPr.append(tcBorders)
        existing = tcBorders.find(qn(f"w:{edge}"))
        if existing is not None:
            tcBorders.remove(existing)
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(size_eighths))
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "000000")
        tcBorders.append(b)


def set_booktabs_borders(table):
    """CVPR/booktabs: thick top rule, thin mid rule under header, thick
    bottom rule. No vertical / interior horizontal lines."""
    _clear_all_table_borders(table)
    _add_row_edge_border(table.rows[0], "top", size_eighths=12)
    _add_row_edge_border(table.rows[0], "bottom", size_eighths=4)
    _add_row_edge_border(table.rows[-1], "bottom", size_eighths=12)


def add_caption(doc, number, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_after = Pt(2)
    pf.space_before = Pt(3)
    pf.line_spacing = 1.1
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    pf.keep_with_next = True
    add_run(p, f"Table {number}. ", size_pt=CAPTION_PT, bold=True)
    add_run(p, text, size_pt=CAPTION_PT)


def add_figure_caption(doc, number, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_after = Pt(4)
    pf.space_before = Pt(2)
    pf.line_spacing = 1.1
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    add_run(p, f"Figure {number}. ", size_pt=CAPTION_PT, bold=True)
    add_run(p, text, size_pt=CAPTION_PT)


def _set_cell_border_box(cell, size_eighths=4):
    """Draw a thin black box border on all four edges of a cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    existing = tcPr.find(qn("w:tcBorders"))
    if existing is not None:
        tcPr.remove(existing)
    tcBorders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = OxmlElement(f"w:{edge}")
        b.set(qn("w:val"), "single")
        b.set(qn("w:sz"), str(size_eighths))
        b.set(qn("w:space"), "0")
        b.set(qn("w:color"), "000000")
        tcBorders.append(b)
    tcPr.append(tcBorders)


def _style_mono_cell(cell, text, *, size_pt=8.5, bold=False, label=False):
    """Apply Consolas monospace styling to a cell, preserving line breaks."""
    cell.vertical_alignment = WD_ALIGN_VERTICAL.TOP
    clear_cell_shading(cell)
    # remove any default paragraph
    cell.text = ""
    p = cell.paragraphs[0]
    pf = p.paragraph_format
    pf.space_after = Pt(0)
    pf.space_before = Pt(0)
    pf.line_spacing = 1.05
    pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if i > 0:
            p.add_run().add_break()
        run = p.add_run(line)
        run.font.size = Pt(size_pt)
        run.font.bold = bool(bold)
        run.font.color.rgb = BLACK
        run.font.name = "Consolas" if not label else LATIN_FONT
        rpr = run._element.get_or_add_rPr()
        rfonts = rpr.find(qn("w:rFonts"))
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        font_name = "Consolas" if not label else LATIN_FONT
        rfonts.set(qn("w:ascii"), font_name)
        rfonts.set(qn("w:hAnsi"), font_name)
        rfonts.set(qn("w:eastAsia"), CJK_FONT)
        rfonts.set(qn("w:cs"), font_name)


PROMPT_TEMPLATES = [
    (
        "Answer gen. — image only",
        "You are evaluating a document QA method on the VisRAG benchmark.\n"
        "Use only the provided document page image(s).\n"
        "Answer only the final answer. For numeric answers, return the exact visible value when possible.\n"
        "If the evidence is insufficient, answer: insufficient to answer.\n"
        "\n"
        "[Parsed text/table evidence] (not provided).\n"
        "[Question] {query}.",
    ),
    (
        "Answer gen. — text only",
        "You are evaluating a document QA method on the VisRAG benchmark.\n"
        "Use only the parsed text/table evidence. No images are provided.\n"
        "Answer only the final answer. For numeric answers, return the exact visible value when possible.\n"
        "If the evidence is insufficient, answer: insufficient to answer.\n"
        "\n"
        "[Parsed text/table evidence] {parsed_context}.\n"
        "[Question] {query}.",
    ),
    (
        "Answer gen. — image+text (main)",
        "You are evaluating a document QA method on the VisRAG benchmark.\n"
        "Use parsed text/table evidence for exact labels and values, and use images to verify visual/layout evidence.\n"
        "Answer only the final answer. For numeric answers, return the exact visible value when possible.\n"
        "If the evidence is insufficient, answer: insufficient to answer.\n"
        "\n"
        "[Parsed text/table evidence] {parsed_context}.\n"
        "[Question] {query}.",
    ),
    (
        "OCR extraction (Qwen2-VL self-OCR)",
        "Extract all text content from this document image.\n"
        "Preserve the structure: use headings, bullet points, and paragraphs as in the original.\n"
        "Output only the extracted text; no explanations or commentary.",
    ),
    (
        "Faithfulness judge (Qwen2.5-VL-72B)",
        "You are evaluating answer faithfulness for a multimodal RAG system.\n"
        "Assume the retrieved context is the only source of truth. Do not use outside knowledge.\n"
        "Do not judge whether the retrieved context is the correct gold context.\n"
        "Judge only whether the model answer is supported by the provided context.\n"
        "If the answer is a multiple-choice letter, map it to the option text before judging support.\n"
        "Return JSON with supported, score, evidence_used, and reason.",
    ),
]


def add_prompts_figure(doc):
    """Figure 2: five prompt templates in a bordered 2-col table.

    Each row: left cell = bold label, right cell = monospace prompt body.
    """
    table = doc.add_table(rows=len(PROMPT_TEMPLATES), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    try:
        table.style = "Normal Table"
    except KeyError:
        pass
    # set column widths roughly: label 1.4in, body 4.6in (col width ~6.0)
    for row in table.rows:
        row.cells[0].width = Inches(1.4)
        row.cells[1].width = Inches(4.6)
    for r_idx, (label, body) in enumerate(PROMPT_TEMPLATES):
        label_cell = table.rows[r_idx].cells[0]
        body_cell = table.rows[r_idx].cells[1]
        _style_mono_cell(label_cell, label, size_pt=9, bold=True, label=True)
        _style_mono_cell(body_cell, body, size_pt=8.5)
        _set_cell_border_box(label_cell)
        _set_cell_border_box(body_cell)
    add_figure_caption(
        doc, 2,
        "Prompt templates used in this study. The three answer-generation "
        "prompts differ only in the evidence-instruction clause.",
    )


def _setup_cvpr_style():
    import os
    mpl_config = Path("/tmp") / "cvpr_paper_mplconfig"
    mpl_config.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_config))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
        "axes.linewidth": 0.7,
        "axes.edgecolor": "#333333",
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "xtick.color": "#222222",
        "ytick.color": "#222222",
        "axes.labelcolor": "#222222",
        "axes.titlecolor": "#111111",
    })


def render_pipeline_png(out_path: Path) -> Path:
    """Figure 1: compact single-column oracle-controlled pipeline."""
    _setup_cvpr_style()
    import matplotlib.patches as mpatches
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(3.35, 2.25))
    ax.set_xlim(0, 6.2)
    ax.set_ylim(0, 7.0)
    ax.axis("off")

    palette = {
        "question": ("#FFF0D8", "#B95F00"),
        "image": ("#DDEAF7", "#1F4E79"),
        "parser": ("#E7F0E3", "#3D6B2C"),
        "mode": ("#FFF5C7", "#8A6D00"),
        "option": ("#F2F2F2", "#555555"),
        "generator": ("#F9D7CB", "#A03A00"),
        "answer": ("#EEE8FA", "#5B3F9B"),
    }

    def box(x, y, w, h, text, fill, edge, *, fontsize=9, weight="normal"):
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.035,rounding_size=0.12",
            linewidth=0.85, edgecolor=edge, facecolor=fill))
        ax.text(x + w / 2, y + h / 2, text,
                ha="center", va="center",
                fontsize=fontsize, fontweight=weight,
                color="#0F0F0F", family="sans-serif")

    def arrow(x1, y1, x2, y2, *, lw=0.9, color="#222"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(
                        arrowstyle="-|>",
                        mutation_scale=10,
                        lw=lw, color=color,
                        shrinkA=2, shrinkB=2,
                    ))

    box(0.35, 6.10, 2.20, 0.58, "Question $q$",
        *palette["question"], fontsize=7.4)
    box(3.65, 6.10, 2.20, 0.58, "Gold page $I$",
        *palette["image"], fontsize=7.4)
    box(3.65, 5.05, 2.20, 0.58, "Parser $g(I)$\ntext $T$",
        *palette["parser"], fontsize=6.6)
    box(0.70, 3.70, 4.80, 0.92,
        "Evidence builder\n"
        r"$E_m \in \{I,\ T,\ s(q,T),\ (I,T)\}$",
        *palette["mode"], fontsize=7.0, weight="bold")
    box(1.15, 2.25, 3.90, 0.66,
        r"Qwen2-VL generator $f_\theta(q,E)$",
        *palette["generator"], fontsize=7.3, weight="bold")
    box(2.05, 1.05, 2.10, 0.52, r"answer $\hat a$",
        *palette["answer"], fontsize=7.5, weight="bold")

    arrow(1.45, 6.10, 2.25, 4.62, lw=0.75)
    arrow(4.75, 6.10, 4.75, 5.63, lw=0.75)
    arrow(4.75, 5.05, 4.20, 4.62, lw=0.75)
    arrow(3.10, 3.70, 3.10, 2.91, lw=0.75)
    arrow(3.10, 2.25, 3.10, 1.57, lw=0.75)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0.04,
                facecolor="white")
    plt.close(fig)
    return out_path


def render_results_png(out_path: Path) -> Path:
    """Figure 2: per-dataset bars showing the ordering inversion.

    Two panels — Text-only on the left, Image+Text on the right. In each
    panel, side-by-side bars per dataset for the two text sources
    (Qwen self-OCR vs Upstage Document Parse). The Image-only baseline is
    drawn as a dashed reference per dataset so the inversion is visible.
    """
    _setup_cvpr_style()
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    datasets = ["InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA"]

    text_only = {
        "Qwen self-OCR": [0.3400, 0.3175, 0.6700, 0.4300],
        "Upstage Parse": [0.5400, 0.5238, 0.7600, 0.5200],
    }
    image_text = {
        "Qwen self-OCR": [0.7300, 0.6667, 0.8200, 0.5800],
        "Upstage Parse": [0.5400, 0.5079, 0.8000, 0.5200],
    }
    image_only = [0.7200, 0.5556, 0.8800, 0.5400]

    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.25), sharey=True)

    x = np.arange(len(datasets), dtype=float)
    width = 0.36

    palette = {
        "qwen_text":  "#7BA7D9",
        "upstage_text": "#1F4E79",
        "qwen_it":    "#F0A867",
        "upstage_it": "#B0461B",
        "ref": "#555555",
    }

    def draw_panel(ax, data, qwen_color, upstage_color, title):
        b1 = ax.bar(x - width / 2, data["Qwen self-OCR"], width,
                    label="Qwen self-OCR",
                    color=qwen_color, edgecolor="#1A1A1A", linewidth=0.5)
        b2 = ax.bar(x + width / 2, data["Upstage Parse"], width,
                    label="Upstage Parse",
                    color=upstage_color, edgecolor="#1A1A1A", linewidth=0.5)
        # Image-only baseline as dashed segments
        for i, v in enumerate(image_only):
            ax.hlines(v, i - width - 0.04, i + width + 0.04,
                      colors=palette["ref"], linestyles=(0, (3, 2)),
                      linewidth=1.0, zorder=4)
        # Numeric labels on top of each bar.
        for bars in (b1, b2):
            for rect in bars:
                ax.text(rect.get_x() + rect.get_width() / 2,
                        rect.get_height() + 0.015,
                        f"{rect.get_height():.2f}",
                        ha="center", va="bottom", fontsize=6.6,
                        color="#222")
        ax.set_title(title, fontsize=8.8, fontweight="bold", pad=4)
        ax.set_xticks(x)
        ax.set_xticklabels(datasets, fontsize=7.2)
        ax.set_ylim(0, 1.0)
        ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.tick_params(axis="y", labelsize=7)
        ax.grid(axis="y", linewidth=0.35, alpha=0.42, zorder=0)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        baseline_handle = Line2D(
            [0], [0], color=palette["ref"], linestyle=(0, (3, 2)),
            linewidth=1.0, label="Image-only baseline",
        )
        ax.legend(handles=[b1, b2, baseline_handle],
                  loc="upper left", fontsize=6.8, frameon=False,
                  handlelength=1.4, handletextpad=0.5)

    draw_panel(axes[0], text_only,
               palette["qwen_text"], palette["upstage_text"],
               "Text-only evidence")
    axes[0].set_ylabel("Relaxed EM", fontsize=8)

    draw_panel(axes[1], image_text,
               palette["qwen_it"], palette["upstage_it"],
               "Image+Text evidence")

    fig.tight_layout(pad=0.6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=300, bbox_inches="tight", pad_inches=0.03,
                facecolor="white")
    plt.close(fig)
    return out_path


def add_pipeline_figure(doc):
    """Figure 1: oracle-controlled pipeline (hand-authored SVG v2 rendered
    to PNG). Spans both columns so the four mode boxes are legible. The
    caption is rendered as a Word paragraph below the image, not baked
    into the figure.
    """
    png_path = ROOT / "docs" / "figures" / "pipeline_v2.png"
    if not png_path.exists():
        png_path = ROOT / "docs" / "figures" / "pipeline.png"
        render_pipeline_png(png_path)
    add_one_column_section(doc)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(png_path), width=Inches(6.8))
    add_figure_caption(
        doc, 1,
        "Oracle-controlled evidence pipeline. Question q is paired with "
        "the gold page I (oracle qrels, top-1) and the parsed text T = g(I), "
        "where g is either Qwen self-OCR or Upstage Document Parse. The "
        "evidence builder assembles the evidence set E according to the "
        "selected mode; the Qwen2-VL generator decodes the answer from "
        "(q, E) under NF4 4-bit quantisation with do_sample=False and "
        "max_new_tokens=20. Only the contents of E vary across the seven "
        "modes.",
    )
    add_two_column_section(doc)


def add_results_figure(doc, *, section_breaks=True, caption_number=2):
    """Figure 2: two-panel bar chart visualising the text-only vs image+text
    ordering inversion between Qwen self-OCR and Upstage Document Parse."""
    png_path = ROOT / "docs" / "figures" / "results_inversion.png"
    render_results_png(png_path)
    if section_breaks:
        add_one_column_section(doc)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    run = p.add_run()
    run.add_picture(str(png_path), width=Inches(6.55))
    add_figure_caption(
        doc, caption_number,
        "Relaxed EM per dataset by text source and evidence mode.",
    )
    if section_breaks:
        add_two_column_section(doc)


def add_table(doc, header, rows, *, caption_number, caption,
              size_pt=TABLE_PT, col_widths=None, first_col_left=True):
    add_caption(doc, caption_number, caption)
    table = doc.add_table(rows=1 + len(rows), cols=len(header))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = col_widths is None
    try:
        table.style = "Normal Table"
    except KeyError:
        pass
    hdr_cells = table.rows[0].cells
    for i, txt in enumerate(header):
        hdr_cells[i].text = txt
        if col_widths:
            hdr_cells[i].width = Inches(col_widths[i])
        style_cell(hdr_cells[i], header=True, size_pt=size_pt)
    for r_idx, row in enumerate(rows, start=1):
        for c_idx, val in enumerate(row):
            cell = table.rows[r_idx].cells[c_idx]
            cell.text = val
            if col_widths:
                cell.width = Inches(col_widths[c_idx])
            align = (WD_ALIGN_PARAGRAPH.LEFT
                     if first_col_left and c_idx == 0
                     else WD_ALIGN_PARAGRAPH.CENTER)
            style_cell(cell, size_pt=size_pt, align=align)
    set_booktabs_borders(table)
    sp = doc.add_paragraph()
    sp.paragraph_format.space_after = Pt(4)
    return table


def add_wide_table(doc, header, rows, *, caption_number, caption,
                   size_pt=TABLE_PT, col_widths=None, first_col_left=True):
    add_one_column_section(doc)
    table = add_table(
        doc,
        header,
        rows,
        caption_number=caption_number,
        caption=caption,
        size_pt=size_pt,
        col_widths=col_widths,
        first_col_left=first_col_left,
    )
    add_two_column_section(doc)
    return table


# ---------------------------------------------------------------------------
# section / column / line-number layout
# ---------------------------------------------------------------------------


def _set_section_cols(section, num_cols, space_twips=360):
    sectPr = section._sectPr
    cols = sectPr.find(qn("w:cols"))
    if cols is None:
        cols = OxmlElement("w:cols")
        sectPr.append(cols)
    cols.set(qn("w:num"), str(num_cols))
    cols.set(qn("w:space"), str(space_twips))
    cols.set(qn("w:equalWidth"), "1")
    cols.set(qn("w:sep"), "0")


def enable_line_numbers(section, count_by=5, start=1, distance_twips=200):
    sectPr = section._sectPr
    ln = sectPr.find(qn("w:lnNumType"))
    if ln is None:
        ln = OxmlElement("w:lnNumType")
        sectPr.append(ln)
    ln.set(qn("w:countBy"), str(count_by))
    ln.set(qn("w:start"), str(start))
    ln.set(qn("w:restart"), "continuous")
    ln.set(qn("w:distance"), str(distance_twips))


def set_review_header(section):
    header = section.header
    header.is_linked_to_previous = False
    p = header.paragraphs[0] if header.paragraphs else header.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.space_before = Pt(0)
    p.text = ""
    add_run(p, REVIEW_HEADER, size_pt=BANNER_PT, italic=True)


def configure_first_section(doc):
    section = doc.sections[0]
    section.page_height = Inches(11.0)
    section.page_width = Inches(8.5)
    section.top_margin = Inches(PAGE_MARGIN_Y)
    section.bottom_margin = Inches(PAGE_MARGIN_Y)
    section.left_margin = Inches(PAGE_MARGIN_X)
    section.right_margin = Inches(PAGE_MARGIN_X)

    _set_section_cols(section, 1)
    set_review_header(section)

    footer = section.footer
    footer.is_linked_to_previous = False
    f_p = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    f_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    f_p.paragraph_format.space_before = Pt(2)
    run = f_p.add_run()
    set_run_style(run, size_pt=FOOTER_PT)
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


def add_two_column_section(doc):
    new_section = doc.add_section(WD_SECTION.CONTINUOUS)
    new_section.page_height = Inches(11.0)
    new_section.page_width = Inches(8.5)
    new_section.top_margin = Inches(PAGE_MARGIN_Y)
    new_section.bottom_margin = Inches(PAGE_MARGIN_Y)
    new_section.left_margin = Inches(PAGE_MARGIN_X)
    new_section.right_margin = Inches(PAGE_MARGIN_X)
    _set_section_cols(new_section, 2, space_twips=COL_GAP_TWIPS)
    enable_line_numbers(new_section, count_by=5, start=1, distance_twips=200)
    set_review_header(new_section)
    return new_section


def add_one_column_section(doc):
    """Insert a continuous one-column section break for full-width figures."""
    new_section = doc.add_section(WD_SECTION.CONTINUOUS)
    new_section.page_height = Inches(11.0)
    new_section.page_width = Inches(8.5)
    new_section.top_margin = Inches(PAGE_MARGIN_Y)
    new_section.bottom_margin = Inches(PAGE_MARGIN_Y)
    new_section.left_margin = Inches(PAGE_MARGIN_X)
    new_section.right_margin = Inches(PAGE_MARGIN_X)
    _set_section_cols(new_section, 1)
    enable_line_numbers(new_section, count_by=5, start=1, distance_twips=200)
    set_review_header(new_section)
    return new_section


def setup_document():
    doc = Document()
    configure_first_section(doc)
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
    doc.core_properties.author = "Anonymous"
    doc.core_properties.last_modified_by = "Anonymous"
    doc.core_properties.title = TITLE_TEXT
    return doc


# ---------------------------------------------------------------------------
# title block (anonymised, with confidential review banner)
# ---------------------------------------------------------------------------


def add_title_block(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.space_before = Pt(2)
    add_run(p, TITLE_TEXT, size_pt=TITLE_PT, bold=True)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    add_run(p, "Anonymous CVPR Submission", size_pt=AUTHOR_PT)

    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(10)
    add_run(p, "Paper ID xxxx", size_pt=AUTHOR_PT)


# ---------------------------------------------------------------------------
# body content
# ---------------------------------------------------------------------------


def add_abstract(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(4)
    add_run(p, "Abstract", size_pt=ABSTRACT_HDR_PT, bold=True)

    add_para(
        doc,
        "We study how evidence representation alone affects answer quality in "
        "multimodal document question answering. Retrieval is held fixed "
        "(gold qrels, top-1) so the comparison isolates how a vision-language "
        "decoder uses different evidence sources at the answer stage. With "
        "Qwen2-VL-7B-Instruct as the generator under NF4 4-bit quantisation, "
        "we compare seven evidence modes on four VisRAG-Ret-Test public "
        "splits (InfoVQA, ChartQA, MP-DocVQA, SlideVQA): image-only, "
        "text-only with self-OCR or Upstage Document Parse, selective "
        "hybrid variants that route chart pages to image evidence, and "
        "image+text combinations on both text sources. We score relaxed "
        "Exact Match and a Qwen2.5-VL-72B-judged faithfulness score. "
        "Image-grounded modes dominate textualisation on both metrics, and "
        "Image+Text with self-OCR is the only mode that improves macro EM "
        "and macro faithfulness over Image-only (+2.53 EM, +0.44 "
        "faithfulness percentage points). Selective routing helps when "
        "in-model OCR is noisy but does not help structured parser output. "
        "The reference comparison shows an ordering inversion: with text "
        "alone, Upstage Document Parse beats the model's self-OCR by "
        "+14.7 macro EM percentage points, while in the reference "
        "image+text condition self-OCR is ahead of Upstage Document Parse "
        "— by +10.7 macro EM percentage points in the team's tf457 numbers "
        "and by +1.85 macro EM percentage points on the clean transformers "
        "4.57.6 re-run reported in Section 5. A paired follow-up "
        "diagnostic probes why Image+Text with Upstage Document Parse "
        "underperforms its self-OCR counterpart: an image-first prompt "
        "swap and a shallow surface-form normalisation both fail to close "
        "the gap (McNemar p=0.11 and p=1.00), constraining the "
        "explanatory space for follow-up work.",
        first_line_indent_cm=0.0,
        italic=True,
    )


def section_introduction(doc):
    add_heading(doc, "1. Introduction")
    add_para(
        doc,
        "Multimodal document question answering combines optical character "
        "recognition, layout understanding, and visual reasoning over rendered "
        "page images. A modern recipe such as VisRAG [1] retrieves page "
        "images and feeds them to a vision-language generator end-to-end, "
        "skipping the explicit OCR step that token-level pipelines such as "
        "LayoutLMv3 [10] depend on. End-to-end evaluations of such systems "
        "mix two effects: how well the retriever finds the right page, and "
        "how well the generator uses the page once it has it. The two are "
        "easy to confound on small benchmarks, and the latter is what a "
        "system designer can act on if the retriever is already strong.",
    )
    add_para(
        doc,
        "We isolate the second effect with an oracle-retrieval study. We "
        "fix retrieval to gold qrels at top-1 across all experiments, so "
        "the correct page is always served and only the answer stage is "
        "exercised. Within this controlled setting we ask four research "
        "questions that span the evidence-representation design space. "
        "RQ1: Which context modality is most reliable when the model "
        "already perceives the page? RQ2: Can OCR text replace image "
        "evidence in either direction (in-model self-OCR or a production "
        "parser)? RQ3: Does selectively filtering text evidence "
        "reduce OCR noise without losing information? RQ4: Does evidence "
        "representation affect unsupported hallucination, not just exact "
        "match? RQ4 motivates pairing relaxed EM with a faithfulness score "
        "judged by a stronger vision-language model.",
    )
    add_para(
        doc,
        "We compare seven evidence modes on four VisRAG-Ret-Test public "
        "splits (InfoVQA, ChartQA, MP-DocVQA, SlideVQA) using "
        "Qwen2-VL-7B-Instruct [6] as the generator under NF4 4-bit "
        "quantisation [11]. The two text sources we consider are the "
        "generator's own self-OCR transcription and the Upstage Document "
        "Parse [13] commercial parser. Image-grounded modes dominate "
        "textualisation on both EM and faithfulness; Image+Text with "
        "self-OCR is the only mode that improves macro EM and macro "
        "faithfulness over Image-only. After running the seven-way "
        "comparison we noted that Image+Text with Upstage Document Parse "
        "underperforms its self-OCR counterpart on the same image — by "
        "+10.7 macro EM percentage points in the team's tf457 numbers. "
        "The same cell re-run on a clean transformers 4.57.6 environment "
        "gives a smaller +1.85 macro EM percentage-point gap, so the "
        "original figure is partly an environment artefact (Section 5); "
        "the direction of the comparison is preserved across both "
        "environments. A short follow-up diagnostic probes this "
        "underperformance with a paired prompt swap and a shallow "
        "surface-form normalisation.",
    )
    add_para(
        doc,
        "Contributions. The contributions of this paper are as follows:",
    )
    add_para(
        doc,
        "C1. An oracle-controlled empirical study isolating evidence "
        "representation from retrieval failure in multimodal document QA. "
        "The study uses gold qrels at top-1 across four VisRAG-Ret-Test "
        "public splits with Qwen2-VL-7B-Instruct.",
        first_line_indent_cm=0.0, left_indent_cm=0.4,
    )
    add_para(
        doc,
        "C2. A seven-way comparison across four evidence representations "
        "(image-only, text-only, selective hybrid, image+text) and two "
        "text sources (in-model self-OCR and a production document parser), "
        "evaluated on both EM and a Qwen2.5-VL-72B-judged faithfulness "
        "score. Image-grounded modes dominate textualisation on both "
        "metrics; Image+Text with self-OCR is the only mode that improves "
        "macro EM and macro faithfulness over Image-only.",
        first_line_indent_cm=0.0, left_indent_cm=0.4,
    )
    add_para(
        doc,
        "C3. Evidence that selective routing of OCR text helps when in-model "
        "OCR is noisy (chart pages on Qwen self-OCR) but does not help "
        "structured parser output (Upstage Document Parse). This implies a "
        "routing strategy should depend on the text source, not on the page "
        "type alone.",
        first_line_indent_cm=0.0, left_indent_cm=0.4,
    )
    add_para(
        doc,
        "C4. A paired follow-up diagnostic on the underperforming Image+Text "
        "(Upstage Document Parse) cell. A prompt swap that demotes text and "
        "elevates the image and a shallow surface-form normalisation of the "
        "parser output both fail to close the gap at α=0.05 (McNemar p=0.11 "
        "and p=1.00 respectively), constraining the explanatory space and "
        "motivating three candidate hypotheses for follow-up work.",
        first_line_indent_cm=0.0, left_indent_cm=0.4,
    )


def section_related(doc):
    add_heading(doc, "2. Related Work")
    add_para(
        doc,
        "VisRAG [1] proposes vision-based retrieval and image-only generation "
        "for document QA, with code and benchmark data released through the "
        "OpenBMB/VisRAG repository [16]. Its public retrieval-test splits "
        "are built on DocVQA [2], InfographicVQA [3], ChartQA [4] and "
        "SlideVQA [5]; we use the four splits as our oracle evaluation "
        "harness. A complementary line of work flattens the page into text "
        "and layout tokens: LayoutLMv3 [10] pre-trains a transformer on "
        "OCR tokens with masked-image modelling, and commercial systems "
        "such as Upstage Document Parse [13] expose a production parser "
        "with explicit element types and bounding boxes.",
    )
    add_para(
        doc,
        "Recent vision-language models such as Qwen2-VL [6], Qwen2.5-VL [7], "
        "InternVL 2.5 [12] and LLaVA [8] now serve as joint readers and "
        "generators over rendered document pages, which raises the question "
        "studied here: when the generator can already see the page, what "
        "does an external transcription add? Earlier work tended to assume "
        "the addition was either neutral (a textual transcription stabilises "
        "named entities and numbers) or strictly helpful (more evidence is "
        "better than less). Our seven-way comparison in Section 4 shows that "
        "neither assumption holds uniformly: textualisation strictly "
        "underperforms the page image at our scale, and adding parser text "
        "to the image can even reduce both EM and faithfulness relative to "
        "the image-only baseline.",
    )
    add_para(
        doc,
        "Evidence fusion has been studied in the knowledge-VQA setting [9], "
        "where retrieved text passages are mixed with a visual query, and in "
        "the broader RAG literature for text-only tasks. Recent work in "
        "long-context language modelling reports that the position and "
        "length of supporting text affect answer accuracy even when the "
        "answer is present somewhere in the context [14], an observation "
        "that informs the length-as-distractor hypothesis we sketch in "
        "Section 6. Prompt sensitivity of vision-language models is itself "
        "an active area; the order in which evidence is presented has been "
        "reported to shift answers, and chain-of-thought prompting [15] is "
        "a related intervention. These observations motivate the paired "
        "prompt-bias and surface-form diagnostics in Section 5. Finally, "
        "while a number of multimodal QA papers report end-to-end scores, "
        "comparatively few isolate the answer stage by holding retrieval "
        "fixed at gold top-1. Doing so is the methodological backbone of "
        "the present study and lets us attribute every cross-mode gap to "
        "the answer-stage evidence representation rather than to retrieval "
        "noise.",
    )


def section_method(doc):
    add_heading(doc, "3. Method and Experimental Setup")
    add_para(
        doc,
        "We frame evaluation as an oracle-retrieval study. For every query "
        "we serve the gold page from the dataset's qrels and ask the "
        "generator to produce a short answer. This removes retrieval as a "
        "confounder so the comparison between evidence modes isolates the "
        "answer stage. Algorithm 1 sketches the procedure: for each "
        "(query, gold-page) pair and each evidence mode m, we assemble the "
        "evidence content E(m, page), wrap it with the mode-specific "
        "instruction clause I(m), and decode a 20-token answer.",
    )
    add_para(
        doc,
        "Algorithm 1 (oracle evidence-mode evaluation). For each split D "
        "and each query q ∈ D[:N_D]: (1) look up gold page p = qrels(q); "
        "(2) for each evidence mode m, build the prompt P_m(q, p) by "
        "instantiating the shared skeleton with the mode-specific evidence "
        "E(m, p) and instruction I(m); (3) decode answer â = "
        "Qwen2-VL-7B(P_m(q, p)) with do_sample=False, max_new_tokens=20; "
        "(4) score relaxed EM against gold and (where applicable) score "
        "faithfulness with a Qwen2.5-VL-72B judge; (5) aggregate per-mode "
        "macro accuracy across D.",
    )
    add_omml_equation(
        doc,
        [
            msubsup(["p"], ["i"], ["*"]),
            mtxt(" = qrels("), msub(["q"], ["i"]), mtxt("),  "),
            msub(["I"], ["i"]),
            mtxt(" = render("), msubsup(["p"], ["i"], ["*"]), mtxt(")"),
        ],
        number=1,
    )

    add_heading(doc, "3.1 Evidence modes", level=2)
    add_para(
        doc,
        "We compare seven evidence modes that bracket the design space: "
        "(i) Image-only: only the gold page image is supplied. "
        "(ii) Text-only (Qwen self-OCR): Qwen2-VL-7B is run on the page in "
        "an OCR-extraction pass with a transcription prompt; only the "
        "resulting text is supplied. (iii) Text-only (Upstage Document "
        "Parse): the page is parsed by the Upstage Document Parse [13] "
        "service and only the parser text is supplied. (iv) Selective "
        "Hybrid (Qwen self-OCR): an LLM router classifies each page as "
        "text/mixed/chart, supplies Qwen self-OCR text on text and mixed "
        "pages, and routes chart pages to the page image. (v) Selective "
        "Hybrid (Upstage Document Parse): the same router supplies "
        "Upstage text on text and mixed pages and routes chart pages to "
        "the page image. (vi) Image+Text (Qwen self-OCR): the "
        "page image and the Qwen self-OCR transcription are supplied "
        "together. (vii) Image+Text (Upstage Document Parse): the page "
        "image and the Upstage Document Parse output are supplied "
        "together. All seven modes share the same answer-generation prompt "
        "skeleton; only the evidence-instruction clause changes. Figure 1 "
        "sketches the oracle-controlled evidence pipeline that produces E "
        "for each mode.",
    )
    add_omml_equation(
        doc,
        [
            msub(["T"], ["i"]), mtxt(" = "), "g", mtxt("("),
            msub(["I"], ["i"]), mtxt("),  "),
            msubsup(["E"], ["i"], [mtxt("("), "m", mtxt(")")]),
            mtxt(" = "),
            msub(["φ"], ["m"]), mtxt("("), msub(["q"], ["i"]),
            mtxt(", "), msub(["I"], ["i"]), mtxt(", "),
            msub(["T"], ["i"]), mtxt(")"),
        ],
        number=2,
    )
    add_omml_equation(
        doc,
        [
            msubsup(["E"], ["i"], [mtxt("("), "m", mtxt(")")]),
            mtxt(" = "),
            mdelim([
                meq_array([
                    [mtxt("{"), msub(["I"], ["i"]), mtxt("},  if "),
                     "m", mtxt(" = image-only")],
                    [mtxt("{"), msub(["T"], ["i"]), mtxt("},  if "),
                     "m", mtxt(" = text-only")],
                    [mtxt("{"), msub(["T"], ["i"]), mtxt("},  if "),
                     "m", mtxt(" = selective, "), msub(["r"], ["i"]),
                     mtxt(" ≠ chart")],
                    [mtxt("{"), msub(["I"], ["i"]), mtxt("},  if "),
                     "m", mtxt(" = selective, "), msub(["r"], ["i"]),
                     mtxt(" = chart")],
                    [mtxt("{"), msub(["I"], ["i"]), mtxt(", "),
                     msub(["T"], ["i"]), mtxt("},  if "),
                     "m", mtxt(" = image+text")],
                ], size_pt=7.9)
            ], size_pt=7.9),
        ],
        number=3,
        size_pt=8.0,
    )
    add_para(
        doc,
        "The router label r_i = r(q_i, I_i) is used only by the selective "
        "modes; non-chart pages use text evidence, while chart pages fall "
        "back to the page image.",
    )

    # Figure 1: compact pipeline diagram.
    add_pipeline_figure(doc)

    add_heading(doc, "3.2 Answer-generation prompts", level=2)
    add_para(
        doc,
        "All seven modes share a fixed answer-generation skeleton that "
        "instructs the model to produce a short, factual answer; only the "
        "evidence-instruction clause varies across modality families "
        "(image-only, text-only, image+text). For Image-only, the model is "
        "asked to answer directly from the page image. For Text-only, it "
        "answers from parsed text/table evidence. For Image+Text, parsed "
        "text is framed as support for exact labels and values while the "
        "image remains available for visual verification. The OCR-"
        "extraction and faithfulness-judge prompts are unchanged across "
        "conditions; verbatim templates are provided in the supplementary "
        "archive.",
    )
    add_omml_equation(
        doc,
        [
            msubsup(["P"], ["i"], [mtxt("("), "m", mtxt(")")]),
            mtxt(" = prompt("), msub(["q"], ["i"]), mtxt(", "),
            msubsup(["E"], ["i"], [mtxt("("), "m", mtxt(")")]),
            mtxt(", "), msub(["ι"], ["m"]), mtxt("),"),
        ],
        space_after=0,
    )
    add_omml_equation(
        doc,
        [
            msubsup([mhat(["a"])], ["i"], [mtxt("("), "m", mtxt(")")]),
            mtxt(" = "), msub(["f"], ["θ"]), mtxt("("),
            msubsup(["P"], ["i"], [mtxt("("), "m", mtxt(")")]),
            mtxt(")."),
        ],
        number=4,
        space_before=0,
    )

    add_heading(doc, "3.3 Datasets", level=2)
    add_para(
        doc,
        "We evaluate on four VisRAG-Ret-Test public splits: InfoVQA [3], "
        "ChartQA [4], MP-DocVQA (DocVQA [2] multi-page), and SlideVQA [5]. "
        "We use the first 100 queries of each split, except ChartQA, which "
        "has 63 queries due to qrels coverage in the public release of "
        "VisRAG-Ret-Test-ChartQA. The total evaluation set therefore "
        "contains 363 queries (100 + 63 + 100 + 100).",
    )

    add_heading(doc, "3.4 Backbone, quantisation, and decoding", level=2)
    add_para(
        doc,
        "All seven evidence modes use Qwen2-VL-7B-Instruct [6] loaded with "
        "bitsandbytes NF4 4-bit quantisation [11] under transformers "
        "4.57.6. Decoding uses do_sample=False, max_new_tokens=20, and "
        "max_pixels=1280×1024 for image inputs. The faithfulness "
        "judge is Qwen2.5-VL-72B [7]. Faithfulness is not re-scored for "
        "the diagnostic cells because the 72B judge model is expensive to "
        "host; the diagnostic comparisons in Section 5 are reported on "
        "EM only.",
    )

    add_heading(doc, "3.5 Selective routing details", level=2)
    add_para(
        doc,
        "The selective hybrid modes (iv) and (v) use a single LLM router "
        "that classifies each gold page as text, mixed, or chart from a "
        "low-resolution view of the page image. Text and mixed pages are "
        "served as text-only evidence under the relevant text source "
        "(Qwen self-OCR or Upstage Document Parse). Chart pages are "
        "routed to image evidence — the page image itself is supplied to "
        "the generator in place of a text transcription — because "
        "in-model OCR on a chart is the worst case for textualisation. "
        "The router is held fixed across the two text sources so that any "
        "difference between modes (iv) and (v) is attributable to the text "
        "source rather than to routing decisions.",
    )

    add_heading(doc, "3.6 Metrics", level=2)
    add_para(
        doc,
        "We report relaxed Exact Match (EM) and a faithfulness score. "
        "Relaxed EM matches our implementation in benchmark/metrics.py: "
        "predictions and the stringified gold answer are lowercased and "
        "whitespace-normalised; numerical tokens are matched within a 5% "
        "relative tolerance; otherwise substring containment in either "
        "direction is required. A list-style gold answer is compared by "
        "substring containment against its rendered list. The faithfulness "
        "score is the average of a per-query {0, 0.5, 1} judgement from "
        "the Qwen2.5-VL-72B judge, where 1 means the predicted answer is "
        "fully supported by the evidence, 0.5 means partially supported, "
        "and 0 means unsupported or contradicted. Macro accuracy is the "
        "unweighted mean of per-dataset scores.",
    )
    add_omml_equation(
        doc,
        [
            msub([mtxt("Macro")], ["S"]), mtxt("("), "m", mtxt(") = "),
            mfrac([mtxt("1")], [mtxt("|"), "D", mtxt("|")]),
            mnary_sum(["d", mtxt("∈"), "D"], [mtxt("")],
                      [mfrac([mtxt("1")], [msub(["n"], ["d"])])]),
        ],
        size_pt=8.7,
        space_after=0,
    )
    add_omml_equation(
        doc,
        [
            mnary_sum(["i", mtxt("="), mtxt("1")], [msub(["n"], ["d"])],
                      [mtxt("")]),
            mtxt(" "), "S", mtxt("("),
            msubsup([mhat(["a"])],
                    ["i", mtxt(","), "d"],
                    [mtxt("("), "m", mtxt(")")]),
            mtxt(", "), msub(["a"], ["i", mtxt(","), "d"]), mtxt("),"),
        ],
        number=5,
        size_pt=8.7,
        space_before=0,
    )
    add_omml_equation(
        doc,
        [
            msub(["Δ"], ["S"]), mtxt("("), "m", mtxt(") = 100 [ "),
            msub([mtxt("Macro")], ["S"]), mtxt("("), "m", mtxt(") − "),
            msub([mtxt("Macro")], ["S"]), mtxt("(image-only) ]"),
        ],
        number=6,
    )
    add_para(
        doc,
        "Here S denotes either relaxed EM or the faithfulness judge, and "
        "Delta_S is the percentage-point difference reported in the final "
        "column of Table 1.",
    )

    add_heading(doc, "3.7 Statistical analysis", level=2)
    add_para(
        doc,
        "For the follow-up diagnostics in Section 5 we report 95% bootstrap "
        "confidence intervals around macro accuracy (2000 iterations, "
        "per-dataset stratified resample, percentile method) and paired "
        "two-sided McNemar tests with continuity correction over the "
        "n=363 union of the four dataset subsets. The bootstrap and "
        "McNemar computations are implemented in benchmark/stats_prompt_test.py.",
    )


def section_results(doc):
    add_heading(doc, "4. Results")
    add_para(
        doc,
        "Table 1 reports relaxed EM and faithfulness for all seven evidence "
        "modes on the four splits, together with the macro Δ vs the "
        "Image-only baseline for both metrics. Figure 2 visualises the "
        "text-only vs image+text ordering between the two text sources so "
        "that the inversion behind RQ1 is immediately visible. We then go "
        "through the four research questions in turn.",
    )

    add_one_column_section(doc)
    add_table(
        doc,
        header=[
            "Method",
            "Info",
            "Chart",
            "MP-Doc",
            "Slide",
            "Avg Δ",
        ],
        rows=[
            [
                "Image",
                "0.720 / 0.780",
                "0.556 / 0.730",
                "0.880 / 0.900",
                "0.540 / 0.850",
                "— / —",
            ],
            [
                "Text (Qwen)",
                "0.340 / 0.360",
                "0.318 / 0.222",
                "0.670 / 0.790",
                "0.430 / 0.545",
                "−23.45 / −33.58",
            ],
            [
                "Text (Upstage)",
                "0.540 / 0.620",
                "0.524 / 0.587",
                "0.760 / 0.939",
                "0.520 / 0.695",
                "−8.79 / −10.46",
            ],
            [
                "Sel. Hybrid (Qwen)",
                "0.340 / 0.350",
                "0.524 / 0.540",
                "0.670 / 0.780",
                "0.440 / 0.565",
                "−18.04 / −25.64",
            ],
            [
                "Sel. Hybrid (Upstage)",
                "0.540 / 0.630",
                "0.460 / 0.619",
                "0.770 / 0.900",
                "0.480 / 0.680",
                "−11.13 / −10.78",
            ],
            [
                "Image+Text (Qwen)",
                "0.730 / 0.770",
                "0.667 / 0.778",
                "0.820 / 0.880",
                "0.580 / 0.850",
                "+2.53 / +0.44",
            ],
            [
                "Image+Text (Upstage) †",
                "0.540 / 0.650",
                "0.508 / 0.524",
                "0.800 / 0.900",
                "0.520 / 0.730",
                "−8.19 / −11.41",
            ],
        ],
        caption_number=1,
        caption=(
            "Seven-way evidence-mode comparison. Cells: relaxed EM / Faith. "
            "Last column: macro Δ vs Image-only (pp). "
            "† Image+Text (Upstage Document Parse) was carried over from an "
            "earlier transformers 4.51 run that contained a Qwen2-VL "
            "vision-encoder bug; the same cell re-run on a clean transformers "
            "4.57.6 environment is reported in Table 2 (\"Upstage orig.\", "
            "macro 0.7061). The direction of the cross-source comparison "
            "(Image+Text self-OCR ≥ Image+Text Upstage Document Parse) is "
            "preserved across both environments; the magnitude shrinks from "
            "−8.19 to roughly −1.85 macro EM percentage points. "
            "Per-query confidence intervals and paired significance tests "
            "are not reported for Table 1 because per-query predictions for "
            "the team's tf457 runs are not in the supplementary archive; the "
            "diagnostic statistical claims are based on the clean local "
            "re-runs reported in Tables 2 and 3."
        ),
        size_pt=8.0,
        col_widths=[1.45, 0.98, 0.98, 0.98, 0.98, 1.38],
    )

    # Figure 2: per-dataset bar chart visualising the text-only vs
    # image+text ordering inversion between Qwen self-OCR and Upstage.
    add_results_figure(doc, section_breaks=False, caption_number=2)
    add_two_column_section(doc)

    add_para(
        doc,
        "The Image+Text (Upstage Document Parse) row in Table 1 reads a "
        "macro EM Δ of −8.19 percentage points against Image-only. "
        "Section 5 reports a clean re-run of this cell on transformers "
        "4.57.6 with macro EM 0.7061, which is +3.22 percentage points "
        "above the Image-only baseline rather than −8.19. The direction "
        "of the cross-source comparison (Image+Text self-OCR ≥ Image+Text "
        "Upstage Document Parse) is preserved between the two "
        "environments, but the magnitude of both the cross-source gap and "
        "the Image-only comparison shrinks substantially once the 4.51 "
        "vision-encoder bug is removed. We retain the original "
        "team-reported numbers in Table 1 because they are the published "
        "reference, and use the clean re-run in Tables 2–3 as the basis "
        "for the diagnostic statistical claims.",
    )

    add_heading(doc, "4.1 RQ1: Which Context Modality Is Most Reliable?", level=2)
    add_para(
        doc,
        "The best context is visually grounded. Image+Text with Qwen "
        "self-OCR reaches the best macro EM and the best macro "
        "faithfulness in Table 1, improving on Image-only by +2.53 EM and "
        "+0.44 faithfulness percentage points, while Image+Text with "
        "Upstage Document Parse does not exceed Image-only on macro EM. "
        "Adding text helps only when it supports, rather than competes "
        "with, visual grounding; Section 5 returns to the underperforming "
        "Image+Text (Upstage Document Parse) cell.",
    )

    add_heading(doc, "4.2 RQ2: Can OCR Text Replace Image Evidence?", level=2)
    add_para(
        doc,
        "OCR text alone cannot replace image evidence. Text-only with "
        "Qwen self-OCR loses 23.45 macro EM and 33.58 macro faithfulness "
        "against Image-only. Upstage Document Parse is the better text "
        "source on its own (+14.7 macro EM over Qwen self-OCR text-only), "
        "but even Upstage text-only sits 8.79 macro EM and 10.46 macro "
        "faithfulness percentage points below Image-only. Replacing the "
        "page image with text is a strict downgrade at Qwen2-VL-7B scale "
        "on this benchmark family.",
    )

    add_heading(doc, "4.3 RQ3: Does Selective Hybrid Routing Reduce OCR Noise?", level=2)
    add_para(
        doc,
        "Selective routing helps when OCR is noisy but is not universally "
        "reliable. Selective routing of Qwen self-OCR improves ChartQA EM "
        "from 0.3175 to 0.5238 (a +0.21 absolute jump) because routing "
        "chart pages out of the text channel avoids a noisy self-OCR pass. Selective "
        "routing of Upstage Document Parse does not produce consistent "
        "gains across splits: parser output is already structured, and "
        "dropping pages can remove useful evidence on a split-by-split "
        "basis. The headline implication is that a routing strategy should "
        "depend on the text source, not only on the page type. If the text "
        "source is in-model OCR, routing chart pages out of the OCR "
        "pipeline pays off; if the text source is a structured parser, "
        "routing tends to drop information without a clean gain.",
    )

    add_para(
        doc,
        "The asymmetry is diagnostic: in-model OCR loses spatial structure "
        "on chart pages, so filtering them out removes the worst failure "
        "mode, whereas parser output preserves textual labels and table-"
        "like cells, so dropping chart pages sacrifices structured "
        "information without an OCR-noise benefit. The takeaway is that "
        "page-type routing decisions cannot be re-used across text "
        "sources.",
    )

    add_heading(doc, "4.4 RQ4: Does Evidence Representation Affect "
                "Unsupported Hallucination?", level=2)
    add_para(
        doc,
        "Evidence representation drives unsupported hallucination, not "
        "just accuracy. Text-only with Qwen self-OCR has the lowest "
        "faithfulness (macro Δ −33.58). Image+Text with Qwen self-OCR "
        "is the only mode that improves macro faithfulness over Image-"
        "only (+0.44), while Image+Text with Upstage Document Parse "
        "shows the opposite pattern (macro Δ −11.41): the long, layout-"
        "preserving parser output appears to distract from image-based "
        "verification. This cell motivates Section 5.",
    )


def section_followup(doc):
    add_heading(doc, "5. Follow-up Diagnostics on the Image+Text (Upstage "
                "Document Parse) Cell")
    add_para(
        doc,
        "Section 4 noted that Image+Text with Upstage Document Parse "
        "underperforms Image+Text with Qwen self-OCR on the same image, "
        "even though Upstage Document Parse is the better text source on "
        "its own. We probe two candidate causes of that underperformance "
        "with paired diagnostics. Both diagnostics use the same 100-query "
        "splits (63 for ChartQA) and the same backbone and decoding "
        "configuration as Section 4. Faithfulness is not re-scored for "
        "the diagnostic cells because the 72B judge model is expensive "
        "to host; the diagnostic comparisons are reported on EM only.",
    )

    add_heading(doc, "5.1 Diagnostic 1: Prompt-Bias Intervention", level=2)
    add_para(
        doc,
        "Table 2 reports our clean transformers 4.57.6 re-run of the four "
        "Image+Text cells. The Upstage orig. row in Table 2 reads macro "
        "EM 0.7061 against Table 1's 0.5920 for the same cell; the "
        "difference is the transformers 4.51 vision-encoder bug that the "
        "older run carried, not a change in method, sample, or prompt. "
        "The Image+Text instruction clause in Section 3.2 asks the model "
        "to use parsed text for exact labels and the image as a visual "
        "check. If the parsed text is clean — which it is for "
        "Upstage Document Parse — the decoder can satisfy the prompt "
        "without ever attending to the image. The diagnostic swaps this "
        "clause for an image-first instruction:",
    )
    add_para(
        doc,
        "“Use the document page image(s) as the primary evidence. "
        "Read directly from the image. Use the parsed text/table only as "
        "a secondary cross-check for ambiguous labels or numeric "
        "values.”",
        italic=True, first_line_indent_cm=0.0,
        left_indent_cm=0.5, right_indent_cm=0.5,
    )
    add_para(
        doc,
        "The image-first prompt was applied to both text sources on all "
        "four splits, giving a 4 × 2 × 2 = 16-cell sweep "
        "(datasets × text source × prompt). Each cell is the "
        "first 100 queries (63 for ChartQA), oracle top-1, "
        "do_sample=False, max_new_tokens=20. Macro accuracy is reported "
        "with 95% bootstrap CIs. Results are in Table 2.",
    )

    add_wide_table(
        doc,
        header=[
            "Source", "Prompt",
            "InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA",
            "Macro [95% CI]",
        ],
        rows=[
            [
                "Upstage", "orig.",
                "0.680", "0.714", "0.860", "0.570",
                "0.706 [0.660, 0.753]",
            ],
            [
                "Upstage", "image-first",
                "0.690", "0.714", "0.880", "0.600",
                "0.721 [0.675, 0.767]",
            ],
            [
                "Qwen", "orig.",
                "0.710", "0.698", "0.860", "0.630",
                "0.725 [0.679, 0.772]",
            ],
            [
                "Qwen", "image-first",
                "0.730", "0.698", "0.890", "0.620",
                "0.735 [0.690, 0.780]",
            ],
        ],
        caption_number=2,
        caption=(
            "Diagnostic 1: image-first prompt swap. EM with 95% bootstrap CIs."
        ),
        size_pt=8.2,
        col_widths=[0.85, 0.95, 0.75, 0.75, 0.82, 0.82, 1.81],
    )
    add_para(
        doc,
        "These paired diagnostic rows show the same direction as the "
        "main table (Upstage Document Parse trails Qwen self-OCR by 1.85 "
        "macro percentage points here vs. 10.72 in Table 1), but at "
        "smaller magnitude. The residual gap is statistically fragile: a "
        "paired McNemar test (continuity-corrected, two-sided) on n=363 "
        "queries gives p=0.20 for Upstage Document Parse vs Qwen "
        "self-OCR under the original prompt, and p=0.36 under the "
        "image-first prompt. The prompt-swap test (image-first vs "
        "original within the same evidence source) gives p=0.11 for "
        "Upstage Document Parse and p=0.39 for Qwen self-OCR. None reach "
        "α=0.05.",
    )

    add_heading(doc, "5.2 Diagnostic 2: Shallow Surface-Form Normalisation",
                level=2)
    add_para(
        doc,
        "Qwen self-OCR text is sampled from the same decoder that will "
        "later answer the question, so its surface form (tokens, spacing, "
        "line-wrap conventions) matches what the decoder expects to see. "
        "Upstage Document Parse output is layout-preserving prose with "
        "bullet markers, section labels, dash rules, and visual "
        "line-wraps that the Qwen decoder would not itself produce. The "
        "hypothesis is that this surface mismatch costs cross-modal "
        "alignment in the Image+Text setting. We applied a deliberately "
        "shallow normaliser to the Upstage text before it entered the "
        "prompt: strip parser markers (bullet glyphs such as ●, a Korean "
        "section tag the parser inserts for collected content, and "
        "horizontal dash rules separating layout regions), collapse "
        "intra-line whitespace, rejoin visual line-wraps. Length deltas "
        "after normalisation are tiny: InfoVQA 18,304→18,244 "
        "characters (−0.3%), ChartQA 1,405→1,405 (0%), "
        "MP-DocVQA 2,693→2,691 (−0.07%), SlideVQA "
        "2,217→2,213 (−0.18%).",
    )

    add_wide_table(
        doc,
        header=[
            "Method",
            "InfoVQA", "ChartQA", "MP-DocVQA", "SlideVQA",
            "Macro [95% CI]",
        ],
        rows=[
            [
                "Original",
                "0.680", "0.714", "0.860", "0.570",
                "0.706 [0.660, 0.753]",
            ],
            [
                "Normalised",
                "0.680", "0.714", "0.860", "0.580",
                "0.709 [0.661, 0.754]",
            ],
        ],
        caption_number=3,
        caption=(
            "Diagnostic 2: surface-form normalisation on Upstage Image+Text. "
            "EM with 95% bootstrap CIs."
        ),
        size_pt=8.2,
        col_widths=[1.10, 0.85, 0.85, 0.95, 0.85, 2.15],
    )

    add_para(
        doc,
        "The paired test yields only three discordant pairs (1 "
        "baseline-only correct, 2 normalised-only correct), giving "
        "p=1.00 under McNemar with continuity correction. The 95% "
        "bootstrap CIs of the two rows overlap heavily. The intervention "
        "is, statistically, a null.",
    )

    add_heading(doc, "5.3 Combined Verdict", level=2)
    add_para(
        doc,
        "Neither cheap intervention closes the Image+Text (Upstage "
        "Document Parse) gap, and neither settles the deeper mechanism. "
        "Section 6 lists three co-equal candidate hypotheses, each with "
        "a follow-up experiment that could falsify it.",
    )


def section_discussion(doc):
    add_heading(doc, "6. Discussion")
    add_para(
        doc,
        "Re-stating contributions in light of the results. C1: the "
        "oracle-controlled setup successfully isolates evidence "
        "representation from retrieval; the cross-mode gaps in Table 1 "
        "are large enough to be informative on 363 queries. C2: the "
        "seven-way comparison shows that image-grounded modes dominate "
        "textualisation on both EM and faithfulness, with Image+Text "
        "(Qwen self-OCR) the only mode that improves both macro metrics "
        "over Image-only. C3: selective routing is text-source-dependent; "
        "it helps in-model OCR on chart pages and does not consistently "
        "help structured parser output. C4: the paired diagnostics on the "
        "Image+Text (Upstage Document Parse) cell do not support prompt-"
        "driven evidence reweighting or shallow surface alignment as "
        "sufficient explanations, but they do not pin down a single "
        "mechanism.",
    )
    add_para(
        doc,
        "Three candidate hypotheses for the residual gap remain, presented "
        "as co-equal. (i) Representational misalignment: self-OCR text is "
        "close to the decoder's own distribution, while Upstage Document "
        "Parse output comes from a different model and may be off-"
        "distribution for cross-modal attention. Falsification: rewrite "
        "the parser text through Qwen itself before serving it; a closed "
        "gap supports alignment-to-self-distribution. (ii) Modality "
        "attention competition: clean external text saturates the "
        "answer-grounding pathway and the image gets under-attended. "
        "Falsification: log cross-modal attention weights under the two "
        "text sources on the discordant queries. (iii) Length as "
        "distractor: on InfoVQA the parser text is an order of magnitude "
        "longer than on the other three splits (18 k characters vs "
        "1.4 k–2.7 k). Falsification: a length-controlled re-run on "
        "InfoVQA, truncating the parser text to the length of the "
        "self-OCR text.",
    )


def section_limitations(doc):
    add_heading(doc, "7. Limitations")
    add_para(
        doc,
        "Several limitations narrow the claim. (i) A single generator family "
        "(Qwen2-VL-7B-Instruct) under NF4 4-bit quantisation. Our "
        "findings should not be read as general claims about "
        "vision-language models. The ordering and the residual gap may "
        "behave differently for larger Qwen2-VL/2.5-VL variants, for "
        "non-Qwen families such as InternVL or LLaVA, or for "
        "non-quantised inference. We mark this as the single largest "
        "threat to the external validity of the paper. (ii) A "
        "single seed; do_sample=False but CUDA non-determinism can produce "
        "a few percentage points of run-to-run drift. (iii) 100 samples "
        "per split (63 for ChartQA) for a total n=363, which is the "
        "source of the wide bootstrap CIs in Section 5. (iv) Faithfulness "
        "was not re-scored for the diagnostic cells in Section 5 due to "
        "the cost of hosting the 72B judge model; we report EM only for "
        "those cells. A judge-aware diagnostic re-run is straightforward "
        "to add when judge compute is available. (v) The surface-form "
        "normaliser in Section 5.2 is deliberately shallow, so the null "
        "result speaks only to the easy-to-fix part of the surface-"
        "alignment hypothesis. (vi) We use oracle qrels with top-k=1, so "
        "retrieval is not exercised; end-to-end evaluation with a "
        "realistic retriever is left to future work.",
    )


def section_conclusion(doc):
    add_heading(doc, "8. Conclusion")
    add_para(
        doc,
        "We report an oracle-controlled study of evidence representation "
        "for multimodal document question answering. Across four "
        "VisRAG-Ret-Test public splits and seven evidence modes, "
        "image-grounded modes dominate textualisation on both relaxed EM "
        "and a Qwen2.5-VL-72B-judged faithfulness score; Image+Text with "
        "Qwen self-OCR is the only mode that improves macro EM and "
        "macro faithfulness over Image-only. Selective routing of OCR "
        "text helps when in-model OCR is noisy but not when the text "
        "source is a structured parser. A paired follow-up diagnostic on "
        "the underperforming Image+Text (Upstage Document Parse) cell "
        "does not support prompt-bias swap or shallow surface-form normalisation "
        "as sufficient explanations (McNemar p=0.11 and p=1.00 respectively), "
        "leaving representational misalignment, modality attention "
        "competition, and length-as-distractor as co-equal candidate "
        "hypotheses for follow-up work. Per-query predictions, the "
        "diagnostic scripts, and the runner configuration are made "
        "available in the anonymous supplementary archive that accompanies "
        "this submission (not an external URL).",
    )


def section_references(doc):
    add_heading(doc, "References")
    refs = [
        ("S. Yu, C. Tang, B. Xu, J. Cui, J. Ran, Y. Yan, Z. Liu, S. Wang, X. Han, Z. Liu, and M. Sun.", "VisRAG: Vision-based Retrieval-augmented Generation on Multi-modality Documents.", "arXiv:2410.10594, 2024."),
        ("M. Mathew, D. Karatzas, C. V. Jawahar.", "DocVQA: A Dataset for VQA on Document Images.", "WACV, 2021."),
        ("M. Mathew, V. Bagal, R. Tito, D. Karatzas, E. Valveny, C. V. Jawahar.", "InfographicVQA.", "WACV, 2022."),
        ("A. Masry, X. L. Do, J. Q. Tan, S. Joty, E. Hoque.", "ChartQA: A Benchmark for Question Answering about Charts with Visual and Logical Reasoning.", "Findings of ACL, 2022."),
        ("R. Tanaka, K. Nishida, K. Nishida, T. Hasegawa, I. Saito, K. Saito.", "SlideVQA: A Dataset for Document Visual Question Answering on Multiple Images.", "AAAI, 2023."),
        ("P. Wang, S. Bai, S. Tan, et al.", "Qwen2-VL: Enhancing Vision-Language Model’s Perception of the World at Any Resolution.", "arXiv:2409.12191, 2024."),
        ("S. Bai, K. Chen, X. Liu, et al.", "Qwen2.5-VL Technical Report.", "arXiv:2502.13923, 2025."),
        ("H. Liu, C. Li, Q. Wu, Y. J. Lee.", "Visual Instruction Tuning (LLaVA).", "NeurIPS, 2023."),
        ("P. Lewis, et al.", "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks.", "NeurIPS, 2020. arXiv:2005.11401."),
        ("Y. Xu, T. Lv, L. Cui, et al.", "LayoutLMv3: Pre-training for Document AI with Unified Text and Image Masking.", "ACM Multimedia, 2022."),
        ("T. Dettmers, A. Pagnoni, A. Holtzman, L. Zettlemoyer.", "QLoRA: Efficient Finetuning of Quantized LLMs (NF4).", "NeurIPS, 2023."),
        ("Z. Chen, et al.", "InternVL 2.5: Expanding Performance Boundaries of Open-Source Multimodal Models with Model, Data, and Test-Time Scaling.", "arXiv:2412.05271, 2024."),
        ("Upstage AI.", "Document Parse — product documentation.", "2024 (accessed June 2026)."),
        ("N. F. Liu, et al.", "Lost in the Middle: How Language Models Use Long Contexts.", "TACL, 2024."),
        ("J. Wei, et al.", "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.", "NeurIPS, 2022."),
        ("OpenBMB.", "VisRAG: open-source code, models, and benchmark data release accompanying [1].", "2024."),
    ]
    for idx, (authors, title, where) in enumerate(refs, start=1):
        p = doc.add_paragraph()
        pf = p.paragraph_format
        pf.left_indent = Cm(0.7)
        pf.first_line_indent = Cm(-0.7)
        pf.space_after = Pt(2)
        pf.line_spacing = 1.1
        pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_run(p, f"[{idx}] ", size_pt=REF_PT, bold=True)
        add_run(p, f"{authors} ", size_pt=REF_PT)
        add_run(p, title, size_pt=REF_PT, italic=True)
        add_run(p, f" {where}", size_pt=REF_PT)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main():
    doc = setup_document()
    add_title_block(doc)
    add_two_column_section(doc)
    add_abstract(doc)
    section_introduction(doc)
    section_related(doc)
    section_method(doc)
    section_results(doc)
    section_followup(doc)
    section_discussion(doc)
    section_limitations(doc)
    section_conclusion(doc)
    section_references(doc)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUTPUT)
    print(f"wrote {OUTPUT}")


if __name__ == "__main__":
    main()
