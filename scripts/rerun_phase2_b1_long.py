"""Re-run only the scenarios that timed out in the main sweep.

Both policy_announcement and public_health_psa hit the 45-min driver timeout
during heavy Anthropic Opus 429 rate-limit cascades (~7 min each). Re-runs use
a 90-min ceiling so a single cascade doesn't kill the subprocess mid-iter-2.

Appends results to results/phase2_b1_full_validation_summary.jsonl (overwriting
any prior entry for the same slug) so the aggregator reads the latest outcome.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS_DIR = ROOT / "scenarios"
RESULTS_DIR = ROOT / "results"
SUMMARY_PATH = RESULTS_DIR / "phase2_b1_full_validation_summary.jsonl"
TIMEOUT_SECONDS = 90 * 60

RERUN = [
    ("policy_announcement", "policy_announcement.json"),
    ("public_health_psa", "public_health_psa.json"),
]


def run_one(slug: str, scenario_file: str) -> dict:
    spec = json.loads((SCENARIOS_DIR / scenario_file).read_text(encoding="utf-8"))
    seed_path = RESULTS_DIR / f"_seed_{slug}.txt"
    seed_path.write_text(spec["seed_content"], encoding="utf-8")
    output_path = RESULTS_DIR / f"phase2_b1_full_validation_{slug}.json"

    cmd = [
        sys.executable, "-m", "orchestrator.cli",
        "--seed-file", str(seed_path),
        "--prediction-question", spec["prediction_question"],
        "--demographic", spec["demographic"],
        "--agent-count", str(spec.get("agent_count", 20)),
        "--max-iterations", str(spec.get("max_iterations", 2)),
        "--output", str(output_path),
    ]
    start = time.time()
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS, text=True, errors="replace",
        )
        duration = time.time() - start
        log_path = RESULTS_DIR / f"phase2_b1_full_validation_{slug}.log"
        log_path.write_text(proc.stdout or "", encoding="utf-8")
        return {
            "scenario": slug, "returncode": proc.returncode,
            "duration_s": round(duration, 1), "output": str(output_path),
            "log": str(log_path), "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - start
        log_path = RESULTS_DIR / f"phase2_b1_full_validation_{slug}.log"
        log_path.write_text(exc.stdout or "", encoding="utf-8")
        return {
            "scenario": slug, "returncode": -1,
            "duration_s": round(duration, 1), "output": str(output_path),
            "log": str(log_path), "timed_out": True,
        }


def update_summary(row: dict) -> None:
    existing: list[dict] = []
    if SUMMARY_PATH.exists():
        for line in SUMMARY_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry["scenario"] != row["scenario"]:
                existing.append(entry)
    existing.append(row)
    SUMMARY_PATH.write_text(
        "\n".join(json.dumps(r) for r in existing) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    failures = 0
    for slug, scenario_file in RERUN:
        print(f"[{time.strftime('%H:%M:%S')}] >>> START {slug}", flush=True)
        result = run_one(slug, scenario_file)
        update_summary(result)
        status = "OK" if result["returncode"] == 0 else "FAIL"
        print(
            f"[{time.strftime('%H:%M:%S')}] <<< {status} {slug} "
            f"duration={result['duration_s']}s rc={result['returncode']}",
            flush=True,
        )
        if result["returncode"] != 0:
            failures += 1
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
