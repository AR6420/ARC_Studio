"""
Campaign CRUD operations for Nexus Sim.

Handles campaign lifecycle (create, get, list, delete, status updates)
and iteration/analysis persistence with JSON column serialization (D-08).
"""

import json
import logging
import uuid
from datetime import datetime, timezone

from orchestrator.api.schemas import (
    AnalysisRecord,
    CampaignCreateRequest,
    CampaignListResponse,
    CampaignResponse,
    CompositeScores,
    IterationRecord,
    MirofishMetrics,
    TribeScores,
)
from orchestrator.storage.database import Database

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a new UUID4 string."""
    return str(uuid.uuid4())


class CampaignStore:
    """
    CRUD operations for campaigns, iterations, and analyses.

    All JSON columns (thresholds, tribe_scores, mirofish_metrics,
    composite_scores, analysis_json, system_availability) are serialized
    via json.dumps() on write and json.loads() on read (per D-08).
    """

    def __init__(self, db: Database):
        self._db = db

    # ── Campaign CRUD ────────────────────────────────────────────────────────

    async def create_campaign(
        self, request: CampaignCreateRequest
    ) -> CampaignResponse:
        """Create a new campaign from a validated request. Returns the persisted response."""
        campaign_id = _new_id()
        created_at = _now_iso()

        await self._db.conn.execute(
            """
            INSERT INTO campaigns
                (id, status, seed_content, prediction_question, demographic,
                 demographic_custom, agent_count, max_iterations, thresholds,
                 constraints, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                campaign_id,
                "pending",
                request.seed_content,
                request.prediction_question,
                request.demographic,
                request.demographic_custom,
                request.agent_count,
                request.max_iterations,
                json.dumps(request.thresholds) if request.thresholds else None,
                request.constraints,
                created_at,
            ),
        )
        await self._db.conn.commit()

        return CampaignResponse(
            id=campaign_id,
            status="pending",
            seed_content=request.seed_content,
            prediction_question=request.prediction_question,
            demographic=request.demographic,
            demographic_custom=request.demographic_custom,
            agent_count=request.agent_count,
            max_iterations=request.max_iterations,
            thresholds=request.thresholds,
            constraints=request.constraints,
            created_at=created_at,
        )

    async def get_campaign(self, campaign_id: str) -> CampaignResponse | None:
        """Fetch a campaign with all its iterations and analyses."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM campaigns WHERE id = ?", (campaign_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        # Fetch nested iterations and analyses
        iterations = await self.get_iterations(campaign_id)
        analyses = await self._get_analyses(campaign_id)

        return CampaignResponse(
            id=row["id"],
            status=row["status"],
            seed_content=row["seed_content"],
            prediction_question=row["prediction_question"],
            demographic=row["demographic"],
            demographic_custom=row["demographic_custom"],
            agent_count=row["agent_count"],
            max_iterations=row["max_iterations"],
            thresholds=json.loads(row["thresholds"]) if row["thresholds"] else None,
            constraints=row["constraints"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error=row["error"],
            iterations=iterations if iterations else None,
            analyses=analyses if analyses else None,
        )

    async def list_campaigns(self) -> CampaignListResponse:
        """List all campaigns ordered by created_at DESC (lightweight, no nested data)."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM campaigns ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()

        campaigns = [
            CampaignResponse(
                id=row["id"],
                status=row["status"],
                seed_content=row["seed_content"],
                prediction_question=row["prediction_question"],
                demographic=row["demographic"],
                demographic_custom=row["demographic_custom"],
                agent_count=row["agent_count"],
                max_iterations=row["max_iterations"],
                thresholds=(
                    json.loads(row["thresholds"]) if row["thresholds"] else None
                ),
                constraints=row["constraints"],
                created_at=row["created_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                error=row["error"],
            )
            for row in rows
        ]

        return CampaignListResponse(campaigns=campaigns, total=len(campaigns))

    async def delete_campaign(self, campaign_id: str) -> bool:
        """Delete a campaign and all related iterations/analyses (CASCADE). Returns True if existed."""
        cursor = await self._db.conn.execute(
            "DELETE FROM campaigns WHERE id = ?", (campaign_id,)
        )
        await self._db.conn.commit()
        return cursor.rowcount > 0

    async def update_campaign_status(
        self, campaign_id: str, status: str, error: str | None = None
    ) -> None:
        """
        Update campaign status. Sets started_at when status='running',
        completed_at when status is 'completed' or 'failed'.
        """
        now = _now_iso()
        updates = ["status = ?"]
        params: list = [status]

        if status == "running":
            updates.append("started_at = ?")
            params.append(now)
        elif status in ("completed", "failed"):
            updates.append("completed_at = ?")
            params.append(now)

        if error is not None:
            updates.append("error = ?")
            params.append(error)

        params.append(campaign_id)

        await self._db.conn.execute(
            f"UPDATE campaigns SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        await self._db.conn.commit()

    # ── Iteration operations ─────────────────────────────────────────────────

    async def save_iteration(
        self,
        campaign_id: str,
        iteration_number: int,
        variant_id: str,
        variant_content: str,
        variant_strategy: str | None,
        tribe_scores: dict | None,
        mirofish_metrics: dict | None,
        composite_scores: dict | None,
    ) -> str:
        """
        Save an iteration record. Serializes score dicts to JSON strings (D-08).
        Returns the generated iteration id.
        """
        iteration_id = _new_id()
        created_at = _now_iso()

        await self._db.conn.execute(
            """
            INSERT INTO iterations
                (id, campaign_id, iteration_number, variant_id, variant_content,
                 variant_strategy, tribe_scores, mirofish_metrics, composite_scores,
                 created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                iteration_id,
                campaign_id,
                iteration_number,
                variant_id,
                variant_content,
                variant_strategy,
                json.dumps(tribe_scores) if tribe_scores else None,
                json.dumps(mirofish_metrics) if mirofish_metrics else None,
                json.dumps(composite_scores) if composite_scores else None,
                created_at,
            ),
        )
        await self._db.conn.commit()
        return iteration_id

    async def get_iterations(
        self, campaign_id: str, iteration_number: int | None = None
    ) -> list[IterationRecord]:
        """
        Get iteration records for a campaign, optionally filtered by iteration_number.
        Deserializes JSON columns back to Pydantic models.
        """
        if iteration_number is not None:
            cursor = await self._db.conn.execute(
                "SELECT * FROM iterations WHERE campaign_id = ? AND iteration_number = ? ORDER BY variant_id",
                (campaign_id, iteration_number),
            )
        else:
            cursor = await self._db.conn.execute(
                "SELECT * FROM iterations WHERE campaign_id = ? ORDER BY iteration_number, variant_id",
                (campaign_id,),
            )

        rows = await cursor.fetchall()
        return [self._row_to_iteration(row) for row in rows]

    # ── Analysis operations ──────────────────────────────────────────────────

    async def save_analysis(
        self,
        campaign_id: str,
        iteration_number: int,
        analysis_json: dict,
        system_availability: dict | None,
    ) -> str:
        """
        Save an analysis record. Serializes dicts to JSON strings (D-08).
        Returns the generated analysis id.
        """
        analysis_id = _new_id()
        created_at = _now_iso()

        await self._db.conn.execute(
            """
            INSERT INTO analyses
                (id, campaign_id, iteration_number, analysis_json,
                 system_availability, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                analysis_id,
                campaign_id,
                iteration_number,
                json.dumps(analysis_json),
                json.dumps(system_availability) if system_availability else None,
                created_at,
            ),
        )
        await self._db.conn.commit()
        return analysis_id

    async def _get_analyses(self, campaign_id: str) -> list[AnalysisRecord]:
        """Get all analysis records for a campaign."""
        cursor = await self._db.conn.execute(
            "SELECT * FROM analyses WHERE campaign_id = ? ORDER BY iteration_number",
            (campaign_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_analysis(row) for row in rows]

    # ── Row conversion helpers ───────────────────────────────────────────────

    @staticmethod
    def _row_to_iteration(row) -> IterationRecord:
        """Convert a database row to an IterationRecord, deserializing JSON columns."""
        tribe_raw = row["tribe_scores"]
        mirofish_raw = row["mirofish_metrics"]
        composite_raw = row["composite_scores"]

        return IterationRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            iteration_number=row["iteration_number"],
            variant_id=row["variant_id"],
            variant_content=row["variant_content"],
            variant_strategy=row["variant_strategy"],
            tribe_scores=TribeScores(**json.loads(tribe_raw)) if tribe_raw else None,
            mirofish_metrics=(
                MirofishMetrics(**json.loads(mirofish_raw)) if mirofish_raw else None
            ),
            composite_scores=(
                CompositeScores(**json.loads(composite_raw)) if composite_raw else None
            ),
            created_at=row["created_at"],
        )

    @staticmethod
    def _row_to_analysis(row) -> AnalysisRecord:
        """Convert a database row to an AnalysisRecord, deserializing JSON columns."""
        return AnalysisRecord(
            id=row["id"],
            campaign_id=row["campaign_id"],
            iteration_number=row["iteration_number"],
            analysis_json=json.loads(row["analysis_json"]),
            system_availability=(
                json.loads(row["system_availability"])
                if row["system_availability"]
                else None
            ),
            created_at=row["created_at"],
        )
