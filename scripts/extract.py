"""Export extraction jobs or validate model responses."""

import argparse
import json
import os
from pathlib import Path

import httpx

from src.common.cache import CachedHTTP
from src.common.environment import load_local_environment
from src.common.io import digest, read_json, read_jsonl, timestamp, write_json
from src.extraction.gemini import DEFAULT_MODEL
from src.extraction.pipeline import export_jobs, make_jobs, run_extraction


def main() -> None:
    """Run extraction with explicit API, imported-response or export-only mode."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=Path("data/interim/corpus"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--cache", type=Path, default=Path("data/raw"))
    parser.add_argument("--screening", type=Path)
    parser.add_argument("--limit-papers", type=int)
    parser.add_argument("--provider", choices=("openai", "gemini"))
    parser.add_argument("--grounding", choices=("single_quote_v1", "multispan_v1", "multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"),
                        default="single_quote_v1")
    parser.add_argument("--ant-identity-overrides", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--export", type=Path)
    mode.add_argument("--responses", type=Path)
    mode.add_argument("--model", nargs="?", const="from_environment")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    load_local_environment()
    args.provider = args.provider or os.environ.get("EXTRACTION_PROVIDER", "openai")
    if args.provider not in {"openai", "gemini"}:
        parser.error("EXTRACTION_PROVIDER must be openai or gemini")
    default_output = Path(
        "data/interim/extraction_gemini" if args.provider == "gemini" else "data/interim/extraction"
    )
    if args.grounding != "single_quote_v1":
        default_output = default_output.with_name(f"{default_output.name}_{args.grounding}")
    args.output = args.output or default_output
    if args.model == "from_environment":
        setting = "GEMINI_MODEL" if args.provider == "gemini" else "OPENAI_MODEL"
        args.model = os.environ.get(setting) or (
            DEFAULT_MODEL if args.provider == "gemini" else None
        )
        if not args.model:
            parser.error(f"Set {setting} in .env or supply --model MODEL_NAME")
    overrides = None
    if args.ant_identity_overrides is not None:
        overrides = read_json(args.ant_identity_overrides)
        if not isinstance(overrides, dict) or not all(isinstance(v, dict) for v in overrides.values()):
            parser.error("Ant identity overrides must map source IDs to resolution objects")
        if args.grounding not in {"multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
            parser.error("Ant identity overrides require --grounding multispan_v2")
    jobs = make_jobs(args.corpus, screening=args.screening, limit_papers=args.limit_papers,
                     grounding_version=args.grounding, ant_identity_overrides=overrides)
    if args.grounding in {"multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
        destination = args.export if args.export else args.output
        write_json(destination / "source_ant_identities.json", {
            job["source_id"]: job["source_ant_identity"] for job in jobs
        })
        if args.grounding in {"multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"}:
            write_json(destination / "glyph_policy.json", jobs[0]["glyph_policy"] if jobs else {})
        if args.grounding in {"multispan_v4", "multispan_v5", "multispan_v6"}:
            write_json(destination / "glyph_source_hashes.json", {
                job["input_hash"]: job["glyph_source_hashes"] for job in jobs
            })
    if args.export:
        export_jobs(jobs, args.export)
        print(json.dumps({"jobs": len(jobs), "destination": str(args.export)}))
        return
    config = read_json(Path("config/analysis.json"))
    write_json(
        args.output / "run_manifest.json",
        {
            "started_at": timestamp(),
            "model": args.model,
            "provider": args.provider,
            "corpus": str(args.corpus),
            "corpus_manifest_hash": digest(read_jsonl(args.corpus / "manifest.jsonl")),
            "screening": str(args.screening) if args.screening else None,
            "screening_hash": digest(read_json(args.screening)) if args.screening else None,
            "limit_papers": args.limit_papers,
            "jobs": len(jobs),
            "grounding_version": args.grounding,
            "input_hashes": [job["input_hash"] for job in jobs],
            **({"ant_identity_overrides_path": str(args.ant_identity_overrides)
                if args.ant_identity_overrides else None,
                "ant_identity_overrides_hash": digest(overrides) if overrides is not None else None,
                "source_ant_identities": {
                    job["source_id"]: job["source_ant_identity"] for job in jobs
                }} if args.grounding in {
                    "multispan_v2", "multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"
                } else {}),
            **({"glyph_policy": jobs[0]["glyph_policy"] if jobs else {}}
               if args.grounding in {"multispan_v3", "multispan_v4", "multispan_v5", "multispan_v6"} else {}),
            **({"glyph_source_hashes": {
                job["input_hash"]: job["glyph_source_hashes"] for job in jobs
            }} if args.grounding in {"multispan_v4", "multispan_v5", "multispan_v6"} else {}),
        },
    )
    cache = CachedHTTP(
        args.cache, args.offline, client=httpx.Client(timeout=180, follow_redirects=True)
    )
    try:
        metrics = run_extraction(
            jobs,
            cache,
            args.output,
            args.responses,
            args.model,
            config["extraction_confidence"],
            provider=args.provider,
        )
        metrics["corpus_papers"] = len(read_jsonl(args.corpus / "manifest.jsonl"))
        metrics["screened_out_papers"] = (
            sum(row["decision"] == "exclude" for row in read_json(args.screening)["decisions"])
            if args.screening
            else 0
        )
        metrics["limited_run"] = args.limit_papers is not None
        metrics["provider"] = args.provider if args.model else "imported"
        metrics["model"] = args.model
        write_json(args.output / "metrics.json", metrics)
        print(json.dumps(metrics, indent=2))
        if metrics["blocked_reason"]:
            raise SystemExit(1)
    finally:
        cache.close()


if __name__ == "__main__":
    main()
