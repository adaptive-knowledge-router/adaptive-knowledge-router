from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from kg_service.app.extract_params import extract_all
from kg_service.app.neo4j_client import DatabaseQueryError, verify_connection
from kg_service.app.service import entity_lookup, relation_filter, multi_hop

app = FastAPI(title="KG Service", version="1.2.0")


@app.on_event("startup")
def startup_check() -> None:
    verify_connection()


@app.exception_handler(DatabaseQueryError)
def database_error_handler(_, exc: DatabaseQueryError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.get("/")
def root():
    return {"message": "KG service is running"}


@app.get("/kg/health")
def health():
    verify_connection()
    return {"status": "ok"}


@app.get("/kg/entity_lookup")
def entity_lookup_api(
    paper_id: str | None = None,
    title: str | None = None,
    doi: str | None = None,
    journal_ref: str | None = None,
    submitter: str | None = None,
    author_name: str | None = None,
    category_name: str | None = None,
    count_only: bool = False,
):
    return entity_lookup(
        paper_id=paper_id,
        title=title,
        doi=doi,
        journal_ref=journal_ref,
        submitter=submitter,
        author_name=author_name,
        category_name=category_name,
        count_only=count_only,
    )


@app.get("/kg/relation_filter")
def relation_filter_api(
    mode: str = Query(...),
    author_name: str | None = None,
    category_name: str | None = None,
    paper_id: str | None = None,
    has_doi: bool | None = None,
    has_journal_ref: bool | None = None,
    submitter: str | None = None,
    comments_contains: str | None = None,
    exclude_category_name: str | None = None,
    category_names: list[str] | None = Query(None),
    logic: str = "or",
    count_only: bool = False,
):
    return relation_filter(
        mode=mode,
        author_name=author_name,
        category_name=category_name,
        paper_id=paper_id,
        has_doi=has_doi,
        has_journal_ref=has_journal_ref,
        submitter=submitter,
        comments_contains=comments_contains,
        exclude_category_name=exclude_category_name,
        category_names=category_names,
        logic=logic,
        count_only=count_only,
    )


@app.get("/kg/multi_hop")
def multi_hop_api(
    hops: int = Query(...),
    mode: str = Query(...),
    author_name: str | None = None,
    category_name: str | None = None,
    paper_id: str | None = None,
    author1: str | None = None,
    author2: str | None = None,
    explain_path: bool = False,
    count_only: bool = False,
):
    return multi_hop(
        hops=hops,
        mode=mode,
        author_name=author_name,
        category_name=category_name,
        paper_id=paper_id,
        author1=author1,
        author2=author2,
        explain_path=explain_path,
        count_only=count_only,
    )


VALID_MULTIHOP_MODES = {
    "author_to_categories",
    "category_to_authors",
    "paper_to_other_papers_by_same_authors",
    "author_to_same_category_papers",
    "category_to_papers_by_authors",
    "paper_to_authors_in_same_categories",
    "author_to_related_authors_via_shared_categories",
    "category_to_related_categories_via_authors",
    "paper_to_related_papers_via_authors_and_categories",
}

VALID_RELATION_MODES = {
    "author_to_papers",
    "category_to_papers",
    "paper_to_authors",
    "paper_to_categories",
}


def _derive_hops_from_mode(mode: str | None, current_hops: int | None = None) -> int | None:
    if current_hops is not None:
        return current_hops

    if mode == "author_to_categories":
        return 2
    if mode == "category_to_authors":
        return 2
    if mode == "paper_to_other_papers_by_same_authors":
        return 2
    if mode == "author_to_same_category_papers":
        return 3
    if mode == "category_to_papers_by_authors":
        return 3
    if mode == "paper_to_authors_in_same_categories":
        return 3
    if mode == "author_to_related_authors_via_shared_categories":
        return 4
    if mode == "category_to_related_categories_via_authors":
        return 4
    if mode == "paper_to_related_papers_via_authors_and_categories":
        return 4

    return None


def _route_question(question: str, count_only: bool = False) -> dict:
    extracted = extract_all(question)
    lowered = question.lower()
    effective_count_only = count_only or bool(extracted.get("is_count_query"))

    response_meta = {
        "question": question,
        "extracted_params": extracted,
        "effective_count_only": effective_count_only,
    }

    if extracted.get("is_count_query"):
        if extracted["author_name"] and "paper" in lowered:
            result = relation_filter(
                mode="author_to_papers",
                author_name=extracted["author_name"],
                count_only=True,
            )
            result["router"] = {
                "selected_endpoint": "relation_filter",
                "selected_mode": "author_to_papers",
                **response_meta,
            }
            return result

        if extracted["category_name"] and "paper" in lowered:
            result = relation_filter(
                mode="category_to_papers",
                category_name=extracted["category_name"],
                count_only=True,
            )
            result["router"] = {
                "selected_endpoint": "relation_filter",
                "selected_mode": "category_to_papers",
                **response_meta,
            }
            return result

    if extracted["hops"] in {2, 3, 4} or extracted["mode"] in VALID_MULTIHOP_MODES:
        hops = _derive_hops_from_mode(extracted["mode"], extracted["hops"])
        mode = extracted["mode"]

        if mode is None:
            if extracted["category_name"] and (
                "category to authors" in lowered
                or "authors in category" in lowered
                or "which authors are in" in lowered
                or "who are the authors in" in lowered
                or "which authors have written papers in" in lowered
            ):
                mode = "category_to_authors"
                hops = 2

            elif extracted["author_name"] and (
                "author to categories" in lowered
                or "categories written by" in lowered
                or "categories by" in lowered
                or "what categories has" in lowered
                or "which categories has" in lowered
                or "what fields has" in lowered
                or "which fields has" in lowered
                or "published in" in lowered
            ):
                mode = "author_to_categories"
                hops = 2

            elif extracted["paper_id"] and (
                "papers by same author" in lowered
                or "other papers by same author" in lowered
                or "same author as paper" in lowered
                or "same author as" in lowered
                or "written by the same author as paper" in lowered
                or "written by the same author as" in lowered
                or "which papers are written by the same author as paper" in lowered
                or "which papers are by the same author as paper" in lowered
            ):
                mode = "paper_to_other_papers_by_same_authors"
                hops = 2

            elif extracted["author_name"] and (
                "same category papers" in lowered
                or "papers in the same categories as" in lowered
                or "papers are in the same categories as" in lowered
                or "same categories as" in lowered
                or "same research areas as" in lowered
            ):
                mode = "author_to_same_category_papers"
                hops = 3

            elif extracted["category_name"] and (
                "papers by authors in" in lowered
                or "papers written by authors in" in lowered
            ):
                mode = "category_to_papers_by_authors"
                hops = 3

            elif extracted["paper_id"] and (
                "authors in same categories" in lowered
                or "authors connected to the same categories as paper" in lowered
                or "same categories" in lowered
            ):
                mode = "paper_to_authors_in_same_categories"
                hops = 3

            elif extracted["author_name"] and (
                "which authors are related to" in lowered
                or "authors are related to" in lowered
                or "related authors" in lowered
                or "similar authors" in lowered
                or "authors related to" in lowered
            ):
                mode = "author_to_related_authors_via_shared_categories"
                hops = 4

            elif extracted["category_name"] and (
                "what categories are related to" in lowered
                or "categories are related to" in lowered
                or "related categories" in lowered
                or "connected categories" in lowered
                or "research areas are connected to" in lowered
            ):
                mode = "category_to_related_categories_via_authors"
                hops = 4

            elif extracted["paper_id"] and (
                "which papers are related to paper" in lowered
                or "papers related to paper" in lowered
                or "papers are related to" in lowered
                or "related papers" in lowered
            ):
                mode = "paper_to_related_papers_via_authors_and_categories"
                hops = 4

        if hops and mode:
            result = multi_hop(
                hops=hops,
                mode=mode,
                author_name=extracted["author_name"],
                category_name=extracted["category_name"],
                paper_id=extracted["paper_id"],
                count_only=effective_count_only,
            )
            result["router"] = {
                "selected_endpoint": "multi_hop",
                "selected_mode": mode,
                "selected_hops": hops,
                **response_meta,
            }
            return result

    relation_mode = extracted["mode"]
    if relation_mode in VALID_RELATION_MODES:
        result = relation_filter(
            mode=relation_mode,
            author_name=extracted["author_name"],
            category_name=extracted["category_name"],
            paper_id=extracted["paper_id"],
            category_names=extracted["category_names"],
            logic=extracted["logic"] or "or",
            has_doi=extracted["has_doi"],
            has_journal_ref=extracted["has_journal_ref"],
            submitter=extracted["submitter"],
            comments_contains=extracted["comments_contains"],
            count_only=effective_count_only,
        )
        result["router"] = {
            "selected_endpoint": "relation_filter",
            "selected_mode": relation_mode,
            **response_meta,
        }
        return result

    if extracted["category_names"] and len(extracted["category_names"]) >= 2:
        result = relation_filter(
            mode="papers_in_categories",
            category_names=extracted["category_names"],
            logic=extracted["logic"] or "or",
            count_only=effective_count_only,
        )
        result["router"] = {
            "selected_endpoint": "relation_filter",
            "selected_mode": "papers_in_categories",
            **response_meta,
        }
        return result

    if any([
        extracted["paper_id"],
        extracted["title"],
        extracted["doi"],
        extracted["journal_ref"],
        extracted["submitter"],
        extracted["author_name"],
        extracted["category_name"],
    ]):
        result = entity_lookup(
            paper_id=extracted["paper_id"],
            title=extracted["title"],
            doi=extracted["doi"],
            journal_ref=extracted["journal_ref"],
            submitter=extracted["submitter"],
            author_name=extracted["author_name"],
            category_name=extracted["category_name"],
            count_only=effective_count_only,
        )
        result["router"] = {"selected_endpoint": "entity_lookup", **response_meta}
        return result

    raise HTTPException(
        status_code=400,
        detail=(
            "Could not infer a KG strategy from the question. Try quoting a paper title, "
            "including a paper id like 0704.0001, adding a category like cs.AI, or using "
            "phrases such as 'papers by author', 'authors of paper', or '2-hop category to authors'."
        ),
    )


@app.get("/kg/query")
def query_from_natural_language(
    question: str = Query(..., description="Natural-language KG question"),
    count_only: bool = False,
):
    return _route_question(question=question, count_only=count_only)


@app.get("/kg/query/entity")
def query_entity_from_natural_language(
    question: str = Query(..., description="Natural-language question already routed to entity_lookup"),
    count_only: bool = False,
):
    extracted = extract_all(question)
    params = {
        "paper_id": extracted["paper_id"],
        "title": extracted["title"],
        "doi": extracted["doi"],
        "journal_ref": extracted["journal_ref"],
        "submitter": extracted["submitter"],
        "author_name": extracted["author_name"],
        "category_name": extracted["category_name"],
    }
    result = entity_lookup(**params, count_only=count_only)
    result["router"] = {
        "selected_endpoint": "entity_lookup",
        "question": question,
        "prepared_params": params,
    }
    return result


@app.get("/kg/query/relation")
def query_relation_from_natural_language(
    question: str = Query(..., description="Natural-language question already routed to relation_filter"),
    count_only: bool = False,
):
    extracted = extract_all(question)
    lowered = question.lower()

    mode = extracted["mode"]
    if mode not in {
        "author_to_papers",
        "category_to_papers",
        "paper_to_authors",
        "paper_to_categories",
        "papers_in_categories",
    }:
        mode = None

    if mode is None:
        if extracted["paper_id"] and (
            "authors of paper" in lowered
            or "paper to authors" in lowered
            or "who wrote paper" in lowered
            or "who are the authors of" in lowered
            or "author of paper" in lowered
        ):
            mode = "paper_to_authors"

        elif extracted["paper_id"] and (
            "categories of paper" in lowered
            or "paper to categories" in lowered
            or "which categories does paper" in lowered
            or "what categories does paper" in lowered
            or "belong to" in lowered
            or "belongs to" in lowered
        ):
            mode = "paper_to_categories"

        elif extracted["author_name"] and (
            "papers by" in lowered
            or "written by" in lowered
            or "authored by" in lowered
            or "papers written by" in lowered
            or "which papers are written by" in lowered
            or "what papers are written by" in lowered
        ):
            mode = "author_to_papers"

        elif extracted["category_name"] and (
            "papers in category" in lowered
            or "papers in the category" in lowered
            or "what papers are in" in lowered
            or "which papers are in" in lowered
            or "category to papers" in lowered
        ):
            mode = "category_to_papers"

        elif extracted["category_names"] and len(extracted["category_names"]) >= 2:
            mode = "papers_in_categories"

    if mode is None:
        raise HTTPException(status_code=400, detail="Could not infer relation_filter mode from the question.")

    effective_count_only = count_only or any(
        x in lowered for x in ["how many", "number of", "count of", "total number"]
    )

    params = {
        "mode": mode,
        "author_name": extracted["author_name"],
        "category_name": extracted["category_name"],
        "paper_id": extracted["paper_id"],
        "category_names": extracted["category_names"],
        "logic": extracted["logic"] or "or",
        "has_doi": extracted["has_doi"],
        "has_journal_ref": extracted["has_journal_ref"],
        "submitter": extracted["submitter"],
        "comments_contains": extracted["comments_contains"],
    }

    result = relation_filter(**params, count_only=effective_count_only)
    result["router"] = {
        "selected_endpoint": "relation_filter",
        "selected_mode": mode,
        "effective_count_only": effective_count_only,
        "question": question,
        "prepared_params": params,
    }
    return result


@app.get("/kg/query/multi_hop")
def query_multihop_from_natural_language(
    question: str = Query(..., description="Natural-language question already routed to multi_hop"),
    count_only: bool = False,
):
    extracted = extract_all(question)
    lowered = question.lower()

    hops = _derive_hops_from_mode(extracted["mode"], extracted["hops"])
    mode = extracted["mode"]

    if mode is None:
        if extracted["category_name"] and (
            "category to authors" in lowered
            or "authors in category" in lowered
            or "which authors are in" in lowered
            or "who are the authors in" in lowered
            or "which authors have written papers in" in lowered
        ):
            mode = "category_to_authors"
            hops = 2

        elif extracted["author_name"] and (
            "author to categories" in lowered
            or "categories written by" in lowered
            or "categories by" in lowered
            or "what categories has" in lowered
            or "which categories has" in lowered
            or "what fields has" in lowered
            or "which fields has" in lowered
            or "published in" in lowered
        ):
            mode = "author_to_categories"
            hops = 2

        elif extracted["paper_id"] and (
            "papers by same author" in lowered
            or "other papers by same author" in lowered
            or "same author as paper" in lowered
            or "same author as" in lowered
            or "written by the same author as paper" in lowered
            or "written by the same author as" in lowered
            or "which papers are written by the same author as paper" in lowered
            or "which papers are by the same author as paper" in lowered
        ):
            mode = "paper_to_other_papers_by_same_authors"
            hops = 2

        elif extracted["author_name"] and (
            "same category papers" in lowered
            or "papers in the same categories as" in lowered
            or "papers are in the same categories as" in lowered
            or "same categories as" in lowered
            or "same research areas as" in lowered
        ):
            mode = "author_to_same_category_papers"
            hops = 3

        elif extracted["category_name"] and (
            "papers by authors in" in lowered
            or "papers written by authors in" in lowered
        ):
            mode = "category_to_papers_by_authors"
            hops = 3

        elif extracted["paper_id"] and (
            "authors in same categories" in lowered
            or "authors connected to the same categories as paper" in lowered
            or "same categories" in lowered
        ):
            mode = "paper_to_authors_in_same_categories"
            hops = 3

        elif extracted["author_name"] and (
            "which authors are related to" in lowered
            or "authors are related to" in lowered
            or "related authors" in lowered
            or "similar authors" in lowered
            or "authors related to" in lowered
        ):
            mode = "author_to_related_authors_via_shared_categories"
            hops = 4

        elif extracted["category_name"] and (
            "what categories are related to" in lowered
            or "categories are related to" in lowered
            or "related categories" in lowered
            or "connected categories" in lowered
            or "research areas are connected to" in lowered
        ):
            mode = "category_to_related_categories_via_authors"
            hops = 4

        elif extracted["paper_id"] and (
            "which papers are related to paper" in lowered
            or "papers related to paper" in lowered
            or "papers are related to" in lowered
            or "related papers" in lowered
        ):
            mode = "paper_to_related_papers_via_authors_and_categories"
            hops = 4

    if mode is None or hops is None:
        raise HTTPException(status_code=400, detail="Could not infer multi_hop mode/hops from the question.")

    params = {
        "hops": hops,
        "mode": mode,
        "author_name": extracted["author_name"],
        "category_name": extracted["category_name"],
        "paper_id": extracted["paper_id"],
    }

    result = multi_hop(**params, count_only=count_only)
    result["router"] = {
        "selected_endpoint": "multi_hop",
        "selected_mode": mode,
        "selected_hops": hops,
        "question": question,
        "prepared_params": params,
    }
    return result


@app.get("/kg/debug_extract")
def debug_extract(question: str):
    extracted = extract_all(question)
    derived_hops = _derive_hops_from_mode(extracted["mode"], extracted["hops"])
    return {
        **extracted,
        "derived_hops": derived_hops,
    }