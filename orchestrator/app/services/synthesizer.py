"""Synthesizer – transforms router prediction + retrieval output into
the final ``QueryResponse`` returned by the orchestrator API.

Query-mode aware: classifies each query into one of five modes
(exact_lookup, list_query, open_explanation, compare_query, fallback)
and picks the right answer strategy for each.
"""

import logging
import re
from collections import OrderedDict
from typing import Any

from app.clients.llm_client import LLMClient
from app.config import settings
from app.schemas.responses import (
    QueryResponse,
    RetrievalResult,
    StrategyResponse,
    SynthesisMetadata,
)

logger = logging.getLogger(__name__)

# Safety cap – avoid enormous LLM prompts.
_MAX_ITEMS = 50

# Maximum chars for any single field value in the compact evidence block.
_MAX_FIELD_LEN = 120

# Fields to extract from each result, in priority order.
_EVIDENCE_FIELDS = ("title", "name", "authors", "doi", "categories", "category",
                    "paper_id", "id", "abstract", "text", "content", "score")

# Per-subtype field selection for compact evidence (LLM path).
_MODE_EVIDENCE_FIELDS: dict[str, tuple[str, ...]] = {
    "doi":                     ("paper_id", "id", "doi", "title"),
    "paper_details":           ("title", "name", "authors", "doi", "categories", "abstract"),
    "paper_titles":            ("title", "name", "paper_id", "id", "authors"),
    "paper_titles_from_seed":  ("title", "name", "paper_id", "id", "authors"),
    "author_names":            ("author_name", "authors", "name"),
    "category_names":          ("category_name", "categories", "category"),
}

# Modes that benefit from longer field values (e.g. abstracts).
_LONG_FIELD_MODES = {"open_explanation", "compare_query"}
_LONG_FIELD_LEN = 250

# Token limits per mode
_LIST_NUM_PREDICT = 512
_SUMMARY_NUM_PREDICT = 256

# ── KG strategies where we can answer from fields directly ──────────
_KG_STRATEGIES = {"entity_lookup", "relation_filter", "multi_hop"}

# ── Query-mode classification ───────────────────────────────────────
# Determines HOW we answer (direct extract vs LLM summary) and WHAT
# field type to extract when in structured mode.

_SAME_AUTHOR_PATTERN = re.compile(
    r"same\s+authors?\s+as\s+(?:paper\s+)?(\S+)", re.IGNORECASE,
)
_DOI_PATTERN = re.compile(
    r"\bdoi\b|digital object identifier", re.IGNORECASE,
)
_PAPER_DETAIL_PATTERN = re.compile(
    r"what (?:is|are) paper\b|\btell me about paper\b", re.IGNORECASE,
)
_PAPER_LIST_PATTERN = re.compile(
    r"which papers|what papers|list papers|show papers|all papers"
    r"|papers (?:written|authored|published|in )",
    re.IGNORECASE,
)
_AUTHOR_LIST_PATTERN = re.compile(
    r"which authors|who are the authors|list authors|what authors"
    r"|who (?:wrote|authored|has written|have written)"
    r"|authors of ",
    re.IGNORECASE,
)
_CATEGORY_LIST_PATTERN = re.compile(
    r"which categor|what categor|list categor"
    r"|which fields|what fields|list fields"
    r"|which subjects|what subjects|which topics|what topics",
    re.IGNORECASE,
)
_COMPARE_PATTERN = re.compile(
    r"\bcompare\b|\bdifference(?:s)? between\b|\bvs\.?\b"
    r"|\bcontrast\b|\bpros and cons\b",
    re.IGNORECASE,
)
_OPEN_PATTERN = re.compile(
    r"^(?:how|why|explain|describe|what (?:is|are) (?!paper\b|the doi\b))"
    r"|techniques|methods|approaches|overview|summarize|summary"
    r"|\bwhat (?:techniques|methods|approaches)\b",
    re.IGNORECASE,
)


