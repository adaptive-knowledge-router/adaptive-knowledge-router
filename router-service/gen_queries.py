import os, json, random, time, logging
from dotenv import load_dotenv
from groq import Groq
from tqdm import tqdm

load_dotenv()

API_KEY        = os.environ["GROQ_API_KEY"]
MODEL          = "llama-3.3-70b-versatile"
ARXIV_FILE     = "papers_subset.jsonl"
SUBSET_FILE    = "papers_subset.jsonl"
OUTPUT_FILE    = "arxiv_queries.jsonl"
PROCESSED_FILE = "processed_ids.json"
MAX_PAPERS     = 1

KG_STRATEGIES  = ["entity_lookup", "relation_filter", "multi_hop"]
RAG_STRATEGIES = ["sparse", "dense", "hybrid"]


def load_processed():
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE) as f:
            return set(json.load(f))
    return set()

def save_processed(processed_ids):
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed_ids), f)

def load_subset_ids():
    ids = set()
    with open(SUBSET_FILE) as f:
        for line in f:
            if line.strip():
                ids.add(json.loads(line)["id"])
    return ids

def sample_arxiv(n, exclude_ids, subset_ids):
    reservoir, count = [], 0
    with open(ARXIV_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                p = json.loads(line.strip())
            except:
                continue
            if not p.get("abstract", "").strip():
                continue
            if p.get("id") in exclude_ids:
                continue
            if p.get("id") not in subset_ids:
                continue
            count += 1
            if len(reservoir) < n:
                reservoir.append(p)
            else:
                j = random.randint(0, count - 1)
                if j < n:
                    reservoir[j] = p
    return reservoir


SYSTEM_PROMPT = (
    "You are a dataset curator for a research retrieval system. "
    "Generate realistic user queries for academic papers. "
    "Respond with valid JSON only — no explanation, no markdown, no extra text."
)

def build_prompt(p):
    paper_id   = p.get("id", "Unknown")
    title      = (p.get("title") or "Unknown").strip().replace("\n", " ")
    authors    = p.get("authors", "Unknown")
    categories = p.get("categories", "Unknown")
    journal    = p.get("journal-ref") or "Not specified"
    abstract   = (p.get("abstract") or "").strip().replace("\n", " ")

    kg_strategy  = random.choice(KG_STRATEGIES)
    rag_strategy = random.choice(RAG_STRATEGIES)

    return f"""You will generate exactly 2 queries for the research paper below.

QUERY TYPE DEFINITIONS

FACTUAL
  Answerable using only structured metadata (authors, title, categories, journal).
  Must NOT require reading the abstract.
  Strategy: {kg_strategy}
    - entity_lookup   : ask about a single specific entity. e.g. "Who are the authors of paper X?"
    - relation_filter : ask about papers filtered by an attribute. e.g. "What papers by author X are in category cs.LG?"
    - multi_hop : requires traversing 2+ relationships, but must still be anchored
              to this specific paper. e.g. "Which co-authors of this paper have
              also published in category stat.ML?"

SEMANTIC
  Requires reading and understanding the abstract.
  Cannot be answered from metadata alone.
  Strategy: {rag_strategy}
    - sparse  : use specific technical terms or exact phrases from the abstract.
    - dense   : ask about a specific concept, mechanism, or finding — not just "what problem does this paper solve?"
    - hybrid  : mix of specific terms and conceptual understanding.

PAPER
ID         : {paper_id}
Title      : {title}
Authors    : {authors}
Categories : {categories}
Journal    : {journal}

Abstract:
{abstract}

Generate exactly 2 queries: one FACTUAL using the {kg_strategy} strategy, one SEMANTIC using the {rag_strategy} strategy.
- Write queries as a real user would ask them (natural language).
- Each query must be specific to this paper, not generic.
- Always refer to the paper by its title.

Respond ONLY with a JSON array:
[
  {{"query": "...", "type": "factual",  "kg_strategy": "{kg_strategy}"}},
  {{"query": "...", "type": "semantic", "rag_strategy": "{rag_strategy}"}}
]"""


def call_llama(client, prompt):
    raw = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.7,
        max_tokens=512,
    ).choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    queries = json.loads(raw)
    assert len(queries) == 2
    assert queries[0]["type"] == "factual"  and queries[0].get("kg_strategy")  in KG_STRATEGIES
    assert queries[1]["type"] == "semantic" and queries[1].get("rag_strategy") in RAG_STRATEGIES
    return queries


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")
    client = Groq(api_key=API_KEY)

    processed_ids = load_processed()
    subset_ids    = load_subset_ids()
    logging.info(f"{len(processed_ids)} papers already processed. Sampling {MAX_PAPERS} from {len(subset_ids)} subset papers...")

    papers = sample_arxiv(MAX_PAPERS, processed_ids, subset_ids)
    logging.info(f"Sampled {len(papers)} papers.")

    with open(OUTPUT_FILE, "a") as f:
        for p in tqdm(papers):
            try:
                queries = call_llama(client, build_prompt(p))
                f.write(json.dumps({"paper_id": p["id"], "queries": queries}) + "\n")
                f.flush()
                processed_ids.add(p["id"])
                save_processed(processed_ids)
            except Exception as e:
                logging.warning(f"[{p.get('id')}] {e}")
            time.sleep(1)


if __name__ == "__main__":
    main()   