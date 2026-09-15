"""Render the committed pipeline run report and coverage funnel to a PDF.

This is the one command that works from a fresh clone. It reads only files
tracked by Git under ``results/`` and writes ``output/pdf/pipeline_report.pdf``.
All paths are resolved relative to the project root, so the command works from
any working directory.
"""

import argparse
import hashlib
import json
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    Flowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "results" / "pipeline_report.md"
FUNNEL = ROOT / "results" / "funnel.json"
SUMMARY = ROOT / "results" / "summary.json"
OUTPUT = ROOT / "output" / "pdf" / "pipeline_report.pdf"
INK = colors.HexColor("#162E35")
TEAL = colors.HexColor("#176B63")
MUTED = colors.HexColor("#53666C")
CONTENT_WIDTH = A4[0] - 84
ASCII_PUNCTUATION = str.maketrans(
    {"–": "-", "—": "-", "−": "-", "’": "'", "“": '"', "”": '"'}
)


def styles() -> dict[str, ParagraphStyle]:
    """Return the paragraph styles used by the report."""
    body = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9.6, leading=13.2, textColor=INK, spaceAfter=8
    )
    return {
        "title": ParagraphStyle(
            "title", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=INK, spaceAfter=10
        ),
        "heading": ParagraphStyle(
            "heading", fontName="Helvetica-Bold", fontSize=15, leading=18, textColor=INK,
            spaceBefore=8, spaceAfter=8, keepWithNext=True,
        ),
        "body": body,
        "bullet": ParagraphStyle(
            "bullet", parent=body, leftIndent=12, firstLineIndent=-8, spaceAfter=5
        ),
        "meta": ParagraphStyle(
            "meta", parent=body, fontSize=8.6, leading=11.5, textColor=MUTED
        ),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.4, leading=10.8, textColor=INK),
        "head": ParagraphStyle(
            "head", fontName="Helvetica-Bold", fontSize=8.4, leading=10.8, textColor=colors.white
        ),
    }


def strip_links(text: str) -> str:
    """Replace Markdown links with their labels.

    Args:
        text: One line of Markdown.

    Returns:
        The line with each ``[label](destination)`` reduced to ``label``.
    """
    result = text
    while True:
        open_bracket = result.find("[")
        if open_bracket < 0:
            return result
        close_bracket = result.find("](", open_bracket)
        if close_bracket < 0:
            return result
        close_paren = result.find(")", close_bracket)
        if close_paren < 0:
            return result
        label = result[open_bracket + 1 : close_bracket]
        result = result[:open_bracket] + label + result[close_paren + 1 :]


def wrap_alternate(text: str, marker: str, open_tag: str, close_tag: str) -> str:
    """Wrap every odd-numbered segment between markers in a tag pair.

    Args:
        text: Already-escaped text.
        marker: Delimiter such as ``**`` or a backtick.
        open_tag: Opening markup.
        close_tag: Closing markup.

    Returns:
        Text with paired markers converted to markup. Unpaired markers are kept.
    """
    parts = text.split(marker)
    if len(parts) % 2 == 0:
        return text
    for index in range(1, len(parts), 2):
        parts[index] = open_tag + parts[index] + close_tag
    return "".join(parts)


def inline(text: str) -> str:
    """Convert a line of Markdown to ReportLab paragraph markup.

    Args:
        text: One line of Markdown.

    Returns:
        Escaped text with bold and code spans converted to markup.
    """
    plain = escape(strip_links(text).translate(ASCII_PUNCTUATION))
    plain = wrap_alternate(plain, "**", "<b>", "</b>")
    return wrap_alternate(plain, "`", '<font face="Courier">', "</font>")


def is_separator_row(cells: list[str]) -> bool:
    """Return whether a table row only contains Markdown alignment markers."""
    return all(cell and set(cell) <= set("-: ") for cell in cells)


def split_row(line: str) -> list[str]:
    """Split a Markdown table row into stripped cell texts."""
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def build_table(rows: list[list[str]], style: dict[str, ParagraphStyle]) -> Table:
    """Build a styled table whose first row is the header.

    Args:
        rows: Cell texts, header first.
        style: Paragraph styles from :func:`styles`.

    Returns:
        A ReportLab table sized to the content width.
    """
    width = len(rows[0])
    fractions = [1 / width] * width
    if width == 3:
        fractions = [0.34, 0.14, 0.52]
    cells = []
    for index, row in enumerate(rows):
        name = "head" if index == 0 else "cell"
        cells.append([Paragraph(inline(cell), style[name]) for cell in row])
    table = Table(cells, colWidths=[CONTENT_WIDTH * f for f in fractions], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF4F2"), colors.HexColor("#F8FAF9")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, TEAL),
            ]
        )
    )
    return table


def markdown_story(text: str, style: dict[str, ParagraphStyle]) -> list[Flowable]:
    """Convert the Markdown run report into flowables.

    Supports titles, headings, pipe tables, bullet lists and paragraphs, which
    is everything the committed report uses.

    Args:
        text: Markdown source.
        style: Paragraph styles from :func:`styles`.

    Returns:
        Flowables in document order.
    """
    story: list[Flowable] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                cells = split_row(lines[index])
                if not is_separator_row(cells):
                    rows.append(cells)
                index += 1
            story.extend([build_table(rows, style), Spacer(1, 10)])
            continue
        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), style["title"]))
        elif line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), style["heading"]))
        elif line.startswith("- "):
            story.append(Paragraph(inline(line[2:]), style["bullet"]))
        else:
            parts = [line]
            while index + 1 < len(lines):
                following = lines[index + 1].strip()
                if not following or following.startswith(("#", "|", "- ")):
                    break
                index += 1
                parts.append(following)
            story.append(Paragraph(inline(" ".join(parts)), style["body"]))
        index += 1
    return story


