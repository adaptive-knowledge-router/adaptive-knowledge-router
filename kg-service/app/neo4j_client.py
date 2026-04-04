from __future__ import annotations

import os
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

_driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


class DatabaseQueryError(RuntimeError):
    """Raised when a Neo4j query fails."""


def get_driver():
    return _driver


def verify_connection() -> None:
    try:
        _driver.verify_connectivity()
    except Neo4jError as exc:
        raise DatabaseQueryError(f"Neo4j connection failed: {exc}") from exc


def run_query(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    params = params or {}
    try:
        with _driver.session(database=DATABASE) as session:
            result = session.run(query, **params)
            return [record.data() for record in result]
    except Neo4jError as exc:
        raise DatabaseQueryError(f"Neo4j query failed: {exc}") from exc


def close_driver() -> None:
    _driver.close()
