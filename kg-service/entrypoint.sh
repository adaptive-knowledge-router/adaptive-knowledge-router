#!/bin/bash
set -e

echo "Waiting for Ollama to be ready..."
until python3 -c "import urllib.request; urllib.request.urlopen('http://ollama:11434/api/tags')" 2>/dev/null; do
    echo "  Ollama not ready yet, retrying in 3s..."
    sleep 3
done
echo "Ollama is ready. Pulling model if needed..."
python3 -c "
import urllib.request, json
data = json.dumps({'name': 'qwen2.5:3b'}).encode()
req = urllib.request.Request('http://ollama:11434/api/pull', data=data, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req).read()
"
echo "Model ready."

echo "Waiting for Neo4j to be ready..."
until python3 -c "
from neo4j import GraphDatabase
import os
d = GraphDatabase.driver(
    os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'password'))
)
d.verify_connectivity()
d.close()
" 2>/dev/null; do
    echo "  Neo4j not ready yet, retrying in 3s..."
    sleep 3
done

echo "Neo4j is ready. Loading data..."
python3 scripts/load_arxiv_to_neo4j.py
echo "Data loaded."

echo "Starting KG service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