def _classify_query_mode(query: str, strategy: str) -> tuple[str, str]:
    """Return ``(mode, answer_subtype)`` for the query.

    Modes: exact_lookup, list_query, open_explanation, compare_query, fallback.
    Subtypes (for exact/list only):
        doi, paper_details, paper_titles, paper_titles_from_seed,
        author_names, category_names, general.
    """
    # "same author as paper X" → list of paper titles
    if _SAME_AUTHOR_PATTERN.search(query):
        return "list_query", "paper_titles_from_seed"

    # DOI lookup
    if _DOI_PATTERN.search(query):
        return "exact_lookup", "doi"

    # Single paper detail ("What is paper 1609.01491?")
    if _PAPER_DETAIL_PATTERN.search(query):
        return "exact_lookup", "paper_details"

    # Explicit list requests — check author/category BEFORE paper
    # because "which authors have written papers in X" contains "papers in"
    if _AUTHOR_LIST_PATTERN.search(query):
        return "list_query", "author_names"
    if _CATEGORY_LIST_PATTERN.search(query):
        return "list_query", "category_names"
    if _PAPER_LIST_PATTERN.search(query):
        return "list_query", "paper_titles"

    # Comparison queries
    if _COMPARE_PATTERN.search(query):
        return "compare_query", "general"

    # Open-ended explanation (how/why/what-is-X, techniques, etc.)
    if _OPEN_PATTERN.search(query):
        return "open_explanation", "general"

    return "fallback", "general"


# ── Author-name filtering ──────────────────────────────────────────
_GARBAGE_AUTHOR_RE = re.compile(
    r"(?:department|university|institute|laboratory|labs?|group|"
    r"center|centre|school|college|division|team|project|"
    r"corporation|inc\.|ltd\.|llc|foundation|consortium|"
    r"microsoft|google|facebook|meta|amazon|ibm|nvidia)"
    r"|\(|\)|@|\.edu|\.org|\.com",
    re.IGNORECASE,
)


def _is_person_name(text: str) -> bool:
    """Heuristic: return True if *text* looks like a person name."""
    t = text.strip()
    if not t or len(t) < 3:
        return False
    if _GARBAGE_AUTHOR_RE.search(t):
        return False
    # person names are typically 2–5 words, each starting with a letter
    words = t.split()
    if len(words) < 1 or len(words) > 8:
        return False
    return True


def _flatten(val: Any) -> str:
    """Flatten a value to a clean string; join lists with ', '."""
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val).strip()


def _extract_field(results: list[dict], *keys: str) -> str | None:
    """Return the first non-empty value for *keys* from the first result."""
    if not results:
        return None
    rec = results[0]
    for k in keys:
        val = rec.get(k)
        if val is not None and val != "" and val != []:
            return _flatten(val)
    return None


def _collect_field(results: list[dict], *keys: str) -> list[str]:
    """Collect a unique, ordered list of values for *keys* across all results."""
    seen: set[str] = set()
    items: list[str] = []
    for rec in results:
        for k in keys:
            val = rec.get(k)
            if val is None or val == "" or val == []:
                continue
            text = _flatten(val)
            if text not in seen:
                seen.add(text)
                items.append(text)
            break  # use first matching key per record
    return items


# ── Direct-answer builders (no LLM needed) ──────────────────────────

def _direct_doi(results: list[dict]) -> str | None:
    doi = _extract_field(results, "doi")
    if doi:
        return f"**DOI:** {doi}"
    return None


def _direct_paper_details(results: list[dict]) -> str | None:
    title = _extract_field(results, "title", "name")
    if not title:
        return None
    authors = _extract_field(results, "authors", "author_name")
    if authors:
        return f"**{title}** by {authors}"
    return f"**{title}**"


def _direct_author_list(results: list[dict]) -> str | None:
    """Return a deduplicated bullet list of author names, filtering garbage."""
    items = _collect_field(results, "author_name", "authors", "name")
    # Expand comma-separated author strings and filter
    expanded: list[str] = []
    seen: set[str] = set()
    for item in items:
        # author fields may be "Alice, Bob, Carol" or single names
        for name in item.split(","):
            name = name.strip()
            norm = _normalize(name)
            if norm and norm not in seen and _is_person_name(name):
                seen.add(norm)
                expanded.append(name)
    if expanded:
        return "\n".join(f"- {n}" for n in expanded)
    return None


