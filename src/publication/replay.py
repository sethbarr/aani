"""Replay saved scientific runs against byte-exact private publication snapshots."""

import hashlib
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from src.common.io import read_json

PRIVATE_DIRECTORY = Path("data/interim/publication_safety")
FROZEN_COMMIT = "98b5e09199a5eef0c46be452793e953f5a2af31e"
PROTOCOL = Path("results/grounding_development_v6/heldout_sample4_protocol.json")
FROZEN_CODE = Path("data/interim/grounding_v6_sample4_frozen_code")
DISPATCHERS = (Path("scripts/extract.py"), Path("src/extraction/pipeline.py"))
CORPUS = Path("data/interim/corpus_targeted_saverschek")
OUTPUT_DIRECTORY = Path("publication_replay_outputs")
RUNS = {
    "baseline": {
        "mode": "single_quote_v1", "cache": "data/raw",
        "original": "data/interim/extraction_saverschek",
    },
    "sample1": {
        "mode": "multispan_v6", "cache": "data/raw",
        "original": "data/interim/extraction_saverschek_multispan_v6/sample1",
    },
    "sample2": {
        "mode": "multispan_v6", "cache": "data/raw/grounding_v3_repeat",
        "original": "data/interim/extraction_saverschek_multispan_v6/sample2",
    },
    "sample3": {
        "mode": "multispan_v6", "cache": "data/raw/grounding_v4_sample3",
        "original": "data/interim/extraction_saverschek_multispan_v6/sample3",
    },
    "sample4": {
        "mode": "multispan_v6", "cache": "data/raw/grounding_v6_sample4",
        "original": "data/interim/extraction_saverschek_multispan_v6/sample4",
    },
}


