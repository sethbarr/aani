"""Fresh-clone smoke test for the PDF run report."""

import json
from pathlib import Path

from pypdf import PdfReader

from scripts.render_report import ROOT, inline, render, strip_links


def test_inline_markup() -> None:
    """Links reduce to labels; bold and code become markup; XML is escaped."""
    assert strip_links("see [funnel](../results/funnel.json) now") == "see funnel now"
    assert inline("**bold** and `code` & <x>") == '<b>bold</b> and <font face="Courier">code</font> &amp; &lt;x&gt;'


def test_render_from_committed_results(tmp_path: Path) -> None:
    """The committed results render to a multi-page PDF in a created directory."""
    output = tmp_path / "nested" / "report.pdf"
    record = render(ROOT / "results/pipeline_report.md", ROOT / "results/funnel.json",
                    ROOT / "results/summary.json", output)
    assert output.exists()
    assert record["pages"] >= 2
    assert len(PdfReader(str(output)).pages) == record["pages"]
    assert json.dumps(record)
