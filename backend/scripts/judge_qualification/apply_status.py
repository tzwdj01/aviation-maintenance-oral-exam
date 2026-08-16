"""Apply a completed Judge Qualification run's conclusion to LLMProfile rows.

Governed post-Gate step: run explicitly (default dry-run) after the human Model
Qualification Gate. Only profiles whose run status == RUN are touched (NOT_RUN providers
are never modified). Credentials are read from the environment; nothing is logged.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.domain import LLMProfile
from sqlalchemy import select

MODEL_ATTR = {
    "MIMO": "mimo_llm_model",
    "DEEPSEEK": "deepseek_default_model",
    "OPENAI": "openai_default_model",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply Judge Qualification conclusion to LLMProfile")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="write to DB (default: dry-run)")
    args = parser.parse_args()

    metrics = json.loads((args.run_dir / "metrics.json").read_text(encoding="utf-8"))
    manifest = json.loads((args.run_dir / "manifest.json").read_text(encoding="utf-8"))
    settings = get_settings()

    with SessionLocal() as session:
        for provider, provider_metrics in metrics.items():
            if provider_metrics.get("status") != "RUN":
                print(f"[{provider}] {provider_metrics.get('status')} — skipped (not run)")
                continue
            model = getattr(settings, MODEL_ATTR.get(provider, ""), None)
            if not model:
                print(f"[{provider}] model attribute missing — skipped")
                continue
            conclusion = provider_metrics.get("conclusion", {})
            status = conclusion.get("proposed_qualification")
            if status not in {"CONDITIONAL", "FAIL", "QUALIFIED"}:
                print(f"[{provider}] no provisional conclusion — skipped")
                continue
            summary = {
                "source": args.run_dir.name,
                "run_id": manifest.get("run_id"),
                "dataset_version": manifest.get("dataset_version"),
                "prompt_bundle_version": manifest.get("prompt_bundle_version"),
                "proposed_qualification": status,
                "failed_thresholds": conclusion.get("failed_thresholds", []),
                "zero_tolerance_failures": conclusion.get("zero_tolerance_failures", []),
                "gate_version": conclusion.get("gate_version"),
                "note": "proposed by Gate evaluator; human Model Qualification Gate required before formal use",
                "metrics": {k: v for k, v in provider_metrics.items() if k not in {"conclusion", "status"}},
            }
            profile = session.scalar(
                select(LLMProfile).where(LLMProfile.provider == provider, LLMProfile.model == model)
            )
            if profile is None:
                print(f"[{provider}/{model}] profile not found — skipped")
                continue
            if args.apply:
                profile.qualification_status = status
                profile.qualification_summary = summary
                session.commit()
                print(f"[{provider}/{model}] -> {status} (applied)")
            else:
                print(f"[{provider}/{model}] -> {status} (dry-run; pass --apply after human Gate)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
