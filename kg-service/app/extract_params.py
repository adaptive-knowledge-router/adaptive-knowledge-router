from __future__ import annotations

import re
from typing import Any

KNOWN_CATEGORIES = {
    "cs.AI",
    "cs.LG",
    "cs.CL",
    "cs.CV",
    "cs.NE",
    "cs.IR",
    "cs.RO",
    "stat.ML",
}

PAPER_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}\b")
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
DOUBLE_QUOTE_TITLE_PATTERN = re.compile(r'"([^"]+)"')
SINGLE_QUOTE_TITLE_PATTERN = re.compile(r"'([^']+)'")

SUBMITTER_PATTERN = re.compile(r"\bsubmitter\s*[:=]?\s*([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE)
JOURNAL_REF_PATTERN = re.compile(r"\bjournal(?:\s+ref(?:erence)?)?\s*[:=]?\s*([A-Za-z0-9 .,:;()\-_/]+)", re.IGNORECASE)
COMMENTS_PATTERN = re.compile(r"\bcomments?\s*(?:contains|about|with)?\s*[:=]?\s*([A-Za-z0-9 .,'()\-_/]+)", re.IGNORECASE)

COUNT_PATTERNS = [
    re.compile(r"\bhow many\b", re.IGNORECASE),
    re.compile(r"\bnumber of\b", re.IGNORECASE),
    re.compile(r"\bcount of\b", re.IGNORECASE),
    re.compile(r"\btotal number\b", re.IGNORECASE),
]

AUTHOR_PATTERNS = [
    re.compile(r"\bwritten by\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bauthored by\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bby\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bhas\s+([A-Za-z0-9 .,'()&\-]+)\s+written\b", re.IGNORECASE),
    re.compile(r"\bhas\s+([A-Za-z0-9 .,'()&\-]+)\s+published\b", re.IGNORECASE),
    re.compile(r"\bwhat categories has\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bwhich categories has\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bwhat fields has\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bwhich fields has\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bcategories written by\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bfields published by\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\brelated authors to\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bsimilar authors to\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bauthors are related to\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bwhich authors are related to\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bauthors related to\s+([A-Za-z0-9 .,'()&\-]+)", re.IGNORECASE),
    re.compile(r"\bas\s+([A-Za-z0-9 .,'()&\-]+)['’]s\s+papers\b", re.IGNORECASE),
]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().strip(",").strip("?").strip()
    return value or None


def _strip_known_suffixes(value: str) -> str:
    lowered = value.lower()
    stop_markers = [
        " with doi",
        " without doi",
        " no doi",
        " with journal",
        " without journal",
        " no journal",
        " in category",
        " in the category",
        " in cs.",
        " category",
        " comments",
        " submitter",
        "'s papers",
        "’s papers",
        " papers",
        " through shared research areas",
        " through shared categories",
        " through shared research areas?",
        " through shared categories?",
    ]
    for marker in stop_markers:
        idx = lowered.find(marker)
        if idx != -1:
            value = value[:idx]
            lowered = value.lower()

    for category in KNOWN_CATEGORIES:
        value = value.replace(category, "")

    return value.strip(" ,")


def extract_paper_id(query: str) -> str | None:
    match = PAPER_ID_PATTERN.search(query)
    return match.group(0) if match else None


def extract_doi(query: str) -> str | None:
    match = DOI_PATTERN.search(query)
    return match.group(0) if match else None


def extract_title(query: str) -> str | None:
    match = DOUBLE_QUOTE_TITLE_PATTERN.search(query)
    if match:
        return _clean(match.group(1))

    match = SINGLE_QUOTE_TITLE_PATTERN.search(query)
    if match:
        return _clean(match.group(1))

    return None


def extract_category(query: str) -> str | None:
    lowered = query.lower()
    for category in sorted(KNOWN_CATEGORIES):
        if category.lower() in lowered:
            return category
    return None


def extract_categories(query: str) -> list[str]:
    lowered = query.lower()
    return [category for category in sorted(KNOWN_CATEGORIES) if category.lower() in lowered]


def extract_author(query: str) -> str | None:
    for pattern in AUTHOR_PATTERNS:
        match = pattern.search(query)
        if match:
            value = _strip_known_suffixes(match.group(1))
            return _clean(value)

    possessive_match = re.search(
        r"\b([A-Z][A-Za-z.\-']+(?:\s+[A-Z][A-Za-z.\-']+)*)['’]s\s+papers\b",
        query,
    )
    if possessive_match:
        value = _strip_known_suffixes(possessive_match.group(1))
        return _clean(value)

    return None


def extract_submitter(query: str) -> str | None:
    match = SUBMITTER_PATTERN.search(query)
    return _clean(match.group(1)) if match else None


def extract_journal_ref(query: str) -> str | None:
    match = JOURNAL_REF_PATTERN.search(query)
    return _clean(match.group(1)) if match else None


def extract_comments_contains(query: str) -> str | None:
    match = COMMENTS_PATTERN.search(query)
    return _clean(match.group(1)) if match else None


def extract_logic(query: str) -> str | None:
    lowered = query.lower()
    if any(token in lowered for token in ["all categories", "both categories", "must include all", " and "]):
        return "and"
    if any(token in lowered for token in ["any category", "either category", " or "]):
        return "or"
    return None


def extract_has_doi(query: str) -> bool | None:
    lowered = query.lower()
    if any(token in lowered for token in ["with doi", "has doi", "having doi"]):
        return True
    if any(token in lowered for token in ["without doi", "no doi"]):
        return False
    return None


def extract_has_journal_ref(query: str) -> bool | None:
    lowered = query.lower()
    if any(token in lowered for token in ["with journal ref", "with journal reference", "has journal ref", "has journal reference"]):
        return True
    if any(token in lowered for token in ["without journal ref", "without journal reference", "no journal ref", "no journal reference"]):
        return False
    return None


def extract_hops(query: str) -> int | None:
    lowered = query.lower()
    if "4 hop" in lowered or "4-hop" in lowered:
        return 4
    if "3 hop" in lowered or "3-hop" in lowered:
        return 3
    if "2 hop" in lowered or "2-hop" in lowered:
        return 2
    return None


def is_count_query(query: str) -> bool:
    return any(pattern.search(query) for pattern in COUNT_PATTERNS)


def infer_mode(query: str) -> str | None:
    lowered = query.lower()

    # -------- MOST SPECIFIC MULTI-HOP FIRST --------

    # multi-hop 2
    if any(p in lowered for p in [
        "papers by same author",
        "other papers by same author",
        "same author as paper",
        "same author as",
        "written by the same author as paper",
        "written by the same author as",
        "which papers are written by the same author as paper",
        "which papers are by the same author as paper",
    ]):
        return "paper_to_other_papers_by_same_authors"

    if any(p in lowered for p in [
        "author to categories",
        "categories written by",
        "categories by",
        "what categories has",
        "which categories has",
        "what fields has",
        "which fields has",
        "published in",
    ]):
        return "author_to_categories"

    if any(p in lowered for p in [
        "category to authors",
        "authors in category",
        "authors in the category",
        "which authors are in",
        "who are the authors in",
        "which authors have written papers in",
        "who are the authors working in",
    ]):
        return "category_to_authors"

    # multi-hop 3
    if any(p in lowered for p in [
        "same category papers",
        "papers in the same categories as",
        "papers are in the same categories as",
        "same categories as",
        "same research areas as",
    ]):
        return "author_to_same_category_papers"

    if any(p in lowered for p in [
        "papers by authors in",
        "papers written by authors in",
    ]):
        return "category_to_papers_by_authors"

    if any(p in lowered for p in [
        "authors in same categories",
        "authors connected to the same categories as paper",
    ]):
        return "paper_to_authors_in_same_categories"

    # multi-hop 4
    if any(p in lowered for p in [
        "related authors",
        "similar authors",
        "authors related to",
        "authors are related to",
        "which authors are related to",
    ]):
        return "author_to_related_authors_via_shared_categories"

    if any(p in lowered for p in [
        "related categories",
        "connected categories",
        "research areas are connected to",
        "categories are related to",
        "what categories are related to",
    ]):
        return "category_to_related_categories_via_authors"

    if any(p in lowered for p in [
        "related papers",
        "papers related to paper",
        "papers are related to",
        "which papers are related to paper",
    ]):
        return "paper_to_related_papers_via_authors_and_categories"

    # -------- RELATION FILTER AFTER SPECIFIC MULTI-HOP --------

    if any(p in lowered for p in [
        "authors of paper",
        "paper to authors",
        "who wrote paper",
        "who are the authors of",
        "author of paper",
    ]):
        return "paper_to_authors"

    if any(p in lowered for p in [
        "categories of paper",
        "paper to categories",
        "which categories does paper",
        "what categories does paper",
        "belong to",
        "belongs to",
    ]):
        return "paper_to_categories"

    if any(p in lowered for p in [
        "author to papers",
        "papers by author",
        "papers by ",
        "written by",
        "authored by",
        "papers written by",
        "papers are written by",
        "which papers are written by",
        "what papers are written by",
    ]):
        return "author_to_papers"

    if any(p in lowered for p in [
        "category to papers",
        "papers in category",
        "papers in the category",
        "what papers are in",
        "which papers are in",
        "papers under category",
    ]):
        return "category_to_papers"

    if ("papers in" in lowered and " and " in lowered) or any(p in lowered for p in [
        "papers in both",
        "papers in either",
    ]):
        return "papers_in_categories"

    return None


def extract_all(query: str) -> dict[str, Any]:
    categories = extract_categories(query)
    return {
        "paper_id": extract_paper_id(query),
        "title": extract_title(query),
        "doi": extract_doi(query),
        "author_name": extract_author(query),
        "category_name": extract_category(query),
        "category_names": categories or None,
        "journal_ref": extract_journal_ref(query),
        "submitter": extract_submitter(query),
        "comments_contains": extract_comments_contains(query),
        "logic": extract_logic(query),
        "has_doi": extract_has_doi(query),
        "has_journal_ref": extract_has_journal_ref(query),
        "hops": extract_hops(query),
        "mode": infer_mode(query),
        "is_count_query": is_count_query(query),
    }