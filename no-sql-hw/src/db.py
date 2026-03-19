from pymongo import MongoClient

from src.config import get_settings


def get_client() -> MongoClient:
    settings = get_settings()
    return MongoClient(settings.mongo_uri, appname="university-cli")


def get_collection():
    settings = get_settings()
    client = get_client()
    database = client[settings.database_name]
    collection = database[settings.collection_name]
    ensure_indexes(collection)
    return collection


def ensure_indexes(collection) -> None:
    collection.create_index([("faculty", 1), ("program", 1)])
    collection.create_index([("group_number", 1)])
    collection.create_index([("updated_at", -1)])
