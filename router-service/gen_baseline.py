import os, json, random, time, logging
from dotenv import load_dotenv
from groq import Groq
from tqdm import tqdm

load_dotenv()

API_KEY        = os.environ["GROQ_API_KEY"]
MODEL          = "llama-3.3-70b-versatile"
SUBSET_FILE    = "../kg-service/data/processed/arxiv_subset.jsonl"
PROCESSED_FILE = "processed_ids.json"
OUTPUT_FILE    = "baseline_queries.jsonl"
BASELINE_PROCESSED_FILE = "baseline_processed_ids.json"
MAX_PAPERS     = 500

ALL_STRATEGIES = ["entity_lookup", "relation_filter", "multi_hop", "sparse", "dense", "hybrid"]


def load_processed():
    ids = set()
    for f in [PROCESSED_FILE, BASELINE_PROCESSED_FILE]:
        if os.path.exists(f):
            with open(f) as fp:
                ids.update(json.load(fp))
    return ids


def save_baseline_processed(processed_ids):
    with open(BASELINE_PROCESSED_FILE, "w") as f:
        json.dump(list(processed_ids), f)


def sample_papers(n, exclude_ids):
    reservoir, count = [], 0
    with open(SUBSET_FILE, encoding="utf-8") as f:
        for line in f:
            try:
                p = json.loads(line.strip())
            except:
                continue
            if not p.get("abstract", "").strip():
                continue
            if p.get("id") in exclude_ids:
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


def build_prompt(p, strategy):
    title      = (p.get("title") or "Unknown").strip().replace("\n", " ")
    authors    = p.get("authors", "Unknown")
    categories = p.get("categories", "Unknown")
    journal    = p.get("journal-ref") or "Not specified"
    abstract   = (p.get("abstract") or "").strip().replace("\n", " ")

    return f"""You will generate exactly 1 query for the research paper below.

STRATEGY DEFINITIONS

FACTUAL strategies — answerable using only structured metadata (authors, title, categories, journal). Must NOT require reading the abstract.
  - entity_lookup   : ask about a single specific entity tied to this paper.
                      e.g. "Who are the authors of paper X?"
  - relation_filter : ask about papers or categories filtered by an attribute related to this paper.
                      e.g. "What papers by the authors of X are in category cs.LG?"
  - multi_hop       : requires traversing 2+ relationships anchored to this paper.
                      e.g. "Which co-authors of paper X have also published in category stat.ML?"

SEMANTIC strategies — require reading and understanding the abstract. Cannot be answered from metadata alone.
  - sparse  : use specific technical terms or exact phrases from the abstract.
              e.g. "What does paper X say about variational inference with reparameterization?"
  - dense   : ask about a specific concept, mechanism, or finding in the paper.
              e.g. "How does paper X improve convergence in non-convex optimization?"
  - hybrid  : mix of specific terms and conceptual understanding.
              e.g. "How does the attention mechanism in paper X relate to memory efficiency?"

SELECTED STRATEGY: {strategy}

PAPER
Title      : {title}
Authors    : {authors}
Categories : {categories}
Journal    : {journal}

Abstract:
{abstract}

Generate exactly 1 query that a real user would ask, written naturally without mentioning the strategy name.
The query must be answerable using the {strategy} strategy and must refer to the paper by its title.

Respond ONLY with a JSON object:
{{"query": "<your query here>"}}"""


def call_llama(client, prompt):
    raw = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        temperature=0.7,
        max_tokens=200,
    ).choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1].removeprefix("json").strip()
    result = json.loads(raw)
    query = result["query"] if isinstance(result, dict) else result
    assert isinstance(query, str) and query.strip()
    return query


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s — %(message)s")
    client = Groq(api_key=API_KEY)

    exclude_ids = load_processed()
    logging.info(f"Excluding {len(exclude_ids)} already-processed papers. Sampling {MAX_PAPERS} new papers...")

    papers = sample_papers(MAX_PAPERS, exclude_ids)
    logging.info(f"Sampled {len(papers)} papers.")

    baseline_processed = set()
    if os.path.exists(BASELINE_PROCESSED_FILE):
        with open(BASELINE_PROCESSED_FILE) as f:
            baseline_processed = set(json.load(f))

    with open(OUTPUT_FILE, "a") as out:
        for p in tqdm(papers):
            paper_id = p["id"]
            strategy = random.choice(ALL_STRATEGIES)
            try:
                query = call_llama(client, build_prompt(p, strategy))
                out.write(json.dumps({"paper_id": paper_id, "query": query, "strategy": strategy}) + "\n")
                out.flush()
                baseline_processed.add(paper_id)
                save_baseline_processed(baseline_processed)
            except Exception as e:
                logging.warning(f"[{paper_id}] {e}")
            time.sleep(1)

    logging.info(f"Done. Written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
