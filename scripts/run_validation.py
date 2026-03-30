"""
Automated validation runner for Nexus Sim demo scenarios.

Reads all JSON test briefs from scenarios/ directory and invokes the
orchestrator CLI for each one, collecting results in results/ directory.

Usage:
    python scripts/run_validation.py             # Run all 5 scenarios
    python scripts/run_validation.py --scenario product_launch  # Run one scenario
    python scripts/run_validation.py --dry-run    # Print commands without executing
"""

import argparse
import json
import os
import subprocess
import sys
from glob import glob
from pathlib import Path


def load_scenarios(scenarios_dir: str = "scenarios") -> list[dict]:
    """Load all JSON scenario briefs from the scenarios directory."""
    pattern = os.path.join(scenarios_dir, "*.json")
    files = sorted(glob(pattern))
    scenarios = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Add the file stem as an identifier
        data["_file"] = os.path.basename(filepath)
        data["_stem"] = Path(filepath).stem
        scenarios.append(data)
    return scenarios


def build_cli_command(scenario: dict, output_path: str) -> list[str]:
    """Build the CLI command list for a given scenario."""
    cmd = [
        sys.executable, "-m", "orchestrator.cli",
        "--seed-content", scenario["seed_content"],
        "--prediction-question", scenario["prediction_question"],
        "--demographic", scenario["demographic"],
        "--agent-count", str(scenario["agent_count"]),
        "--max-iterations", str(scenario["max_iterations"]),
        "--output", output_path,
        "--verbose",
    ]
    return cmd


def run_scenario(scenario: dict, results_dir: str = "results", dry_run: bool = False) -> bool:
    """
    Run a single scenario through the orchestrator CLI.

    Returns True if the scenario completed successfully, False otherwise.
    """
    name = scenario.get("name", scenario["_stem"])
    stem = scenario["_stem"]
    output_path = os.path.join(results_dir, f"{stem}_result.json")

    cmd = build_cli_command(scenario, output_path)

    if dry_run:
        # Print the command without executing
        cmd_str = " ".join(f'"{c}"' if " " in c else c for c in cmd)
        print(f"  {cmd_str}")
        return True

    print(f"  Output: {output_path}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1200,  # 20 minutes max per scenario
        )
        if result.returncode != 0:
            print(f"  ERROR (exit code {result.returncode})")
            if result.stderr:
                # Print last 10 lines of stderr for diagnostics
                stderr_lines = result.stderr.strip().split("\n")
                for line in stderr_lines[-10:]:
                    print(f"    {line}")
            return False
        else:
            print(f"  SUCCESS")
            return True
    except subprocess.TimeoutExpired:
        print(f"  ERROR: Timed out after 20 minutes")
        return False
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Run Nexus Sim validation scenarios",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default=None,
        help="Run a single scenario by file stem name (e.g., 'product_launch')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print CLI commands without executing them",
    )
    parser.add_argument(
        "--scenarios-dir",
        type=str,
        default="scenarios",
        help="Directory containing scenario JSON files (default: scenarios)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results",
        help="Directory to write result JSON files (default: results)",
    )
    args = parser.parse_args()

    # Load scenarios
    scenarios = load_scenarios(args.scenarios_dir)
    if not scenarios:
        print(f"ERROR: No scenario files found in {args.scenarios_dir}/")
        sys.exit(1)

    # Filter to single scenario if requested
    if args.scenario:
        scenarios = [s for s in scenarios if s["_stem"] == args.scenario]
        if not scenarios:
            print(f"ERROR: Scenario '{args.scenario}' not found")
            sys.exit(1)

    # Create results directory
    if not args.dry_run:
        os.makedirs(args.results_dir, exist_ok=True)

    total = len(scenarios)
    successes = 0

    if args.dry_run:
        print(f"DRY RUN: {total} scenario(s) would be executed\n")
    else:
        print(f"Running {total} scenario(s)...\n")

    for i, scenario in enumerate(scenarios, 1):
        name = scenario.get("name", scenario["_stem"])
        print(f"Running scenario {i}/{total}: {name}")
        success = run_scenario(scenario, args.results_dir, args.dry_run)
        if success:
            successes += 1
        print()

    # Summary
    print("=" * 60)
    if args.dry_run:
        print(f"DRY RUN COMPLETE: {total} CLI commands printed")
    else:
        print(f"VALIDATION RUN COMPLETE: {successes}/{total} scenarios completed successfully")
        if successes < total:
            print(f"  {total - successes} scenario(s) failed -- check output above for details")
    print("=" * 60)

    if not args.dry_run and successes < total:
        sys.exit(1)


if __name__ == "__main__":
    main()
