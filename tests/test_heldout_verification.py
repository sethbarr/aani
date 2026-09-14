"""Guard the isolated held-out replay against runner drift and missing dependencies."""

import hashlib
import sys
from pathlib import Path
from types import ModuleType

import pytest

from scripts import run_frozen_holdout
from src.common.io import write_json


def configure_snapshot(root: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create one pinned recovery module and one pinned live dependency."""
    copies = root / "recovery"
    paths = {
        "scripts/extract.py": copies / "scripts/extract.py",
        "config/grounding_glyphs_v4.json": root / "config/grounding_glyphs_v4.json",
    }
    rows = []
    for name, path in paths.items():
        write_json(path, {"fixture": name})
        rows.append({"path": name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    write_json(root / "results/grounding_development_v4/heldout_preserved_inputs.json", {"files": rows})
    monkeypatch.setattr(run_frozen_holdout, "ROOT", root)
    monkeypatch.setattr(run_frozen_holdout, "COPIES", copies)
    return copies


def test_recovered_bytes_allow_concurrent_live_runner_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Use the exact copy while leaving a different live runner untouched."""
    configure_snapshot(tmp_path, monkeypatch)
    live = tmp_path / "scripts/extract.py"
    write_json(live, {"concurrent": "v5"})
    before = live.read_bytes()
    run_frozen_holdout.verify_code()
    assert live.read_bytes() == before


def test_recovered_module_drift_blocks_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refuse a recovery copy whose bytes differ from the pre-draw hash."""
    copies = configure_snapshot(tmp_path, monkeypatch)
    write_json(copies / "scripts/extract.py", {"changed": True})
    with pytest.raises(ValueError) as error:
        run_frozen_holdout.verify_code()
    assert str(error.value).startswith("heldout_frozen_replay_input_changed:")


def test_live_validator_dependency_drift_blocks_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep all dependencies outside the two recovery paths strictly frozen."""
    configure_snapshot(tmp_path, monkeypatch)
    write_json(tmp_path / "config/grounding_glyphs_v4.json", {"changed": True})
    with pytest.raises(ValueError) as error:
        run_frozen_holdout.verify_code()
    assert str(error.value).startswith("heldout_frozen_replay_input_changed:")


def test_loader_preserves_original_config_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Load source bytes from the copy with the original repository-relative file path."""
    copies = configure_snapshot(tmp_path, monkeypatch)
    name = "heldout_fixture_module"
    monkeypatch.setitem(sys.modules, name, ModuleType(name))
    path = copies / "scripts/extract.py"
    path.write_text("observed_file = __file__\n", encoding="utf-8")
    module = run_frozen_holdout.load_frozen_module(name, "scripts/extract.py")
    assert module.observed_file == str(tmp_path / "scripts/extract.py")
    assert sys.modules[name] is module
