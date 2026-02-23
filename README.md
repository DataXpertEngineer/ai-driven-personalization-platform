# AI-Driven Personalization Platform

Mini data platform: **vector** (Milvus), **graph** (Neo4j), **analytics** (SQLite), **Redis** cache. Observability via **Streamlit** (pipeline runs, anomalies, engagement).

**System overview:** [Architecture.png](Architecture.png)

---

## 1. Setup

### 1.1 Dependencies

Install using **pip** or **uv**. Core dependencies:

| Purpose        | Package |
|----------------|---------|
| Config & schema| `pydantic`, `pydantic-settings`, `python-dotenv` |
| Embeddings     | `sentence-transformers`, `torch` |
| Stores         | `pymongo`, `pymilvus`, `neo4j`, `redis` |
| API            | `fastapi`, `uvicorn[standard]` |
| Logging        | `structlog` |
| Dashboard      | `streamlit` |

### 1.2 Python environment

**Option A — pip (requirements.txt):**

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Option B — uv (pyproject.toml):**

```bash
uv sync
```

### 1.3 Services (optional, for full stack)

Start MongoDB, Milvus, Neo4j, Redis, API, and Streamlit via Docker:

```bash
docker-compose up -d
```

This exposes: **API** on 8000, **Streamlit** on 8501. For local runs without Docker, ensure MongoDB, Milvus, Neo4j, and Redis are available (or run them via Docker and only run pipeline/API on the host).

### 1.4 Environment

Create a `.env` in the project root to override defaults. Main variables: `MONGODB_URI`, `MILVUS_HOST`, `MILVUS_PORT`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`, `REDIS_URL`, `SQLITE_PATH`. See `src/utils/config.py` for all options.

---

## 2. How to execute

### 2.0 Quick run & test (recommended order)

Run them in order. The pipeline and API need MongoDB, Milvus, Neo4j, and Redis; the easiest way is Docker.

**Option A — All in Docker (API and Streamlit run in containers):**

```bash
# 1. Start all services (MongoDB, Milvus, Neo4j, Redis, API, Streamlit)
docker-compose up -d

# 2. Wait ~30–60s for services to be healthy, then run the pipeline from the host (ingest → embed → store)
uv run python -c "from src.pipeline import run_pipeline; run_pipeline('data/sample_conversations.json')"
```

Then verify: `curl -s http://localhost:8000/health` → `{"status":"ok"}`. Test recommendations: `curl -s "http://localhost:8000/recommendations/user_1?top=5"`. Open the dashboard: http://localhost:8501.

**Option B — Backing services in Docker, API and Streamlit on host:**

```bash
# 1. Start backing services only (MongoDB, Milvus, Neo4j, Redis)
docker-compose up -d

# 2. Wait ~30–60s, then run the pipeline
uv run python -c "from src.pipeline import run_pipeline; run_pipeline('data/sample_conversations.json')"

# 3. Start the API (leave running in one terminal)
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

In **another terminal**, test the API and start the dashboard:

```bash
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/recommendations/user_1?top=5"
uv run python -m streamlit run src/streamlit_app.py --server.port 8501
# or --server.port 8502 if 8501 is in use; then open http://localhost:8502
```

To see what is using port 8501: `lsof -i :8501`. To stop it: `kill <PID>`.

### 2.1 Run the pipeline (ingest → embed → store)

From the **project root** (so `src` is importable):

```bash
uv run python -c "from src.pipeline import run_pipeline; run_pipeline('data/sample_conversations.json')"
```

With pip (after activating the venv):

```bash
python -c "from src.pipeline import run_pipeline; run_pipeline('data/sample_conversations.json')"
```

Input: a JSON file containing conversation records (list of objects with `user_id`, `message`, `timestamp`; optional `message_id`). Output: summary dict with `run_id`, `status`, `stages`, and optional `error`.

### 2.2 Run the API

```bash
uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

- **Health:** `GET /health` → `{"status":"ok"}`
- **Recommendations:** `GET /recommendations/<user_id>?top=5` → `{"user_id":"...", "recommendations":[...]}`

### 2.3 Run the Streamlit dashboard

```bash
uv run python -m streamlit run src/streamlit_app.py --server.port 8501
```

Open http://localhost:8501 for pipeline runs, latency, anomalies, and engagement (reads from SQLite). Run evidences and example dashboard screens (pipeline latency, recent runs, anomalies, user engagement) are in [docs/screenshots/](docs/screenshots/).

### 2.4 Understanding the Streamlit dashboard

The dashboard reads from the SQLite analytics DB (`pipeline_runs`, `user_engagement`). Each part means:

| Section | What it signifies |
|--------|--------------------|
| **Pipeline latency** | Bar chart of **end-to-end duration (seconds)** of each pipeline run. Helps spot slow runs (e.g. one run ~280 s vs others &lt;50 s). |
| **Recent pipeline runs** | Table of recent runs: `run_id`, `stage`, `record_count`, `status`, `started_at`, `finished_at`, `latency_seconds`. Use it to see success/failure and how many records were processed. |
| **Anomalies** | Issues derived from pipeline runs: **failed runs** (status=failed), **empty embeddings** (embed/full_pipeline with 0 records), **zero records on success** (success but 0 records). These are computed from `pipeline_runs` in SQLite. |
| **User engagement (top campaigns)** | Total engagement per campaign from `user_engagement` (SQLite). Shows which campaigns get the most engagement for prioritization. |

**Not on the dashboard (application logs only):** API response time and recommendation-level anomalies (e.g. missing embeddings for a user, no similar users, missing relationships) are logged via `log_anomaly` in the API and pipeline to **structlog**; they are not stored in SQLite or shown in Streamlit. To add them you would record API latency and those anomaly types in SQLite and extend the dashboard.

---

## 3. Design choices

- **Custom Python DAG** — Lightweight, single-run pipeline without Airflow; same steps can be moved into Airflow later for scheduling and retries.
- **1024-dim embeddings** — `sentence-transformers/all-roberta-large-v1` for quality; configurable via `embedding_dim`; smaller models can be used and dimension padded if needed.
- **Neo4j** — Explicit User–Campaign–Intent graph; in the prototype, campaign and intent are derived from messages (e.g. campaign from user hash, intent from first token).
- **SQLite for analytics** — Single-file, no extra service for the prototype; lineage (`pipeline_runs`) and engagement (`user_engagement`) in one place. Scaling plan describes moving to PostgreSQL or a cloud warehouse.
- **Redis** — TTL cache for recommendation responses to keep latency low and avoid repeated Milvus/Neo4j/SQLite calls for the same user.
- **Streamlit** — Simple dashboard over SQLite for runs, anomalies, and engagement; no separate metrics backend.

---

## 4. Project layout

```
├── src/
│   ├── pipeline/    # ETL / orchestration (ingest, embed, store)
│   ├── api/         # FastAPI (recommendations, health)
│   ├── db/           # DB setup & clients (MongoDB, Milvus, Neo4j, SQLite, Redis)
│   └── utils/        # Helpers, config, logging, schemas, observability
├── data/             # Sample datasets (e.g. sample_conversations.json)
├── docs/screenshots/ # Run evidences: pipeline latency, recent runs, anomalies, engagement
├── docker-compose.yml
├── README.md
├── Architecture.png  # System diagram
├── architecture.md
└── scaling_plan.md
```

See **architecture.md** for the system diagram and trade-offs, and **scaling_plan.md** for evolving to 10M+ users, sub-100 ms queries, and cost-efficient cloud deployment.
