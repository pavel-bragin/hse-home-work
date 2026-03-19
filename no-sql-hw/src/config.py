from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/?directConnection=false")
    database_name: str = os.getenv("MONGO_DB", "university")
    collection_name: str = os.getenv("MONGO_COLLECTION", "students")


def get_settings() -> Settings:
    return Settings()
