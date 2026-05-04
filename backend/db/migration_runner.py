import logging
import sqlite3
from pathlib import Path
from typing import List

from backend.db.connection import apply_pragmas_sync

logger = logging.getLogger(__name__)


class MigrationRunner:
    """Uruchamia numerowane migracje SQL zgodnie z docs/DB_SCHEMA.md (schema_migrations)."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.migrations_dir = Path(__file__).resolve().parent / "migrations"

    def run_migrations(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(str(self.db_path))
        try:
            apply_pragmas_sync(conn)
            cursor = conn.cursor()

            migration_files = self._get_migration_files()

            for migration_file in migration_files:
                migration_version = int(migration_file.name.split("_")[0])
                current = self._get_current_version(cursor)

                if migration_version <= current:
                    continue

                logger.info("Applying migration %s", migration_file.name)
                self._apply_migration(cursor, migration_file)
                cursor.execute(
                    "INSERT INTO schema_migrations (version) VALUES (?)",
                    (migration_version,),
                )

            conn.commit()
            logger.info("Database migrations completed successfully")
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _get_current_version(self, cursor: sqlite3.Cursor) -> int:
        try:
            cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 0
        except sqlite3.OperationalError:
            return 0

    def _get_migration_files(self) -> List[Path]:
        if not self.migrations_dir.is_dir():
            raise FileNotFoundError(f"Migration directory does not exist: {self.migrations_dir}")

        migration_files = sorted(
            (p for p in self.migrations_dir.iterdir() if p.is_file() and p.suffix == ".sql"),
            key=lambda f: int(f.name.split("_")[0]),
        )
        return migration_files

    def _apply_migration(self, cursor: sqlite3.Cursor, migration_file: Path) -> None:
        sql_script = migration_file.read_text(encoding="utf-8")
        try:
            cursor.executescript(sql_script)
        except sqlite3.Error as e:
            raise RuntimeError(f"Error executing migration {migration_file.name}: {e}") from e

    def get_migration_status(self) -> dict:
        conn = sqlite3.connect(str(self.db_path))
        try:
            apply_pragmas_sync(conn)
            cursor = conn.cursor()
            migration_files = self._get_migration_files()
            try:
                cursor.execute("SELECT COALESCE(MAX(version), 0) FROM schema_migrations")
                current_version = int(cursor.fetchone()[0])
            except sqlite3.OperationalError:
                current_version = 0

            return {
                "current_version": current_version,
                "available_migrations": [
                    {
                        "version": int(f.name.split("_")[0]),
                        "name": f.name,
                        "applied": int(f.name.split("_")[0]) <= current_version,
                    }
                    for f in migration_files
                ],
            }
        finally:
            conn.close()
