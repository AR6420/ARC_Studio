"""
Results validation checker for A.R.C Studio demo scenarios.

Reads result JSON files from results/ directory and checks three quality criteria:
  1. Iteration improvement (VAL-03): 4/5 scenarios must show score improvement
  2. Cross-system reasoning (VAL-04): All 5 must reference both TRIBE and MiroFish
  3. Demographic sensitivity (VAL-05): Score variance across scenarios must exceed threshold

Usage:
    python scripts/validate_results.py
    python scripts/validate_results.py --results-dir results
"""

import argparse
import json
import os
import re
import statistics
import sys
from glob import glob


def load_results(results_dir: str = "results") -> list[dict]:
    """Load all result JSON files from the results directory."""
    pattern = os.path.join(results_dir, "*_result.json")
    files = sorted(glob(pattern))
    results = []
    for filepath in files:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["_file"] = os.path.basename(filepath)
        results.append(data)
    return results


def get_best_composite_average(iteration_data: dict) -> float | None:
    """
    Get the average composite score of the best variant in an iteration.

    Looks for composite_scores in the iteration data. The best variant
    is the one with the highest average across all composite score dimensions.
    """
    composite_scores = iteration_data.get("composite_scores", [])
    if not composite_scores:
        return None

    best_avg = None
    for scores in composite_scores:
        if not scores or not isinstance(scores, dict):
            continue
        values = [v for v in scores.values() if v is not None and isinstance(v, (int, float))]
        if not values:
            continue
        avg = sum(values) / len(values)
        if best_avg is None or avg > best_avg:
            best_avg = avg

    return best_avg


def check_iteration_improvement(result: dict) -> tuple[bool, str]:
    """
    Check if the last iteration scores higher than the first iteration (VAL-03).

    Returns (passed, detail_message).
    """
    iterations = result.get("iterations", [])
    if len(iterations) < 2:
        return False, "Only 1 iteration found (need at least 2 to measure improvement)"

    first_avg = get_best_composite_average(iterations[0])
    last_avg = get_best_composite_average(iterations[-1])

    if first_avg is None:
        return False, "No composite scores in first iteration"
    if last_avg is None:
        return False, "No composite scores in last iteration"

    improved = last_avg > first_avg
    detail = (
        f"First iteration avg: {first_avg:.1f}, "
        f"Last iteration avg: {last_avg:.1f}, "
        f"Change: {last_avg - first_avg:+.1f} "
        f"({'IMPROVED' if improved else 'NO IMPROVEMENT'})"
    )
    return improved, detail


def check_cross_system_reasoning(result: dict) -> tuple[bool, str]:
    """
    Check if cross-system insights reference both TRIBE/neural and MiroFish/social (VAL-04).

    Searches the analysis.cross_system_insights array in each iteration for strings
    containing BOTH a neural-related term AND a social-related term.

    Returns (passed, detail_message).
    """
    neural_terms = re.compile(
        r"(?:TRIBE|neural|brain|attention|emotional|memory|cognitive|reward|threat)",
        re.IGNORECASE,
    )
    social_terms = re.compile(
        r"(?:MiroFish|simulation|social|share|propagation|sentiment|coalition|virality)",
        re.IGNORECASE,
    )

    iterations = result.get("iterations", [])
    if not iterations:
        return False, "No iterations found"

    found_cross_system = False
    total_insights = 0
    cross_system_count = 0

    for iteration in iterations:
        analysis = iteration.get("analysis", {})
        insights = analysis.get("cross_system_insights", [])
        for insight in insights:
            total_insights += 1
            has_neural = neural_terms.search(str(insight)) is not None
            has_social = social_terms.search(str(insight)) is not None
            if has_neural and has_social:
                cross_system_count += 1
                found_cross_system = True

    if found_cross_system:
        detail = f"{cross_system_count}/{total_insights} insights reference both systems"
    else:
        detail = f"0/{total_insights} insights reference both systems"

    return found_cross_system, detail


