from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.cypher_templates import *
from app.neo4j_client import DatabaseQueryError, run_query

VALID_RELATION_FILTER_MODES = {
    "author_to_papers",
    "category_to_papers",
    "paper_to_authors",
    "paper_to_categories",
    "papers_in_categories",
}

VALID_MULTI_HOP_MODES_BY_HOPS = {
    2: {
        "author_to_categories",
        "category_to_authors",
        "paper_to_other_papers_by_same_authors",
    },
    3: {
        "author_to_same_category_papers",
        "category_to_papers_by_authors",
        "paper_to_authors_in_same_categories",
        "co_authors_in_category",
    },
    4: {
        "author_to_related_authors_via_shared_categories",
        "category_to_related_categories_via_authors",
        "paper_to_related_papers_via_authors_and_categories",
    },
}

# VALID_AGGREGATE_MODES = {
#     "papers_per_category",
#     "papers_per_author",
#     "top_categories_for_author",
#     "top_authors_in_category",
#     "papers_with_doi_count",
#     "papers_without_journal_ref_count",
# }


def _http_400(message: str) -> None:
    raise HTTPException(status_code=400, detail=message)


def _resolve_paper_id(paper_id: str | None, title: str | None) -> str | None:
    if paper_id:
        return paper_id
    if title:
        results = _safe_run(ENTITY_LOOKUP_PAPER_BY_TITLE, {"title": title})
        if results:
            return results[0].get("paper_id")
        # Fallback: try first 5 words in case title has punctuation mismatch
        words = title.split()
        if len(words) >= 5:
            short_title = " ".join(words[:5])
            results = _safe_run(ENTITY_LOOKUP_PAPER_BY_TITLE, {"title": short_title})
            if results:
                return results[0].get("paper_id")
    return None



def _safe_run(query: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    try:
        return run_query(query, params)
    except DatabaseQueryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc



def format_response(strategy: str, results: list[dict[str, Any]], query_params: dict[str, Any] | None = None, total_count: int | None = None) -> dict[str, Any]:
    response = {
        "strategy": strategy,
        "query_params": query_params or {},
        "count": len(results),
        "results": results,
    }
    if total_count is not None:
        response["total_count"] = total_count
    return response



def get_total_count(query: str, params: dict[str, Any]) -> int:
    result = _safe_run(query, params)
    if result:
        return int(result[0].get("total_count", 0))
    return 0



def entity_lookup(
    paper_id: str | None = None,
    title: str | None = None,
    doi: str | None = None,
    journal_ref: str | None = None,
    submitter: str | None = None,
    author_name: str | None = None,
    category_name: str | None = None,
    count_only: bool = False,
):
    provided = [paper_id, title, doi, journal_ref, submitter, author_name, category_name]
    if not any(provided):
        _http_400("Provide at least one lookup field: paper_id, title, doi, journal_ref, submitter, author_name, or category_name.")

    if paper_id:
        params = {"paper_id": paper_id}
        if count_only:
            total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_ID_COUNT, params)
            return format_response("entity_lookup", [], params, total_count)
        results = _safe_run(ENTITY_LOOKUP_PAPER_BY_ID, params)
        total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_ID_COUNT, params)
        return format_response("entity_lookup", results, params, total_count)

    if title:
        params = {"title": title}
        if count_only:
            total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_TITLE_COUNT, params)
            return format_response("entity_lookup", [], params, total_count)
        results = _safe_run(ENTITY_LOOKUP_PAPER_BY_TITLE, params)
        total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_TITLE_COUNT, params)
        return format_response("entity_lookup", results, params, total_count)

    if doi:
        params = {"doi": doi}
        if count_only:
            total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_DOI_COUNT, params)
            return format_response("entity_lookup", [], params, total_count)
        results = _safe_run(ENTITY_LOOKUP_PAPER_BY_DOI, params)
        total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_DOI_COUNT, params)
        return format_response("entity_lookup", results, params, total_count)

    if journal_ref:
        params = {"journal_ref": journal_ref}
        if count_only:
            total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_JOURNAL_REF_COUNT, params)
            return format_response("entity_lookup", [], params, total_count)
        results = _safe_run(ENTITY_LOOKUP_PAPER_BY_JOURNAL_REF, params)
        total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_JOURNAL_REF_COUNT, params)
        return format_response("entity_lookup", results, params, total_count)

    if submitter:
        params = {"submitter": submitter}
        if count_only:
            total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_SUBMITTER_COUNT, params)
            return format_response("entity_lookup", [], params, total_count)
        results = _safe_run(ENTITY_LOOKUP_PAPER_BY_SUBMITTER, params)
        total_count = get_total_count(ENTITY_LOOKUP_PAPER_BY_SUBMITTER_COUNT, params)
        return format_response("entity_lookup", results, params, total_count)

    if author_name:
        params = {"author_name": author_name}
        if count_only:
            total_count = get_total_count(ENTITY_LOOKUP_AUTHOR_BY_NAME_COUNT, params)
            return format_response("entity_lookup", [], params, total_count)
        results = _safe_run(ENTITY_LOOKUP_AUTHOR_BY_NAME, params)
        total_count = get_total_count(ENTITY_LOOKUP_AUTHOR_BY_NAME_COUNT, params)
        return format_response("entity_lookup", results, params, total_count)

    params = {"category_name": category_name}
    if count_only:
        total_count = get_total_count(ENTITY_LOOKUP_CATEGORY_BY_NAME_COUNT, params)
        return format_response("entity_lookup", [], params, total_count)
    results = _safe_run(ENTITY_LOOKUP_CATEGORY_BY_NAME, params)
    total_count = get_total_count(ENTITY_LOOKUP_CATEGORY_BY_NAME_COUNT, params)
    return format_response("entity_lookup", results, params, total_count)



