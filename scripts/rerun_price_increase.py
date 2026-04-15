"""Re-run just price_increase after TRIBE ffmpeg fix.

Inherits the rerun_phase2_b1_long pattern: 90-min timeout, updates
the shared summary.jsonl entry.
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
SLUG = "price_increase"
TIMEOUT_SECONDS = 90 * 60


def main() -> int:
    spec = json.loads((SCENARIOS_DIR / "price_increase.json").read_text(encoding="utf-8"))
    seed_path = RESULTS_DIR / f"_seed_{SLUG}.txt"
    seed_path.write_text(spec["seed_content"], encoding="utf-8")
    output_path = RESULTS_DIR / f"phase2_b1_full_validation_{SLUG}.json"

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
    print(f"[{time.strftime('%H:%M:%S')}] >>> START {SLUG}", flush=True)
    try:
        proc = subprocess.run(
            cmd, cwd=ROOT,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=TIMEOUT_SECONDS, text=True, errors="replace",
        )
        duration = time.time() - start
        log_path = RESULTS_DIR / f"phase2_b1_full_validation_{SLUG}.log"
        log_path.write_text(proc.stdout or "", encoding="utf-8")
        row = {
            "scenario": SLUG, "returncode": proc.returncode,
            "duration_s": round(duration, 1), "output": str(output_path),
            "log": str(log_path), "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        duration = time.time() - start
        log_path = RESULTS_DIR / f"phase2_b1_full_validation_{SLUG}.log"
        log_path.write_text(exc.stdout or "", encoding="utf-8")
        row = {
            "scenario": SLUG, "returncode": -1,
            "duration_s": round(duration, 1), "output": str(output_path),
            "log": str(log_path), "timed_out": True,
        }

    existing: list[dict] = []
    if SUMMARY_PATH.exists():
        for line in SUMMARY_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            entry = json.loads(line)
            if entry["scenario"] != SLUG:
                existing.append(entry)
    existing.append(row)
    SUMMARY_PATH.write_text(
        "\n".join(json.dumps(r) for r in existing) + "\n",
        encoding="utf-8",
    )
    status = "OK" if row["returncode"] == 0 else "FAIL"
    print(
        f"[{time.strftime('%H:%M:%S')}] <<< {status} {SLUG} "
        f"duration={row['duration_s']}s rc={row['returncode']}",
        flush=True,
    )
    return 0 if row["returncode"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
