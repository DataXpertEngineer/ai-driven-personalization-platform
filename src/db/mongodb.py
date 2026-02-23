"""MongoDB connection and document storage."""
from pymongo import MongoClient
from src.utils.config import settings


def get_mongo_client() -> MongoClient:
    return MongoClient(settings.mongodb_uri)


def get_conversations_collection():
    client = get_mongo_client()
    return client[settings.mongodb_db]["conversations"]


def ensure_indexes(collection):
    collection.create_index("user_id")
    collection.create_index("timestamp")
    collection.create_index("message_id", unique=True)
