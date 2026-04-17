#!/usr/bin/env sh
set -e

OLLAMA_URL="${ORCH_OLLAMA_URL:-http://ollama:11434}"
ANSWER_MODEL="${ORCH_ANSWER_MODEL:-qwen2.5:1.5b}"

echo "[orchestrator] Step 1/3: Waiting for Ollama API at ${OLLAMA_URL} ..."
until python3 -c "import urllib.request; urllib.request.urlopen('${OLLAMA_URL}/api/tags')" 2>/dev/null; do
    echo "  Ollama not ready yet, retrying in 3s..."
    sleep 3
done
echo "[orchestrator] Step 1/3: Ollama API is reachable."

echo "[orchestrator] Step 2/3: Pulling synthesis model '${ANSWER_MODEL}' if needed..."
python3 -c "
import urllib.request, json
data = json.dumps({'name': '${ANSWER_MODEL}'}).encode()
req = urllib.request.Request('${OLLAMA_URL}/api/pull', data=data, headers={'Content-Type': 'application/json'})
urllib.request.urlopen(req, timeout=600).read()
"
echo "[orchestrator] Step 2/3: Model pull complete."

echo "[orchestrator] Step 3/3: Starting orchestrator..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8003
