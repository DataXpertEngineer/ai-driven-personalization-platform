# Scaling Plan

How to evolve this prototype to:

1. **Handle 10M+ users** (ingestion, storage, and serving).
2. **Ensure sub-100 ms vector queries** (recommendation latency).
3. **Maintain cost efficiency** in cloud environments.

---

## 1. Handle 10M+ users

### Data ingestion and pipeline

- **Orchestration:** Move to **Apache Airflow** (or similar) with scheduled and event-triggered DAGs. Use per-shard or per-user-id partitioning so ingestion and embedding jobs run in parallel.
- **Queue-first:** Ingest raw events into **Kafka** (or SQS). Pipeline workers consume, validate, embed, and write to stores. This decouples ingestion from processing and allows backpressure and replay.
- **Embedding:** Scale embedding workers horizontally (batch from queue, write to Milvus/MongoDB). Use a **GPU pool** for Sentence Transformers or switch to a **hosted embedding API** (e.g. OpenAI, Cohere) with rate limits and batching.
- **Idempotency:** Deduplicate by `(user_id, message_id)` or event id in the pipeline and in each store to support at-least-once processing.

### Storage

- **MongoDB:** Shard by `user_id`; use read replicas for serving.
- **Milvus:** Use a **Milvus cluster** with sharding by `user_id` or by embedding partition; scale query and data nodes independently.
- **Neo4j:** Scale with **causal clustering** (core + read replicas); route writes to core, reads to replicas.
- **Analytics:** Replace SQLite with **PostgreSQL** or **Snowflake/BigQuery**; batch upserts (e.g. daily/hourly) for engagement aggregates.

---

## 2. Ensure sub-100 ms vector queries

- **Milvus:**
  - Tune index (e.g. HNSW, IVF) and parameters (`nprobe`, `ef`) for latency vs recall.
  - Keep hot partitions (e.g. recent or active users) in memory; use disk-based storage for cold data.
  - Use connection pooling and enough query nodes to handle target QPS.
- **Redis:**
  - Cache full recommendation responses by `user_id` with TTL (e.g. 5–15 min).
  - Optionally cache “similar user ids” or “user embedding” to avoid repeated Milvus reads for the same user.
- **API:**
  - Serve from the same region as Milvus/Neo4j to minimize network latency.
  - Use async I/O (FastAPI already does) and parallelize Milvus + Neo4j + analytics where possible; return as soon as the slowest required call completes.
- **SLA:** Define p95/p99 targets; use a **circuit breaker** for Neo4j/analytics so partial results (e.g. from cache + Milvus only) can be returned if the graph or analytics layer is slow.

---

## 3. Maintain cost efficiency in cloud environments

- **Compute:**
  - **Serverless** for the API (e.g. Lambda, Cloud Run) to scale to zero when idle.
  - **Spot/preemptible** for batch embedding and pipeline workers where acceptable.
  - Right-size embedding workers (GPU vs CPU) based on throughput and cost.
- **Databases:**
  - **Milvus:** Use managed Milvus (e.g. Zilliz Cloud) or Kubernetes with autoscaling; scale down replicas in low-traffic windows.
  - **Neo4j:** Managed (Aura) or self-hosted with reserved instances for baseline and spot for batch.
  - **Analytics:** Use a columnar warehouse (Snowflake, BigQuery) with clustering/partitioning by date and user_id; separate compute for heavy reporting.
- **Caching:**
  - **Redis:** Managed Redis (e.g. ElastiCache) with eviction and TTL to cap memory; consider a second tier (e.g. local cache in the API) to reduce Redis traffic and cost.
- **Embeddings:**
  - Evaluate **hosted embedding APIs** vs self-hosted Sentence Transformers (GPU and ops cost vs per-token API cost).
- **Observability:**
  - Use centralized logging and metrics (e.g. Grafana + Prometheus or cloud-native) with retention and sampling to control cost.

---

## Summary table

| Concern        | Prototype              | At scale (10M+ users, sub-100 ms, cost-aware)   |
|----------------|------------------------|-------------------------------------------------|
| Orchestration  | Custom Python DAG      | Airflow (or similar) + Kafka/SQS               |
| Vector DB      | Milvus standalone      | Milvus cluster / Zilliz Cloud, tuned index     |
| Graph          | Neo4j single           | Neo4j causal cluster, read replicas            |
| Analytics      | SQLite                 | PostgreSQL or Snowflake/BigQuery                |
| Cache          | Redis single           | Managed Redis, optional L2 cache               |
| Embeddings     | Sentence Transformers  | Scaled workers or hosted API                    |
| API            | Single process         | Serverless or Kubernetes, multi-replica         |

This plan keeps the same logical architecture (vector + graph + analytics + cache) while replacing components with scalable and cost-efficient alternatives.
