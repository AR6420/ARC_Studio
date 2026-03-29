"""
Shared test fixtures for the orchestrator test suite.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest


@pytest.fixture(scope="function")
def tmp_db_path(tmp_path: Path) -> str:
    """Return a temporary file path for a SQLite test database."""
    db_file = tmp_path / "test_nexus_sim.db"
    return str(db_file)


@pytest.fixture(scope="function")
def mock_claude_client() -> AsyncMock:
    """
    AsyncMock of ClaudeClient with call_haiku_json returning sample variants.
    """
    client = AsyncMock()
    client.call_haiku_json.return_value = {
        "variants": [
            {
                "id": "v1",
                "content": "Sample variant content for testing purposes.",
                "strategy": "direct_appeal",
            },
            {
                "id": "v2",
                "content": "Another variant with different approach.",
                "strategy": "social_proof",
            },
            {
                "id": "v3",
                "content": "Third variant using urgency framing.",
                "strategy": "urgency",
            },
        ]
    }
    client.call_opus_json.return_value = {
        "analysis": "Cross-system analysis placeholder.",
        "recommendations": [],
    }
    return client