def _direct_category_list(results: list[dict]) -> str | None:
    """Return a deduplicated bullet list of category names."""
    items = _collect_field(results, "category_name", "categories", "category")
    if items:
        return "\n".join(f"- {it}" for it in items)
    return None


def _normalize(text: str) -> str:
    """Lower-case, strip punctuation for dedup."""
    return re.sub(r"[^\w\s]", "", text.strip().lower())


def _direct_paper_titles(results: list[dict],
                         exclude_ids: set[str] | None = None) -> str | None:
    """Return a deduplicated bullet list of paper titles from results.

    *exclude_ids* (optional) — set of paper_id values to skip (e.g. seed paper).
    """
    if not results:
        return None

    seen: set[str] = set()
    lines: list[str] = []
    for rec in results:
        pid = rec.get("paper_id") or rec.get("id") or ""
        if exclude_ids and str(pid) in exclude_ids:
            continue
        title = rec.get("title") or rec.get("name") or ""
        if not title:
            title = str(pid) if pid else "(unknown)"
        norm = _normalize(title)
        if norm in seen:
            continue
        seen.add(norm)
        authors = rec.get("authors") or rec.get("author_name") or ""
        if isinstance(authors, list):
            authors = ", ".join(str(a) for a in authors)
        if authors:
            lines.append(f"- **{title}** by {authors}")
        else:
            lines.append(f"- **{title}**")
    return "\n".join(lines) if lines else None


def _extract_seed_id(query: str) -> str | None:
    """Extract the seed paper ID from a 'same author as paper X' query."""
    m = _SAME_AUTHOR_PATTERN.search(query)
    if m:
        return m.group(1).strip("?.,;")
    return None


# ── LLM prompts ─────────────────────────────────────────────────────

_LIST_PROMPT = """\
You are a research assistant. Answer using ONLY the evidence below.

Rules:
- If the user asks for papers, list paper TITLES only. Do NOT list authors or categories instead.
- If the user asks for authors, list author NAMES only. Do NOT list paper titles instead.
- If the user asks for fields or categories, list CATEGORY NAMES only.
- Return ALL items from the evidence. Do NOT omit any.
- One bullet (`-`) per item.
- Do NOT add explanations, summaries, or extra text.
- Do NOT stop early or truncate the list.
- Do NOT mix output types (e.g. don't list authors when asked for papers).
- If the evidence is insufficient, say: "I could not determine this from the retrieved results."

Question: {query}

Evidence:
{evidence}

Answer:"""

_EXPLANATION_PROMPT = """\
You are a research assistant. Answer the question using ONLY the evidence below.
If the evidence is insufficient, say: "I could not determine this from the retrieved results."

Rules:
- Provide a concise, grounded explanation in 2–4 bullet points or 2 short paragraphs.
- Summarise the key ideas, methods, or findings from the evidence.
- Use markdown: **bold** for paper titles or key terms, `-` for bullets.
- Do NOT just list paper titles or author names.
- Do NOT invent facts, quote raw JSON, or mention field names.
- Write complete sentences. Do NOT stop mid-sentence.
- Keep the answer factual and concise.

Question: {query}

Evidence:
{evidence}

Answer (concise markdown):"""

_SUMMARY_PROMPT = """\
You are a research assistant. Answer the question using ONLY the evidence below.
If the evidence is insufficient, say: "I could not determine this from the retrieved results."

Rules:
- For exact lookup queries, return the exact field value directly.
- If the user asks for papers, mention paper TITLES. Do NOT substitute with author names or categories.
- If the user asks for authors, mention author NAMES only.
- If the user asks for fields or categories, mention CATEGORY NAMES only.
- Provide a concise answer: at most 3–5 short bullet points or a brief paragraph.
- Use markdown: **bold** for paper titles, `-` for bullets.
- Do NOT invent facts, quote raw JSON, or mention field names.
- Write complete sentences. Do NOT stop mid-sentence.

Question: {query}

Evidence:
{evidence}

Answer (concise markdown):"""


