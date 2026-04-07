"""
Report retrieval and export API endpoints for A.R.C Studio.

Provides:
- GET /campaigns/{id}/report: Full report as JSON (ReportResponse)
- GET /campaigns/{id}/export/json: Complete campaign data download (RPT-06, D-04)
- GET /campaigns/{id}/export/markdown: Formatted Markdown report (RPT-07, D-05)
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import Response

from orchestrator.api.schemas import CampaignResponse, ReportResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.get("/campaigns/{campaign_id}/report", response_model=ReportResponse)
async def get_report(request: Request, campaign_id: str):
    """Get the report for a campaign with all 5 layer fields."""
    store = request.app.state.campaign_store
    report = await store.get_report(campaign_id)
    if report is None:
        raise HTTPException(status_code=404, detail=f"Report for campaign {campaign_id} not found")
    return report


@router.get("/campaigns/{campaign_id}/export/json")
async def export_json(request: Request, campaign_id: str):
    """
    Export full campaign data as JSON download (RPT-06, D-04).

    Includes the complete audit trail: campaign config, all iterations,
    all analyses, and all report layers.
    """
    store = request.app.state.campaign_store
    campaign = await store.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    report = await store.get_report(campaign_id)

    export_data = {
        "campaign": campaign.model_dump(),
        "report": report.model_dump() if report else None,
    }

    content = json.dumps(export_data, indent=2, default=str)

    return Response(
        content=content,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="campaign_{campaign_id}.json"',
        },
    )


@router.get("/campaigns/{campaign_id}/export/markdown")
async def export_markdown(request: Request, campaign_id: str):
    """
    Export campaign report as formatted Markdown download (RPT-07, D-05).

    Renders all 4 report layers as Markdown sections with tables.
    """
    store = request.app.state.campaign_store
    campaign = await store.get_campaign(campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail=f"Campaign {campaign_id} not found")

    report = await store.get_report(campaign_id)

    md = _render_markdown_report(campaign, report)

    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="campaign_{campaign_id}.md"',
        },
    )


# ── Markdown rendering helpers ───────────────────────────────────────────────


def _escape_pipe(text: str) -> str:
    """Escape pipe characters for Markdown table cell safety (per Pitfall 4)."""
    if text is None:
        return ""
    return str(text).replace("|", "\\|")


def _markdown_table(headers: list[str], rows: list[list[str]]) -> str:
    """Generate a properly formatted Markdown table string."""
    if not headers:
        return ""

    header_line = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    lines = [header_line, separator]

    for row in rows:
        # Pad row to match header count
        padded = row + [""] * (len(headers) - len(row))
        line = "| " + " | ".join(_escape_pipe(cell) for cell in padded) + " |"
        lines.append(line)

    return "\n".join(lines)


def _render_markdown_report(
    campaign: CampaignResponse,
    report: ReportResponse | None,
) -> str:
    """
    Render a full Markdown report with all 4 layers as sections.

    Follows the template from RESEARCH.md Pattern 6:
    - Header with campaign metadata
    - ## Verdict
    - ## Scorecard (variant ranking table, trajectory, thresholds)
    - ## Deep Analysis (per-iteration data tables)
    - ## Mass Psychology (general + technical subsections)
    - Footer
    """
    sections: list[str] = []

    # Header
    sections.append(f"# Campaign Report: {campaign.id}")
    sections.append("")
    sections.append(f"- **Demographic:** {campaign.demographic}")
    sections.append(f"- **Max Iterations:** {campaign.max_iterations}")
    sections.append(f"- **Agent Count:** {campaign.agent_count}")
    sections.append(f"- **Status:** {campaign.status}")
    sections.append("")

    # ── Section 1: Verdict ────────────────────────────────────────────────

    sections.append("## Verdict")
    sections.append("")
    if report and report.verdict:
        sections.append(report.verdict)
    else:
        sections.append("*(No report generated)*")
    sections.append("")

    # ── Section 2: Scorecard ──────────────────────────────────────────────

    sections.append("## Scorecard")
    sections.append("")

    if report and report.scorecard:
        sc = report.scorecard

        # Winning variant
        sections.append(f"**Winner:** {sc.winning_variant_id}")
        sections.append("")

        # Variant ranking table
        if sc.variants:
            headers = ["Rank", "Variant", "Strategy"]
            # Collect all composite score keys from first variant
            score_keys: list[str] = []
            if sc.variants:
                score_keys = list(sc.variants[0].composite_scores.keys())
                headers.extend(score_keys)

            rows: list[list[str]] = []
            for v in sc.variants:
                row = [str(v.rank), v.variant_id, v.strategy or ""]
                for key in score_keys:
                    val = v.composite_scores.get(key)
                    color = v.color_coding.get(key, "")
                    if val is not None:
                        row.append(f"{val:.1f} ({color})")
                    else:
                        row.append("N/A")
                rows.append(row)

            sections.append("### Variant Ranking")
            sections.append("")
            sections.append(_markdown_table(headers, rows))
            sections.append("")

        # Iteration trajectory
        if sc.iteration_trajectory:
            sections.append("### Iteration Trajectory")
            sections.append("")
            for entry in sc.iteration_trajectory:
                iter_num = entry.get("iteration", "?")
                best = entry.get("best_scores", {})
                score_parts = [
                    f"{k}={v:.1f}" if isinstance(v, float) else f"{k}={v}"
                    for k, v in best.items()
                    if v is not None
                ]
                sections.append(f"- **Iteration {iter_num}:** {', '.join(score_parts) if score_parts else 'N/A'}")
            sections.append("")

        # Thresholds status
        if sc.thresholds_status:
            sections.append("### Thresholds")
            sections.append("")
            all_met = sc.thresholds_status.get("all_met", False)
            sections.append(f"All met: **{'Yes' if all_met else 'No'}**")
            per_threshold = sc.thresholds_status.get("per_threshold", {})
            if per_threshold:
                for k, v in per_threshold.items():
                    sections.append(f"- {k}: {v}")
            sections.append("")

        # Summary
        sections.append(f"*{sc.summary}*")
        sections.append("")
    else:
        sections.append("*(No scorecard data)*")
        sections.append("")

    # ── Section 3: Deep Analysis ──────────────────────────────────────────

    sections.append("## Deep Analysis")
    sections.append("")

    if report and report.deep_analysis:
        iterations_data = report.deep_analysis.get("iterations", [])
        for iter_data in iterations_data:
            iter_num = iter_data.get("iteration", "?")
            sections.append(f"### Iteration {iter_num}")
            sections.append("")

            variants = iter_data.get("variants", [])
            for v in variants:
                vid = v.get("variant_id", "unknown")
                strategy = v.get("strategy", "")
                sections.append(f"**Variant {vid}** ({strategy})")
                sections.append("")

                # TRIBE scores table
                tribe = v.get("tribe_scores")
                if tribe:
                    t_headers = ["Dimension", "Score"]
                    t_rows = [[k, f"{val:.1f}" if isinstance(val, float) else str(val)]
                              for k, val in tribe.items()]
                    sections.append("TRIBE Scores:")
                    sections.append("")
                    sections.append(_markdown_table(t_headers, t_rows))
                    sections.append("")

                # MiroFish metrics table
                mirofish = v.get("mirofish_metrics")
                if mirofish:
                    m_headers = ["Metric", "Value"]
                    m_rows = [[k, str(val)] for k, val in mirofish.items()
                              if not isinstance(val, list)]
                    sections.append("MiroFish Metrics:")
                    sections.append("")
                    sections.append(_markdown_table(m_headers, m_rows))
                    sections.append("")

                # Composite scores table
                composite = v.get("composite_scores")
                if composite:
                    c_headers = ["Score", "Value"]
                    c_rows = [[k, f"{val:.1f}" if isinstance(val, float) else str(val)]
                              for k, val in composite.items() if val is not None]
                    sections.append("Composite Scores:")
                    sections.append("")
                    sections.append(_markdown_table(c_headers, c_rows))
                    sections.append("")

            # Analysis text
            analysis = iter_data.get("analysis", {})
            if analysis:
                ranking = analysis.get("ranking", [])
                if ranking:
                    sections.append(f"**Ranking:** {' > '.join(ranking)}")
                    sections.append("")
                insights = analysis.get("cross_system_insights", [])
                if insights:
                    sections.append("**Insights:**")
                    for insight in insights:
                        sections.append(f"- {insight}")
                    sections.append("")
    else:
        sections.append("*(No deep analysis data)*")
        sections.append("")

    # ── Section 4: Mass Psychology ────────────────────────────────────────

    sections.append("## Mass Psychology")
    sections.append("")

    if report and report.mass_psychology_general:
        sections.append("### General Narrative")
        sections.append("")
        sections.append(report.mass_psychology_general)
        sections.append("")
    else:
        sections.append("### General Narrative")
        sections.append("")
        sections.append("*(Not available)*")
        sections.append("")

    if report and report.mass_psychology_technical:
        sections.append("### Technical Analysis")
        sections.append("")
        sections.append(report.mass_psychology_technical)
        sections.append("")
    else:
        sections.append("### Technical Analysis")
        sections.append("")
        sections.append("*(Not available)*")
        sections.append("")

    # Footer
    sections.append("---")
    sections.append("*Exported from A.R.C Studio*")

    return "\n".join(sections)
