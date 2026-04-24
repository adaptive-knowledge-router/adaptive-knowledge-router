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
    "cs.DC", "cs.DS", "cs.SY", "cs.IT",
    "cs.HC", "cs.CY", "cs.DB", "cs.CC",
    "cs.LO", "cs.DL", "cs.MM", "cs.RO",
    "math.OC", "math.IT", "math.ST",
    "stat.TH", "eess.SP", "q-bio.QM",
}

PAPER_ID_PATTERN = re.compile(r"\b\d{4}\.\d{4,5}\b")
DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")

# Regex fallback for paper title extraction when LLM fails
# Titles always follow "the paper" in our query templates
_TITLE_PATTERNS = [
    # "who are the authors of TITLE?" / "who wrote TITLE?" / "give me the authors of TITLE?"
    re.compile(
        r"(?:who\s+(?:are|were)\s+the\s+authors?\s+of\s+(?:(?:the\s+)?paper\s+)?(?:titled\s+)?)(.+?)\??$",
        re.IGNORECASE,
    ),
    re.compile(r"(?:who\s+(?:wrote|authored)|list\s+the\s+authors?\s+of|who\s+is\s+the\s+(?:writer|author)\s+of)\s+(?:(?:the\s+)?paper\s+)?(?:titled\s+)?(.+?)\??$", re.IGNORECASE),
    re.compile(
        r"(?:give|show|tell|find)\s+me\s+the\s+authors?\s+of\s+(?:(?:the\s+)?paper\s+)?(?:titled\s+)?(.+?)\??$",
        re.IGNORECASE,
    ),
    re.compile(
        r"what\s+are\s+the\s+authors?\s+of\s+(?:(?:the\s+)?paper\s+)?(?:titled\s+)?(.+?)\??$",
        re.IGNORECASE,
    ),
    # "titled X" / "paper is titled X" / "which paper is titled X?"
    re.compile(r"\btitled\s+['\"]?(.+?)['\"]?\s*\??$", re.IGNORECASE),
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
    # "of the TITLE paper" — title between "of the" and "paper",
    # skipping "of the authors/paper ..." which are not titles
    re.compile(
        r"of\s+the\s+(?!(?:paper|authors?)\b)(.+?)\s+paper\b",
        re.IGNORECASE,
    ),
    # "the TITLE paper" — title comes before the word "paper"
    re.compile(r"\bthe\s+(.+?)\s+paper\b", re.IGNORECASE),
    # "same author as TITLE" / "same authors as TITLE"
    re.compile(r"same\s+authors?\s+as\s+(.+?)(?:\?|$)", re.IGNORECASE),
    # "by the authors of TITLE" / "authors of TITLE" at end of query
    re.compile(
        r"(?:by\s+the\s+authors?\s+of|authors?\s+of)\s+['\"]?(.+?)['\"]?\??$",
        re.IGNORECASE,
    ),
]

