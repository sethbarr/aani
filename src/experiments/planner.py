"""Build draft fungal panels without inventing assay parameters or measured outcomes."""

import csv
import hashlib
import io
import json
import random
from pathlib import Path

from src.common.io import digest, write_json
from src.experiments.render import render_viewer

CONTROLS = ("vehicle_growth", "medium_blank", "reference_antifungal")
MISSING = (
    "isolate_id", "sample_source", "assay_method_version", "dose_values_and_units",
    "compound_identity_purity_and_stock", "solvent_and_solubility", "medium",
    "preparation_and_incubation", "readout_and_endpoint", "reference_control",
    "lab_acceptance", "physical_labware_and_instruments",
)


def _unique_rows(rows: list[dict], key: str) -> dict[str, dict]:
    """Index records without silently overwriting duplicate identifiers."""
    result = {}
    for row in rows:
        value = row[key]
        if value in result:
            raise ValueError(f"Duplicate {key}: {value}")
        result[value] = row
    return result


def build_plan(
    evidence: list[dict], config: dict, record_ids: list[str] | None = None,
    fungus_ids: list[str] | None = None,
) -> dict:
    """Create a deterministic draft with source snapshots and unresolved method fields."""
    by_record = _unique_rows(evidence, "record_id")
    by_fungus = _unique_rows(config["fungi"], "id")
    records = config["default_records"] if record_ids is None else record_ids
    fungi = (
        [row["id"] for row in config["fungi"] if row["scope"] == "core"]
        if fungus_ids is None else fungus_ids
    )
    for name, values, index in (("record", records, by_record), ("fungus", fungi, by_fungus)):
        if not values or len(values) != len(set(values)):
            raise ValueError(f"Select at least one {name}; duplicate selections are not allowed")
        if missing := set(values) - set(index):
            raise ValueError(f"Unknown {name} IDs: {', '.join(sorted(missing))}")
    design = dict(config["design"])
    for name in ("dose_slots", "technical_replicates", "independent_runs"):
        value = design[name]
        if type(value) is not int or value < 1:
            raise ValueError(f"{name} must be a positive integer")
    if type(design["layout_seed"]) is not int:
        raise ValueError("layout_seed must be an integer")
    candidates = []
    material_keys = set()
    for record_id in records:
        source = by_record[record_id]
        # Multiple endpoints from the same material are evidence, not new candidates.
        material_key = tuple(
            source.get(k, "") for k in ("material", "material_type", "source_plant", "source_organ")
        )
        if material_key in material_keys:
            raise ValueError("Select one representative record per material, not multiple endpoints")
        material_keys.add(material_key)
        if not source.get("original_url") or not source.get("source_locator"):
            raise ValueError(f"Record {record_id} needs a source URL and locator")
        candidates.append({
            "id": record_id, "name": source["material"],
            "material_type": source["material_type"],
            "selection_reason": config["candidate_roles"].get(record_id, "User-selected evidence"),
            "evidence": source,
            "availability": "Not sourced; identity, stock and supply require confirmation",
        })
    organisms = [dict(by_fungus[key]) for key in fungi]
    for organism in organisms:
        organism["method"] = dict.fromkeys(MISSING)
        organism["status"] = "planned"
    identity = {"candidates": candidates, "fungi": organisms, "design": design,
                "source_config_hash": digest(config)}
    plan = {
        "schema_version": "1.0", "plan_id": "fungal-" + digest(identity)[:12],
        "status": "draft", "biological_execution_ready": False,
        "robot_demo_report": "simulation_report.json", "results_status": "not_run",
        "purpose": design["purpose"], "design": design, "candidates": candidates,
        "fungi": organisms,
        "specialist_options": [x for x in config["fungi"] if x["scope"] == "specialist"],
        "partners": config["partners"], "source_checked_on": config["source_checked_on"],
        "source_config_hash": digest(config),
        "limitations": [
            "Dose slots are labels; no biological doses, volumes or incubation times are assigned.",
            "One proposed isolate per fungus does not establish species-wide susceptibility.",
            "Technical wells are not independent biological replicates; runs retain separate IDs.",
            "The 96-well layout is a capacity illustration, not an approved format for every fungus.",
            "Normalize within each validated assay; do not pool raw growth or mix MIC with IC50.",
            "Unknown and untested outcomes remain unknown; broad activity requires valid measured data.",
            "New measurements belong in prospective validation, separate from the frozen analysis.",
        ],
    }
    matrix = []
    for fungus in organisms:
        for candidate in candidates:
            matrix.append({
                "plan_id": plan["plan_id"], "fungus_id": fungus["id"],
                "fungus": fungus["name"], "candidate_id": candidate["id"],
                "material": candidate["name"], "status": "not_tested",
                "isolate_id": None, "assay_method_version": None,
                "endpoint": None, "value": None, "unit": None, "qc_status": None,
                "raw_data_uri": None, "source_record_id": candidate["id"],
            })
    plan["matrix"] = matrix
    plan["layout"] = build_layout(plan)
    # Put selected records first so the catalogue preserves their representative endpoints.
    options = list(candidates)
    seen = set(material_keys)
    for source in evidence:
        key = tuple(source.get(k, "") for k in (
            "material", "material_type", "source_plant", "source_organ"))
        if (key in seen or source.get("material_type") != "pure_compound"
                or not source.get("original_url") or not source.get("source_locator")):
            continue
        seen.add(key)
        options.append({
            "id": source["record_id"], "name": source["material"],
            "material_type": source["material_type"], "evidence": source,
            "selection_reason": "Source-backed option; review evidence and availability",
            "availability": "Not sourced; identity, stock and supply require confirmation",
        })
    plan["catalog"] = {"candidates": options, "fungi": config["fungi"]}
    return plan


