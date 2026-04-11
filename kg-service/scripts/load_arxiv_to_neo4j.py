import json
import os
from pathlib import Path
from neo4j import GraphDatabase

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "password")

DATA_PATH = Path(os.getenv("DATA_PATH", "data/processed/arxiv_subset.jsonl"))

driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))


def clean_text(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def parse_authors(authors_str: str) -> list[str]:
    if not authors_str:
        return []
    return [author.strip() for author in authors_str.split(",") if author.strip()]


def parse_categories(categories_str: str) -> list[str]:
    if not categories_str:
        return []
    return [category.strip() for category in categories_str.split() if category.strip()]


def insert_paper(tx, paper: dict) -> None:
    versions = paper.get("versions", [])
    authors_parsed = paper.get("authors_parsed", [])

    tx.run(
        """
        MERGE (p:Paper {paper_id: $paper_id})
        SET p.submitter = $submitter,
            p.authors = $authors,
            p.title = $title,
            p.comments = $comments,
            p.journal_ref = $journal_ref,
            p.doi = $doi,
            p.report_no = $report_no,
            p.categories_raw = $categories_raw,
            p.license = $license,
            p.abstract = $abstract,
            p.update_date = $update_date,
            p.versions_json = $versions_json,
            p.version_count = $version_count,
            p.authors_parsed_json = $authors_parsed_json
        """,
        paper_id=paper["id"],
        submitter=clean_text(paper.get("submitter")),
        authors=clean_text(paper.get("authors")),
        title=clean_text(paper.get("title")),
        comments=clean_text(paper.get("comments")),
        journal_ref=clean_text(paper.get("journal_ref")),
        doi=clean_text(paper.get("doi")),
        report_no=clean_text(paper.get("report_no")),
        categories_raw=clean_text(paper.get("categories")),
        license=clean_text(paper.get("license")),
        abstract=clean_text(paper.get("abstract")),
        update_date=clean_text(paper.get("update_date")),
        versions_json=json.dumps(versions, ensure_ascii=False),
        version_count=len(versions),
        authors_parsed_json=json.dumps(authors_parsed, ensure_ascii=False),
    )


def insert_author_relationship(tx, author_name: str, paper_id: str) -> None:
    tx.run(
        """
        MERGE (a:Author {author_name: $author_name})
        WITH a
        MATCH (p:Paper {paper_id: $paper_id})
        MERGE (a)-[:WROTE]->(p)
        """,
        author_name=author_name,
        paper_id=paper_id,
    )


def insert_category_relationship(tx, category_name: str, paper_id: str) -> None:
    tx.run(
        """
        MERGE (c:Category {category_name: $category_name})
        WITH c
        MATCH (p:Paper {paper_id: $paper_id})
        MERGE (p)-[:IN_CATEGORY]->(c)
        """,
        category_name=category_name,
        paper_id=paper_id,
    )


def main() -> None:
    if not DATA_PATH.exists():
        print(f"Subset file not found: {DATA_PATH}")
        return

    processed = 0

    with driver.session() as session:
        with DATA_PATH.open("r", encoding="utf-8") as infile:
            for line in infile:
                paper = json.loads(line)

                session.execute_write(insert_paper, paper)

                for author in parse_authors(clean_text(paper.get("authors"))):
                    session.execute_write(insert_author_relationship, author, paper["id"])

                for category in parse_categories(clean_text(paper.get("categories"))):
                    session.execute_write(insert_category_relationship, category, paper["id"])

                processed += 1
                if processed % 100 == 0:
                    print(f"Processed {processed} papers")

    driver.close()
    print("Done loading data into Neo4j")


if __name__ == "__main__":
    main()