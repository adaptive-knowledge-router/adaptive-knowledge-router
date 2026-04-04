# KG Service

Knowledge Graph microservice for arXiv-style paper retrieval using Neo4j + FastAPI.

It supports 3 KG strategy families:

- `entity_lookup`
- `relation_filter`
- `multi_hop`

It also supports natural-language query wrappers that extract parameters from plain English and call the right KG logic.

---

# 1. What this service does

This service supports two styles of usage:

## A. Structured endpoints
These expect explicit query parameters.

Examples:
- `/kg/entity_lookup`
- `/kg/relation_filter`
- `/kg/multi_hop`

Use these when the caller already knows exactly which KG strategy and parameters to use.


---

## B. Natural-language wrappers
These accept a plain English question, extract parameters, infer internal details like mode/hops, and then call the corresponding KG function.

Examples:
- `/kg/query`
- `/kg/query/entity`
- `/kg/query/relation`
- `/kg/query/multi_hop`

Used these for:
- testing
- debugging
- endpoint-specific natural-language parsing

---

# 2. Difference between `/kg/entity_lookup` and `/kg/query/entity`

## `/kg/entity_lookup`
This is a **structured endpoint**.

You must pass fields directly, for example:

```bash
curl "http://127.0.0.1:8000/kg/entity_lookup?paper_id=0704.0001"
```
## `/kg/query/entity`

This is a natural-language wrapper.

You give a plain English question, and the service extracts fields like paper_id, title, doi, etc., then calls entity_lookup() internally.

```bash
curl "http://127.0.0.1:8000/kg/query/entity?question=What%20is%20paper%200704.0001%3F"
```

4. Setup 

pip install -r requirements.txt

Start Neo4j

Make sure Neo4j is running with the correct credentials.

Default expected values:

URI: bolt://localhost:7687
User: neo4j
Password: password

Create indexes and constraints

Run this after loading data into Neo4j:

```bash
python kg_service/setup_indexes.py
```

Start service 
```bash
uvicorn kg_service.app.main:app --reload
```

Open swagger 
```bash
http://127.0.0.1:8000/docs
```
## stratergy overview 

1. Entity Lookup 
Used for direct entity retrieval by:

paper id
title
DOI
journal ref
submitter
author name
category name

Example intent:

"What is paper 0704.0001?"
"Which paper is titled 'Attention Is All You Need'?"

2. Relation Filter 

Used for direct entity retrieval by:

paper id
title
DOI
journal ref
submitter
author name
category name

Example intent:

"What is paper 0704.0001?"
"Which paper is titled 'Attention Is All You Need'?"

3. Multi-Hop 

Used for 1-hop relationships such as:

author -> papers
paper -> authors
paper -> categories
category -> papers
papers in multiple categories

Example intent:

"Who are the authors of paper 0704.0001?"
"Which papers are written by Christopher Hitchcock?"

## Example Queries that work

1. /kg/query/entity

```bash
    What is paper 0704.0001?
    Which paper is titled "Attention Is All You Need"?
    What is the DOI of the paper 0704.0001?
   Which papers are submitted by Pavel Nadolsky?
   What papers are in category cs.AI?
```

2. /kg/query/relation

```bash
    Who are the authors of paper 0704.0001?
   `Which categories does paper 0704.0001 belong to?
    Which papers are written by Christopher Hitchcock?
    What papers are in the category cs.AI?
    How many papers are written by Christopher Hitchcock?
```

3. /kg/query/multi_hop - 2 hop

```bash

Which authors have written papers in cs.AI?
What fields has Christopher Hitchcock published in?
Which papers are written by the same author as paper 1609.01491?
```
3. /kg/query/multi_hop - 3 hop

```bash
Which papers are in the same categories as Christopher Hitchcock’s papers?
```

4. /kg/query/multi_hop - 4 hop
```bash
Which authors are related to Christopher Hitchcock?
What categories are related to cs.AI?
Which papers are related to paper 1609.01491?
```