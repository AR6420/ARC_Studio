"""
SQLite database layer for A.R.C Studio.

Manages async connection, WAL mode, foreign keys, and schema initialization.
Uses aiosqlite for non-blocking database access from the async FastAPI server.
"""

import logging
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS campaigns (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL DEFAULT 'pending',
    seed_content TEXT NOT NULL,
    prediction_question TEXT NOT NULL,
    demographic TEXT NOT NULL,
    demographic_custom TEXT,
    agent_count INTEGER NOT NULL DEFAULT 40,
    max_iterations INTEGER NOT NULL DEFAULT 4,
    thresholds TEXT,
    constraints TEXT,
    created_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    error TEXT,
    media_type TEXT NOT NULL DEFAULT 'text',
    media_path TEXT
);

CREATE TABLE IF NOT EXISTS iterations (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    variant_id TEXT NOT NULL,
    variant_content TEXT NOT NULL,
    variant_strategy TEXT,
    tribe_scores TEXT,
    mirofish_metrics TEXT,
    composite_scores TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, iteration_number, variant_id)
);

CREATE TABLE IF NOT EXISTS analyses (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    iteration_number INTEGER NOT NULL,
    analysis_json TEXT NOT NULL,
    system_availability TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(campaign_id, iteration_number)
);

CREATE TABLE IF NOT EXISTS reports (
    id TEXT PRIMARY KEY,
    campaign_id TEXT NOT NULL UNIQUE REFERENCES campaigns(id) ON DELETE CASCADE,
    verdict TEXT,
    scorecard TEXT,
    deep_analysis TEXT,
    mass_psychology_general TEXT,
    mass_psychology_technical TEXT,
    created_at TEXT NOT NULL
);
"""


class Database:
    """
    Async SQLite database wrapper.

    Usage:
        db = Database("/path/to/nexus_sim.db")
        await db.connect()
        # ... use db.conn for queries ...
        await db.close()
    """

    def __init__(self, path: str):
        self._path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self):
        """Open the database, enable WAL mode and foreign keys, create tables."""
        Path(self._path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA_SQL)
        await self._migrate_schema()
        await self._conn.commit()
        logger.info("Database initialized at %s", self._path)

    async def _migrate_schema(self) -> None:
        """Lightweight additive migrations for databases created before a column existed.

        SQLite lacks `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`, so we introspect
        existing columns and only add the ones that are missing. This is safe to
        run on a fresh database (no-op when columns already exist from SCHEMA_SQL).
        """
        cursor = await self._conn.execute("PRAGMA table_info(campaigns)")
        rows = await cursor.fetchall()
        existing_cols = {row["name"] for row in rows}

        # Phase 2 A.1 -- add media columns to pre-existing campaigns tables.
        if "media_type" not in existing_cols:
            await self._conn.execute(
                "ALTER TABLE campaigns ADD COLUMN media_type TEXT NOT NULL DEFAULT 'text'"
            )
            logger.info("Migrated campaigns: added media_type column")
        if "media_path" not in existing_cols:
            await self._conn.execute(
                "ALTER TABLE campaigns ADD COLUMN media_path TEXT"
            )
            logger.info("Migrated campaigns: added media_path column")

    async def close(self):
        """Close the database connection."""
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        """
        Return the active connection.

        Raises RuntimeError if connect() has not been called.
        """
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn
