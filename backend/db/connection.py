"""SQLite connection helpers — PRAGMAs z docs/DB_SCHEMA.md."""

PRAGMAS = (
    "PRAGMA journal_mode = WAL",
    "PRAGMA synchronous = NORMAL",
    "PRAGMA foreign_keys = ON",
    "PRAGMA cache_size = -64000",
    "PRAGMA temp_store = MEMORY",
    "PRAGMA mmap_size = 268435456",
)


def apply_pragmas_sync(conn) -> None:
    cur = conn.cursor()
    for pragma in PRAGMAS:
        cur.execute(pragma)


async def apply_pragmas_async(db) -> None:
    for pragma in PRAGMAS:
        await db.execute(pragma)
