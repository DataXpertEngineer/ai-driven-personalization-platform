"""Write enriched data to MongoDB, Milvus, Neo4j, SQLite."""
from datetime import datetime

from src.db import (
    get_conversations_collection,
    ensure_indexes,
    get_collection,
    insert_vectors,
    get_neo4j_client,
    get_connection,
    init_analytics_schema,
    upsert_engagement,
    record_pipeline_run,
)
from src.utils.schemas import EnrichedRecord
from src.utils.logger import log_pipeline_stage, log_anomaly, measure_latency


def store_mongodb(records: list[EnrichedRecord], run_id: str) -> None:
    coll = get_conversations_collection()
    ensure_indexes(coll)
    docs = [
        {
            "message_id": r.message_id,
            "user_id": r.user_id,
            "message": r.message,
            "timestamp": r.timestamp.isoformat(),
            "run_id": r.run_id,
            "source_file": r.source_file,
        }
        for r in records
    ]
    with measure_latency("store_mongodb", run_id=run_id, count=len(docs)):
        if docs:
            coll.insert_many(docs)
    log_pipeline_stage("store_mongodb", run_id=run_id, count=len(docs))


def store_milvus(records: list[EnrichedRecord], run_id: str) -> None:
    if not records:
        log_anomaly("empty_milvus", "No records to insert", run_id=run_id)
        return
    coll = get_collection()
    message_ids = [r.message_id for r in records]
    user_ids = [r.user_id for r in records]
    embeddings = [r.embedding for r in records]
    with measure_latency("store_milvus", run_id=run_id, count=len(embeddings)):
        insert_vectors(coll, message_ids, user_ids, embeddings)
    log_pipeline_stage("store_milvus", run_id=run_id, count=len(embeddings))


def store_neo4j_and_sqlite(records: list[EnrichedRecord], run_id: str) -> None:
    """Derive user–campaign–intent from records and write to Neo4j + SQLite."""
    neo4j = get_neo4j_client()
    neo4j.ensure_constraints()
    conn = get_connection()
    init_analytics_schema(conn)
    with measure_latency("store_neo4j_sqlite", run_id=run_id):
        for r in records:
            campaign_id = f"campaign_{hash(r.user_id) % 5}"
            intent = (r.message.split() or ["general"])[0].lower()[:50]
            neo4j.upsert_user_campaign_intent(r.user_id, campaign_id, intent, engagement_count=1)
            upsert_engagement(conn, r.user_id, campaign_id, 1)
    log_pipeline_stage("store_neo4j_sqlite", run_id=run_id, count=len(records))
    neo4j.close()


def record_lineage(run_id: str, stage: str, record_count: int, status: str, started_at: datetime, finished_at: datetime | None = None) -> None:
    """Basic data lineage: persist run_id, stage, record_count, status, timestamps to pipeline_runs."""
    conn = get_connection()
    init_analytics_schema(conn)
    record_pipeline_run(
        conn,
        run_id=run_id,
        stage=stage,
        record_count=record_count,
        status=status,
        started_at=started_at.isoformat(),
        finished_at=finished_at.isoformat() if finished_at else None,
    )
