from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")

KNOWN_CATEGORIES = {
    "cs.AI", "cs.LG", "cs.CL", "cs.CV",
    "cs.NE", "cs.IR", "cs.RO", "stat.ML",
}

PAPER_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}\b")
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")

# Regex fallback for paper title extraction when LLM fails
# Titles always follow "the paper" in our query templates
_TITLE_PATTERNS = [
    # "of/for/about the paper TITLE" — title ends at ?, end, or transition words
    re.compile(
        r"(?:of|for|about|is|called|titled)\s+the\s+paper\s+['\"]?(.+?)['\"]?"
        r"(?:\?|$|\s+(?:have|also|published|written|who|that|been|are|were|was|in\s+categor))",
        re.IGNORECASE,
    ),
    # "the paper TITLE" at end of string
    re.compile(r"\bthe\s+paper\s+(.+?)\??$", re.IGNORECASE),
    # quoted title: paper 'TITLE' or paper "TITLE"
    re.compile(r"\bpaper\s+['\"](.+?)['\"]", re.IGNORECASE),
]

# Regex fallbacks for author name extraction when LLM fails
_AUTHOR_PATTERNS = [
    re.compile(r"(?:what|which)\s+papers?\s+has\s+(.+?)\s+written", re.IGNORECASE),
    re.compile(r"(?:what|which)\s+papers?\s+did\s+(.+?)\s+(?:write|publish)", re.IGNORECASE),
    re.compile(r"(?:papers?|publications?)\s+(?:by|written\s+by|authored\s+by)\s+(.+?)(?:\?|$|in\s+[a-z])", re.IGNORECASE),
    re.compile(r"(?:find|show|list)\s+papers?\s+by\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"(?:who\s+is|find|show)\s+(.+?)\s+(?:as\s+an?\s+author)", re.IGNORECASE),
    re.compile(r"co-authors?\s+of\s+(?!the\s+paper|paper\s)(.+?)(?:\?|$|who|that|\s+have|\s+also|\s+published)", re.IGNORECASE),
    re.compile(r"authors?\s+related\s+to\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"(?:what\s+categories|which\s+categories|what\s+fields?|which\s+fields?)\s+(?:has|have|did)\s+(.+?)\s+(?:published?|written?|work)", re.IGNORECASE),
    re.compile(r"same\s+categor\w*\s+as\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"(?:related\s+to|similar\s+to)\s+(.+?)\s+(?:via|through|by|using)", re.IGNORECASE),
    re.compile(r"(?:which|what)\s+authors?\s+are\s+related\s+to\s+(.+?)(?:\?|$|\s+via|\s+through)", re.IGNORECASE),
]

_CATEGORY_PATTERN = re.compile(
    r"\b(cs\.[A-Z]{2,3}|stat\.[A-Z]{2,4}|math\.[A-Z]{2,4}|eess\.[A-Z]{2,4}|q-bio\.[A-Z]{2,4})\b"
)


COUNT_PATTERNS = [
    re.compile(r"\bhow many\b", re.IGNORECASE),
    re.compile(r"\bnumber of\b", re.IGNORECASE),
    re.compile(r"\bcount of\b", re.IGNORECASE),
    re.compile(r"\btotal number\b", re.IGNORECASE),
]

# Strategy-specific prompts with few-shot examples.
# Mode is already known (passed by router/orchestrator) — LLM only extracts entities.

PROMPT_ENTITY_LOOKUP = """You are an entity extractor for an academic paper search system.
Extract named entities from the query and return JSON only. No explanation.

Fields:
- title: the exact paper title if the query asks about a specific paper by name, else null
- author_name: the person's full name if the query asks about a specific person, else null
- category_name: arxiv category code (e.g. cs.LG) if mentioned, else null

Rules:
- A paper ID like "1706.03762" is NOT a title — set title to null if only an ID is given
- "Who are the authors of the paper X?" → title is X, author_name is null (the query asks WHO, it does not name an author)
- "Who wrote X?" → title is X, author_name is null
- Only extract author_name if a real person's name is mentioned, not phrases like "the authors of"
- Only extract what is explicitly named — do not infer

Examples:
Query: "Who wrote Attention is All You Need?"
{{"title": "Attention is All You Need", "author_name": null, "category_name": null}}

Query: "Who are the authors of the paper Deep Learning?"
{{"title": "Deep Learning", "author_name": null, "category_name": null}}

Query: "Who are the authors of the paper Sequential anomaly detection in the presence of noise?"
{{"title": "Sequential anomaly detection in the presence of noise", "author_name": null, "category_name": null}}

Query: "List the authors of the paper Learning from compressed observations"
{{"title": "Learning from compressed observations", "author_name": null, "category_name": null}}

Query: "Show me paper 1706.03762"
{{"title": null, "author_name": null, "category_name": null}}

Query: "Find papers by Geoffrey Hinton"
{{"title": null, "author_name": "Geoffrey Hinton", "category_name": null}}

Query: "What is the paper BERT about?"
{{"title": "BERT", "author_name": null, "category_name": null}}

Query: "Show me paper 1508.07933"
{{"title": null, "author_name": null, "category_name": null}}

Query: "{query}"
"""

PROMPT_RELATION_FILTER = """You are an entity extractor for an academic paper search system.
Extract named entities from the query and return JSON only. No explanation.

Fields:
- title: paper title if a specific paper is named, else null
- author_name: person's full name if mentioned, else null
- category_name: map any field/area mention to one of: cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.IR, cs.RO, stat.ML — else null

Rules:
- Extract the author name even if it appears mid-sentence (e.g. "papers by X", "written by X", "authored by X")
- If both an author AND a category appear, extract both
- "machine learning" or "ML" → cs.LG, "computer vision" → cs.CV, "NLP" or "natural language" → cs.CL

Examples:
Query: "What papers has Yann LeCun written?"
{{"title": null, "author_name": "Yann LeCun", "category_name": null}}

Query: "What papers are in category cs.AI?"
{{"title": null, "author_name": null, "category_name": "cs.AI"}}

Query: "What categories is the paper Fast Private Data Release Algorithms published in?"
{{"title": "Fast Private Data Release Algorithms", "author_name": null, "category_name": null}}

Query: "Who are the authors of the paper k-Sparse Autoencoders?"
{{"title": "k-Sparse Autoencoders", "author_name": null, "category_name": null}}

Query: "What papers in machine learning are written by Ilya Sutskever?"
{{"title": null, "author_name": "Ilya Sutskever", "category_name": "cs.LG"}}

Query: "List papers by Andrew Ng in computer vision"
{{"title": null, "author_name": "Andrew Ng", "category_name": "cs.CV"}}

Query: "Show papers by Maxim Raginsky in cs.IT"
{{"title": null, "author_name": "Maxim Raginsky", "category_name": "cs.IR"}}

Query: "{query}"
"""

PROMPT_MULTI_HOP = """You are an entity extractor for an academic paper search system.
Extract named entities from the query and return JSON only. No explanation.

Fields:
- title: paper title if a specific paper is named, else null
- author_name: ANY person's name that appears in the query — regardless of where it appears, else null
- category_name: extract the exact arxiv category code if present (e.g. cs.LG, stat.ML), else null

Rules:
- ALWAYS extract a person's name even if it appears after words like "as", "of", "related to", "similar to", "same categories as"
  Example: "same categories as Geoffrey Hinton" → author_name = "Geoffrey Hinton"
  Example: "related to Yoshua Bengio via" → author_name = "Yoshua Bengio"
- If both an author name AND a category code appear in the query, extract BOTH — never drop one
- Category codes appear verbatim in the query (e.g. "cs.LG", "stat.ML") — copy them exactly
- CRITICAL: If the query mentions the word "categories" but does NOT contain a specific category code (like cs.LG), set category_name to null. Do NOT invent or guess a category.
  Example: "What categories has Geoffrey Hinton published in?" → category_name: null (the query asks WHICH categories, it does not specify one)
- If only a natural language field is mentioned (e.g. "machine learning"), map it: ml/machine learning → cs.LG, vision → cs.CV, NLP → cs.CL

Valid categories: cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.IR, cs.RO, stat.ML

Examples:
Query: "Which co-authors of Yann LeCun have also published in cs.CV?"
{{"title": null, "author_name": "Yann LeCun", "category_name": "cs.CV"}}

Query: "Which co-authors of Attention is All You Need also published in cs.LG?"
{{"title": "Attention is All You Need", "author_name": null, "category_name": "cs.LG"}}

Query: "What categories has Geoffrey Hinton published in?"
{{"title": null, "author_name": "Geoffrey Hinton", "category_name": null}}

Query: "What categories has Maxim Raginsky published in?"
{{"title": null, "author_name": "Maxim Raginsky", "category_name": null}}

Query: "Which authors in cs.AI have also published in stat.ML?"
{{"title": null, "author_name": null, "category_name": "cs.AI"}}

Query: "What other papers did the authors of k-Sparse Autoencoders write?"
{{"title": "k-Sparse Autoencoders", "author_name": null, "category_name": null}}

Query: "What papers are in the same categories as Yoshua Bengio?"
{{"title": null, "author_name": "Yoshua Bengio", "category_name": null}}

Query: "Which authors are related to Andrew Ng via shared categories?"
{{"title": null, "author_name": "Andrew Ng", "category_name": null}}

Query: "Which co-authors of Yoshua Bengio have also worked in stat.ML?"
{{"title": null, "author_name": "Yoshua Bengio", "category_name": "stat.ML"}}

Query: "{query}"
"""

PROMPT_GENERAL = """Extract information from this research paper query and return JSON only.

Fields:
- title: the paper title if mentioned, else null
- author_name: the author name if mentioned, else null
- category_name: map to one of [cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.IR, cs.RO, stat.ML] if mentioned or implied, else null
- mode: pick one based on what the query starts from and what it wants:
    entity_lookup       — find/show a specific paper or author (e.g. "who wrote X?", "show paper X")
    author_to_papers    — START from AUTHOR, find papers (e.g. "papers by John Smith")
    paper_to_authors    — START from PAPER, find authors (e.g. "authors of paper X")
    paper_to_categories — START from PAPER, find categories (e.g. "what category is paper X in?")
    category_to_papers  — START from CATEGORY, find papers (e.g. "papers in cs.AI")
    author_to_categories — START from AUTHOR, find categories (e.g. "what fields does John publish in?")
    category_to_authors  — START from CATEGORY, find authors (e.g. "who publishes in cs.LG?")
    paper_to_other_papers_by_same_authors — other papers by same authors as this paper
    author_to_same_category_papers — papers in same categories as this author
    category_to_papers_by_authors — papers by authors in a category
    paper_to_authors_in_same_categories — authors sharing categories with this paper
    author_to_related_authors_via_shared_categories — related authors via shared categories
    category_to_related_categories_via_authors — related categories via shared authors
    paper_to_related_papers_via_authors_and_categories — related papers via authors and categories
    papers_in_categories — papers in multiple categories

Examples:
Query: "Who wrote Attention is All You Need?"
{{"title": "Attention is All You Need", "author_name": null, "category_name": null, "mode": "paper_to_authors"}}

Query: "What papers has Yann LeCun written?"
{{"title": null, "author_name": "Yann LeCun", "category_name": null, "mode": "author_to_papers"}}

Query: "Which co-authors of k-Sparse Autoencoders also published in cs.LG?"
{{"title": "k-Sparse Autoencoders", "author_name": null, "category_name": "cs.LG", "mode": "paper_to_other_papers_by_same_authors"}}

Query: "{query}"
"""

STRATEGY_PROMPTS = {
    "entity_lookup"  : PROMPT_ENTITY_LOOKUP,
    "relation_filter": PROMPT_RELATION_FILTER,
    "multi_hop"      : PROMPT_MULTI_HOP,
}

VALID_MODES = {
    "entity_lookup", "author_to_papers", "paper_to_authors",
    "paper_to_categories", "category_to_papers", "author_to_categories",
    "category_to_authors", "paper_to_other_papers_by_same_authors",
    "author_to_same_category_papers", "category_to_papers_by_authors",
    "paper_to_authors_in_same_categories",
    "author_to_related_authors_via_shared_categories",
    "category_to_related_categories_via_authors",
    "paper_to_related_papers_via_authors_and_categories",
    "papers_in_categories",
}


def _call_ollama(query: str, strategy: str | None = None) -> dict:
    """Call Ollama to extract entities. Uses strategy-specific prompt if strategy is known."""
    prompt_template = STRATEGY_PROMPTS.get(strategy, PROMPT_GENERAL)
    prompt = prompt_template.format(query=query)

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "{}")
        result = json.loads(raw)
        return {
            "title"        : result.get("title") or None,
            "author_name"  : result.get("author_name") or None,
            "category_name": result.get("category_name") if result.get("category_name") in KNOWN_CATEGORIES else None,
            "mode"         : result.get("mode") if result.get("mode") in VALID_MODES else None,
        }
    except Exception as e:
        import sys
        print(f"[extract_params] _call_ollama failed: {e}", file=sys.stderr)
        return {"title": None, "author_name": None, "category_name": None, "mode": None}


def extract_author_name_regex(query: str) -> str | None:
    """Regex fallback for author name extraction when LLM returns null."""
    for pattern in _AUTHOR_PATTERNS:
        m = pattern.search(query)
        if m:
            name = m.group(1).strip().rstrip("?.,")
            # Reject if the extracted name looks like a category (cs.XX) or is very short
            if len(name) > 2 and not re.match(r"^[a-z]{2,5}\.[A-Z]{2,3}$", name):
                return name
    return None


def extract_paper_id(query: str) -> str | None:
    match = PAPER_ID_PATTERN.search(query)
    return match.group(0) if match else None


def extract_doi(query: str) -> str | None:
    match = DOI_PATTERN.search(query)
    return match.group(0) if match else None


def extract_hops(query: str) -> int | None:
    lowered = query.lower()
    if "4 hop" in lowered or "4-hop" in lowered:
        return 4
    if "3 hop" in lowered or "3-hop" in lowered:
        return 3
    if "2 hop" in lowered or "2-hop" in lowered:
        return 2
    return None


def extract_has_doi(query: str) -> bool | None:
    lowered = query.lower()
    if any(t in lowered for t in ["with doi", "has doi", "having doi"]):
        return True
    if any(t in lowered for t in ["without doi", "no doi"]):
        return False
    return None


def extract_has_journal_ref(query: str) -> bool | None:
    lowered = query.lower()
    if any(t in lowered for t in ["with journal ref", "with journal reference", "has journal ref"]):
        return True
    if any(t in lowered for t in ["without journal ref", "without journal reference", "no journal ref"]):
        return False
    return None


def extract_logic(query: str) -> str | None:
    lowered = query.lower()
    if any(t in lowered for t in ["all categories", "both categories", "must include all", " and "]):
        return "and"
    if any(t in lowered for t in ["any category", "either category", " or "]):
        return "or"
    return None


def is_count_query(query: str) -> bool:
    return any(p.search(query) for p in COUNT_PATTERNS)


def extract_category_regex(query: str) -> str | None:
    """Regex fallback for category extraction — matches known arxiv category codes."""
    match = _CATEGORY_PATTERN.search(query)
    if match:
        candidate = match.group(1)
        return candidate if candidate in KNOWN_CATEGORIES else None
    return None


def extract_title_regex(query: str) -> str | None:
    """Regex fallback for title extraction when LLM returns null."""
    for pattern in _TITLE_PATTERNS:
        m = pattern.search(query)
        if m:
            title = m.group(1).strip().rstrip("?.,")
            if len(title) > 3:
                return title
    return None


def extract_all(query: str, strategy: str | None = None) -> dict[str, Any]:
    llm = _call_ollama(query, strategy=strategy)
    paper_id = extract_paper_id(query)

    # If LLM failed to extract entities, fall back to regex
    author_name = llm["author_name"] or extract_author_name_regex(query)
    title = llm["title"] or extract_title_regex(query)
    category_name = llm["category_name"] or extract_category_regex(query)

    return {
        "paper_id"        : paper_id,
        "title"           : title,
        "doi"             : extract_doi(query),
        "author_name"     : author_name,
        "category_name"   : category_name,
        "category_names"  : [category_name] if category_name else None,
        "journal_ref"     : None,
        "submitter"       : None,
        "comments_contains": None,
        "logic"           : extract_logic(query),
        "has_doi"         : extract_has_doi(query),
        "has_journal_ref" : extract_has_journal_ref(query),
        "hops"            : extract_hops(query),
        "mode"            : llm["mode"],
        "is_count_query"  : is_count_query(query),
    }
