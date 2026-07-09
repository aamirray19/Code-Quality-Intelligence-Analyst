from functools import lru_cache

from neo4j import Driver, GraphDatabase

from app.core.config import settings


@lru_cache
def get_neo4j_driver() -> Driver:
    return GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_username, settings.neo4j_password),
    )
