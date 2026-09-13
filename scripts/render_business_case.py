"""Render the judge-focused business case and verify its local headline evidence."""

from pathlib import Path
import csv
import hashlib
import json
import re
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "results/business_case/platform_business_case.md"
OUT = ROOT / "output/pdf/platform_business_case.pdf"
RESEARCH = ROOT / "research/attine_selection_2026-09-12"
INK = colors.HexColor("#162E35")
TEAL = colors.HexColor("#176B63")
MUTED = colors.HexColor("#53666C")
W = A4[0] - 84


def evidence():
    """Recount records and capture input provenance without modifying source runs."""
    files = [
        ROOT / "data/interim/extraction_gemini/metrics.json",
        ROOT / "data/interim/extraction_gemini/semantic_review.json",
        ROOT / "results/saverschek_audit/summary.json",
        ROOT / "results/experiment_planner/simulation_report.json",
        RESEARCH / "bundle_stats.json",
        RESEARCH / "compound_assays_from_fulltexts.csv",
        RESEARCH / "napal2015_all_89_plants.csv",
        RESEARCH / "compound_modelling/feasibility_counts.json",
        RESEARCH / "compound_modelling/molecular_assay_evidence.csv",
        RESEARCH / "compound_modelling/validation_panel.csv",
        RESEARCH / "compound_modelling/dose_response/digitized_points.csv",
        RESEARCH / "compound_modelling/dose_response/descriptive_fits.csv",
    ]
    def rows(name):
        with (RESEARCH / name).open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))
    plants = rows("napal2015_all_89_plants.csv")
    fits = rows("compound_modelling/dose_response/descriptive_fits.csv")
    fungal = lambda row: "+" in row["fungal_screen"]
    deter = lambda row: float(row["antiforaging_index"]) > 70
    counts = {
        "paired_plants": len(plants),
        "paired_fungal_positive": sum(fungal(row) for row in plants),
        "paired_deterrent": sum(deter(row) for row in plants),
        "paired_both": sum(fungal(row) and deter(row) for row in plants),
        "base_assay_records": len(rows("compound_assays_from_fulltexts.csv")),
        "molecular_reference_records": len(rows("compound_modelling/molecular_assay_evidence.csv")),
        "validation_panel_materials": len(rows("compound_modelling/validation_panel.csv")),
        "digitized_markers": len(rows("compound_modelling/dose_response/digitized_points.csv")),
        "curve_fits": len(fits),
        "curve_series": len({row["series_id"] for row in fits}),
        "max_abs_midpoint_difference_percent": max(abs(float(row["percent_difference_from_author"])) for row in fits),
    }
    assert [counts[k] for k in ["paired_plants", "paired_fungal_positive", "paired_deterrent", "paired_both"]] == [89, 11, 12, 2]
    assert [counts[k] for k in ["base_assay_records", "molecular_reference_records", "validation_panel_materials", "digitized_markers", "curve_fits", "curve_series"]] == [149, 71, 10, 36, 16, 8]
    assert counts["max_abs_midpoint_difference_percent"] < 3.2
    manifest = {
        "review_date": "2026-09-12",
        "purpose": "Business case: verify existing results, not re-run biological or predictive experiments",
        "verified_counts": counts,
        "inputs": [{"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
        "commercial_assumptions": {
            "team_subscription_usd_per_year": [30000, 75000],
            "enterprise_usd_per_year": [100000, 250000],
            "scoped_project_usd": [25000, 100000],
            "example_acv_usd": 50000,
            "example_arr_usd": {str(n): n * 50000 for n in [10, 20, 50]},
            "example_gross_margin_target": 0.70,
            "direct_delivery_cost_ceiling_at_example_acv": 50000 * (1 - 0.70),
            "status": "Illustrative, unvalidated; no customers, prices or margins asserted as observed",
        },
        "judging_rubric_source": "Team Playbook pasted by user; authenticated Google document not independently accessed",
        "judging_weights": {"innovation": 0.30, "technical": 0.25, "business": 0.25, "presentation": 0.20},
    }
    return manifest


def inline(s):
    s = s.translate(str.maketrans({"–": "-", "—": "-", "−": "-", "’": "'", "“": '"', "”": '"', "\u2011": "-"}))
    parts = []
    def link(m):
        label, dest = m.group(1), m.group(2)
        if not dest.startswith(("https://", "http://")):
            dest = (SOURCE.parent / dest).resolve().as_uri()
        parts.append(f'<link href="{escape(dest, {chr(34): "&quot;"})}" color="#176B63">{escape(label)}</link>')
        return f"LINKTOKEN{len(parts)-1}END"
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)
    s = escape(s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    for i, item in enumerate(parts):
        s = s.replace(f"LINKTOKEN{i}END", item)
    return s


def main():
    manifest = evidence()
    text = SOURCE.read_text()
    pages = text.split("<!-- PAGEBREAK -->")
    styles = {
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=26, leading=29, textColor=INK, spaceAfter=10),
        "heading": ParagraphStyle("heading", fontName="Helvetica-Bold", fontSize=20, leading=23, textColor=INK, spaceAfter=13, keepWithNext=True),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.6, leading=13.2, textColor=INK, spaceAfter=9),
        "source": ParagraphStyle("source", fontName="Helvetica", fontSize=8.6, leading=11.5, textColor=INK, spaceAfter=8),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.3, leading=12.7, textColor=INK, leftIndent=10, firstLineIndent=-7, spaceAfter=7),
        "cell": ParagraphStyle("cell", fontName="Helvetica", fontSize=8.4, leading=10.8, textColor=INK),
        "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8.4, leading=10.8, textColor=colors.white),
        "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=9, leading=12, textColor=TEAL, spaceAfter=16),
    }
    story = []
    for pi, raw in enumerate(pages):
        if pi:
            story.append(PageBreak())
        lines = raw.strip().splitlines()
        i = 0
        body = styles["source" if pi >= 10 else "body"]
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
            if line.startswith("| "):
                tab = []
                while i < len(lines) and lines[i].strip().startswith("|"):
                    row = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    if not all(re.fullmatch(r"[-: ]+", c) for c in row):
                        tab.append(row)
                    i += 1
                n = len(tab[0])
                fractions = [0.31, 0.69] if n == 2 else [0.22, 0.38, 0.40] if n == 3 else [1 / n] * n
                if pi == 1:
                    fractions = [0.20, 0.36, 0.44]
                if pi == 9:
                    fractions = [0.24, 0.36, 0.40]
                rows = [[Paragraph(inline(c), styles["th" if j == 0 else "cell"]) for c in row] for j, row in enumerate(tab)]
                table = Table(rows, colWidths=[W * f for f in fractions], repeatRows=1, hAlign="LEFT")
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), TEAL),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#EEF4F2"), colors.HexColor("#F8FAF9")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 7),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.6, TEAL),
                ]))
                story.extend([table, Spacer(1, 11)])
                continue
            if line.startswith("# "):
                story.append(Paragraph(inline(line[2:]), styles["title"]))
            elif line.startswith("## "):
                style = styles["heading"]
                if pi == 0:
                    style = ParagraphStyle("coverSub", parent=styles["heading"], fontSize=16, leading=19)
                story.append(Paragraph(inline(line[3:]), style))
            elif line.startswith("- "):
                style = body if pi >= 10 else styles["bullet"]
                story.append(Paragraph(inline(line[2:]), style))
            else:
                parts = [line]
                while i + 1 < len(lines) and lines[i+1].strip() and not lines[i+1].startswith(("#", "|", "- ")):
                    i += 1
                    parts.append(lines[i].strip())
                style = styles["meta"] if pi == 0 and line.startswith("Business case") else body
                story.append(Paragraph(inline(" ".join(parts)), style))
            i += 1
    def footer(c, doc):
        c.saveState()
        c.setStrokeColor(colors.HexColor("#CFDCD8"))
        c.line(42, 35, A4[0]-42, 35)
        c.setFont("Helvetica", 7.5)
        c.setFillColor(MUTED)
        c.drawString(42, 23, "BEHAVIOUR TO CHEMISTRY  |  HACKATHON BUSINESS CASE  |  12 SEP 2026")
        c.drawRightString(A4[0]-42, 23, str(doc.page))
        c.restoreState()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, leftMargin=42, rightMargin=42, topMargin=38, bottomMargin=49,
                            title="The discovery platform is the asset", author="Behaviour-Chemistry project")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(OUT)
    manifest["pdf_pages"] = len(reader.pages)
    manifest["pdf_page_text_lengths"] = [len(p.extract_text()) for p in reader.pages]
    manifest["output_sha256"] = hashlib.sha256(OUT.read_bytes()).hexdigest()
    missing = []
    for dest in re.findall(r"\]\(([^)]+)\)", text):
        if not dest.startswith(("http://", "https://")) and not (SOURCE.parent / dest).resolve().exists():
            missing.append(dest)
    assert not missing, missing
    manifest["all_local_source_links_exist"] = True
    (SOURCE.parent / "evidence_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"pdf": str(OUT), "pages": len(reader.pages), "headline_counts": manifest["verified_counts"]}, indent=2))


if __name__ == "__main__":
    main()
