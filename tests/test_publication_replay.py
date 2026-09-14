"""Check private publication replay paths, integrity guards, and output boundaries."""

import hashlib
from pathlib import Path

import pytest

from src.common.io import write_json
from src.publication.replay import (
    OUTPUT_DIRECTORY,
    compare_scientific_artifacts,
    materialize_fixture,
    prepare_mirror,
    private_snapshot_checks,
    read_test_counts,
    relative_path,
    resolve_original,
    run_tests,
    scientific_artifact_names,
    verify,
)


def make_snapshot(root: Path, name: str, body: str) -> Path:
    """Create one private original and manifest for an isolated test."""
    private = root / "data/interim/publication_safety"
    original = private / "originals" / name
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(body, encoding="utf-8")
    write_json(private / "snapshot.json", {"files": [{
        "path": name, "sha256": hashlib.sha256(body.encode()).hexdigest(), "bytes": len(body),
    }]})
    return private


def test_private_resolver_returns_exact_original_and_ignores_public_redaction(tmp_path: Path) -> None:
    """Resolve the private bytes independently of a changed public projection."""
    private = make_snapshot(tmp_path, "results/example.json", '{"private": "original"}')
    write_json(tmp_path / "results/example.json", {"public": "redacted"})
    original = resolve_original(tmp_path, Path("results/example.json"))
    assert original == private / "originals/results/example.json"
    assert original.read_text() == '{"private": "original"}'
    assert private_snapshot_checks(tmp_path, private)[0]["unchanged"] is True


def test_private_resolver_rejects_changed_original_bytes(tmp_path: Path) -> None:
    """Never accept a mutated private original after publication redaction."""
    private = make_snapshot(tmp_path, "results/example.json", "original")
    (private / "originals/results/example.json").write_text("changed")
    with pytest.raises(ValueError) as caught:
        resolve_original(tmp_path, Path("results/example.json"))
    assert "publication_private_original_changed" in str(caught.value)


@pytest.mark.parametrize("name", ["../outside", ".", "data/../../outside"])
def test_relative_paths_cannot_escape_the_private_mirror(tmp_path: Path, name: str) -> None:
    """Reject path traversal before resolving or copying an original."""
    with pytest.raises(ValueError):
        relative_path(Path(name), tmp_path)


def test_missing_snapshot_is_explicitly_blocked_without_creating_outputs(tmp_path: Path) -> None:
    """Report missing local evidence without inventing scores or writing public files."""
    report = verify(tmp_path)
    assert report["status"] == "blocked"
    assert report["blocked_reason"] == "publication_replay_error:FileNotFoundError"
    assert report["runs"] == []
    assert not (tmp_path / "results").exists()


def test_prepare_mirror_isolates_outputs_and_preserves_private_inputs(tmp_path: Path) -> None:
    """Keep replay destinations outside linked raw and interim inputs."""
    root = tmp_path / "repo"
    private = make_snapshot(root, "results/example.json", "private original")
    for name in ("src", "scripts", "config"):
        (root / name).mkdir(exist_ok=True)
    for name in ("scripts/extract.py", "src/extraction/pipeline.py"):
        path = root / "data/interim/grounding_v6_sample4_frozen_code" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# frozen dispatcher\n")
        current = root / name
        current.parent.mkdir(parents=True, exist_ok=True)
        current.write_text("# current dispatcher\n")
    for name in ("raw", "processed"):
        (root / "data" / name).mkdir()
    mirror = tmp_path / "mirror"
    mirror.mkdir()
    prepare_mirror(root, private, mirror)
    assert (mirror / "data/interim").resolve() == root / "data/interim"
    assert (mirror / "data/raw").resolve() == root / "data/raw"
    assert (mirror / OUTPUT_DIRECTORY).resolve().is_relative_to(mirror)
    assert not (mirror / OUTPUT_DIRECTORY).is_symlink()
    assert (mirror / "scripts/extract.py").read_text() == "# frozen dispatcher\n"
    assert (root / "scripts/extract.py").read_text() == "# current dispatcher\n"
    assert (mirror / "results/example.json").read_text() == "private original"


def test_v6_scientific_artifact_list_has_thirteen_files(tmp_path: Path) -> None:
    """Preserve the same thirteen-file replay contract used by the v6 experiment."""
    (tmp_path / "responses").mkdir()
    for name in ("first", "middle", "last"):
        write_json(tmp_path / "responses" / f"{name}.json", {})
    assert len(scientific_artifact_names(tmp_path, "multispan_v6")) == 13
    assert len(scientific_artifact_names(tmp_path, "single_quote_v1")) == 9


def test_missing_replay_files_fail_the_byte_comparison(tmp_path: Path) -> None:
    """Require actual matching files; two absent outputs never count as identical."""
    checks = compare_scientific_artifacts(tmp_path / "original", tmp_path / "missing", "multispan_v6")
    assert checks
    assert all(row["identical"] is False for row in checks)


def test_test_report_keeps_counts_without_source_bearing_failure_details(tmp_path: Path) -> None:
    """Keep exact JUnit counts while excluding assertion messages and captured text."""
    path = tmp_path / "pytest.xml"
    path.write_text('<testsuites><testsuite tests="4" failures="1" errors="1" skipped="1">'
                    '<testcase classname="tests.example" name="failed">'
                    '<failure message="private source prose">private assertion text</failure>'
                    '</testcase><testcase classname="tests.example" name="errored">'
                    '<error message="private error">private traceback</error></testcase>'
                    '</testsuite></testsuites>')
    result = read_test_counts(path)
    assert result["counts"] == {"tests": 4, "failures": 1, "errors": 1, "skipped": 1, "passed": 1}
    assert result["summary"] == "1 passed; 1 failed; 1 errors; 1 skipped."
    assert len(result["failed_tests"]) == 2
    assert "private" not in str(result)


def test_test_runner_blocks_without_private_snapshot(tmp_path: Path) -> None:
    """Avoid a pytest subprocess when the original private fixtures are unavailable."""
    result = run_tests(tmp_path)
    assert result["status"] == "blocked"
    assert result["counts"] is None
    assert result["blocked_reason"] == "publication_test_error:FileNotFoundError"


def test_materialized_fixture_satisfies_in_repository_path_checks(tmp_path: Path) -> None:
    """Copy linked input bytes into the mirror while leaving private files unchanged."""
    root = tmp_path / "repo"
    original = root / "data/interim/example/manifest.json"
    original.parent.mkdir(parents=True)
    original.write_text("original manifest")
    sibling = original.with_name("other.json")
    sibling.write_text("untouched sibling")
    mirror = tmp_path / "mirror"
    (mirror / "data").mkdir(parents=True)
    (mirror / "data/interim").symlink_to(root / "data/interim", target_is_directory=True)
    relative = Path("data/interim/example/manifest.json")
    materialize_fixture(root, mirror, relative)
    assert (mirror / relative).resolve().is_relative_to(mirror)
    assert (mirror / relative).read_bytes() == original.read_bytes()
    assert (mirror / relative.parent / "other.json").resolve() == sibling
    assert original.read_text() == "original manifest"
