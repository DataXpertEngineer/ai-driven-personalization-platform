"""Observability: pipeline run summary, latency, and anomaly detection from SQLite lineage."""
from datetime import datetime

from src.db import get_connection, init_analytics_schema
from src.utils.logger import logger


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def get_pipeline_run_summary(limit: int = 20) -> list[dict]:
    """Recent pipeline runs with latency_seconds computed from started_at/finished_at."""
    conn = get_connection()
    init_analytics_schema(conn)
    cur = conn.execute(
        "SELECT run_id, stage, record_count, status, started_at, finished_at FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
        (limit,),
    )
    out = []
    for r in cur.fetchall():
        run_id, stage, record_count, status, started_at, finished_at = r
        latency_seconds = None
        if started_at and finished_at:
            start, end = _parse_ts(started_at), _parse_ts(finished_at)
            if start and end:
                latency_seconds = round((end - start).total_seconds(), 2)
        out.append({
            "run_id": run_id,
            "stage": stage,
            "record_count": record_count or 0,
            "status": status,
            "started_at": started_at,
            "finished_at": finished_at,
            "latency_seconds": latency_seconds,
        })
    return out


def detect_anomalies(run_summary: list[dict]) -> list[dict]:
    """Detect anomalies: failed runs, empty embeddings, zero records on success."""
    anomalies = []
    for run in run_summary:
        if run["status"] == "failed":
            anomalies.append({"type": "failed_run", "run_id": run["run_id"], "stage": run["stage"]})
        if run.get("record_count") == 0 and run["stage"] in ("embed", "full_pipeline"):
            anomalies.append({"type": "empty_embeddings", "run_id": run["run_id"]})
        if run["status"] == "success" and run.get("record_count") == 0:
            anomalies.append({"type": "zero_records_success", "run_id": run["run_id"], "stage": run["stage"]})
    return anomalies


def log_pipeline_metrics() -> dict:
    """Log pipeline status and latency from lineage; report anomalies."""
    summary = get_pipeline_run_summary(limit=10)
    anomalies = detect_anomalies(summary)
    for run in summary:
        logger.info(
            "pipeline_run",
            run_id=run["run_id"],
            stage=run["stage"],
            record_count=run["record_count"],
            status=run["status"],
            latency_seconds=run.get("latency_seconds"),
            started_at=run["started_at"],
            finished_at=run["finished_at"],
        )
    if latencies := [r["latency_seconds"] for r in summary if r.get("latency_seconds") is not None]:
        logger.info("pipeline_latency", avg_seconds=round(sum(latencies) / len(latencies), 2), max_seconds=round(max(latencies), 2), run_count=len(latencies))
    logger.info("observability_summary", runs=len(summary), anomalies=len(anomalies), anomaly_list=anomalies)
    return {"runs": summary, "anomalies": anomalies}
