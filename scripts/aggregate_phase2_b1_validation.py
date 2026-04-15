"""Aggregate Phase 2 B.1 5-scenario validation results into a markdown doc.

Reads results/phase2_b1_full_validation_<slug>.json for each scenario plus the
timing summary in results/phase2_b1_full_validation_summary.jsonl, then writes
docs/phase2_b1_full_validation.md with a side-by-side comparison table and a
success-criteria verdict.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"
DOC_PATH = ROOT / "docs" / "phase2_b1_full_validation.md"
SUMMARY_PATH = RESULTS_DIR / "phase2_b1_full_validation_summary.jsonl"

SCENARIOS = [
    ("product_launch", "Product Launch", "tech_professionals"),
    ("gen_z_marketing", "Gen Z Marketing", "gen_z_digital_natives"),
    ("policy_announcement", "Policy Announcement", "policy_aware_public"),
    ("price_increase", "Price Increase", "enterprise_decision_makers"),
    ("public_health_psa", "Public Health PSA", "general_consumer_us"),
]


def load_summary() -> dict[str, dict]:
    if not SUMMARY_PATH.exists():
        return {}
    out: dict[str, dict] = {}
    for line in SUMMARY_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        out[row["scenario"]] = row
    return out


def extract_metrics(slug: str) -> dict | None:
    path = RESULTS_DIR / f"phase2_b1_full_validation_{slug}.json"
    if not path.exists():
        return None
    d = json.loads(path.read_text(encoding="utf-8"))
    iter_data = []
    pseudo_count = 0
    variant_count = 0
    tribe_atts: list[float] = []
    comp_atts: list[float] = []
    word_counts: list[int] = []
    for it in d.get("iterations", []):
        for v, t, c in zip(
            it.get("variants", []),
            it.get("tribe_scores") or [],
            it.get("composite_scores") or [],
        ):
            variant_count += 1
            word_counts.append(len(v.get("content", "").split()))
            if t:
                if t.get("is_pseudo_score"):
                    pseudo_count += 1
                if t.get("attention_capture") is not None:
                    tribe_atts.append(float(t["attention_capture"]))
            if c and c.get("attention_score") is not None:
                comp_atts.append(float(c["attention_score"]))
        iter_avg_comp = None
        iter_composites = [
            float(c["attention_score"])
            for c in (it.get("composite_scores") or [])
            if c and c.get("attention_score") is not None
        ]
        if iter_composites:
            iter_avg_comp = statistics.mean(iter_composites)
        iter_data.append({
            "iter_n": it.get("iteration_number"),
            "avg_composite_attention": iter_avg_comp,
        })

    improvement = None
    if len(iter_data) >= 2 and iter_data[0]["avg_composite_attention"] is not None \
            and iter_data[1]["avg_composite_attention"] is not None:
        improvement = iter_data[1]["avg_composite_attention"] - iter_data[0]["avg_composite_attention"]

    return {
        "pseudo_count": pseudo_count,
        "variant_count": variant_count,
        "tribe_att_min": min(tribe_atts) if tribe_atts else None,
        "tribe_att_max": max(tribe_atts) if tribe_atts else None,
        "tribe_att_range": (max(tribe_atts) - min(tribe_atts)) if len(tribe_atts) >= 2 else None,
        "comp_att_min": min(comp_atts) if comp_atts else None,
        "comp_att_max": max(comp_atts) if comp_atts else None,
        "word_min": min(word_counts) if word_counts else None,
        "word_max": max(word_counts) if word_counts else None,
        "iter1_avg_comp": iter_data[0]["avg_composite_attention"] if iter_data else None,
        "iter2_avg_comp": iter_data[1]["avg_composite_attention"] if len(iter_data) > 1 else None,
        "improvement": improvement,
        "iterations_completed": d.get("iterations_completed"),
    }


def fmt(v, precision=1) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{precision}f}"
    return str(v)


def main() -> int:
    summary = load_summary()
    rows: list[dict] = []
    for slug, label, demo in SCENARIOS:
        metrics = extract_metrics(slug)
        timing = summary.get(slug, {})
        if not metrics:
            continue
        rows.append({
            "slug": slug,
            "label": label,
            "demo": demo,
            "duration_min": round(timing.get("duration_s", 0) / 60, 1) if timing else None,
            "returncode": timing.get("returncode") if timing else None,
            **metrics,
        })

    # Success criteria
    total_variants = sum(r["variant_count"] for r in rows)
    total_pseudos = sum(r["pseudo_count"] for r in rows)
    improved_count = sum(
        1 for r in rows if r["improvement"] is not None and r["improvement"] > 0
    )
    max_duration = max((r["duration_min"] or 0) for r in rows) if rows else 0

    crit_pseudo = "PASS" if total_pseudos == 0 else "FAIL"
    crit_improve = "PASS" if improved_count >= 3 else "FAIL"
    crit_duration = "PASS" if max_duration <= 45 else "FAIL"
    tribe_variance_ok = all(
        (r["tribe_att_range"] or 0) > 5.0 for r in rows if r["tribe_att_range"] is not None
    )
    crit_variance = "PASS" if tribe_variance_ok else "FAIL"

    # Write doc
    lines: list[str] = []
    lines.append("# Phase 2 B.1 Full 5-Scenario Validation")
    lines.append("")
    lines.append("**Date:** 2026-04-14")
    lines.append("**Defaults:** 150-word max variants, 2 variants per iteration, 2 iterations, 20 agents")
    lines.append("")
    lines.append("## Side-by-Side Results")
    lines.append("")
    lines.append(
        "| Scenario | Demographic | Duration (min) | Pseudo-scores | TRIBE attention range | Composite attention range | Iter1→Iter2 Δ |"
    )
    lines.append(
        "|---|---|---|---|---|---|---|"
    )
    for r in rows:
        tribe_range = f"{fmt(r['tribe_att_min'])}-{fmt(r['tribe_att_max'])}" if r["tribe_att_min"] is not None else "—"
        comp_range = f"{fmt(r['comp_att_min'])}-{fmt(r['comp_att_max'])}" if r["comp_att_min"] is not None else "—"
        delta = f"{r['improvement']:+.1f}" if r["improvement"] is not None else "—"
        lines.append(
            f"| {r['label']} | {r['demo']} | {fmt(r['duration_min'])} | {r['pseudo_count']}/{r['variant_count']} "
            f"| {tribe_range} | {comp_range} | {delta} |"
        )
    lines.append("")

    lines.append("## Success Criteria")
    lines.append("")
    lines.append("| Criterion | Target | Actual | Status |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| Pseudo-score fallbacks | 0/{total_variants} | {total_pseudos}/{total_variants} | **{crit_pseudo}** |"
    )
    lines.append(
        f"| TRIBE attention variance (per scenario) | range > 5.0 | {'all pass' if tribe_variance_ok else 'some fail'} | **{crit_variance}** |"
    )
    lines.append(
        f"| Scenarios with iter1→iter2 composite improvement | ≥ 3/5 | {improved_count}/5 | **{crit_improve}** |"
    )
    lines.append(
        f"| Max campaign duration | ≤ 45 min | {max_duration:.1f} min | **{crit_duration}** |"
    )
    lines.append("")

    overall = "PASS" if all(
        s == "PASS" for s in (crit_pseudo, crit_improve, crit_duration, crit_variance)
    ) else "FAIL"
    lines.append(f"**Overall:** {overall}")
    lines.append("")

    lines.append("## Per-Scenario Iteration Averages (composite attention)")
    lines.append("")
    lines.append("| Scenario | Iter 1 avg | Iter 2 avg | Δ |")
    lines.append("|---|---|---|---|")
    for r in rows:
        delta = f"{r['improvement']:+.1f}" if r["improvement"] is not None else "—"
        lines.append(
            f"| {r['label']} | {fmt(r['iter1_avg_comp'])} | {fmt(r['iter2_avg_comp'])} | {delta} |"
        )
    lines.append("")

    lines.append("## Variant Word Counts (bounded by 150-word max)")
    lines.append("")
    lines.append("| Scenario | Min words | Max words |")
    lines.append("|---|---|---|")
    for r in rows:
        lines.append(f"| {r['label']} | {fmt(r['word_min'], 0)} | {fmt(r['word_max'], 0)} |")
    lines.append("")

    DOC_PATH.parent.mkdir(exist_ok=True)
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {DOC_PATH}")
    print(f"Overall verdict: {overall}")
    print(f"Criteria — pseudo:{crit_pseudo} variance:{crit_variance} improvement:{crit_improve} duration:{crit_duration}")
    # Also emit JSON summary for downstream tag/push script
    verdict = {
        "overall": overall,
        "total_variants": total_variants,
        "total_pseudos": total_pseudos,
        "improved_count": improved_count,
        "max_duration_min": max_duration,
        "tribe_variance_ok": tribe_variance_ok,
    }
    (RESULTS_DIR / "phase2_b1_full_validation_verdict.json").write_text(
        json.dumps(verdict, indent=2), encoding="utf-8"
    )
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