def relation_filter(
    mode: str | None = None,
    author_name: str | None = None,
    category_name: str | None = None,
    paper_id: str | None = None,
    title: str | None = None,
    has_doi: bool | None = None,
    has_journal_ref: bool | None = None,
    submitter: str | None = None,
    comments_contains: str | None = None,
    exclude_category_name: str | None = None,
    category_names: list[str] | None = None,
    logic: str = "or",
    count_only: bool = False,
):
    if mode not in VALID_RELATION_FILTER_MODES:
        _http_400(f"Invalid relation_filter mode. Allowed modes: {sorted(VALID_RELATION_FILTER_MODES)}")
    if logic not in {"and", "or"}:
        _http_400("logic must be 'and' or 'or'")

    if mode == "author_to_papers":
        if not author_name:
            _http_400("author_to_papers requires author_name")
        params = {"author_name": author_name}
        if exclude_category_name:
            params["exclude_category_name"] = exclude_category_name
            if count_only:
                total_count = get_total_count(RELATION_FILTER_AUTHOR_TO_PAPERS_EXCLUDING_CATEGORY_COUNT, params)
                return format_response("relation_filter", [], {"mode": mode, **params}, total_count)
            results = _safe_run(RELATION_FILTER_AUTHOR_TO_PAPERS_EXCLUDING_CATEGORY, params)
            total_count = get_total_count(RELATION_FILTER_AUTHOR_TO_PAPERS_EXCLUDING_CATEGORY_COUNT, params)
            return format_response("relation_filter", results, {"mode": mode, **params}, total_count)

        if count_only:
            total_count = get_total_count(RELATION_FILTER_AUTHOR_TO_PAPERS_COUNT, params)
            return format_response("relation_filter", [], {"mode": mode, **params}, total_count)
        results = _safe_run(RELATION_FILTER_AUTHOR_TO_PAPERS, params)
        total_count = get_total_count(RELATION_FILTER_AUTHOR_TO_PAPERS_COUNT, params)
        return format_response("relation_filter", results, {"mode": mode, **params}, total_count)

    if mode == "category_to_papers":
        if not category_name:
            _http_400("category_to_papers requires category_name")
        params = {
            "category_name": category_name,
            "has_doi": has_doi,
            "has_journal_ref": has_journal_ref,
            "submitter": submitter,
            "comments_contains": comments_contains,
        }
        if any(value is not None for key, value in params.items() if key != "category_name"):
            if count_only:
                total_count = get_total_count(RELATION_FILTER_CATEGORY_TO_PAPERS_WITH_METADATA_COUNT, params)
                return format_response("relation_filter", [], {"mode": mode, **params}, total_count)
            results = _safe_run(RELATION_FILTER_CATEGORY_TO_PAPERS_WITH_METADATA, params)
            total_count = get_total_count(RELATION_FILTER_CATEGORY_TO_PAPERS_WITH_METADATA_COUNT, params)
            return format_response("relation_filter", results, {"mode": mode, **params}, total_count)

        base_params = {"category_name": category_name}
        if count_only:
            total_count = get_total_count(RELATION_FILTER_CATEGORY_TO_PAPERS_COUNT, base_params)
            return format_response("relation_filter", [], {"mode": mode, **base_params}, total_count)
        results = _safe_run(RELATION_FILTER_CATEGORY_TO_PAPERS, base_params)
        total_count = get_total_count(RELATION_FILTER_CATEGORY_TO_PAPERS_COUNT, base_params)
        return format_response("relation_filter", results, {"mode": mode, **base_params}, total_count)

    if mode == "paper_to_authors":
        paper_id = _resolve_paper_id(paper_id, title)
        if not paper_id:
            _http_400("paper_to_authors requires paper_id or title")
        params = {"paper_id": paper_id}
        if count_only:
            total_count = get_total_count(RELATION_FILTER_PAPER_TO_AUTHORS_COUNT, params)
            return format_response("relation_filter", [], {"mode": mode, **params}, total_count)
        results = _safe_run(RELATION_FILTER_PAPER_TO_AUTHORS, params)
        total_count = get_total_count(RELATION_FILTER_PAPER_TO_AUTHORS_COUNT, params)
        return format_response("relation_filter", results, {"mode": mode, **params}, total_count)

    if mode == "paper_to_categories":
        paper_id = _resolve_paper_id(paper_id, title)
        if not paper_id:
            _http_400("paper_to_categories requires paper_id or title")
        params = {"paper_id": paper_id}
        if count_only:
            total_count = get_total_count(RELATION_FILTER_PAPER_TO_CATEGORIES_COUNT, params)
            return format_response("relation_filter", [], {"mode": mode, **params}, total_count)
        results = _safe_run(RELATION_FILTER_PAPER_TO_CATEGORIES, params)
        total_count = get_total_count(RELATION_FILTER_PAPER_TO_CATEGORIES_COUNT, params)
        return format_response("relation_filter", results, {"mode": mode, **params}, total_count)

    if not category_names:
        _http_400("papers_in_categories requires category_names")
    params = {"category_names": category_names}
    if logic == "and":
        if count_only:
            total_count = get_total_count(RELATION_FILTER_PAPERS_IN_ALL_CATEGORIES_COUNT, params)
            return format_response("relation_filter", [], {"mode": mode, "logic": logic, **params}, total_count)
        results = _safe_run(RELATION_FILTER_PAPERS_IN_ALL_CATEGORIES, params)
        total_count = get_total_count(RELATION_FILTER_PAPERS_IN_ALL_CATEGORIES_COUNT, params)
        return format_response("relation_filter", results, {"mode": mode, "logic": logic, **params}, total_count)

    if count_only:
        total_count = get_total_count(RELATION_FILTER_PAPERS_IN_ANY_OF_CATEGORIES_COUNT, params)
        return format_response("relation_filter", [], {"mode": mode, "logic": logic, **params}, total_count)
    results = _safe_run(RELATION_FILTER_PAPERS_IN_ANY_OF_CATEGORIES, params)
    total_count = get_total_count(RELATION_FILTER_PAPERS_IN_ANY_OF_CATEGORIES_COUNT, params)
    return format_response("relation_filter", results, {"mode": mode, "logic": logic, **params}, total_count)



