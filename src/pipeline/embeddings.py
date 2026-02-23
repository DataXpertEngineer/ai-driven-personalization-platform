"""Generate 1024-dim embeddings with Sentence Transformers (uses torch backend)."""
from sentence_transformers import SentenceTransformer

from src.utils.config import settings
from src.utils.schemas import ConversationRecord, EnrichedRecord
from src.utils.logger import log_pipeline_stage, log_anomaly, measure_latency

_model: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer("sentence-transformers/all-roberta-large-v1")
    return _model


def _ensure_dim(embedding: list[float], target_dim: int) -> list[float]:
    """Pad or truncate to target_dim (e.g. 1024). For demo we pad with zeros if needed."""
    n = len(embedding)
    if n >= target_dim:
        return embedding[:target_dim]
    return embedding + [0.0] * (target_dim - n)


def generate_embeddings(
    records: list[ConversationRecord],
    run_id: str,
    source_file: str | None = None,
) -> list[EnrichedRecord]:
    log_pipeline_stage("embed", run_id=run_id, count=len(records))
    model = get_embedding_model()
    texts = [r.message for r in records]
    with measure_latency("embed_batch", run_id=run_id, batch_size=len(texts)):
        embeds = model.encode(texts, show_progress_bar=False).tolist()
    dim = getattr(settings, "embedding_dim", 1024)
    if dim != len(embeds[0]) if embeds else 0:
        embeds = [_ensure_dim(e, dim) for e in embeds]
    enriched = []
    for r, emb in zip(records, embeds):
        if not emb:
            log_anomaly("empty_embedding", f"message_id={getattr(r, 'message_id', '?')}", run_id=run_id)
            continue
        mid = r.message_id or str(id(r))
        enriched.append(
            EnrichedRecord(
                user_id=r.user_id,
                message=r.message,
                timestamp=r.timestamp,
                message_id=mid,
                embedding=emb,
                run_id=run_id,
                source_file=source_file,
            )
        )
    return enriched