def build_layout(plan: dict) -> list[dict]:
    """Allocate placeholder treatments with per-plate controls and explicit run identities."""
    design = plan["design"]
    reps = design["technical_replicates"]
    # Each candidate needs matched material-only blanks at every dose slot.
    per_candidate = 2 * design["dose_slots"] * reps
    per_plate_controls = len(CONTROLS) * reps
    capacity = (96 - per_plate_controls) // per_candidate
    if capacity < 1:
        raise ValueError("A candidate with matched blanks and controls exceeds 96-well capacity")
    output = []
    for fungus in plan["fungi"]:
        for run in range(1, design["independent_runs"] + 1):
            for start in range(0, len(plan["candidates"]), capacity):
                batch = start // capacity + 1
                plate_id = f"{fungus['id']}-run{run}-plate{batch}"
                conditions = []
                for candidate in plan["candidates"][start:start + capacity]:
                    for dose in range(1, design["dose_slots"] + 1):
                        for role in ("treatment", "material_only_blank"):
                            for replicate in range(1, reps + 1):
                                conditions.append((candidate["id"], f"D{dose}", role, replicate))
                for role in CONTROLS:
                    for replicate in range(1, reps + 1):
                        conditions.append((None, None, role, replicate))
                seed = f"{design['layout_seed']}:{plate_id}"
                wells = [f"{row}{col}" for row in "ABCDEFGH" for col in range(1, 13)]
                random.Random(seed).shuffle(wells)
                for well, (candidate, dose, role, replicate) in zip(wells, conditions, strict=False):
                    output.append({
                        "plan_id": plan["plan_id"], "plate_id": plate_id,
                        "fungus_id": fungus["id"], "independent_run": run,
                        "isolate_id": None, "well": well, "candidate_id": candidate,
                        "dose_slot": dose, "dose_value": None, "dose_unit": None,
                        "role": role, "technical_replicate": replicate,
                        "layout_status": "illustrative_not_lab_approved",
                    })
    return output


def csv_text(rows: list[dict]) -> str:
    """Serialize a table with empty cells for missing values and safe spreadsheet text."""
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    for row in rows:
        writer.writerow({
            key: "'" + value if isinstance(value, str) and value.startswith(("=", "+", "-", "@"))
            else value for key, value in row.items()
        })
    return buffer.getvalue()


