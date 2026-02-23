"""Orchestrated pipeline DAG: ingest -> embed -> store (MongoDB, Milvus, Neo4j, SQLite)."""
import uuid
from datetime import datetime
from pathlib import Path

from src.pipeline.ingest import ingest_file
from src.pipeline.embeddings import generate_embeddings
from src.pipeline.stores import store_mongodb, store_milvus, store_neo4j_and_sqlite, record_lineage
from src.utils.logger import log_pipeline_stage, log_anomaly, log_latency


def run_pipeline(input_path: str | Path, run_id: str | None = None) -> dict:
    run_id = run_id or str(uuid.uuid4())
    started = datetime.utcnow()
    summary = {"run_id": run_id, "stages": {}, "status": "success", "error": None}

    try:
        records = ingest_file(input_path, run_id)
        summary["stages"]["ingest"] = len(records)
        if not records:
            record_lineage(run_id, "ingest", 0, "failed", started, datetime.utcnow())
            summary["status"] = "failed"
            summary["error"] = "No valid records after ingest"
            log_anomaly("empty_ingest", "No valid records after ingest", run_id=run_id)
            return summary

        enriched = generate_embeddings(records, run_id)
        summary["stages"]["embed"] = len(enriched)
        if not enriched:
            log_anomaly("empty_embeddings", "No enriched records after embedding", run_id=run_id)
            record_lineage(run_id, "embed", 0, "failed", started, datetime.utcnow())
            summary["status"] = "failed"
            summary["error"] = "No enriched records"
            return summary

        store_mongodb(enriched, run_id)
        store_milvus(enriched, run_id)
        store_neo4j_and_sqlite(enriched, run_id)

        finished = datetime.utcnow()
        duration_sec = (finished - started).total_seconds()
        record_lineage(run_id, "full_pipeline", len(enriched), "success", started, finished)
        summary["stages"]["store"] = len(enriched)
        summary["finished_at"] = finished.isoformat()
        log_pipeline_stage("pipeline_complete", run_id=run_id, status="success", duration_seconds=round(duration_sec, 2), **summary["stages"])
        log_latency("pipeline_run", duration_sec * 1000, run_id=run_id, record_count=len(enriched))
        return summary

    except Exception as e:
        log_anomaly("pipeline_failed", str(e), run_id=run_id)
        record_lineage(run_id, "pipeline", 0, "failed", started, datetime.utcnow())
        summary["status"] = "failed"
        summary["error"] = str(e)
        duration_sec = (datetime.utcnow() - started).total_seconds()
        log_latency("pipeline_run", duration_sec * 1000, run_id=run_id)
        return summary