def sha256(path: Path) -> str:
    """Hash an existing file without changing its contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative_path(path: Path, root: Path) -> Path:
    """Require a repository-relative path without parent traversal.

    Args:
        path: Relative path or absolute path inside this repository.
        root: Repository root.

    Returns:
        Safe relative path for the private snapshot mirror.

    Raises:
        ValueError: The path could escape the repository or names its root.
    """
    relative = path.relative_to(root) if path.is_absolute() else path
    if not relative.parts or ".." in relative.parts:
        raise ValueError("publication_original_path_outside_repository")
    return relative


def resolve_original(root: Path, path: Path, private: Path | None = None) -> Path:
    """Resolve and hash-check one exact private original for local inspection.

    Args:
        root: Repository containing the ignored publication snapshot.
        path: Repository-relative path of the public artifact.
        private: Optional publication snapshot directory with snapshot.json.

    Returns:
        Verified private original path; public redacted content is never substituted.

    Raises:
        ValueError: Snapshot entry is absent, missing, or has changed bytes.
    """
    private = private or root / PRIVATE_DIRECTORY
    relative = relative_path(path, root)
    manifest = read_json(private / "snapshot.json")
    entries = [row for row in manifest["files"] if row["path"] == str(relative)]
    original = private / "originals" / relative
    if len(entries) != 1 or not original.is_file():
        raise ValueError(f"publication_private_original_missing:{relative}")
    if sha256(original) != entries[0]["sha256"]:
        raise ValueError(f"publication_private_original_changed:{relative}")
    return original


def private_snapshot_checks(root: Path, private: Path) -> list[dict]:
    """Check every private original against the publication snapshot manifest."""
    manifest = read_json(private / "snapshot.json")
    checks = []
    for row in manifest["files"]:
        relative = relative_path(Path(row["path"]), root)
        path = private / "originals" / relative
        actual = sha256(path) if path.is_file() else None
        checks.append({"path": str(relative), "sha256": actual,
                       "expected_sha256": row["sha256"], "unchanged": actual == row["sha256"]})
    return checks


def protocol_input_checks(root: Path, private: Path) -> list[dict]:
    """Check frozen rule inputs using private originals for publication-only projections."""
    protocol = read_json(resolve_original(root, PROTOCOL, private))
    checks = []
    for row in protocol["frozen_inputs"]:
        relative = relative_path(Path(row["path"]), root)
        if relative in DISPATCHERS:
            path = root / FROZEN_CODE / relative
        elif relative.parts[0] in {"results", "docs"}:
            path = resolve_original(root, relative, private)
        else:
            path = root / relative
        actual = sha256(path) if path.is_file() else None
        checks.append({"path": str(relative), "sha256": actual,
                       "expected_sha256": row["sha256"], "unchanged": actual == row["sha256"]})
    return checks


def frozen_protocol_checks(root: Path) -> list[dict]:
    """Compare both live scientific protocol files with the original Git commit."""
    checks = []
    for name in ("docs/analysis_plan.md", "config/analysis.json"):
        original = subprocess.run(["git", "show", f"{FROZEN_COMMIT}:{name}"], cwd=root,
                                  check=True, capture_output=True)
        expected = hashlib.sha256(original.stdout).hexdigest()
        actual = sha256(root / name)
        checks.append({"path": name, "sha256": actual, "expected_sha256": expected,
                       "unchanged": actual == expected})
    return checks


def prepare_mirror(root: Path, private: Path, mirror: Path) -> None:
    """Create isolated code and result copies with existing private inputs linked for reads.

    Args:
        root: Repository containing unchanged scientific code and private caches.
        private: Byte-exact publication snapshot directory.
        mirror: Newly created empty temporary directory.

    Raises:
        ValueError: The mirror is nonempty or a required private original is invalid.
    """
    if any(mirror.iterdir()):
        raise ValueError("publication_replay_mirror_must_be_empty")
    for name in ("src", "scripts", "config"):
        shutil.copytree(root / name, mirror / name,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    manifest = read_json(private / "snapshot.json")
    for row in manifest["files"]:
        relative = relative_path(Path(row["path"]), root)
        if relative.parts[0] not in {"results", "docs"}:
            continue
        original = resolve_original(root, relative, private)
        destination = mirror / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    for relative in DISPATCHERS:
        shutil.copyfile(root / FROZEN_CODE / relative, mirror / relative)
    (mirror / "data").mkdir()
    for name in ("raw", "interim", "processed"):
        (mirror / "data" / name).symlink_to(root / "data" / name, target_is_directory=True)
    (mirror / OUTPUT_DIRECTORY).mkdir()


def scientific_artifact_names(original: Path, mode: str) -> list[str]:
    """List nine baseline or thirteen v6 scientific files, excluding timestamps."""
    names = ["observations.jsonl", "rejections.jsonl", "metrics.json", "failures.jsonl",
             "partial_observations.jsonl", "chunk_status.jsonl"]
    names.extend(str(path.relative_to(original))
                 for path in sorted((original / "responses").glob("*.json")))
    if mode == "multispan_v6":
        names += ["source_ant_identities.json", "glyph_policy.json", "glyph_source_hashes.json",
                  "glyph_grounding_audit.jsonl"]
    return names


def compare_scientific_artifacts(original: Path, replay: Path, mode: str) -> list[dict]:
    """Compare every scientific output byte without exposing any stored quotation."""
    checks = []
    for name in scientific_artifact_names(original, mode):
        expected = sha256(original / name) if (original / name).is_file() else None
        actual = sha256(replay / name) if (replay / name).is_file() else None
        checks.append({"artifact": name, "original_sha256": expected, "replay_sha256": actual,
                       "identical": expected is not None and expected == actual})
    return checks


def child_environment() -> dict[str, str]:
    """Disable bytecode writes and remove model credentials from isolated subprocesses."""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment.pop("PYTHONPATH", None)
    for key in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        environment.pop(key, None)
    return environment


def execute_replay(root: Path, mirror: Path, name: str, run: dict, baseline: dict,
                   timeout_seconds: int) -> dict:
    """Run one cached extraction in the isolated mirror and compare its baseline scores.

    Args:
        root: Repository containing the Python environment and original outputs.
        mirror: Temporary private replay root with original publication artifacts.
        name: Fixed sample identifier.
        run: Fixed grounding mode, cache path, and original output path.
        baseline: Original reference set from the private snapshot.
        timeout_seconds: Per-run subprocess time limit.

    Returns:
        Count-only scores, artifact hashes, and an explicit blocker if replay fails.
    """
    from src.evaluation.identity_comparison import score_variant

    output = OUTPUT_DIRECTORY / name
    command = [str(root / ".venv/bin/python"), "-m", "scripts.extract", "--provider", "gemini",
               "--model", "gemini-3.8-flash", "--grounding", run["mode"], "--corpus", str(CORPUS),
               "--output", str(output), "--cache", run["cache"], "--offline"]
    try:
        completed = subprocess.run(command, cwd=mirror, env=child_environment(), check=False,
                                   capture_output=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return {"sample": name, "status": "blocked", "blocked_reason": "offline_replay_timeout",
                "offline": True, "model_requests": 0, "artifact_checks": []}
    original = root / run["original"]
    replay = mirror / output
    checks = compare_scientific_artifacts(original, replay, run["mode"])
    expected_count = 13 if run["mode"] == "multispan_v6" else 9
    previous_score = score_variant(original, baseline, None)
    current_score = score_variant(replay, baseline, None)
    score_matches = (previous_score["status"] == current_score["status"] == "complete"
                     and previous_score["groups"] == current_score["groups"])
    if name == "baseline":
        score_matches = score_matches and current_score["groups"] == baseline["groups"]
    passed = (completed.returncode == 0 and len(checks) == expected_count
              and all(row["identical"] for row in checks) and score_matches)
    return {
        "sample": name, "status": "passed" if passed else "failed",
        "blocked_reason": None if passed else "offline_replay_artifacts_or_scores_differ",
        "grounding_mode": run["mode"], "cache": run["cache"], "original": run["original"],
        "offline": True, "model_requests": 0, "subprocess_returncode": completed.returncode,
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
        "artifact_checks": checks, "scientific_artifacts_compared": len(checks),
        "baseline_convention_counts_identical": score_matches, "groups": current_score["groups"],
    }


def verify(root: Path, private: Path | None = None, timeout_seconds: int = 60) -> dict:
    """Verify publication-only redaction with five isolated offline scientific replays.

    Args:
        root: Repository root containing unchanged private source and response files.
        private: Optional snapshot directory; defaults to data/interim/publication_safety.
        timeout_seconds: Maximum duration of each of the five offline subprocesses.

    Returns:
        Publication-safe verification data. This function writes only inside a temporary
        directory, removes that directory afterward, and never replaces private originals.
    """
    root = root.resolve()
    private = private.resolve() if private is not None else root / PRIVATE_DIRECTORY
    report = {"status": "blocked", "blocked_reason": None, "model_requests": 0,
              "private_snapshot": str(private.relative_to(root)),
              "full_text_policy": "Full text is retained locally and is not redistributed.",
              "input_access": "Existing private inputs are linked for offline reads; all replay "
              "outputs are written into a separate temporary directory.", "runs": []}
    try:
        original_checks = private_snapshot_checks(root, private)
        frozen_inputs = protocol_input_checks(root, private)
        frozen_files = frozen_protocol_checks(root)
        report.update({"private_original_checks": original_checks,
                       "frozen_input_checks": frozen_inputs, "frozen_files": frozen_files})
        if not all(row["unchanged"] for row in original_checks + frozen_inputs + frozen_files):
            report["blocked_reason"] = "publication_replay_input_integrity_failed"
            return report
        with tempfile.TemporaryDirectory(prefix="aani-publication-replay-") as temporary:
            from src.evaluation.comparison import baseline_integrity

            mirror = Path(temporary)
            prepare_mirror(root, private, mirror)
            baseline = read_json(mirror / "results/recall_baseline.json")
            integrity = baseline_integrity(baseline, mirror)
            report["baseline_integrity"] = integrity
            if not integrity["all_original_bytes_unchanged"]:
                report["blocked_reason"] = "private_baseline_integrity_failed"
                return report
            report["runs"] = [execute_replay(root, mirror, name, run, baseline, timeout_seconds)
                              for name, run in RUNS.items()]
        after_originals = private_snapshot_checks(root, private)
        after_frozen = protocol_input_checks(root, private)
        unchanged = original_checks == after_originals and frozen_inputs == after_frozen
        report["private_inputs_unchanged_after_replay"] = unchanged
        passed = unchanged and all(run["status"] == "passed" for run in report["runs"])
        report["status"] = "passed" if passed else "failed"
        report["blocked_reason"] = None if passed else "publication_replay_or_preservation_failed"
    except (OSError, KeyError, ValueError, subprocess.SubprocessError) as error:
        report["status"] = "blocked"
        report["blocked_reason"] = f"publication_replay_error:{type(error).__name__}"
    return report


def materialize_fixture(root: Path, mirror: Path, relative: Path) -> None:
    """Copy one local fixture into the mirror without leaving symlinked ancestors.

    Args:
        root: Repository containing the unchanged fixture.
        mirror: Temporary test root containing read-only-by-workflow input links.
        relative: Safe repository-relative path to one fixture file.

    Raises:
        ValueError: The fixture path escapes the repository.
    """
    relative = relative_path(relative, root)
    parent = mirror
    for part in relative.parts[:-1]:
        parent /= part
        if parent.is_symlink():
            source = parent.resolve()
            parent.unlink()
            parent.mkdir()
            for child in source.iterdir():
                (parent / child.name).symlink_to(child, target_is_directory=child.is_dir())
        else:
            parent.mkdir(exist_ok=True)
    destination = mirror / relative
    if destination.is_symlink():
        destination.unlink()
    if not destination.exists():
        shutil.copyfile(root / relative, destination)


def prepare_test_mirror(root: Path, private: Path, mirror: Path) -> None:
    """Add current tests and code with private original result fixtures to an empty mirror.

    Args:
        root: Repository containing the test suite and unchanged local input fixtures.
        private: Hash-checked private publication snapshot.
        mirror: Empty temporary directory for this isolated test run.

    Raises:
        ValueError: A required private original has changed or the mirror is nonempty.
    """
    prepare_mirror(root, private, mirror)
    shutil.copytree(root / "tests", mirror / "tests",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    shutil.copyfile(root / "pyproject.toml", mirror / "pyproject.toml")
    for relative in DISPATCHERS:
        shutil.copyfile(root / relative, mirror / relative)
    for original in (root / "results").rglob("*"):
        if not original.is_file():
            continue
        destination = mirror / original.relative_to(root)
        if destination.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(original, destination)
    supplement_path = Path("data/interim/trema_resolution/manifest.json")
    supplement = read_json(root / supplement_path)
    fixtures = [supplement_path, *[Path(row["path"]) for row in (
        supplement["original_observations"], supplement["observations"],
        supplement["amendment"], *supplement["provenance"]
    )]]
    for fixture in fixtures:
        materialize_fixture(root, mirror, fixture)
    if (root / ".git").exists():
        (mirror / ".git").symlink_to(root / ".git", target_is_directory=(root / ".git").is_dir())


def read_test_counts(path: Path) -> dict:
    """Read aggregate JUnit counts and failing test identifiers without source-bearing logs.

    Args:
        path: XML report written by pytest inside the isolated temporary directory.

    Returns:
        Counts, safe failure identifiers, and a numeric summary of the test outcome.
    """
    document = ET.parse(path).getroot()
    suites = [document] if document.tag == "testsuite" else document.findall("testsuite")
    counts = {name: sum(int(suite.get(name, "0")) for suite in suites)
              for name in ("tests", "failures", "errors", "skipped")}
    counts["passed"] = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    failures = []
    for case in document.iter("testcase"):
        for outcome in ("failure", "error"):
            if case.find(outcome) is not None:
                failures.append({"class": case.get("classname"), "test": case.get("name"),
                                 "outcome": outcome})
    return {"counts": counts, "failed_tests": failures,
            "summary": f"{counts['passed']} passed; {counts['failures']} failed; "
            f"{counts['errors']} errors; {counts['skipped']} skipped."}


def run_tests(root: Path, private: Path | None = None, timeout_seconds: int = 60) -> dict:
    """Run the full unchanged test suite against private originals in an isolated mirror.

    Args:
        root: Repository containing the current test suite, code, and Python environment.
        private: Optional private publication snapshot directory.
        timeout_seconds: Maximum duration of the pytest subprocess.

    Returns:
        Aggregate test counts, safe failing test identifiers, output hashes, and integrity
        checks. Full pytest output remains temporary and is never included in this report.
        Existing private input files, scientific tests, and frozen code remain unchanged.
    """
    root = root.resolve()
    private = private.resolve() if private is not None else root / PRIVATE_DIRECTORY
    report = {
        "status": "blocked", "blocked_reason": None, "counts": None, "failed_tests": [],
        "full_text_policy": "Full text is retained locally and is not redistributed.",
        "test_scope": "Full current pytest suite with private original result fixtures and "
        "unchanged scientific tests; current dispatchers are tested, and scientific replay "
        "separately checks the frozen dispatchers.",
        "output_policy": "Raw test output remains temporary; this report contains counts, "
        "test identifiers, and output hashes.",
    }
    try:
        before_originals = private_snapshot_checks(root, private)
        before_frozen = protocol_input_checks(root, private)
        report["private_original_checks"] = before_originals
        report["frozen_input_checks"] = before_frozen
        if not all(row["unchanged"] for row in before_originals + before_frozen):
            report["blocked_reason"] = "publication_test_input_integrity_failed"
            return report
        with tempfile.TemporaryDirectory(prefix="aani-publication-tests-") as temporary:
            mirror = Path(temporary)
            prepare_test_mirror(root, private, mirror)
            junit = OUTPUT_DIRECTORY / "pytest.xml"
            command = [str(root / ".venv/bin/python"), "-m", "pytest", "-q",
                       f"--junitxml={junit}", "-o", "cache_dir=publication_replay_outputs/pytest_cache"]
            completed = subprocess.run(command, cwd=mirror, env=child_environment(), check=False,
                                       capture_output=True, timeout=timeout_seconds)
            report.update({"subprocess_returncode": completed.returncode,
                           "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest(),
                           "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest(),
                           "stdout_bytes": len(completed.stdout), "stderr_bytes": len(completed.stderr)})
            if (mirror / junit).is_file():
                report.update(read_test_counts(mirror / junit))
            else:
                report["blocked_reason"] = "pytest_junit_report_missing"
                return report
        after_originals = private_snapshot_checks(root, private)
        after_frozen = protocol_input_checks(root, private)
        unchanged = before_originals == after_originals and before_frozen == after_frozen
        report["private_inputs_unchanged_after_tests"] = unchanged
        passed = completed.returncode == 0 and unchanged
        report["status"] = "passed" if passed else "failed"
        report["blocked_reason"] = None if passed else "pytest_failed_or_private_inputs_changed"
    except subprocess.TimeoutExpired:
        report["blocked_reason"] = "publication_test_timeout"
    except (OSError, KeyError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        report["blocked_reason"] = f"publication_test_error:{type(error).__name__}"
    return report
