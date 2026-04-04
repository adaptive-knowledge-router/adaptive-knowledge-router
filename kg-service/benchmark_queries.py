from __future__ import annotations

import os
import time
from statistics import mean

from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

SAMPLE_QUERIES = [
    (
        "paper_by_id",
        "MATCH (p:Paper {paper_id: $paper_id}) RETURN p.title LIMIT 1",
        {"paper_id": "0704.0001"},
    ),
    (
        "author_to_papers",
        "MATCH (a:Author {author_name: $author_name})-[:WROTE]->(p:Paper) RETURN p.paper_id LIMIT 10",
        {"author_name": "C. Balazs"},
    ),
    (
        "category_to_papers",
        "MATCH (c:Category {category_name: $category_name})<-[:IN_CATEGORY]-(p:Paper) RETURN p.paper_id LIMIT 10",
        {"category_name": "cs.AI"},
    ),
]


def benchmark(session, query: str, params: dict, repeats: int = 5) -> float:
    durations = []
    for _ in range(repeats):
        start = time.perf_counter()
        list(session.run(query, **params))
        durations.append(time.perf_counter() - start)
    return mean(durations)



def main() -> None:
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session(database=DATABASE) as session:
        for name, query, params in SAMPLE_QUERIES:
            avg_seconds = benchmark(session, query, params)
            print(f"{name}: avg {avg_seconds:.6f} sec | params={params}")
    driver.close()


if __name__ == "__main__":
    main()
