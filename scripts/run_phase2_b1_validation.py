"""Sequential 5-scenario validation runner for Phase 2 B.1 Option A.

Runs each scenario in scenarios/*.json through `python -m orchestrator.cli`,
writes per-scenario results to results/phase2_b1_full_validation_<scenario>.json,
and appends a timing/status summary line to results/phase2_b1_full_validation_summary.jsonl
so the orchestrator can tail progress while this runs.

Sequential (not parallel) because TRIBE v2 holds a threading lock over a single
shared GPU — running concurrently would just serialize + add contention.
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

SCENARIO_ORDER = [
    ("product_launch", "product_launch.json"),
    ("gen_z_marketing", "gen_z_marketing.json"),
    ("policy_announcement", "policy_announcement.json"),
    ("price_increase", "price_increase.json"),
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
            cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=45 * 60,
            text=True,
            errors="replace",
        )
        duration = time.time() - start
        log_path = RESULTS_DIR / f"phase2_b1_full_validation_{slug}.log"
        log_path.write_text(proc.stdout or "", encoding="utf-8")
        return {
            "scenario": slug,
            "returncode": proc.returncode,
            "duration_s": round(duration, 1),
            "output": str(output_path),
            "log": str(log_path),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - start
        log_path = RESULTS_DIR / f"phase2_b1_full_validation_{slug}.log"
        log_path.write_text(exc.stdout or "", encoding="utf-8")
        return {
            "scenario": slug,
            "returncode": -1,
            "duration_s": round(duration, 1),
            "output": str(output_path),
            "log": str(log_path),
            "timed_out": True,
        }


def main() -> int:
    RESULTS_DIR.mkdir(exist_ok=True)
    if SUMMARY_PATH.exists():
        SUMMARY_PATH.unlink()
    failures = 0
    for slug, scenario_file in SCENARIO_ORDER:
        print(f"[{time.strftime('%H:%M:%S')}] >>> START {slug}", flush=True)
        result = run_one(slug, scenario_file)
        with SUMMARY_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result) + "\n")
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
