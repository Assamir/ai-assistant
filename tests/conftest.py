"""Wspólne fixture dla testów jednostkowych."""

from __future__ import annotations

import pytest

from backend.db.migration_runner import MigrationRunner


@pytest.fixture
def migrated_db_path(tmp_path):
    db_path = tmp_path / "test.db"
    MigrationRunner(str(db_path)).run_migrations()
    return str(db_path)
