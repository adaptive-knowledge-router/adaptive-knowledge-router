#!/usr/bin/env sh
set -e

echo "[kg-service] Step 1/5: Waiting for Ollama API..."
until python3 -c "import urllib.request; urllib.request.urlopen('http://ollama:11434/api/tags')" 2>/dev/null; do
    echo "  Ollama not ready yet, retrying in 3s..."
    sleep 3
done
echo "[kg-service] Step 1/5: Ollama API is reachable."

echo "[kg-service] Step 2/5: Pulling model if needed..."
python3 -c "
import urllib.request, json
data = json.dumps({'name': '${OLLAMA_MODEL:-qwen2.5:3b}'}).encode()
req = urllib.request.Request('http://ollama:11434/api/pull', data=data, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req).read()
"
echo "[kg-service] Step 2/5: Model pull complete."

echo "[kg-service] Step 3/5: Warming up model (may take a while on first run)..."
# Warm-up is best-effort: retry up to 3 times, but never block service start.
WARMUP_OK=0
for attempt in 1 2 3; do
    if python3 -c "
import urllib.request, json
data = json.dumps({
    'model': '${OLLAMA_MODEL:-qwen2.5:3b}',
    'prompt': 'hi',
    'stream': False,
    'options': {'num_predict': 1}
}).encode()
req = urllib.request.Request('http://ollama:11434/api/generate', data=data,
                             headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req, timeout=180).read()
" 2>/dev/null; then
        WARMUP_OK=1
        break
    fi
    echo "  Warm-up attempt $attempt failed, retrying..."
done
if [ "$WARMUP_OK" = "1" ]; then
    echo "[kg-service] Step 3/5: Model warm and ready."
else
    echo "[kg-service] Step 3/5: Warm-up did not complete — first query will be slower."
fi

echo "[kg-service] Step 4/5: Waiting for Neo4j..."
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
echo "[kg-service] Step 4/5: Neo4j is reachable."

echo "[kg-service] Step 5/5: Checking if data already loaded..."
NODE_COUNT=$(python3 -c "
from neo4j import GraphDatabase
import os
d = GraphDatabase.driver(
    os.getenv('NEO4J_URI', 'bolt://localhost:7687'),
    auth=(os.getenv('NEO4J_USER', 'neo4j'), os.getenv('NEO4J_PASSWORD', 'password'))
)
with d.session() as s:
    print(s.run('MATCH (n) RETURN count(n) AS c').single()['c'])
d.close()
")

if [ "$NODE_COUNT" -gt 0 ] 2>/dev/null; then
    echo "[kg-service] Database already has $NODE_COUNT nodes, skipping data load."
else
    echo "[kg-service] Database is empty. Loading data..."
    python3 scripts/load_arxiv_to_neo4j.py
    echo "[kg-service] Data loaded."
fi

echo "[kg-service] Starting uvicorn..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