def _compact_evidence(results: list[dict[str, Any]],
                      subtype: str = "general",
                      mode: str = "fallback") -> str:
    """Build a short text block from results, keeping only fields
    relevant to *subtype* and truncating long values.

    *mode* controls truncation length — open-ended modes allow longer
    abstracts so the LLM has more context to work with.
    """
    fields = _MODE_EVIDENCE_FIELDS.get(subtype, _EVIDENCE_FIELDS)
    max_len = _LONG_FIELD_LEN if mode in _LONG_FIELD_MODES else _MAX_FIELD_LEN
    lines: list[str] = []
    for i, rec in enumerate(results, 1):
        parts: list[str] = []
        for key in fields:
            val = rec.get(key)
            if val is None or val == "":
                continue
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            text = str(val).strip()
            if len(text) > max_len:
                text = text[:max_len] + "…"
            parts.append(f"{key}: {text}")
        if parts:
            lines.append(f"[{i}] " + " | ".join(parts))
    return "\n".join(lines) if lines else "(no results)"


class _LRUCache:
    """Simple in-memory LRU cache for synthesised answers.

    Thread-safe enough for a single async process — Python's GIL
    serialises dict mutations within one event loop.
    """

    def __init__(self, maxsize: int = 128) -> None:
        self._maxsize = maxsize
        self._data: OrderedDict[str, tuple[str, str]] = OrderedDict()

    @staticmethod
    def _key(query: str, strategy: str, n_results: int) -> str:
        return f"{query.strip().lower()}|{strategy}|{n_results}"

    def get(self, query: str, strategy: str, n_results: int) -> tuple[str, str] | None:
        """Return ``(answer, query_mode)`` on hit, or ``None``."""
        k = self._key(query, strategy, n_results)
        if k not in self._data:
            return None
        self._data.move_to_end(k)
        return self._data[k]

    def put(self, query: str, strategy: str, n_results: int,
            answer: str, query_mode: str) -> None:
        """Store a successful answer.  Evicts oldest entry when full."""
        k = self._key(query, strategy, n_results)
        self._data[k] = (answer, query_mode)
        self._data.move_to_end(k)
        while len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def __len__(self) -> int:
        return len(self._data)