# Regex fallbacks for author name extraction when LLM fails
_AUTHOR_PATTERNS = [
    re.compile(r"(?:what|which)\s+papers?\s+has\s+(.+?)\s+written", re.IGNORECASE),
    re.compile(r"(?:what|which)\s+papers?\s+did\s+(.+?)\s+(?:write|publish)", re.IGNORECASE),
    re.compile(r"(?:papers?|publications?)\s+(?:by|written\s+by|authored\s+by)\s+(.+?)(?:\?|$|in\s+[a-z])", re.IGNORECASE),
    re.compile(r"(?:find|show|list)\s+papers?\s+by\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"(?:who\s+is|find|show)\s+(.+?)\s+(?:as\s+an?\s+author)", re.IGNORECASE),
    re.compile(r"co-authors?\s+of\s+(?!the\s+paper|paper\s)(.+?)(?:\?|$|who|that|\s+have|\s+also|\s+published)", re.IGNORECASE),
    re.compile(r"co-authored\s+papers?\s+with\s+(.+?)(?:\s+in\s+(?:cs|stat|math|eess|q-bio)\b|\s+have|\s+also|\s+who|\s+that|\?|$)", re.IGNORECASE),
    re.compile(r"co-authored\s+by\s+(.+?)(?:\s+in\s+(?:cs|stat|math|eess|q-bio)\b|\s+have|\s+also|\s+who|\s+that|\?|$)", re.IGNORECASE),
    re.compile(r"authors?\s+related\s+to\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"(?:what\s+categories|which\s+categories|what\s+fields?|which\s+fields?)\s+(?:has|have|did)\s+(.+?)\s+(?:published?|written?|work)", re.IGNORECASE),
    re.compile(r"same\s+categor\w*\s+as\s+(.+?)(?:\?|$)", re.IGNORECASE),
    re.compile(r"(?:related\s+to|similar\s+to)\s+(.+?)\s+(?:via|through|by|using)", re.IGNORECASE),
    re.compile(r"(?:which|what)\s+authors?\s+are\s+related\s+to\s+(.+?)(?:\?|$|\s+via|\s+through)", re.IGNORECASE),
]

_CATEGORY_PATTERN = re.compile(
    r"\b(cs\.[A-Z]{2,3}|stat\.[A-Z]{2,4}|math\.[A-Z]{2,4}|eess\.[A-Z]{2,4}|q-bio\.[A-Z]{2,4})\b"
)

# Phrases that look like author names but aren't — LLM hallucinations.
_BOGUS_AUTHOR_RE = re.compile(
    r"^(?:the\s+)?(?:authors?\s+of|co-authors?\s+of|written\s+by|all\s+authors?)(\s+.+)?$",
    re.IGNORECASE,
)

# Phrases that pattern-7 ("the … paper") falsely captures as titles.
_NOT_A_TITLE_RE = re.compile(
    r"^(?:authors?\s+of|DOI\s+of|same\s+author|co-authors?\s+of|categories?\s+of|"
    r"fields?\s+(?:of|has|does)|written\s+by|published\s+in|papers?\s+(?:by|in|from))",
    re.IGNORECASE,
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

Query: "List the authors of the paper Attention is All You Need"
{{"title": "Attention is All You Need", "author_name": null, "category_name": null}}

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
Extract named entities and the relation mode from the query. Return JSON only. No explanation.

Fields:
- title: paper title if a specific paper is named, else null
- author_name: person's full name if mentioned, else null
- category_name: map any field/area mention to one of: cs.AI, cs.LG, cs.CL, cs.CV, cs.NE, cs.IR, cs.RO, stat.ML — else null
- mode: pick the best relation mode from the list below, else null

Valid modes:
  author_to_papers           — START from author, find their papers
  category_to_papers         — START from category, find papers in it
  paper_to_authors           — START from paper, find its authors
  paper_to_categories        — START from paper, find its categories
  paper_to_papers_in_category — papers by the same authors as a given paper, filtered to a category
  papers_in_categories       — papers that appear in multiple categories

Rules:
- Extract the author name even if it appears mid-sentence (e.g. "papers by X", "written by X", "authored by X")
- If both an author AND a category appear, extract both
- "machine learning" or "ML" → cs.LG, "computer vision" → cs.CV, "NLP" or "natural language" → cs.CL

Examples:
Query: "What papers has Yann LeCun written?"
{{"title": null, "author_name": "Yann LeCun", "category_name": null, "mode": "author_to_papers"}}

Query: "What papers are in category cs.AI?"
{{"title": null, "author_name": null, "category_name": "cs.AI", "mode": "category_to_papers"}}

Query: "What categories is the paper Fast Private Data Release Algorithms published in?"
{{"title": "Fast Private Data Release Algorithms", "author_name": null, "category_name": null, "mode": "paper_to_categories"}}

Query: "Who are the authors of the paper BERT: Pre-training of Deep Bidirectional Transformers?"
{{"title": "BERT: Pre-training of Deep Bidirectional Transformers", "author_name": null, "category_name": null, "mode": "paper_to_authors"}}

Query: "What papers in machine learning are written by Ilya Sutskever?"
{{"title": null, "author_name": "Ilya Sutskever", "category_name": "cs.LG", "mode": "author_to_papers"}}

Query: "List papers by Andrew Ng in computer vision"
{{"title": null, "author_name": "Andrew Ng", "category_name": "cs.CV", "mode": "author_to_papers"}}

Query: "What other papers in category cs.LG are written by the authors of Generative Adversarial Networks?"
{{"title": "Generative Adversarial Networks", "author_name": null, "category_name": "cs.LG", "mode": "paper_to_papers_in_category"}}

Query: "What other papers in category cs.AI are written by the authors of 'Dropout: A Simple Way to Prevent Overfitting'?"
{{"title": "Dropout: A Simple Way to Prevent Overfitting", "author_name": null, "category_name": "cs.AI", "mode": "paper_to_papers_in_category"}}

Query: "What other papers in category cs.CV have been written by authors of Deep Residual Learning for Image Recognition?"
{{"title": "Deep Residual Learning for Image Recognition", "author_name": null, "category_name": "cs.CV", "mode": "paper_to_papers_in_category"}}

Query: "Which papers in category stat.ML are by the same authors as Variational Autoencoders?"
{{"title": "Variational Autoencoders", "author_name": null, "category_name": "stat.ML", "mode": "paper_to_papers_in_category"}}

Query: "{query}"
"""

PROMPT_MULTI_HOP = """You are an entity extractor for an academic paper search system.
Extract named entities and the traversal mode from the query. Return JSON only. No explanation.

Fields:
- title: paper title if a specific paper is named, else null
- author_name: ANY person's name that appears in the query — regardless of where it appears, else null
- category_name: extract the exact arxiv category code if present (e.g. cs.LG, stat.ML), else null
- mode: pick the best traversal mode from the list below, else null

Valid modes:
  author_to_categories                          — what categories has author X published in?
  category_to_authors                           — which authors publish in category X?
  paper_to_other_papers_by_same_authors         — other papers by the same authors as paper X
  author_to_same_category_papers                — papers in the same categories as author X
  category_to_papers_by_authors                 — papers written by authors who publish in category X
  paper_to_authors_in_same_categories           — authors who share categories with paper X
  co_authors_in_category                        — co-authors of author X who also publish in category Y
  paper_to_co_authors_in_category               — co-authors of paper X's authors who publish in category Y
  author_to_related_authors_via_shared_categories — researchers related to author X via shared categories (use when asking about co-authors of X with no category filter)
  category_to_related_categories_via_authors    — categories related to category X via shared authors
  paper_to_related_papers_via_authors_and_categories — papers related to paper X via authors and categories

Rules:
- ALWAYS extract a person's name even if it appears after words like "as", "of", "related to", "co-authored with"
- If both an author name AND a category code appear, extract BOTH
- Category codes appear verbatim (e.g. "cs.LG") — copy exactly; if asking WHICH categories (not specifying one), set null
- Use author_to_related_authors_via_shared_categories when query asks for co-authors/researchers who worked with X and no category is specified

Examples:
Query: "What categories has Geoffrey Hinton published in?"
{{"title": null, "author_name": "Geoffrey Hinton", "category_name": null, "mode": "author_to_categories"}}

Query: "Which co-authors of Yann LeCun have also published in cs.CV?"
{{"title": null, "author_name": "Yann LeCun", "category_name": "cs.CV", "mode": "co_authors_in_category"}}

Query: "Which other researchers have co-authored papers with Dmitry Krotov?"
{{"title": null, "author_name": "Dmitry Krotov", "category_name": null, "mode": "author_to_related_authors_via_shared_categories"}}

Query: "Which other papers did the authors of Generative Adversarial Networks write?"
{{"title": "Generative Adversarial Networks", "author_name": null, "category_name": null, "mode": "paper_to_other_papers_by_same_authors"}}

Query: "Which other journals have published papers by co-authors of Funnel Transformer?"
{{"title": "Funnel Transformer", "author_name": null, "category_name": null, "mode": "paper_to_other_papers_by_same_authors"}}

Query: "Which authors in cs.AI have also published in stat.ML?"
{{"title": null, "author_name": null, "category_name": "cs.AI", "mode": "category_to_authors"}}

Query: "What papers are in the same categories as Yoshua Bengio?"
{{"title": null, "author_name": "Yoshua Bengio", "category_name": null, "mode": "author_to_same_category_papers"}}

Query: "Which authors are related to Andrew Ng via shared categories?"
{{"title": null, "author_name": "Andrew Ng", "category_name": null, "mode": "author_to_related_authors_via_shared_categories"}}

Query: "Which co-authors of Yoshua Bengio have also worked in stat.ML?"
{{"title": null, "author_name": "Yoshua Bengio", "category_name": "stat.ML", "mode": "co_authors_in_category"}}

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

Query: "Which co-authors of Generative Adversarial Networks also published in cs.LG?"
{{"title": "Generative Adversarial Networks", "author_name": null, "category_name": "cs.LG", "mode": "paper_to_other_papers_by_same_authors"}}

Query: "Which other papers in category cs.AI have been co-authored by authors of the paper Attention is All You Need?"
{{"title": "Attention is All You Need", "author_name": null, "category_name": "cs.AI", "mode": "paper_to_other_papers_by_same_authors"}}

Query: "Which other categories, besides cs.LG, have papers co-authored by Yann LeCun?"
{{"title": null, "author_name": "Yann LeCun", "category_name": "cs.LG", "mode": "author_to_categories"}}

Query: "What categories besides cs.AI has Geoffrey Hinton published in?"
{{"title": null, "author_name": "Geoffrey Hinton", "category_name": "cs.AI", "mode": "author_to_categories"}}

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
    "paper_to_authors_in_same_categories", "co_authors_in_category",
    "paper_to_co_authors_in_category", "paper_to_papers_in_category",
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
            timeout=120,
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
            title = m.group(1).strip().rstrip("?.,").strip("'\"")
            # Reject if the "title" is actually a paper ID (e.g. 0704.0001)
            if PAPER_ID_PATTERN.fullmatch(title):
                continue
            # Reject common noise phrases captured by broad patterns
            if _NOT_A_TITLE_RE.match(title):
                continue
            if len(title) > 3:
                return title
    return None


def extract_all(query: str, strategy: str | None = None) -> dict[str, Any]:
    paper_id = extract_paper_id(query)

    # entity_lookup: regex is reliable — skip LLM to avoid latency
    if strategy == "entity_lookup":
        det_title    = extract_title_regex(query)
        det_author   = extract_author_name_regex(query)
        det_category = extract_category_regex(query)
        return {
            "paper_id"         : paper_id,
            "title"            : det_title,
            "doi"              : extract_doi(query),
            "author_name"      : det_author,
            "category_name"    : det_category,
            "category_names"   : [det_category] if det_category else None,
            "journal_ref"      : None,
            "submitter"        : None,
            "comments_contains": None,
            "logic"            : extract_logic(query),
            "has_doi"          : extract_has_doi(query),
            "has_journal_ref"  : extract_has_journal_ref(query),
            "hops"             : extract_hops(query),
            "mode"             : None,
            "is_count_query"   : is_count_query(query),
        }

    # relation_filter / multi_hop: regex first, LLM only when regex finds nothing
    author_name   = extract_author_name_regex(query)
    title         = extract_title_regex(query)
    category_name = extract_category_regex(query)

    if not any([author_name, title, category_name]):
        llm = _call_ollama(query, strategy=strategy)
        llm_author = llm["author_name"]
        if llm_author and _BOGUS_AUTHOR_RE.match(llm_author.strip()):
            llm_author = None
        author_name   = llm_author           or author_name
        title         = llm["title"]         or title
        category_name = llm["category_name"] or category_name
        llm_mode      = llm["mode"]
    else:
        llm_mode = None

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
        "mode"            : llm_mode,
        "is_count_query"  : is_count_query(query),
    }
