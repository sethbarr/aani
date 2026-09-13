"""Package the audited report and explicit replay inputs without environment secrets."""

import hashlib
import json
import zipfile
from pathlib import Path

from src.common.io import read_json, read_jsonl, write_json

AUDIT = Path("results/saverschek_audit")
BASE = Path("data/interim/saverschek_audit")


def file_hash(path: Path) -> str:
    """Return the digest of exact file bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    """Archive only named audit dependencies and verify the ZIP contents."""
    manifest = read_json(AUDIT / "manifest.json")
    inputs = {Path(row["path"]) for row in manifest["inputs"]}
    inputs.update(p for p in AUDIT.iterdir() if p.is_file() and p.suffix != ".zip"
                  and p.name != "bundle_manifest.json")
    inputs.update({Path("output/pdf/saverschek_behavioral_audit.pdf"),
                   Path("scripts/package_saverschek_audit.py"),
                   Path("tests/test_saverschek_audit.py"),
                   Path("src/__init__.py"), Path("src/common/__init__.py"),
                   Path("src/common/io.py"), Path("scripts/__init__.py"),
                   Path("pyproject.toml"), Path("docs/targeted_saverschek.md"),
                   Path("data/interim/corpus_targeted_saverschek/manifest.jsonl"),
                   Path("data/interim/corpus_targeted_saverschek/build_source.py"),
                   Path("data/interim/corpus_targeted_saverschek/web_line_coverage.json"),
                   Path("data/interim/corpus_targeted_saverschek/access_log.json")})
    inputs.update(p for p in BASE.rglob("*") if p.is_file() and "taxonomy_offline" not in p.parts)
    anchors = read_json(AUDIT / "evidence_anchors.json")
    for anchor in anchors.values():
        inputs.update(Path("data/raw/web") / f"{key}.json" for key in anchor["raw_request_hashes"])
    for row in read_jsonl(BASE / "taxonomy/observations.jsonl") + read_jsonl(BASE / "taxonomy/review.jsonl"):
        inputs.add(Path("data/raw/http") / f"{row['taxonomy_request_hash']}.json")
    verification = read_json(BASE / "source_verification.json")
    for request in verification["web_requests"]:
        inputs.add(Path(request["raw_cache_path"]))
    for response_path in Path("data/interim/extraction_saverschek/responses").glob("*.json"):
        response = read_json(response_path)
        inputs.add(Path("data/raw/http") / f"{response['request_hash']}.json")
    inputs.update(Path("src/extraction").glob("*.py"))
    root = Path.cwd().resolve()
    for path in inputs:
        assert path.is_file(), path
        assert path.resolve().is_relative_to(root), path
        assert not any(part in {".env", ".git", ".venv"} for part in path.parts), path
    bundle_manifest = {
        "status": "complete_text_audit_with_disclosed_unverified_fields",
        "files": [{"path": str(path), "sha256": file_hash(path)} for path in sorted(inputs)],
        "replay_data": "python -m scripts.build_saverschek_audit",
        "replay_pdf": "python scripts/render_saverschek_report.py",
        "python": "3.12", "dependencies": ["pandas", "numpy", "matplotlib", "reportlab"],
        "raw_source_original_pdf_included": False,
        "includes_original_model_inputs_and_outputs": True,
        "includes_environment_or_credentials": False,
    }
    write_json(AUDIT / "bundle_manifest.json", bundle_manifest)
    inputs.add(AUDIT / "bundle_manifest.json")
    output = AUDIT / "saverschek_audit_bundle.zip"
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(inputs):
            archive.write(path, str(path))
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        for row in bundle_manifest["files"]:
            assert hashlib.sha256(archive.read(row["path"])).hexdigest() == row["sha256"]
    print(json.dumps({"output": str(output), "files": len(inputs),
                      "bytes": output.stat().st_size, "sha256": file_hash(output)}))


if __name__ == "__main__":
    main()
