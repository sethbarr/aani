"""Write preserved v6 reports from previously saved scores and verification evidence."""

import argparse
from pathlib import Path

from src.common.io import read_json
from src.evaluation.cache_control_comparison import render_tables

REPORT = Path("results/grounding_development_v6")


def optional_json(path: Path) -> dict:
    """Read saved evidence or return an explicit missing-evidence blocker.

    Args:
        path: Expected saved evidence path.

    Returns:
        Existing JSON object or an explicit blocked record.
    """
    if not path.is_file():
        return {"status": "blocked", "blocked_reason": f"missing_evidence:{path}"}
    return read_json(path)


def regression_text(report: dict) -> list[str]:
    """Render each previous rule's survivor retention without merging samples.

    Args:
        report: Saved comparison containing v4 and v5 regression deltas.

    Returns:
        Markdown lines describing retained identities, losses, and direction changes.
    """
    lines = ["## Regression on development samples", "",
             "Sample 3 is DEVELOPMENT-SET evidence because its failures informed v6.", "",
             "| Sample | Previous rules | Survivor retention | Lost | Direction changes |",
             "| --- | --- | --- | --- | --- |"]
    for sample, comparisons in report["regressions"].items():
        for rule, value in comparisons.items():
            if value["status"] == "blocked":
                lines.append(f"| {sample} | {rule} | Blocked: {value['blocked_reason']} | "
                             "unscorable | unscorable |")
            else:
                lines.append(
                    f"| {sample} | {rule} | {value['previous_survivors_retained']} of "
                    f"{value['previous_survivors']} | {len(value['lost_record_ids'])} | "
                    f"{len(value['direction_changes'])} |"
                )
    return lines + [""]


def failure_text(report: dict, audit: dict) -> list[str]:
    """Describe saved sample-4 ordered rejections after the scoring marker exists.

    Args:
        report: Saved four-sample comparison with completed scoring timestamp.
        audit: Subsequent failure classification report, or explicit blocker.

    Returns:
        Count-only ordered reasons and available classification counts.
    """
    lines = ["## Sample 4 ordered rejections", ""]
    if not report.get("score_completed_at"):
        return lines + ["Blocked reason: sample4_score_completion_marker_missing.", ""]
    run = report["sample4_v6"]
    if run["blocked_reason"]:
        return lines + [f"Blocked reason: {run['blocked_reason']}.", ""]
    reasons = run["failure_reasons"]["all_candidates"]
    lines.extend(["| First ordered reason | Records |", "| --- | --- |"])
    if reasons:
        lines.extend(f"| `{reason}` | {count} |" for reason, count in sorted(reasons.items()))
    else:
        lines.append("| No rejected records | 0 |")
    lines += ["", "These are the first failed gates; later checks remain unadjudicated.", ""]
    if audit.get("category_counts") is not None:
        lines.extend(["| Rejection class | Records |", "| --- | --- |"])
        lines.extend(f"| {category} | {count} |"
                     for category, count in sorted(audit["category_counts"].items()))
        lines.append("")
    if audit.get("blocked_reason"):
        lines.extend([f"Failure classification blocked reason: {audit['blocked_reason']}.", ""])
    lines += ["Per-record reasons, offsets, and any observed unsupported character substitutions "
              "are recorded in [heldout_sample4_failures.json](heldout_sample4_failures.json).", ""]
    return lines


def generalization_text(report: dict, audit: dict) -> str:
    """State the observed held-out result without claiming unseen-paper performance.

    Args:
        report: Saved comparison containing sample 4.
        audit: Post-score audit that may provide a specific generalization verdict.

    Returns:
        One evidence-bounded sentence, or the explicit blocker preventing a verdict.
    """
    if audit.get("generalization_verdict"):
        return audit["generalization_verdict"]
    run = report["sample4_v6"]
    reason = run["blocked_reason"] or audit.get("blocked_reason")
    if reason:
        return f"The sample-4 generalization verdict is blocked: {reason}."
    counts = {group: run["groups"][group]["stages"]["correctness"]["species_direction_pair_count"]
              for group in ("PRIMARY", "CONTEXT")}
    return (f"On the untouched draw, v6 reached PRIMARY {counts['PRIMARY']} of 6 and "
            f"CONTEXT {counts['CONTEXT']} of 10 correct surviving pairs; this result covers "
            "one additional model draw from the same known panel.")


