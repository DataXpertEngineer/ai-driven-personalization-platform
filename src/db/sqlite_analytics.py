"""SQLite analytics DB: aggregated metrics and engagement."""
import sqlite3
from datetime import datetime
from pathlib import Path

from src.utils.config import settings


def get_connection():
    Path(settings.sqlite_path).parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(settings.sqlite_path)


def init_analytics_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS user_engagement (
            user_id TEXT NOT NULL,
            campaign_id TEXT NOT NULL,
            engagement_count INTEGER DEFAULT 1,
            last_updated TEXT,
            PRIMARY KEY (user_id, campaign_id)
        );
        CREATE INDEX IF NOT EXISTS idx_user_engagement_user ON user_engagement(user_id);
        CREATE INDEX IF NOT EXISTS idx_user_engagement_campaign ON user_engagement(campaign_id);
        CREATE TABLE IF NOT EXISTS pipeline_runs (
            run_id TEXT PRIMARY KEY,
            stage TEXT,
            record_count INTEGER,
            status TEXT,
            started_at TEXT,
            finished_at TEXT
        );
    """)
    conn.commit()


def upsert_engagement(conn, user_id: str, campaign_id: str, count_delta: int = 1):
    now = datetime.utcnow().isoformat()
    conn.execute(
        """
        INSERT INTO user_engagement (user_id, campaign_id, engagement_count, last_updated)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, campaign_id) DO UPDATE SET
            engagement_count = engagement_count + ?,
            last_updated = ?
        """,
        (user_id, campaign_id, count_delta, now, count_delta, now),
    )
    conn.commit()


def get_campaign_engagement_ranked(conn, campaign_ids: list[str]) -> list[tuple]:
    """Return (campaign_id, total_engagement) sorted by total engagement desc."""
    if not campaign_ids:
        return []
    placeholders = ",".join("?" * len(campaign_ids))
    cur = conn.execute(
        f"""
        SELECT campaign_id, SUM(engagement_count) AS total
        FROM user_engagement
        WHERE campaign_id IN ({placeholders})
        GROUP BY campaign_id
        ORDER BY total DESC
        """,
        campaign_ids,
    )
    return cur.fetchall()


def record_pipeline_run(conn, run_id: str, stage: str, record_count: int, status: str, started_at: str, finished_at: str = None):
    conn.execute(
        "INSERT OR REPLACE INTO pipeline_runs (run_id, stage, record_count, status, started_at, finished_at) VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, stage, record_count, status, started_at, finished_at),
    )
    conn.commit()


