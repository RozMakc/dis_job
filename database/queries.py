from datetime import datetime, timezone
from database.db import get_db


async def upsert_user(discord_id: int, username: str, display_name: str, avatar_url: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO users (discord_id, username, display_name, avatar_url, updated_at)
           VALUES (?, ?, ?, ?, datetime('now'))
           ON CONFLICT(discord_id) DO UPDATE SET
               username=excluded.username,
               display_name=excluded.display_name,
               avatar_url=excluded.avatar_url,
               updated_at=datetime('now')""",
        (discord_id, username, display_name, avatar_url),
    )
    await db.commit()


async def set_monitored_channel(channel_id: int, guild_id: int, channel_name: str):
    db = await get_db()
    await db.execute(
        """INSERT INTO monitored_channel (channel_id, guild_id, channel_name)
           VALUES (?, ?, ?)
           ON CONFLICT(channel_id) DO UPDATE SET
               guild_id=excluded.guild_id,
               channel_name=excluded.channel_name""",
        (channel_id, guild_id, channel_name),
    )
    await db.commit()


async def create_session(discord_id: int) -> int:
    db = await get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    cursor = await db.execute(
        "INSERT INTO sessions (discord_id, joined_at) VALUES (?, ?)",
        (discord_id, now),
    )
    await db.commit()
    return cursor.lastrowid


async def close_session(discord_id: int) -> int | None:
    db = await get_db()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    row = await db.execute_fetchall(
        "SELECT id FROM sessions WHERE discord_id = ? AND left_at IS NULL",
        (discord_id,),
    )
    if not row:
        return None

    session_id = row[0]["id"]
    await db.execute(
        """UPDATE sessions SET left_at = ?, duration_seconds = CAST(
               (julianday(?) - julianday(joined_at)) * 86400 AS INTEGER
           ) WHERE id = ?""",
        (now, now, session_id),
    )
    await db.commit()

    result = await db.execute_fetchall(
        "SELECT duration_seconds FROM sessions WHERE id = ?", (session_id,)
    )
    return result[0]["duration_seconds"] if result else None


async def get_active_sessions():
    db = await get_db()
    rows = await db.execute_fetchall(
        """SELECT s.discord_id, u.display_name, u.username, s.joined_at,
                  CAST((julianday(datetime('now')) - julianday(s.joined_at)) * 86400 AS INTEGER) as current_duration
           FROM sessions s
           JOIN users u ON u.discord_id = s.discord_id
           WHERE s.left_at IS NULL
           ORDER BY s.joined_at ASC""",
    )
    return [dict(r) for r in rows]


def _period_filter(period: str, table_alias: str = "s") -> tuple[str, list]:
    if period == "today":
        return f"DATE({table_alias}.joined_at) = DATE('now')", []
    elif period == "month":
        return f"STRFTIME('%Y-%m', {table_alias}.joined_at) = STRFTIME('%Y-%m', 'now')", []
    elif period == "all":
        return "1=1", []
    raise ValueError(f"Unknown period: {period}")


async def get_channel_stats(period: str) -> dict:
    db = await get_db()
    where, params = _period_filter(period)

    row = await db.execute_fetchall(
        f"""SELECT
               COALESCE(SUM(s.duration_seconds), 0) as total_seconds,
               COUNT(*) as total_sessions,
               COUNT(DISTINCT s.discord_id) as unique_users,
               COALESCE(AVG(s.duration_seconds), 0) as avg_session_seconds,
               COALESCE(MAX(s.duration_seconds), 0) as max_session_seconds
           FROM sessions s
           WHERE {where} AND s.left_at IS NOT NULL""",
        params,
    )
    if not row:
        return {}
    result = dict(row[0])

    peak_row = await db.execute_fetchall(
        f"""SELECT MAX(concurrent) as peak_online FROM (
               SELECT COUNT(*) as concurrent
               FROM sessions s
               WHERE {where}
               GROUP BY strftime('%Y-%m-%d %H:%M', s.joined_at)
           )""",
        params,
    )
    result["peak_online"] = dict(peak_row[0])["peak_online"] if peak_row else 0
    return result


async def get_user_stats(discord_id: int, period: str) -> dict:
    db = await get_db()
    where, params = _period_filter(period)
    params = [discord_id] + params

    row = await db.execute_fetchall(
        f"""SELECT
               COALESCE(SUM(s.duration_seconds), 0) as total_seconds,
               COUNT(*) as total_sessions,
               COALESCE(AVG(s.duration_seconds), 0) as avg_session_seconds,
               COALESCE(MAX(s.duration_seconds), 0) as max_session_seconds,
               MIN(s.joined_at) as first_joined,
               MAX(s.joined_at) as last_joined
           FROM sessions s
           WHERE s.discord_id = ? AND {where} AND s.left_at IS NOT NULL""",
        params,
    )
    return dict(row[0]) if row else {}


async def get_top_users(period: str, limit: int = 10) -> list[dict]:
    db = await get_db()
    where, params = _period_filter(period)

    rows = await db.execute_fetchall(
        f"""SELECT u.discord_id, u.display_name, u.username,
               COALESCE(SUM(s.duration_seconds), 0) as total_seconds,
               COUNT(*) as total_sessions
           FROM sessions s
           JOIN users u ON u.discord_id = s.discord_id
           WHERE {where} AND s.left_at IS NOT NULL
           GROUP BY s.discord_id
           ORDER BY total_seconds DESC
           LIMIT ?""",
        params + [limit],
    )
    return [dict(r) for r in rows]


async def get_all_users() -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT discord_id, display_name, username FROM users ORDER BY display_name"
    )
    return [dict(r) for r in rows]


async def get_user_display_name(discord_id: int) -> str:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT display_name, username FROM users WHERE discord_id = ?",
        (discord_id,),
    )
    if rows:
        return rows[0]["display_name"] or rows[0]["username"]
    return str(discord_id)


async def get_current_online_count() -> int:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT COUNT(*) as cnt FROM sessions WHERE left_at IS NULL"
    )
    return rows[0]["cnt"] if rows else 0