def render_summary(report: dict, verification: dict, sampling: dict | None = None,
                   audit: dict | None = None) -> str:
    """Render saved counts, regressions, replay evidence, and development-set caveats.

    Args:
        report: Existing three-sample or four-sample score artifact.
        verification: Corresponding saved offline replay and preservation result.
        sampling: Held-out request-attempt record when sample 4 exists.
        audit: Post-score rejection classification when sample 4 exists.

    Returns:
        Complete Markdown report without changing scores or accessing candidate files.
    """
    heldout = "sample4_v6" in report["variant_order"]
    title = "V6 sample 4 — held-out model draw" if heldout else "V6 — DEVELOPMENT SET"
    lines = [f"# {title}", "",
             "V6 adds cache-side control inference after exact, v4, and v5 quote matching. "
             "The new route permits one cached non-whitespace C0 control aligned to one "
             "printable punctuation or symbol, with unique equal-length alignment, literal "
             "anchors, exact agreement elsewhere, and candidate-local consistency.", "",
             report["contamination_risk"], "", report["sampling_caveat"], "",
             "All counts use the unchanged baseline structured-direction convention. "
             "PRIMARY and CONTEXT remain separate, with fixed denominators and explicit "
             "unscorable species.", "", render_tables(report), *regression_text(report)]
    if heldout:
        evidence = audit or {"status": "blocked", "blocked_reason": "sample4_failure_audit_missing"}
        draw = sampling or {"status": "blocked", "blocked_reason": "sample4_sampling_record_missing"}
        lines += ["## Held-out procedure", "",
                  f"Sampling status: {draw.get('status', 'blocked')}; network attempts: "
                  f"{draw.get('network_attempts', 'unreported')}; retries: "
                  f"{draw.get('retries', 'unreported')}. "
                  f"Scores were saved at {report.get('score_completed_at', 'unreported')} "
                  "before the failure audit. The pre-draw rule and request hashes are in "
                  "[heldout_sample4_protocol.json](heldout_sample4_protocol.json).", "",
                  *failure_text(report, evidence), "## Generalization verdict", "",
                  generalization_text(report, evidence), ""]
    else:
        lines += ["These three samples informed v6 development; their results do not establish "
                  "performance on an untouched draw. Any separately scored sample 4 is reported "
                  "in [heldout_sample4_summary.md](heldout_sample4_summary.md).", ""]
    lines += ["## Replay and scope", "",
              f"Offline replay and preservation status: {verification.get('status', 'blocked')}.",
              "", report["table_caveat"], "",
              "The frozen protocol files remain at `98b5e09`; thresholds, unanimity, assay "
              "eligibility, unknown activity, and the 25-genus feasibility gate are unchanged. "
              "The biological feasibility-failure label is unchanged.", "",
              f"Blocked reason: {report['blocked_reason'] or verification.get('blocked_reason') or 'none'}.", ""]
    return "\n".join(lines)


def write_reports(root: Path) -> list[Path]:
    """Create new report files while preserving every existing artifact.

    Args:
        root: Repository with saved v6 scores, sampling, audit, and replay evidence.

    Returns:
        Newly written report paths; existing reports are left untouched.
    """
    folder = root / REPORT
    written = []
    targets = (
        ("development_scores.json", "development_verification.json", "summary.md"),
        ("heldout_sample4_scores.json", "heldout_sample4_verification.json",
         "heldout_sample4_summary.md"),
    )
    for score_name, verification_name, target_name in targets:
        score_path = folder / score_name
        target = folder / target_name
        if not score_path.is_file() or target.exists():
            continue
        report = read_json(score_path)
        verification = optional_json(folder / verification_name)
        sampling = optional_json(folder / "heldout_sample4_sampling.json")
        audit = optional_json(folder / "heldout_sample4_failures.json")
        text = render_summary(report, verification, sampling, audit)
        target.write_text(text, encoding="utf-8")
        written.append(target)
    return written


def main() -> None:
    """Write v6 Markdown reports from saved score artifacts without resampling."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    arguments = parser.parse_args()
    for path in write_reports(arguments.root):
        print(path)


if __name__ == "__main__":
    main()
