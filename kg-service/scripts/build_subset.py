import json
from pathlib import Path

RAW_PATH = Path("kg_service/data/raw/arxiv-metadata-oai-snapshot.json")
OUTPUT_PATH = Path("kg_service/data/processed/arxiv_subset.jsonl")

TARGET_CATEGORIES = {"cs.AI", "cs.LG", "cs.CL"}
MAX_PAPERS = 20000


def has_target_category(category_string: str) -> bool:
    categories = set(category_string.split())
    return len(categories.intersection(TARGET_CATEGORIES)) > 0


def clean_text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def main():
    if not RAW_PATH.exists():
        print(f"Raw dataset not found: {RAW_PATH}")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    scanned = 0
    kept = 0
    skipped_missing_id = 0
    skipped_missing_title = 0

    with RAW_PATH.open("r", encoding="utf-8") as infile, OUTPUT_PATH.open("w", encoding="utf-8") as outfile:
        for line in infile:
            scanned += 1

            try:
                paper = json.loads(line)
            except json.JSONDecodeError:
                continue

            categories = clean_text(paper.get("categories"))
            if not categories or not has_target_category(categories):
                continue

            paper_id = clean_text(paper.get("id"))
            title = clean_text(paper.get("title"))

            if not paper_id:
                skipped_missing_id += 1
                continue

            if not title:
                skipped_missing_title += 1
                continue

            record = {
                "id": paper_id,
                "submitter": clean_text(paper.get("submitter")),
                "authors": clean_text(paper.get("authors")),
                "title": title,
                "comments": clean_text(paper.get("comments")),
                "journal_ref": clean_text(paper.get("journal-ref")),
                "doi": clean_text(paper.get("doi")),
                "report_no": clean_text(paper.get("report-no")),
                "categories": categories,
                "license": clean_text(paper.get("license")),
                "abstract": clean_text(paper.get("abstract")),
                "versions": paper.get("versions", []),
                "update_date": clean_text(paper.get("update_date")),
                "authors_parsed": paper.get("authors_parsed", []),
            }

            outfile.write(json.dumps(record, ensure_ascii=False) + "\n")
            kept += 1

            if kept >= MAX_PAPERS:
                break

    print(f"Scanned papers: {scanned}")
    print(f"Kept papers: {kept}")
    print(f"Skipped missing id: {skipped_missing_id}")
    print(f"Skipped missing title: {skipped_missing_title}")
    print(f"Saved subset to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()