class Synthesizer:
    """Builds a unified ``QueryResponse`` from dispatcher outputs and
    synthesises a final answer via an Ollama LLM.

    Fast path: structured KG queries (exact lookups, list queries) are
    answered by deterministic field extraction — no LLM call needed.

    LLM path: open-ended, comparison, and fallback queries build a
    compact, mode-aware evidence block and call the LLM.

    Caching: successful answers are stored in a small in-memory LRU
    cache keyed by (query, strategy, num_results).
    """

    def __init__(self) -> None:
        self._llm = LLMClient()
        self._cache = _LRUCache(maxsize=settings.cache_size)

    async def build_response(
        self,
        query: str,
        prediction: StrategyResponse,
        retrieval: RetrievalResult,
        retrieval_latency_ms: float,
    ) -> QueryResponse:
        """Assemble the final API response and synthesise an answer."""
        num_results = len(retrieval.results)
        strategy = prediction.strategy

        # ── Cache check ──────────────────────────────────────────────
        hit = self._cache.get(query, strategy, num_results)
        if hit is not None:
            answer, cached_mode = hit
            logger.info("Cache HIT: strategy=%s, mode=%s, len=%d",
                        strategy, cached_mode, len(answer))
            return QueryResponse(
                query=query,
                strategy=strategy,
                confidence=prediction.confidence,
                synthesized_answer=answer,
                synthesis_metadata=SynthesisMetadata(
                    model=settings.answer_model,
                    query_mode=cached_mode,
                    retrieval_latency_ms=round(retrieval_latency_ms, 2),
                    synthesis_latency_ms=0.0,
                    total_latency_ms=round(retrieval_latency_ms, 2),
                    used_results_count=num_results,
                    cached=True,
                ),
                results=retrieval.results,
                latency_ms=round(retrieval_latency_ms, 2),
                source=retrieval.source,
            )

        # ── Synthesis ────────────────────────────────────────────────
        synthesized_answer: str | None = None
        synthesis_meta: SynthesisMetadata | None = None
        mode = "fallback"

        try:
            mode, subtype = _classify_query_mode(query, strategy)
            capped = retrieval.results[:_MAX_ITEMS]

            logger.info("Synthesis: strategy=%s, mode=%s, subtype=%s, results=%d",
                        strategy, mode, subtype, len(capped))

            direct: str | None = None
            llm_latency_ms = 0.0

            # ── Fast path: direct extraction ─────────────────────────
            if mode in ("exact_lookup", "list_query") and strategy in _KG_STRATEGIES and capped:
                if subtype == "doi":
                    direct = _direct_doi(capped)
                elif subtype == "paper_details":
                    direct = _direct_paper_details(capped)
                elif subtype == "paper_titles":
                    direct = _direct_paper_titles(capped)
                elif subtype == "paper_titles_from_seed":
                    seed_id = _extract_seed_id(query)
                    exclude = {seed_id} if seed_id else None
                    direct = _direct_paper_titles(capped, exclude_ids=exclude)
                elif subtype == "author_names":
                    direct = _direct_author_list(capped)
                elif subtype == "category_names":
                    direct = _direct_category_list(capped)

            if direct is not None:
                synthesized_answer = direct
                logger.info("Direct extraction (mode=%s, subtype=%s), len=%d",
                            mode, subtype, len(direct))
            else:
                # ── LLM path: mode-aware compact evidence ────────────
                evidence = _compact_evidence(capped, subtype=subtype, mode=mode)

                if mode in ("open_explanation", "compare_query"):
                    template = _EXPLANATION_PROMPT
                    num_predict = _SUMMARY_NUM_PREDICT
                elif mode == "list_query":
                    template = _LIST_PROMPT
                    num_predict = _LIST_NUM_PREDICT
                else:
                    template = _SUMMARY_PROMPT
                    num_predict = _SUMMARY_NUM_PREDICT

                prompt = template.format(query=query, evidence=evidence)

                logger.info("LLM synthesis: mode=%s, prompt=%d chars, num_predict=%d",
                            mode, len(prompt), num_predict)

                answer, llm_latency_ms = await self._llm.generate(
                    prompt, num_predict=num_predict,
                )
                synthesized_answer = answer

            synthesis_meta = SynthesisMetadata(
                model=settings.answer_model,
                query_mode=mode,
                retrieval_latency_ms=round(retrieval_latency_ms, 2),
                synthesis_latency_ms=llm_latency_ms,
                total_latency_ms=round(retrieval_latency_ms + llm_latency_ms, 2),
                used_results_count=num_results,
            )
        except Exception as exc:
            logger.exception("Synthesis failed: %s", exc)
            mode = "fallback"
            synthesis_meta = SynthesisMetadata(
                model=settings.answer_model,
                query_mode=mode,
                retrieval_latency_ms=round(retrieval_latency_ms, 2),
                synthesis_latency_ms=0.0,
                total_latency_ms=round(retrieval_latency_ms, 2),
                used_results_count=num_results,
                error=f"{type(exc).__name__}: {exc}",
            )

        # ── Cache store (successful answers only) ────────────────────
        if synthesized_answer and not (synthesis_meta and synthesis_meta.error):
            self._cache.put(query, strategy, num_results,
                            synthesized_answer, mode)

        total_ms = synthesis_meta.total_latency_ms

        return QueryResponse(
            query=query,
            strategy=strategy,
            confidence=prediction.confidence,
            synthesized_answer=synthesized_answer,
            synthesis_metadata=synthesis_meta,
            results=retrieval.results,
            latency_ms=total_ms,
            source=retrieval.source,
        )
