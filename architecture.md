# Architecture

## System diagram

The high-level architecture is in **Architecture.png**. It shows:

1. **Data sources** — JSON conversation data (`user_id`, `message`, `timestamp`).
2. **ETL/orchestration** — A single Python DAG: ingest → schema validation (Pydantic) → embedding (Sentence Transformer 1024-dim) → write to all stores.
3. **Stores** — MongoDB (raw documents), Milvus (vectors + metadata), Neo4j (User–Campaign–Intent graph), SQLite (engagement + pipeline lineage).
4. **Caching** — Redis for recommendation responses (and optional session cache).
5. **Serving** — FastAPI `GET /recommendations/<user_id>`: Redis → Milvus (similar users) → Neo4j (campaigns) → SQLite (rank by engagement) → cache and return.

### Data flows

| Flow       | Type        | Path                                   | Use case           |
|-----------|-------------|----------------------------------------|--------------------|
| Ingestion | Batch       | JSON → validate → embed → all stores   | ETL pipeline run   |
| Query     | Real-time   | API → Redis or Milvus → Neo4j → SQLite | Recommendations    |

---

## Justification of trade-offs

### Milvus vs FAISS

- **Choice:** Milvus for vector search.
- **Why:** Milvus is built for production: persistent storage, distributed deployment, and standard APIs. FAISS is better for single-node, in-memory demos and research; for a multi-database prototype that can scale, Milvus keeps the path to a cluster (or Zilliz Cloud) straightforward.

### SQLite for analytics (engagement + lineage)

- **Choice:** SQLite for `user_engagement` and `pipeline_runs`.
- **Why:** No extra process or network; one file per environment; good enough for prototype volume. At scale, the same schema and query patterns move to PostgreSQL or a cloud warehouse (see scaling_plan.md) without changing the application’s logical model.

### Custom Python DAG vs Airflow

- **Choice:** A small Python DAG in the repo (ingest → embed → store) instead of Airflow.
- **Why:** The repo stays runnable with a single `run_pipeline()` call and minimal setup. The same steps (ingest, embed, store) can be wrapped as Airflow tasks later for scheduling, retries, and monitoring without changing the core logic.

### Embedding model (1024-dim RoBERTa)

- **Choice:** `sentence-transformers/all-roberta-large-v1` (1024 dimensions).
- **Why:** Good quality for semantic similarity; dimension is configurable. Smaller models (e.g. 384/768 dim) can be swapped in and the schema (e.g. Milvus/SQLite) adjusted for cost or speed; the pipeline stays the same.

### Redis for recommendations only

- **Choice:** Redis used only to cache recommendation responses (keyed by `user_id`), not for pipeline or session storage.
- **Why:** Cuts repeated work across Milvus, Neo4j, and SQLite and helps keep recommendation latency low (especially on cache hit). Session or other caches can be added later if needed.

### Streamlit over SQLite for observability

- **Choice:** Streamlit dashboard that reads pipeline runs and engagement from SQLite (no Prometheus/Grafana in this prototype).
- **Why:** Single stack (Python + SQLite), no extra metrics server; enough for runs, latency, anomalies, and engagement. At scale, this can be replaced or supplemented by centralized logging and metrics.

---

## Fault tolerance and observability

- **Pipeline:** Lineage is written to SQLite (`pipeline_runs`) for each run (stage, record_count, status, timestamps). Failed runs and empty stages are logged; status and latency are available for the dashboard.
- **Observability:** Streamlit shows pipeline runs, latency, anomalies, and engagement from SQLite. Anomalies (e.g. failed runs, empty embeddings) are derived from `get_pipeline_run_summary` and `detect_anomalies`.
- **Retries:** The pipeline is idempotent per run; re-running with the same or new data does not require special cleanup.
