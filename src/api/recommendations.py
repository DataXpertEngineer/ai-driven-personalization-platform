"""Hybrid retrieval: Milvus (similar users) -> Neo4j (campaigns) -> SQLite (rank by engagement)."""
import numpy as np
from pymilvus import Collection

from src.db import (
    get_collection,
    get_neo4j_client,
    get_connection,
    init_analytics_schema,
    get_campaign_engagement_ranked,
    get_cached_recommendations,
    cache_recommendations,
)
from src.utils.logger import measure_latency, log_anomaly


def _get_user_embedding(collection: Collection, user_id: str) -> list[float] | None:
    """Return mean embedding for user's messages, or None if not found."""
    collection.load()
    expr = f'user_id == "{user_id}"'
    res = collection.query(expr=expr, output_fields=["embedding"])
    if not res:
        return None
    embs = []
    for r in res:
        e = r.get("embedding")
        if e is not None:
            embs.append(e if isinstance(e, list) else list(e))
    if not embs:
        return None
    arr = np.array(embs)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)
    return arr.mean(axis=0).tolist()


def get_similar_user_ids(collection: Collection, query_embedding: list[float], top_k: int = 5) -> list[str]:
    """Return top_k user_ids by vector similarity (excluding query user if present)."""
    collection.load()
    results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"nprobe": 16}},
        limit=top_k * 3,
    )
    if not results or not results[0].ids:
        return []
    ids = results[0].ids
    id_list = [int(x) for x in ids]
    id_str = ",".join(str(x) for x in id_list)
    user_res = collection.query(expr=f"id in [{id_str}]", output_fields=["user_id"])
    user_ids = []
    seen = set()
    for r in (user_res or []):
        uid = r.get("user_id")
        if uid and uid not in seen:
            seen.add(uid)
            user_ids.append(uid)
            if len(user_ids) >= top_k:
                break
    return user_ids


def get_recommendations_for_user(user_id: str, top_campaigns: int = 5) -> list[dict]:
    """
    Retrieve top 5 most similar users (Milvus), fetch their campaigns (Neo4j),
    return results ranked by engagement frequency (analytics DB). Uses Redis cache.
    """
    cached = get_cached_recommendations(user_id)
    if cached is not None:
        return cached

    coll = get_collection()
    with measure_latency("get_user_embedding", user_id=user_id):
        query_emb = _get_user_embedding(coll, user_id)
    if not query_emb:
        log_anomaly("missing_embedding", f"No embedding for user_id={user_id}", user_id=user_id)
        return []

    with measure_latency("milvus_similar_users", user_id=user_id):
        similar_users = get_similar_user_ids(coll, query_emb, top_k=5)
    if not similar_users:
        log_anomaly("no_similar_users", f"user_id={user_id}", user_id=user_id)
        return []

    neo4j = get_neo4j_client()
    with measure_latency("neo4j_campaigns", user_id=user_id):
        campaigns = neo4j.get_campaigns_for_users(similar_users, limit=20)
    neo4j.close()

    if not campaigns:
        log_anomaly("missing_relationships", f"No campaigns for similar users, user_id={user_id}", user_id=user_id)
        return []

    campaign_ids = [c["campaign_id"] for c in campaigns]
    conn = get_connection()
    init_analytics_schema(conn)
    ranked = get_campaign_engagement_ranked(conn, campaign_ids)
    engagement_by_campaign = {c["campaign_id"]: c["engagement"] for c in campaigns}
    for cid, total in ranked:
        engagement_by_campaign[cid] = engagement_by_campaign.get(cid, 0) + total
    sorted_campaigns = sorted(
        engagement_by_campaign.items(),
        key=lambda x: -x[1],
    )[:top_campaigns]
    result = [{"campaign_id": cid, "engagement_score": score} for cid, score in sorted_campaigns]
    cache_recommendations(user_id, result)
    return result
