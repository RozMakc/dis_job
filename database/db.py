import aiosqlite
import os

from config import config

_db: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        os.makedirs(os.path.dirname(config.DB_PATH), exist_ok=True)
        _db = await aiosqlite.connect(config.DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            discord_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL DEFAULT '',
            display_name TEXT NOT NULL DEFAULT '',
            avatar_url TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER NOT NULL,
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            left_at TEXT,
            duration_seconds INTEGER,
            FOREIGN KEY (discord_id) REFERENCES users(discord_id)
        );

        CREATE TABLE IF NOT EXISTS monitored_channel (
            channel_id INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            channel_name TEXT NOT NULL DEFAULT ''
        );

        CREATE INDEX IF NOT EXISTS idx_sessions_discord_id ON sessions(discord_id);
        CREATE INDEX IF NOT EXISTS idx_sessions_joined_at ON sessions(joined_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_left_at ON sessions(left_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(left_at) WHERE left_at IS NULL;
    """)
    await db.commit()


async def close_db():
    global _db
    if _db is not None:
        await _db.close()
        _db = None
