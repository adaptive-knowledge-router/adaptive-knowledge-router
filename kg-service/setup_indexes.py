from __future__ import annotations

import os

from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

SCHEMA_QUERIES = [
    "CREATE CONSTRAINT paper_id_unique IF NOT EXISTS FOR (p:Paper) REQUIRE p.paper_id IS UNIQUE",
    "CREATE CONSTRAINT author_name_unique IF NOT EXISTS FOR (a:Author) REQUIRE a.author_name IS UNIQUE",
    "CREATE CONSTRAINT category_name_unique IF NOT EXISTS FOR (c:Category) REQUIRE c.category_name IS UNIQUE",
    "CREATE INDEX paper_title IF NOT EXISTS FOR (p:Paper) ON (p.title)",
    "CREATE INDEX paper_doi IF NOT EXISTS FOR (p:Paper) ON (p.doi)",
    "CREATE INDEX paper_submitter IF NOT EXISTS FOR (p:Paper) ON (p.submitter)",
    "CREATE INDEX paper_update_date IF NOT EXISTS FOR (p:Paper) ON (p.update_date)",
    "CREATE INDEX paper_journal_ref IF NOT EXISTS FOR (p:Paper) ON (p.journal_ref)",
]


def main() -> None:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session(database=DATABASE) as session:
        for query in SCHEMA_QUERIES:
            session.run(query)
            print(f"OK: {query}")
    driver.close()
    print("Schema setup complete.")


if __name__ == "__main__":
    main()
