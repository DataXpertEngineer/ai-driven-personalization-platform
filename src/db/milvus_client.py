"""Milvus connection and vector collection setup."""
from pymilvus import (
    connections,
    Collection,
    CollectionSchema,
    FieldSchema,
    DataType,
    utility,
)
from src.utils.config import settings
from src.utils.logger import log_anomaly


def connect_milvus():
    connections.connect(
        alias="default",
        host=settings.milvus_host,
        port=settings.milvus_port,
    )


def create_collection_if_not_exists():
    connect_milvus()
    if utility.has_collection(settings.milvus_collection):
        return Collection(settings.milvus_collection)
    dim = settings.embedding_dim
    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="message_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="user_id", dtype=DataType.VARCHAR, max_length=256),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=dim),
    ]
    schema = CollectionSchema(fields=fields, description="Conversation embeddings")
    coll = Collection(name=settings.milvus_collection, schema=schema)
    coll.create_index(field_name="embedding", index_params={"metric_type": "IP", "index_type": "IVF_FLAT", "params": {"nlist": 128}})
    return coll


def get_collection() -> Collection:
    connect_milvus()
    if not utility.has_collection(settings.milvus_collection):
        return create_collection_if_not_exists()
    coll = Collection(settings.milvus_collection)
    coll.load()
    return coll


def insert_vectors(collection: Collection, message_ids: list, user_ids: list, embeddings: list[list[float]]):
    if not embeddings or not message_ids:
        log_anomaly("empty_embeddings", "insert_vectors called with no data", message_ids_len=len(message_ids))
        return
    entities = [message_ids, user_ids, embeddings]
    collection.insert(entities)
    collection.flush()
