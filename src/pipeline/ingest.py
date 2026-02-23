"""Ingest conversation data from JSON with schema validation."""
import json
import uuid
from pathlib import Path
from datetime import datetime

from src.utils.schemas import ConversationRecord
from src.utils.logger import log_pipeline_stage, log_anomaly


def _parse_timestamp(ts) -> datetime:
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return datetime.utcnow()
    return datetime.utcnow()


def ingest_file(path: str | Path, run_id: str) -> list[ConversationRecord]:
    path = Path(path)
    if path.suffix.lower() != ".json":
        raise ValueError("Only JSON input is supported")
    log_pipeline_stage("ingest", run_id=run_id, source=str(path))
    records = []
    with open(path) as f:
        data = json.load(f)
    items = data if isinstance(data, list) else data.get("conversations", [data])
    for item in items:
        try:
            item["timestamp"] = _parse_timestamp(item.get("timestamp", datetime.utcnow()))
            item.setdefault("message_id", str(uuid.uuid4()))
            records.append(ConversationRecord(**item))
        except Exception as e:
            log_anomaly("schema_validation", str(e), raw=item)
    if not records:
        log_anomaly("empty_ingest", f"No valid records from {path}", run_id=run_id)
    return records