def multi_hop(
    hops: int,
    mode: str,
    author_name: str | None = None,
    category_name: str | None = None,
    paper_id: str | None = None,
    title: str | None = None,
    author1: str | None = None,
    author2: str | None = None,
    explain_path: bool = False,
    count_only: bool = False,
):
    if hops not in VALID_MULTI_HOP_MODES_BY_HOPS:
        _http_400("hops must be 2, 3, or 4")

    valid_modes = VALID_MULTI_HOP_MODES_BY_HOPS[hops]
    explain_modes = {"author_to_author_via_category", "paper_to_author"}
    if explain_path:
        if mode not in explain_modes:
            _http_400(f"Invalid explain_path mode. Allowed modes: {sorted(explain_modes)}")
        if mode == "author_to_author_via_category":
            if not author1 or not author2:
                _http_400("author_to_author_via_category requires author1 and author2")
            params = {"author1": author1, "author2": author2}
            results = _safe_run(PATH_EXPLAIN_AUTHOR_TO_AUTHOR_VIA_CATEGORY, params)
            return format_response("multi_hop", results, {"mode": mode, "explain_path": True, **params})

        if not paper_id:
            _http_400("paper_to_author explain_path requires paper_id")
        params = {"paper_id": paper_id}
        results = _safe_run(PATH_EXPLAIN_PAPER_TO_AUTHOR, params)
        return format_response("multi_hop", results, {"mode": mode, "explain_path": True, **params})

    if mode not in valid_modes:
        _http_400(f"Invalid multi_hop mode for hops={hops}. Allowed modes: {sorted(valid_modes)}")

    if hops == 2 and mode == "author_to_categories":
        if not author_name:
            _http_400("author_to_categories requires author_name")
        params = {"author_name": author_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_2_AUTHOR_TO_CATEGORIES_COUNT, params)
            return format_response("multi_hop", [], {"hops": 2, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_2_AUTHOR_TO_CATEGORIES, params)
        total_count = get_total_count(MULTI_HOP_2_AUTHOR_TO_CATEGORIES_COUNT, params)
        return format_response("multi_hop", results, {"hops": 2, "mode": mode, **params}, total_count)

    if hops == 2 and mode == "category_to_authors":
        if not category_name:
            _http_400("category_to_authors requires category_name")
        params = {"category_name": category_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_2_CATEGORY_TO_AUTHORS_COUNT, params)
            return format_response("multi_hop", [], {"hops": 2, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_2_CATEGORY_TO_AUTHORS, params)
        total_count = get_total_count(MULTI_HOP_2_CATEGORY_TO_AUTHORS_COUNT, params)
        return format_response("multi_hop", results, {"hops": 2, "mode": mode, **params}, total_count)

    if hops == 2 and mode == "paper_to_other_papers_by_same_authors":
        paper_id = _resolve_paper_id(paper_id, title)
        if not paper_id:
            _http_400("paper_to_other_papers_by_same_authors requires paper_id or title")
        params = {"paper_id": paper_id}
        if count_only:
            total_count = get_total_count(MULTI_HOP_2_PAPER_TO_OTHER_PAPERS_BY_SAME_AUTHORS_COUNT, params)
            return format_response("multi_hop", [], {"hops": 2, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_2_PAPER_TO_OTHER_PAPERS_BY_SAME_AUTHORS, params)
        total_count = get_total_count(MULTI_HOP_2_PAPER_TO_OTHER_PAPERS_BY_SAME_AUTHORS_COUNT, params)
        return format_response("multi_hop", results, {"hops": 2, "mode": mode, **params}, total_count)

    if hops == 3 and mode == "co_authors_in_category":
        if not author_name:
            _http_400("co_authors_in_category requires author_name")
        if not category_name:
            _http_400("co_authors_in_category requires category_name")
        params = {"author_name": author_name, "category_name": category_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_3_CO_AUTHORS_IN_CATEGORY_COUNT, params)
            return format_response("multi_hop", [], {"hops": 3, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_3_CO_AUTHORS_IN_CATEGORY, params)
        total_count = get_total_count(MULTI_HOP_3_CO_AUTHORS_IN_CATEGORY_COUNT, params)
        return format_response("multi_hop", results, {"hops": 3, "mode": mode, **params}, total_count)

    if hops == 3 and mode == "author_to_same_category_papers":
        if not author_name:
            _http_400("author_to_same_category_papers requires author_name")
        params = {"author_name": author_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_3_AUTHOR_TO_SAME_CATEGORY_PAPERS_COUNT, params)
            return format_response("multi_hop", [], {"hops": 3, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_3_AUTHOR_TO_SAME_CATEGORY_PAPERS, params)
        total_count = get_total_count(MULTI_HOP_3_AUTHOR_TO_SAME_CATEGORY_PAPERS_COUNT, params)
        return format_response("multi_hop", results, {"hops": 3, "mode": mode, **params}, total_count)

    if hops == 3 and mode == "category_to_papers_by_authors":
        if not category_name:
            _http_400("category_to_papers_by_authors requires category_name")
        params = {"category_name": category_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_3_CATEGORY_TO_PAPERS_BY_AUTHORS_COUNT, params)
            return format_response("multi_hop", [], {"hops": 3, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_3_CATEGORY_TO_PAPERS_BY_AUTHORS, params)
        total_count = get_total_count(MULTI_HOP_3_CATEGORY_TO_PAPERS_BY_AUTHORS_COUNT, params)
        return format_response("multi_hop", results, {"hops": 3, "mode": mode, **params}, total_count)

    if hops == 3 and mode == "paper_to_authors_in_same_categories":
        paper_id = _resolve_paper_id(paper_id, title)
        if not paper_id:
            _http_400("paper_to_authors_in_same_categories requires paper_id or title")
        params = {"paper_id": paper_id}
        if count_only:
            total_count = get_total_count(MULTI_HOP_3_PAPER_TO_AUTHORS_IN_SAME_CATEGORIES_COUNT, params)
            return format_response("multi_hop", [], {"hops": 3, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_3_PAPER_TO_AUTHORS_IN_SAME_CATEGORIES, params)
        total_count = get_total_count(MULTI_HOP_3_PAPER_TO_AUTHORS_IN_SAME_CATEGORIES_COUNT, params)
        return format_response("multi_hop", results, {"hops": 3, "mode": mode, **params}, total_count)

    if hops == 4 and mode == "author_to_related_authors_via_shared_categories":
        if not author_name:
            _http_400("author_to_related_authors_via_shared_categories requires author_name")
        params = {"author_name": author_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_4_AUTHOR_TO_RELATED_AUTHORS_VIA_SHARED_CATEGORIES_COUNT, params)
            return format_response("multi_hop", [], {"hops": 4, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_4_AUTHOR_TO_RELATED_AUTHORS_VIA_SHARED_CATEGORIES, params)
        total_count = get_total_count(MULTI_HOP_4_AUTHOR_TO_RELATED_AUTHORS_VIA_SHARED_CATEGORIES_COUNT, params)
        return format_response("multi_hop", results, {"hops": 4, "mode": mode, **params}, total_count)

    if hops == 4 and mode == "category_to_related_categories_via_authors":
        if not category_name:
            _http_400("category_to_related_categories_via_authors requires category_name")
        params = {"category_name": category_name}
        if count_only:
            total_count = get_total_count(MULTI_HOP_4_CATEGORY_TO_RELATED_CATEGORIES_VIA_AUTHORS_COUNT, params)
            return format_response("multi_hop", [], {"hops": 4, "mode": mode, **params}, total_count)
        results = _safe_run(MULTI_HOP_4_CATEGORY_TO_RELATED_CATEGORIES_VIA_AUTHORS, params)
        total_count = get_total_count(MULTI_HOP_4_CATEGORY_TO_RELATED_CATEGORIES_VIA_AUTHORS_COUNT, params)
        return format_response("multi_hop", results, {"hops": 4, "mode": mode, **params}, total_count)

    paper_id = _resolve_paper_id(paper_id, title)
    if not paper_id:
        _http_400("paper_to_related_papers_via_authors_and_categories requires paper_id or title")
    params = {"paper_id": paper_id}
    if count_only:
        total_count = get_total_count(MULTI_HOP_4_PAPER_TO_RELATED_PAPERS_VIA_AUTHORS_AND_CATEGORIES_COUNT, params)
        return format_response("multi_hop", [], {"hops": 4, "mode": mode, **params}, total_count)
    results = _safe_run(MULTI_HOP_4_PAPER_TO_RELATED_PAPERS_VIA_AUTHORS_AND_CATEGORIES, params)
    total_count = get_total_count(MULTI_HOP_4_PAPER_TO_RELATED_PAPERS_VIA_AUTHORS_AND_CATEGORIES_COUNT, params)
    return format_response("multi_hop", results, {"hops": 4, "mode": mode, **params}, total_count)



