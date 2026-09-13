"""Reproduce the Saverschek text audit, evidence recovery, and report data offline."""

import csv
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", str(Path("tmp/matplotlib").resolve()))
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap

from src.common.io import digest, read_json, read_jsonl, write_json, write_jsonl

matplotlib.rcParams["svg.hashsalt"] = "saverschek_audit_v1"
BASE = Path("data/interim/saverschek_audit")
OUT = Path("results/saverschek_audit")
SOURCE = Path("data/interim/corpus_targeted_saverschek/texts/SAVERSCHEK2010.json")
EXTRACTION = Path("data/interim/extraction_saverschek")
PROTOCOL_COMMIT = "98b5e09199a5eef0c46be452793e953f5a2af31e"
TAX_FIELDS = ["usage_key", "accepted_usage_key", "accepted_name", "genus", "family",
              "checklist_key", "taxonomy_confidence", "taxonomy_request_hash"]


def sha(path: Path) -> str:
    """Return an exact byte digest."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_file(name: str, rows: list[dict]) -> None:
    """Write all fields without losing structured values in CSV exports."""
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with (OUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows({key: json.dumps(value, ensure_ascii=True) if isinstance(value, (dict, list))
                         else value for key, value in row.items()} for row in rows)


def bind_anchors(natural: dict, manipulation: dict, source: dict) -> dict:
    """Verify literal anchors and bind both reviewers to the immutable source."""
    blocks = {block["block_id"]: block for block in source["blocks"]}
    tail = read_json(BASE / "source_verification/recovered_tail.json")
    blocks.update({block["block_id"]: block for block in tail["blocks"]})
    anchors = {}
    for prefix, values in [("natural", natural["evidence_anchors"]),
                           ("manipulation", manipulation["anchors"])]:
        for key, raw in values.items():
            quote = raw.get("evidence_quote", raw.get("quote"))
            block = blocks[raw["block_id"]]
            assert quote in block["text"], (prefix, key, raw["block_id"])
            start = block["text"].index(quote)
            anchors[f"{prefix}:{key}"] = {
                **raw, "evidence_quote": quote, "anchor_id": f"{prefix}:{key}",
                "source_file_sha256": sha(SOURCE), "block_text_sha256": digest(block["text"]),
                "character_start": start, "character_end_exclusive": start + len(quote),
                "character_offset_representation": "Python Unicode string indices in cached block",
                "raw_request_hashes": block.get("raw_request_hashes", []),
                "original_pdf_visually_verified": False,
            }
    for key, raw in manipulation.get("recovered_tail_evidence", {}).items():
        block = blocks[raw["block_id"]]
        assert " ".join(raw["quote"].split()) == " ".join(block["text"].split())
        assert sha(Path(raw["raw_cache_path"])) == raw["raw_cache_sha256"]
        anchors[f"manipulation:{key}"] = {
            **raw, "anchor_id": f"manipulation:{key}", "evidence_quote": block["text"],
            "source_path": str(BASE / "source_verification/recovered_tail.json"),
            "source_file_sha256": sha(BASE / "source_verification/recovered_tail.json"),
            "block_text_sha256": digest(block["text"]), "character_start": 0,
            "character_end_exclusive": len(block["text"]),
            "raw_request_hashes": block["raw_request_hashes"],
            "original_pdf_visually_verified": False,
        }
    return anchors


def recover_cells(natural: dict, anchors: dict, taxonomy: dict) -> list[dict]:
    """Create distinct curator records while keeping all model records unchanged."""
    rows = []
    for cell in natural["cells"]:
        anchor_ids = [f"natural:{key}" for key in cell["evidence_anchor_ids"]]
        named = next(anchors[key] for key in anchor_ids
                     if cell["plant_name_as_written"] in anchors[key]["evidence_quote"])
        match = taxonomy.get(cell["plant_name_as_written"])
        row = {
            **cell, "record_id": digest({"curation": "saverschek_audit_v1", "cell": cell}),
            "record_type": "curated_aggregate_context", "engine": "codex_assisted_source_audit_v1",
            "provider": "manual_curation", "model_extraction_record": False,
            "source_url": natural["source_url"], "source_file_sha256": sha(SOURCE),
            "source_audit_sha256": sha(BASE / "natural_audit.json"),
            "taxonomic_rank": "species", "substrate_treatment": "natural",
            "audit_rejection_timing": cell["rejection_timing"],
            "rejection_timing": {"immediate_pattern": "immediate", "not_applicable": "unspecified"}
            .get(cell["rejection_timing"], cell["rejection_timing"]),
            "evidence_type": "field_choice_assay", "behavioural_choice": True,
            "choice_design": cell["experiment_id"],
            "strict_alternatives_eligible": cell["experiment_id"] == "simultaneous_choice",
            "evidence_group_id": cell["independence_group_id"],
            "section": f"Published page {named['publication_page']}",
            "block_id": named["block_id"], "evidence_quote": named["evidence_quote"],
            "evidence_anchor_ids": anchor_ids,
            "grounding_method": "multiple exact anchors: name, author direction, habitat/day, methods",
            "quantitative_measure": None, "quantitative_measure_verified": False,
            "semantic_decision": "include" if cell["outcome"] != "unclear" else "review",
            "taxonomy_status": "exact" if match else "review_variant_spelling",
            "original_source_id": None,
            "study_context": f"{cell['experiment_id']}; habitat {cell['habitat']}; day {cell['test_day']}; pooled report of three colonies",
        }
        if match:
            row.update({key: match[key] for key in TAX_FIELDS})
        rows.append(row)
    return rows


def aggregate(rows: list[dict], genus_key: str = "genus") -> list[dict]:
    """Apply the frozen all-directions rule without counting repeated cells as support."""
    groups = {}
    for row in rows:
        if row.get(genus_key):
            groups.setdefault(row[genus_key], []).append(row)
    output = []
    for genus, members in sorted(groups.items()):
        directions = sorted({row["outcome"] for row in members
                             if row["outcome"] in {"accepted", "rejected"}})
        status = "conflict" if len(directions) > 1 else directions[0] if directions else "unclear"
        output.append({
            "genus": genus, "status": status, "directions": directions,
            "record_count_descriptive_only": len(members),
            "source_count": len({row["source_id"] for row in members}),
            "sources": sorted({row["source_id"] for row in members}),
            "ant_species": sorted({row["ant_species"] for row in members}),
            "families": sorted({row["family"] for row in members if row.get("family")}),
            "record_ids": [row["record_id"] for row in members],
            "independent_sample_size": None,
            "chemistry_joined": False,
        })
    return output


def sensitivity_rows(rows: list[dict], scope: str) -> list[dict]:
    """Reaggregate each evidence subset before any chemistry join."""
    subsets = {
        "all_supported_natural": rows,
        "simultaneous_alternatives_only": [r for r in rows if r.get("strict_alternatives_eligible")],
        "individual_pickup_only": [r for r in rows if r.get("choice_design") == "individual_pickup"],
        "delayed_rejection_and_acceptance": [r for r in rows if r["outcome"] == "accepted"
                                            or (r["outcome"] == "rejected"
                                                and r["rejection_timing"] == "delayed")],
    }
    result = []
    for name, members in subsets.items():
        genera = aggregate(members)
        counts = Counter(g["status"] for g in genera)
        result.append({"scope": scope, "subset": name, **{key: counts[key]
                       for key in ["accepted", "rejected", "conflict", "unclear"]},
                       "records_descriptive_only": len(members),
                       "two_directional_genera_each_before_chemistry": counts["accepted"] >= 2
                       and counts["rejected"] >= 2,
                       "enrichment_status": "not_estimated_no_chemistry_join",
                       "genera": [{"genus": g["genus"], "status": g["status"]} for g in genera]})
    return result


def extraction_rows() -> list[dict]:
    """Audit every original candidate without mixing curator contexts into its denominator."""
    review = read_json(EXTRACTION / "semantic_review.json")
    decisions = {r["record_id"]: r for r in review["decisions"]}
    rows = []
    for row in read_jsonl(EXTRACTION / "observations.jsonl"):
        decision = decisions[row["record_id"]]
        rows.append({"candidate_id": row["record_id"], "plant": row["plant_name_as_written"],
                     "model_direction": row["outcome"], "automatic_gate": "pass",
                     "semantic_gate": decision["decision"], "reason": decision["reason_code"],
                     "raw_file": str(EXTRACTION / "observations.jsonl"),
                     "input_hash": row["input_hash"], "candidate_hash": digest(row)})
    for row in read_jsonl(EXTRACTION / "rejections.jsonl"):
        candidate = row["candidate"]
        rows.append({"candidate_id": digest(row), "plant": candidate["plant_name_as_written"],
                     "model_direction": candidate["outcome"], "automatic_gate": "fail",
                     "semantic_gate": "not_promoted_original_failure_preserved",
                     "reason": row["reason"], "raw_file": str(EXTRACTION / "rejections.jsonl"),
                     "input_hash": row["input_hash"], "candidate_hash": digest(candidate)})
    assert len(rows) == 14
    return rows


def matrix_figure(cells: list[dict], plants: list[dict]) -> None:
    """Plot author-assigned directions without substituting signs of numerical indices."""
    names = [p["plant_name_as_written"] for p in plants]
    columns = [("individual_pickup", habitat, day) for habitat in ["p", "a"] for day in [1, 2, 3]]
    columns += [("simultaneous_choice", habitat, day) for habitat in ["p", "a"] for day in [1, 2]]
    lookup = {(r["plant_name_as_written"], r["experiment_id"], r["habitat"], r["test_day"]): r
              for r in cells}
    codes = {"unclear": 0, "accepted": 1, "rejected": 2}
    matrix = np.array([[codes[lookup[(name, *column)]["outcome"]] for column in columns]
                       for name in names])
    fig, ax = plt.subplots(figsize=(11.8, 6.5))
    ax.imshow(matrix, cmap=ListedColormap(["#E4E8EB", "#227A65", "#AD5136"]), vmin=0, vmax=2,
              aspect="auto")
    ax.set_xticks(range(10), [f"{habitat.upper()} / day {day}" for _, habitat, day in columns], fontsize=9)
    ax.set_yticks(range(11), names, fontsize=10)
    ax.tick_params(length=0, pad=8)
    for y in range(11):
        for x in range(10):
            code = matrix[y, x]
            ax.text(x, y, ["?", "A", "R"][code], ha="center", va="center", fontsize=11,
                    color="#34424C" if code == 0 else "white", fontweight="bold")
    ax.set_xticks(np.arange(-0.5, 10, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 11, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=2)
    ax.tick_params(which="minor", bottom=False, left=False)
    ax.axvline(5.5, color="#133B3A", linewidth=3)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_title("INDIVIDUAL PICKUP (6 contexts)     |     SIMULTANEOUS CHOICE (4 contexts)",
                 fontsize=11, pad=18, fontweight="bold")
    fig.text(0.25, 0.075, "A  accepted     R  rejected     ?  direction unresolved from cached text",
             fontsize=10)
    fig.text(0.25, 0.035, "P = plant present in habitat; A = absent. Cells summarize three colonies; they are not independent replicates.",
             fontsize=8.5)
    fig.subplots_adjust(left=0.25, right=0.985, top=0.88, bottom=0.15)
    fig.savefig(OUT / "behavior_matrix.png", dpi=180, facecolor="white")
    fig.savefig(OUT / "behavior_matrix.svg", facecolor="white", metadata={"Date": None})
    plt.close(fig)


def paragraph(text: str) -> dict:
    """Create a report paragraph."""
    return {"type": "paragraph", "text": text}


def report_table(headers: list[str], rows: list[list], widths: list[int]) -> dict:
    """Create a report table shared by Markdown and PDF renderers."""
    return {"type": "table", "headers": headers, "rows": rows, "widths": widths}


def report_pages(natural: dict, manipulation: dict, plants: list[dict], summary: dict,
                 sensitivities: list[dict], extraction: list[dict]) -> list[dict]:
    """Compose a complete readable account with limitations next to each claim."""
    primary = summary["combined_genus_counts"]
    pages = [{"title": "The rejection evidence is real.\nIts scope is specific.",
              "lead": "Saverschek et al. (2010): complete text-based behavioural audit, with explicit visual-verification gaps.",
              "items": [paragraph("The natural-substrate experiments support five consistently rejected source genera, one accepted genus and five conflicted genera. Ten of eleven species pass the frozen exact GBIF rule; Trema is a high-confidence VARIANT (98), so it remains on hold. Four rejecting genera are therefore ready for the taxonomy-filtered dataset."),
                        report_table(["Plant as published", "Across natural assays", "Taxonomy"],
                                     [[p["plant_name_as_written"], p["within_source_direction_status"],
                                       "Exact" if p["taxonomy_status"] == "exact" else "Variant - hold"] for p in plants],
                                     [230, 170, 110]),
                        paragraph("This is evidence of voluntary leaf-disc collection, avoidance and learning in Atta colombica. It is not direct proof of fungal toxicity, chemical identity, or activity against human-pathogenic fungi."),
                        paragraph("Source: Avoiding plants unsuitable for the symbiotic fungus: learning and long-term memory in leaf-cutting ants. Animal Behaviour 79, 689-698. DOI: 10.1016/j.anbehav.2009.12.021. Audit date: 12 September 2026.")]}]
    pages.append({"title": "Every natural-assay context", "lead": "110 context cells: 87 text-supported directions, 23 unresolved directions. Zero visually verified numerical cells.",
                  "items": [{"type": "image", "path": str(OUT / "behavior_matrix.png"), "width": 510, "height": 281},
                            paragraph("Individual pickup: 66 cells, 10 accepted and 56 rejected. Simultaneous choice: 44 cells, eight accepted, 13 rejected and 23 unresolved. The unresolved cells need original Figure 4; a rank position or positive index alone is not used to invent an author-assigned direction."),
                            paragraph("Hymenaea, Inga, Tetragastris and Trichilia are initially accepted in the plant-absent habitat and subsequently rejected. Miconia is rejected when offered alone but accepted with alternatives. All five remain conflicts under the all-directions rule."),
                            paragraph("Spondias is explicitly accepted in all individual tests. Its simultaneous assay rank and positive index are recorded in the source audit, but the exact habitat/day direction cells remain conservative unknowns. Unknowns contribute no direction; 'consistent' refers only to supported observations."),
                            paragraph("The categorical matrix is reconstructed from author prose and table groups. It is not a redraw of Figure 4 and does not encode numerical effect sizes.")]})
    pages.append({"title": "Design, dependence and eligibility", "lead": "Prepared natural discs; voluntary field collection; distinct single-species and simultaneous assays.",
                  "items": [report_table(["Feature", "Individual pickup", "Simultaneous choice"],
                                          [["Plant panel", "11 species: ten seldom harvested plus Spondias comparator", "Same eleven species"],
                                           ["Sampling", "Three colonies per plant/habitat; days 1-3", "Three different colonies per habitat; days 1-2"],
                                           ["Observation", "Up to 30 min; uptake and trail clearing; oat test beforehand", "45 min; plant discs and sugared oat co-presented"],
                                           ["Exposure history", "Additional plant feeding after first acceptance; later days measure response after exposure", "Additional plant feeding after day 1"],
                                           ["Dependence", "198 reported tests; colony identities across plants not reconstructable", "12 design-implied colony-day sessions; repeated measurements"]], [90, 210, 210]),
                            paragraph("Habitat P was Barro Colorado Island, where the tested plants occurred; habitat A was Gamboa, where they were absent. Prior experience is inferred from habitat and is confounded with site. The selected plants do not represent a random sample of local flora."),
                            paragraph("The frozen protocol's feeding-choice wording is implemented as voluntary collection/rejection of natural substrate. Simultaneous alternatives are reported as a separate stricter sensitivity. Forced plant damage in the earlier jasmonate study is not comparative-preference evidence."),
                            paragraph("Cells are pooled author summaries, not independent workers, colonies or papers. Colony IDs, individual outcomes and covariance are unavailable. This audit does not refit the paper's models, regenerate its P-values, or claim extraction accuracy from context counts."),
                            paragraph("Natural rejection is not equivalent to antifungal action: the authors leave fungal mediation of the natural avoidance series unresolved. The separate CHX manipulation addresses learned avoidance after an experimental insult.")]})
    phases = manipulation["phases"]
    for part, selected in enumerate([phases[:6], phases[6:]]):
        pages.append({"title": ["Treatment history changes the claim", "Memory, recovery and controls"][part],
                      "lead": "Stigmaphyllon lindenianum: the full phase ledger is retained separately from natural-substrate inference.",
                      "items": [report_table(["Phase / timing", "Reported behaviour", "Primary decision and reason"],
                                              [[str(p["phase_id"]).replace("_", " ") + "\n" + str(p.get("time") or "Not reported"),
                                                str(p["direction"]).replace("_", " "),
                                                p["decision"].upper() + ": " + p["reason"]] for p in selected],
                                              [120, 105, 285]),
                                paragraph("CHX = cycloheximide. Test leaves described as untreated after induction are CHX-free but explicitly sugared; colonies have a treatment history. Intercepting returning carriers limits corrective experience. These outcomes cannot classify intrinsic natural Stigmaphyllon chemistry." if part == 0 else
                                          "Figure 7 uses intake minus trail-clearing events per 30 min, unlike the oat-standardized natural index. Its recovered caption reports five colonies at weeks 14/16 and four at week 18, conflicting with prose mentioning three of five still clearing at week 18. The reason for the missing colony is not given. Figure 6 also conflicts with methods on long-term sample size; no silent harmonization is made.")]})
    pages.append({"title": "What Gemini extracted - and missed", "lead": "Three completed chunks; 14 candidates; six automatic passes; eight automatic failures; no API failures.",
                  "items": [report_table(["Original candidate", "Direction", "Gate / review"],
                                          [[r["plant"], r["model_direction"],
                                            "pass / " + r["semantic_gate"] if r["automatic_gate"] == "pass" else "fail / " + r["reason"]]
                                           for r in extraction], [185, 75, 250]),
                            paragraph("Of six automatic passes, source review retained three contextual natural observations, excluded the conditioned retest and held two records for review. They represent three distinct genera, but only Spondias and Desmopsis remain direction-eligible; Hymenaea is conflicted."),
                            paragraph("Curator recovery accounts for all eleven natural plants and both designs. Miconia was absent from model candidates. Initial acceptance of the four delayed genera was missing as separate output. Eight failed model candidates stay failed: corrections have separate IDs and multi-anchor provenance."),
                            paragraph("The original pilot remains 47 candidates -> 35 automatic passes -> six semantic inclusions. This is retention, not validated model precision or recall. The 110 audit cells use a different unit and must not enter either model-candidate denominator.")]})
    inventory = [[f"Figure {f['figure']}", f["topic"],
                  "Caption recovered from raw tail; graphic unverified" if f["figure"] == 7 else "Caption/text audited; graphic unverified"]
                 for f in manipulation["figure_inventory"]]
    inventory.append(["Table 1", "All 11 rows and 66 numerical tokens preserved",
                      "Author groups audited; numeric glyphs/layout unverified"])
    pages.append({"title": "Source verification and open issues", "lead": "All reported study components are inventoried. Original PDF graphics remain unavailable.",
                  "items": [report_table(["Component", "Content", "Verification"], inventory, [65, 265, 180]),
                            paragraph("The archive contains 1,005 indexed lines from the ten-page published article. The original model corpus has nine body-page blocks and stops at the References heading; this removed Figure 7's caption, which is now restored as an audit-only supplement. Original model inputs and raw responses remain unchanged."),
                            paragraph("Current author-PDF screenshot requests failed and no accessible alternate original PDF was found. Numerical control glyphs in Table 1 are preserved verbatim plus a labelled provisional normalization. The table's plus/minus component is not explicitly typed in its cached caption; it is not assumed to be a standard error."),
                            paragraph("Unresolved: 23 Figure 4 directional cells; all graphic coordinates; Table 1 signs/layout and Spondias 0.39 versus prose maximum 0.38; baseline/control sugar status; long-term sample sizes and week-18 attrition; exact colony IDs. No reported inferential statistic is independently reproduced.")]})
    selected_sensitivity = [s for s in sensitivities if s["scope"] == "combined_current"]
    pages.append({"title": "What this enables next", "lead": f"Under the current acceptability rule: {primary.get('accepted', 0)} accepted and {primary.get('rejected', 0)} rejected genera before chemistry; five conflicted genera excluded.",
                  "items": [report_table(["Subset (exact taxonomy)", "Accepted", "Rejected", "Conflict"],
                                          [[s["subset"].replace("_", " "), s["accepted"], s["rejected"], s["conflict"]]
                                           for s in selected_sensitivity], [315, 65, 65, 65]),
                            paragraph("This targeted behavioural source extends the frozen 30-paper sample; it is not a random corpus expansion. The combined snapshot replaces the three old Saverschek rows with curated evidence. Earlier records retain their provenance and design labels. Miconia is held across sources because its opposite directions matter even when another study reports acceptance."),
                            paragraph("No chemistry or antifungal activity outcomes were joined. Enrichment remains uncomputed. At least two genera in each direction must survive the chemistry join. These ten eligible behavioural genera cannot yet meet the frozen 25-joined-genus feasibility target, even with perfect chemistry coverage. The strict simultaneous subset has only one accepted genus and fails the minimum comparison requirement."),
                            paragraph("Next: resolve Trema's spelling under a separately documented taxonomy decision; recover the original Figure 4 and verify table glyphs; then import traceable natural-product occurrences and the precommitted ChEMBL activity endpoints. Do not relax the protocol to increase apparent coverage."),
                            paragraph("Reproduce locally: .venv/bin/python -m scripts.build_saverschek_audit. Inputs, source anchors, raw candidate hashes, taxonomy request hashes, cell matrix, phase ledger, figure inventory, conflict tables and automated checks are indexed in manifest.json. The PDF renderer reads report_content.json. The model corpus, prompt, original outputs and frozen protocol are unchanged."),
                            paragraph(f"Protocol commit: {PROTOCOL_COMMIT}. Audit provenance: Codex-assisted manual source review, not an independent blinded human replication. This is a complete text audit with disclosed unresolved fields, not complete graphical verification.")]})
    return pages


def markdown_report(pages: list[dict]) -> str:
    """Render the same report content to plain, portable Markdown."""
    parts = ["# Saverschek 2010: audited behavioural study\n"]
    for page in pages:
        parts.extend([f"\n## {page['title'].replace(chr(10), ' ')}\n", page.get("lead", "") + "\n"])
        for item in page["items"]:
            if item["type"] == "paragraph":
                parts.append(item["text"] + "\n")
            elif item["type"] == "table":
                parts.extend(["| " + " | ".join(item["headers"]) + " |",
                              "| " + " | ".join("---" for _ in item["headers"]) + " |"])
                parts.extend("| " + " | ".join(str(v).replace("\n", "; ").replace("|", "/")
                                                for v in row) + " |" for row in item["rows"])
                parts.append("")
            elif item["type"] == "image":
                parts.append("![Author-direction matrix](behavior_matrix.png)\n")
    return "\n".join(parts)


def main() -> None:
    """Verify source evidence, recover all contexts, and write the audit packet."""
    OUT.mkdir(parents=True, exist_ok=True)
    natural = read_json(BASE / "natural_audit.json")
    manipulation = read_json(BASE / "manipulation_audit.json")
    source = read_json(SOURCE)
    assert natural["source_file_sha256"] == sha(SOURCE)
    anchors = bind_anchors(natural, manipulation, source)
    taxonomy = {r["plant_name_as_written"]: r for r in read_jsonl(BASE / "taxonomy/observations.jsonl")}
    cells = recover_cells(natural, anchors, taxonomy)
    assert len(cells) == len({r["cell_id"] for r in cells}) == 110
    assert Counter(r["experiment_id"] for r in cells) == {"individual_pickup": 66, "simultaneous_choice": 44}
    plants = [{**p, "taxonomy_status": "exact" if p["plant_name_as_written"] in taxonomy else "review_variant_spelling",
               **{k: taxonomy[p["plant_name_as_written"]][k] for k in TAX_FIELDS
                  if p["plant_name_as_written"] in taxonomy}} for p in natural["plants"]]
    directional = [r for r in cells if r["outcome"] in {"accepted", "rejected"}]
    matched = [r for r in directional if r["taxonomy_status"] == "exact"]
    prior = [r for r in read_jsonl(Path("data/interim/evidence_current/contextual_observations.jsonl"))
             if r["source_id"] != "SAVERSCHEK2010"]
    combined = prior + matched
    assert len({r["record_id"] for r in combined}) == len(combined)
    genera = aggregate(combined)
    statuses = {r["genus"]: r["status"] for r in genera}
    combined = [{**r, "combined_genus_status": statuses[r["genus"]],
                 "primary_genus_eligible": statuses[r["genus"]] in {"accepted", "rejected"}}
                for r in combined]
    eligible = [r for r in combined if statuses[r["genus"]] in {"accepted", "rejected"}]
    conflict = [r for r in combined if statuses[r["genus"]] == "conflict"]
    sensitivities = sensitivity_rows(matched, "saverschek_only") + sensitivity_rows(combined, "combined_current")
    candidates = extraction_rows()
    tables = [{"cell_id": r["cell_id"], "plant": r["plant_name_as_written"], "habitat": r["habitat"],
               "day": r["test_day"], "author_direction": r["outcome"], **r["table_cell"]}
              for r in cells if r.get("table_cell")]
    assert len(tables) == 66 and not any(r["use_as_verified_quantitative_measure"] for r in tables)
    summary = {
        "audit_version": 1, "audit_date": "2026-09-12", "protocol_commit": PROTOCOL_COMMIT,
        "status": "complete_text_audit_with_explicit_visual_and_numeric_gaps",
        "source_id": "SAVERSCHEK2010", "natural_species": len(plants), "context_cells": len(cells),
        "directional_context_cells": len(directional), "unresolved_context_cells": len(cells) - len(directional),
        "source_genus_counts": dict(Counter(p["within_source_direction_status"] for p in plants)),
        "exact_taxa": len(taxonomy), "taxonomy_review_taxa": 11 - len(taxonomy),
        "source_exact_genus_counts": dict(Counter(g["status"] for g in aggregate(matched))),
        "combined_records": len(combined), "combined_genus_counts": dict(Counter(g["status"] for g in genera)),
        "combined_eligible_records": len(eligible), "combined_conflict_records": len(conflict),
        "manipulation_phases": len(manipulation["phases"]),
        "manipulation_decisions": dict(Counter(p["decision"] for p in manipulation["phases"])),
        "source_anchor_count": len(anchors), "visual_numeric_cells_verified": 0,
        "independent_observation_count": None, "chemistry_joined": False,
        "extraction_metrics": read_json(EXTRACTION / "metrics.json"),
        "replacement_policy": "Replace all three previous included Saverschek rows; do not append to prior snapshot.",
    }
    for name, rows in [("natural_contexts", cells), ("curated_directional_observations", directional),
                       ("taxonomy_matched_directional", matched), ("combined_contextual_observations", combined),
                       ("combined_genus_eligible_observations", eligible), ("combined_conflict_hold", conflict),
                       ("combined_genera", genera), ("source_genus_audit", plants),
                       ("manipulation_phases", manipulation["phases"]), ("extraction_candidate_audit", candidates),
                       ("sensitivity_counts", sensitivities), ("table1_provisional_transcription", tables)]:
        write_jsonl(OUT / f"{name}.jsonl", rows)
        table_file(f"{name}.csv", rows)
    write_json(OUT / "summary.json", summary)
    write_json(OUT / "evidence_anchors.json", anchors)
    write_json(OUT / "figure_table_inventory.json", {"figures": manipulation["figure_inventory"],
                                                     "tables": manipulation["table_inventory"]})
    write_json(OUT / "source_verification.json", read_json(BASE / "source_verification.json"))
    write_json(OUT / "figure7_recovered_tail.json", read_json(BASE / "source_verification/recovered_tail.json"))
    write_json(OUT / "secondary_claims.json", manipulation["secondary_claim_groups"])
    write_json(OUT / "unresolved_items.json", {
        "manipulation": manipulation["unresolved_items"], "natural": natural["scope_limitations"],
        "unresolved_cells": [r["cell_id"] for r in cells if r["outcome"] == "unclear"],
        "taxonomy": read_jsonl(BASE / "taxonomy/review.jsonl"),
    })
    matrix_figure(cells, plants)
    pages = report_pages(natural, manipulation, plants, summary, sensitivities, candidates)
    write_json(OUT / "report_content.json", {"title": "Saverschek 2010: audited behavioural study", "pages": pages})
    (OUT / "study_report.md").write_text(markdown_report(pages))
    checks = {
        "passed": True, "exact_anchors_verified": len(anchors), "all_110_unique_contexts": True,
        "all_66_table_tokens_preserved": True, "numeric_fields_not_used_for_direction": True,
        "all_14_original_candidates_accounted_for": True, "curation_separate_from_model": True,
        "source_digest_matches_review": True, "no_duplicate_record_ids_in_combined_snapshot": True,
        "opposing_directions_retained": True, "original_pdf_visually_verified": False,
        "note": "Checks verify internal consistency and source grounding; they do not replace expert review or visual source verification.",
    }
    write_json(OUT / "validation.json", checks)
    inputs = [SOURCE, BASE / "natural_audit.json", BASE / "manipulation_audit.json",
              BASE / "source_verification.json", BASE / "source_verification/recovered_tail.json",
              BASE / "taxonomy/observations.jsonl", BASE / "taxonomy/review.jsonl",
              Path("docs/analysis_plan.md"), Path("config/analysis.json"),
              Path("data/interim/evidence_current/contextual_observations.jsonl"),
              Path("scripts/build_saverschek_audit.py"), Path("scripts/render_saverschek_report.py")]
    inputs += sorted(p for p in EXTRACTION.rglob("*") if p.is_file())
    write_json(OUT / "manifest.json", {
        "audit_version": 1, "protocol_commit": PROTOCOL_COMMIT,
        "rebuild": ".venv/bin/python -m scripts.build_saverschek_audit",
        "network_required_for_rebuild": False,
        "inputs": [{"path": str(p), "sha256": sha(p)} for p in inputs],
        "artifacts": [{"path": str(p), "sha256": sha(p)} for p in sorted(OUT.iterdir())
                      if p.is_file() and p.name not in {"manifest.json", "saverschek_audit_bundle.zip"}],
    })
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