def funnel_story(funnel: dict, summary: dict, style: dict[str, ParagraphStyle]) -> list[Flowable]:
    """Build the coverage funnel and feasibility pages from machine-readable results.

    Args:
        funnel: Parsed ``results/funnel.json``.
        summary: Parsed ``results/summary.json``.
        style: Paragraph styles from :func:`styles`.

    Returns:
        Flowables for the funnel section.
    """
    story: list[Flowable] = [Paragraph("Coverage funnel", style["heading"])]
    meta = (
        f"Protocol commit {funnel.get('protocol_commit', 'unknown')}; "
        f"generated {funnel.get('generated_at', 'unknown')}; "
        f"status {funnel.get('status', 'unknown')}; estimable {funnel.get('estimable', 'unknown')}."
    )
    story.append(Paragraph(inline(meta), style["meta"]))
    rows = [["Stage", "Count", "Unit / status"]]
    for stage in funnel.get("stages", []):
        status = stage.get("status", "unknown")
        if stage.get("blocked_reason"):
            status = f"{status}: {stage['blocked_reason']}"
        rows.append([str(stage.get("stage", "")), str(stage.get("count", "")), f"{stage.get('unit', '')}; {status}"])
    story.extend([build_table(rows, style), Spacer(1, 10)])
    blockers = funnel.get("inference_blockers") or []
    if blockers:
        story.append(Paragraph("Inference blockers", style["heading"]))
        for blocker in blockers:
            story.append(Paragraph(inline(str(blocker)), style["bullet"]))
    primary = summary.get("primary", {})
    if primary:
        story.append(Paragraph("Primary test", style["heading"]))
        keys = [
            "status", "estimable", "reason", "minimum_genera", "minimum_per_direction",
            "n_genera", "n_accepted", "n_rejected", "observed_difference", "p_one_sided",
        ]
        rows = [["Field", "Value"]]
        for key in keys:
            if key in primary:
                rows.append([key, json.dumps(primary[key])])
        story.extend([build_table(rows, style), Spacer(1, 10)])
    return story


def provenance_story(inputs: list[Path], style: dict[str, ParagraphStyle]) -> list[Flowable]:
    """List the input files and their SHA-256 digests.

    Args:
        inputs: Files the report was rendered from.
        style: Paragraph styles from :func:`styles`.

    Returns:
        Flowables for the provenance section.
    """
    rows = [["Input", "SHA-256"]]
    for path in inputs:
        rows.append([str(path.relative_to(ROOT)), hashlib.sha256(path.read_bytes()).hexdigest()])
    return [Paragraph("Rendered from", style["heading"]), build_table(rows, style)]


def footer(canvas: Canvas, document: SimpleDocTemplate) -> None:
    """Draw the page footer and page number."""
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#CFDCD8"))
    canvas.line(42, 35, A4[0] - 42, 35)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(42, 23, "AANI  |  PIPELINE RUN REPORT")
    canvas.drawRightString(A4[0] - 42, 23, str(document.page))
    canvas.restoreState()


def render(report: Path, funnel: Path, summary: Path, output: Path) -> dict:
    """Render the PDF and return a small verification record.

    Args:
        report: Markdown run report.
        funnel: Machine-readable coverage funnel.
        summary: Analysis summary; skipped when absent.
        output: Destination PDF path; parent directories are created.

    Returns:
        Output path, page count and SHA-256 digest of the written PDF.

    Raises:
        FileNotFoundError: If the report or funnel input is missing.
    """
    for required in (report, funnel):
        if not required.exists():
            raise FileNotFoundError(f"Required input is missing: {required}")
    style = styles()
    inputs = [report, funnel]
    summary_data: dict = {}
    if summary.exists():
        inputs.append(summary)
        summary_data = json.loads(summary.read_text(encoding="utf-8"))
    funnel_data = json.loads(funnel.read_text(encoding="utf-8"))
    story = markdown_story(report.read_text(encoding="utf-8"), style)
    story.append(PageBreak())
    story.extend(funnel_story(funnel_data, summary_data, style))
    story.append(Spacer(1, 12))
    story.extend(provenance_story(inputs, style))
    output.parent.mkdir(parents=True, exist_ok=True)
    document = SimpleDocTemplate(
        str(output), pagesize=A4, leftMargin=42, rightMargin=42, topMargin=42, bottomMargin=49,
        title="aani pipeline run report", author="aani project",
    )
    document.build(story, onFirstPage=footer, onLaterPages=footer)
    pages = len(PdfReader(str(output)).pages)
    return {"pdf": str(output), "pages": pages, "sha256": hashlib.sha256(output.read_bytes()).hexdigest()}


def main() -> None:
    """Parse arguments, render the PDF and print the verification record."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--funnel", type=Path, default=FUNNEL)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(render(args.report, args.funnel, args.summary, args.output), indent=2))


if __name__ == "__main__":
    main()