def handoff_briefs(plan: dict) -> dict[str, str]:
    """Produce local drafts for partner review without claiming API integration."""
    candidates = "\n".join(
        f"- {c['name']} ({c['id']}, {c['material_type']}): "
        f"{c['evidence']['original_url']} — {c['evidence']['source_locator']}"
        for c in plan["candidates"]
    )
    fungi = "\n".join(f"- {f['name']}: {f['assay_family']}" for f in plan["fungi"])
    common = (
        f"Plan: {plan['plan_id']}\nStatus: draft; no samples sourced or experiments run.\n\n"
        f"Objective: {plan['purpose']}\n\nCandidates\n{candidates}\n\nFungal panel\n{fungi}\n\n"
        "Attachments: experiment_plan.json, study_matrix.csv and illustrative_plate_map.csv.\n"
        "Dose labels are unassigned. Historical assay values are evidence, not new settings.\n"
        "Keep an isolated cultivar distinct from a mixed garden sample. Use organism-specific "
        "methods and controls; preserve independent run IDs and raw measurements.\n"
        "Return assay versions, isolate IDs, actual exposures, raw data, QC and uncertainty. "
        "Unknown is not inactive; results apply to the tested isolates and conditions.\n\n"
    )
    return {
        "potato": "# Potato planning handoff — draft, not submitted\n\n" + common + (
            "Help refine this panel into source-backed protocols and identify the missing "
            "method parameters for each organism. Assess solubility, material-only interference "
            "controls, assay readouts, replicate structure and format suitability before exporting.\n\n"
            "Please confirm available Protocol Builder / Research Plan / Optimizer access, "
            "supported imports or API, OT-2 export, and any remote-lab integration. The intended "
            "role is experiment planning; physical execution needs a laboratory. We have not "
            "verified Potato-to-Opentrons or Potato-to-Emerald compatibility.\n\n"
            "Public reference: https://www.potato.ai/products/\n"
        ),
        "emerald": "# Remote lab feasibility brief — draft, not submitted\n\n" + common + (
            "Please assess which panel members and materials your facility accepts, whether "
            "existing assays fit each organism, and whether cultivar work requires method "
            "development. Quote setup, consumables, instrument/operator time, sample handling "
            "and turnaround separately. No cost or completion date is assumed.\n\n"
            "Please specify sample requirements, required identifiers, suitable readouts, "
            "and the translation into ECL Command Center / Symbolic Lab Language. The local "
            "Opentrons water demonstration is not an ECL-compatible biological protocol.\n\n"
            "Public references: https://www.emeraldcloudlab.com/how-it-works/ and "
            "https://www.emeraldcloudlab.com/documentation/functions/\n"
        ),
        "gerardo": "# Cultivar collaboration inquiry — draft, not sent\n\n" + (
            "Hi Nicole,\n\nI'm building a hackathon project linking leafcutter ant plant "
            "selection to candidate antifungal chemistry. The next step is to compare a small "
            "compound panel across diverse fungi, including the cultivated fungus relevant "
            "to the ecological hypothesis.\n\nDoes your lab currently maintain an identified "
            "cultivar isolate that might be available for a small collaborative pilot, or "
            "could you suggest a collaborator who does? An isolate with host-ant identity, "
            "donor colony and origin, fungal identification, culture history and an existing "
            "growth-assay reference would be especially useful. Multiple independent colony "
            "isolates could support a later robustness check.\n\nIf an intact garden sample "
            "is the available material, we would treat it as a separate community-level "
            "experiment. Would your lab prefer to run the cultivar arm locally, or discuss "
            "a transfer to a participating laboratory?\n\nThis is an exploratory project; "
            "sample availability, timing and collaboration arrangements are still open.\n"
        ),
    }


def water_protocol(plan: dict) -> str:
    """Export a water-only OT-2 demonstration of one representative layout."""
    plate_id = plan["layout"][0]["plate_id"]
    wells = [row["well"] for row in plan["layout"] if row["plate_id"] == plate_id]
    return f'''"""Water-only layout demonstration; no fungi, compounds or assay execution."""
from opentrons import protocol_api

metadata = {{
    "protocolName": "Fungal discovery — WATER ONLY layout demo",
    "description": "One representative plate. Demonstrates placement, not biological testing.",
    "author": "Behaviour chemistry hackathon",
}}
requirements = {{"robotType": "OT-2", "apiLevel": "2.16"}}
PLAN_ID = {plan["plan_id"]!r}
PLATE_ID = {plate_id!r}
DESTINATIONS = {wells!r}


def run(protocol: protocol_api.ProtocolContext) -> None:
    """Place water into the occupied wells of one illustrative plate."""
    tips = protocol.load_labware("opentrons_96_tiprack_300ul", "1")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "2")
    plate = protocol.load_labware("nest_96_wellplate_200ul_flat", "3")
    pipette = protocol.load_instrument("p300_single_gen2", "left", tip_racks=[tips])
    water = protocol.define_liquid(name="Water", description="Demo water only", display_color="#25816b")
    reservoir["A1"].load_liquid(liquid=water, volume=6000)
    protocol.comment("WATER ONLY. No biological preparation, incubation or measurement.")
    protocol.comment("Load 6 mL water into reservoir A1. Use the specified labware and pipette.")
    protocol.pause("Confirm water-only deck setup before proceeding.")
    for well in DESTINATIONS:
        pipette.transfer(50, reservoir["A1"], plate[well], new_tip="always")
    protocol.comment("Water layout demo complete. No fungal result was generated.")
'''


def export_plan(plan: dict, output: Path) -> None:
    """Write a portable review bundle and offline interactive viewer."""
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "experiment_plan.json", plan)
    for filename, rows in (("study_matrix.csv", plan["matrix"]),
                           ("illustrative_plate_map.csv", plan["layout"])):
        (output / filename).write_text(csv_text(rows), encoding="utf-8")
    briefs = handoff_briefs(plan)
    for partner, brief in briefs.items():
        (output / f"{partner}_brief.md").write_text(brief, encoding="utf-8")
    protocol_path = output / "opentrons_water_demo.py"
    protocol_path.write_text(water_protocol(plan), encoding="utf-8")
    # Regeneration cannot inherit a success report from an older protocol.
    write_json(output / "simulation_report.json", {
        "status": "not_run", "plan_id": plan["plan_id"],
        "protocol_sha256": hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        "scope": "water_only_layout_demo",
    })
    render_viewer(plan, output)