def check_demographic_sensitivity(results: list[dict]) -> tuple[bool, float, str]:
    """
    Check that composite score profiles differ meaningfully across scenarios (VAL-05).

    Computes the standard deviation of average composite scores across all scenarios.
    The threshold is > 5.0 points of variance.

    Returns (passed, variance_value, detail_message).
    """
    scenario_averages = []

    for result in results:
        iterations = result.get("iterations", [])
        if not iterations:
            continue

        # Use the last iteration for comparison
        last_iteration = iterations[-1]
        avg = get_best_composite_average(last_iteration)
        if avg is not None:
            scenario_averages.append(avg)

    if len(scenario_averages) < 2:
        return False, 0.0, f"Only {len(scenario_averages)} scenario(s) have valid scores (need at least 2)"

    std_dev = statistics.stdev(scenario_averages)
    passed = std_dev > 5.0

    detail_parts = [f"Score averages across scenarios: {[f'{a:.1f}' for a in scenario_averages]}"]
    detail_parts.append(f"Standard deviation: {std_dev:.1f} (threshold: > 5.0)")
    detail = "; ".join(detail_parts)

    return passed, std_dev, detail


def main():
    parser = argparse.ArgumentParser(
        description="Validate A.R.C Studio scenario results against quality criteria",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="results",
        help="Directory containing result JSON files (default: results)",
    )
    args = parser.parse_args()

    # Load results
    results = load_results(args.results_dir)
    if not results:
        print(f"ERROR: No result files found in {args.results_dir}/")
        print("Run 'python scripts/run_validation.py' first to generate results.")
        sys.exit(1)

    total = len(results)
    print(f"Loaded {total} result file(s) from {args.results_dir}/\n")

    # ── Check 1: Iteration improvement (VAL-03) ──────────────────────────────

    improvement_results = []
    for result in results:
        passed, detail = check_iteration_improvement(result)
        improvement_results.append((result["_file"], passed, detail))

    improved_count = sum(1 for _, passed, _ in improvement_results if passed)
    improvement_passed = improved_count >= 4  # D-03: 4/5 threshold

    # ── Check 2: Cross-system reasoning (VAL-04) ─────────────────────────────

    cross_system_results = []
    for result in results:
        passed, detail = check_cross_system_reasoning(result)
        cross_system_results.append((result["_file"], passed, detail))

    cross_system_count = sum(1 for _, passed, _ in cross_system_results if passed)
    cross_system_passed = cross_system_count == total  # All must pass

    # ── Check 3: Demographic sensitivity (VAL-05) ────────────────────────────

    demo_passed, demo_variance, demo_detail = check_demographic_sensitivity(results)

    # ── Print report ─────────────────────────────────────────────────────────

    print("=" * 60)
    print("VALIDATION REPORT")
    print("=" * 60)
    print()

    # Summary
    status_improvement = "PASS" if improvement_passed else "FAIL"
    status_cross_system = "PASS" if cross_system_passed else "FAIL"
    status_demographic = "PASS" if demo_passed else "FAIL"

    print(f"Iteration Improvement: {improved_count}/{total} scenarios improved (need 4/5) [{status_improvement}]")
    print(f"Cross-System Reasoning: {cross_system_count}/{total} reports reference both systems (need {total}/{total}) [{status_cross_system}]")
    print(f"Demographic Sensitivity: Score variance = {demo_variance:.1f} (need > 5.0) [{status_demographic}]")
    print()

    # Per-scenario details
    print("-" * 60)
    print("Per-scenario details:")
    print("-" * 60)
    print()

    for i, result in enumerate(results):
        filename = result["_file"]
        print(f"  {filename}:")

        # Iteration improvement
        _, imp_passed, imp_detail = improvement_results[i]
        imp_mark = "PASS" if imp_passed else "FAIL"
        print(f"    Iteration Improvement: [{imp_mark}] {imp_detail}")

        # Cross-system reasoning
        _, cs_passed, cs_detail = cross_system_results[i]
        cs_mark = "PASS" if cs_passed else "FAIL"
        print(f"    Cross-System Reasoning: [{cs_mark}] {cs_detail}")

        print()

    # Demographic sensitivity detail (applies across all scenarios)
    print(f"  Demographic Sensitivity (across all scenarios):")
    print(f"    [{status_demographic}] {demo_detail}")
    print()

    # Overall result
    all_passed = improvement_passed and cross_system_passed and demo_passed
    print("=" * 60)
    if all_passed:
        print("OVERALL: ALL CRITERIA PASSED")
    else:
        failed = []
        if not improvement_passed:
            failed.append("Iteration Improvement")
        if not cross_system_passed:
            failed.append("Cross-System Reasoning")
        if not demo_passed:
            failed.append("Demographic Sensitivity")
        print(f"OVERALL: FAILED ({', '.join(failed)})")
    print("=" * 60)

    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
