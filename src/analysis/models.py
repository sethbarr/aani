"""Run the required R model and make unavailable fits explicit."""

import shutil
import subprocess
from pathlib import Path

import pandas as pd


def model_environment() -> dict:
    """Report R and lme4 availability independently of available observations."""
    executable = shutil.which("Rscript")
    if executable is None:
        return {"status": "unavailable", "reason": "Rscript_unavailable"}
    expression = (
        'cat(R.version.string, "\\n"); '
        'if (requireNamespace("lme4", quietly=TRUE)) '
        'cat("lme4=", as.character(packageVersion("lme4")), sep="") '
        'else quit(status=2)'
    )
    try:
        result = subprocess.run(
            [executable, "--vanilla", "-e", expression],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as error:
        return {"status": "unavailable", "reason": "R_environment_probe_failed", "detail": str(error)}
    return {
        "status": "available" if result.returncode == 0 else "unavailable",
        "reason": None if result.returncode == 0 else "lme4_unavailable",
        "executable": executable,
        "version_output": result.stdout.strip(),
        "error_output": result.stderr.strip(),
    }


def run_mixed_effects(frame: pd.DataFrame, output: Path) -> dict:
    """Run lme4 and return diagnostics without substituting a simpler model."""
    output.mkdir(parents=True, exist_ok=True)
    environment = model_environment()
    if frame.empty or environment["status"] != "available":
        return {
            "status": "not_estimable",
            "estimable": False,
            "reason": "no_classified_compound_rows" if frame.empty else environment["reason"],
            "environment": environment,
        }
    executable = environment["executable"]
    source = output / "model_input.csv"
    frame.to_csv(source, index=False)
    try:
        result = subprocess.run(
            [
                executable,
                "--vanilla",
                str(Path(__file__).with_name("mixed_effects.R")),
                str(source),
                str(output),
            ],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "not_estimable", "estimable": False, "reason": "model_timeout", "environment": environment}
    (output / "model.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    diagnostics_path = output / "diagnostics.csv"
    if result.returncode or not diagnostics_path.exists():
        return {
            "status": "not_estimable",
            "estimable": False,
            "reason": "R_model_failed",
            "log": str(output / "model.log"),
            "environment": environment,
        }
    diagnostics = pd.read_csv(diagnostics_path, keep_default_na=False).to_dict("records")
    if not diagnostics or any(row["status"] == "not_estimable" for row in diagnostics):
        status = "not_estimable"
    else:
        status = "ok" if all(row["status"] == "ok" for row in diagnostics) else "diagnostic_warning"
    return {
        "status": status,
        "estimable": status != "not_estimable",
        "fits": diagnostics,
        "output": str(output),
        "environment": environment,
    }
