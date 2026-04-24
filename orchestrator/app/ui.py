"""Self-contained HTML UI for the orchestrator query page."""

UI_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Adaptive Knowledge Router</title>
<style>
  *, *::before, *::after { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    margin: 0; padding: 0;
    background: #f5f7fa; color: #1a1a2e;
  }
  .container { max-width: 960px; margin: 0 auto; padding: 24px 16px; }
  h1 { font-size: 1.5rem; margin: 0 0 20px; }
  h1 span { color: #6c63ff; }

  /* ── query form ─── */
  .query-form { display: flex; gap: 8px; margin-bottom: 24px; }
  .query-form input {
    flex: 1; padding: 10px 14px; font-size: 1rem;
    border: 1px solid #ccc; border-radius: 8px; outline: none;
  }
  .query-form input:focus { border-color: #6c63ff; }
  .query-form button {
    padding: 10px 20px; font-size: 1rem; font-weight: 600;
    color: #fff; background: #6c63ff; border: none; border-radius: 8px;
    cursor: pointer;
  }
  .query-form button:disabled { opacity: .5; cursor: wait; }

  /* ── cards ─── */
  .card {
    background: #fff; border-radius: 10px;
    box-shadow: 0 1px 4px rgba(0,0,0,.08);
    padding: 20px; margin-bottom: 16px;
  }
  .card h2 { font-size: 1.1rem; margin: 0 0 12px; }
  .card h2 .badge {
    display: inline-block; font-size: .75rem; font-weight: 600;
    padding: 2px 8px; border-radius: 4px; vertical-align: middle;
    margin-left: 8px;
  }
  .badge-kg   { background: #e0f7fa; color: #00695c; }
  .badge-rag  { background: #fce4ec; color: #b71c1c; }

  /* ── metadata table ─── */
  .meta-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 6px 16px; font-size: .88rem; margin-bottom: 8px;
  }
  .meta-grid .label { color: #777; }
  .meta-grid .value { color: #777; font-weight: 500; }

  /* ── synthesized answer ─── */
  .answer-text {
    line-height: 1.65;
    font-size: .95rem;
  }
  .answer-text ul, .answer-text ol { margin: 4px 0 4px 20px; padding: 0; }
  .answer-text li { margin-bottom: 4px; }
  .answer-text p { margin: 6px 0; }
  .answer-text strong { font-weight: 600; }
  .answer-text code { background: #f0f0f0; padding: 1px 5px; border-radius: 3px; font-size: .9em; }

  .error-text { color: #c62828; font-style: italic; }

  /* ── raw JSON ─── */
  .json-toggle {
    font-size: .85rem; color: #6c63ff; cursor: pointer;
    border: none; background: none; padding: 0; font-weight: 600;
  }
  .json-block {
    margin-top: 8px; padding: 12px; font-size: .8rem;
    background: #f8f8f8; border-radius: 6px; overflow-x: auto;
    white-space: pre-wrap; word-break: break-all;
    max-height: 500px; overflow-y: auto;
    display: none;
  }
  .json-block.open { display: block; }

  .spinner {
    display: inline-block; width: 16px; height: 16px;
    border: 2px solid #ccc; border-top-color: #6c63ff;
    border-radius: 50%; animation: spin .6s linear infinite;
    vertical-align: middle; margin-right: 6px;
  }
  @keyframes spin { to { transform: rotate(360deg); } }

  #status { font-size: .9rem; color: #555; min-height: 22px; margin-bottom: 12px; }
  #results-area { display: none; }
</style>
</head>
<body>
<div class="container">
  <h1><span>&#9670;</span> Adaptive Knowledge Router</h1>

  <form class="query-form" id="queryForm">
    <input type="text" id="queryInput" placeholder="Ask a question…"
           autocomplete="off" required>
    <button type="submit" id="submitBtn">Search</button>
  </form>

  <div id="status"></div>
  <div id="results-area"></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
const form     = document.getElementById('queryForm');
const input    = document.getElementById('queryInput');
const btn      = document.getElementById('submitBtn');
const status   = document.getElementById('status');
const results  = document.getElementById('results-area');

form.addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q) return;

  btn.disabled = true;
  status.innerHTML = '<span class="spinner"></span> Querying…';
  results.style.display = 'none';
  results.innerHTML = '';

  try {
    const resp = await fetch('/query', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({query: q}),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || resp.statusText);
    }
    const data = await resp.json();
    renderResponse(data);
  } catch (err) {
    status.textContent = 'Error: ' + err.message;
  } finally {
    btn.disabled = false;
  }
});

/* ── render helpers ─── */
function esc(s) {
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function renderResponse(data) {
  status.textContent = '';
  results.style.display = 'block';

  const sourceBadge = data.source === 'kg'
    ? '<span class="badge badge-kg">KG</span>'
    : '<span class="badge badge-rag">RAG</span>';

  /* ── synthesis card ─── */
  let synthesisHTML = '';
  if (data.synthesized_answer || data.synthesis_metadata) {
    const meta = data.synthesis_metadata || {};
    synthesisHTML = `
      <div class="card">
        <h2>Synthesized Answer ${sourceBadge}</h2>
        <div class="meta-grid">
          <div><span class="label">Strategy</span></div>
          <div><span class="value">${esc(data.strategy)}</span></div>
          <div><span class="label">Confidence</span></div>
          <div><span class="value">${(data.confidence * 100).toFixed(1)}%</span></div>
          <div><span class="label">Model</span></div>
          <div><span class="value">${esc(meta.model || '—')}</span></div>
          <div><span class="label">Query mode</span></div>
          <div><span class="value">${esc(meta.query_mode || '—')}</span></div>
          <div><span class="label">Retrieval latency</span></div>
          <div><span class="value">${meta.retrieval_latency_ms != null ? meta.retrieval_latency_ms.toFixed(0) + ' ms' : '—'}</span></div>
          <div><span class="label">Synthesis latency</span></div>
          <div><span class="value">${meta.synthesis_latency_ms != null ? meta.synthesis_latency_ms.toFixed(0) + ' ms' : '—'}</span></div>
          <div><span class="label">Total latency</span></div>
          <div><span class="value">${meta.total_latency_ms != null ? meta.total_latency_ms.toFixed(0) + ' ms' : '—'}</span></div>
          <div><span class="label">Results used</span></div>
          <div><span class="value">${meta.used_results_count ?? '—'}</span></div>
          <div><span class="label">Cached</span></div>
          <div><span class="value">${meta.cached ? 'Yes ⚡' : 'No'}</span></div>
        </div>`;

    if (meta.error) {
      synthesisHTML += `<p class="error-text">Synthesis error: ${esc(meta.error)}</p>`;
    }

    if (data.synthesized_answer) {
      synthesisHTML += `<div class="answer-text">${renderMarkdown(data.synthesized_answer)}</div>`;
    }
    synthesisHTML += '</div>';
  }

  /* ── raw JSON card ─── */
  const rawJSON = JSON.stringify(data, null, 2);
  const rawCard = `
    <div class="card">
      <h2>Raw Response &amp; Retrieved Results
        <span style="font-size:.85rem;color:#777;font-weight:400;">
          (${(data.results || []).length} results)
        </span>
      </h2>
      <button class="json-toggle" onclick="this.nextElementSibling.classList.toggle('open')">
        Show / hide JSON
      </button>
      <pre class="json-block">${esc(rawJSON)}</pre>
    </div>`;

  results.innerHTML = synthesisHTML + rawCard;
}

/**
 * Render synthesized answer as proper markdown HTML.
 * Uses the marked library to convert markdown to formatted HTML.
 * Falls back to escaped text with preserved whitespace if marked is unavailable.
 */
function renderMarkdown(text) {
  // Normalise escaped newlines that may leak from JSON serialisation
  text = text.replace(/\\\\n/g, '\\n');

  if (typeof marked !== 'undefined' && marked.parse) {
    // Configure marked for safe, clean output
    marked.setOptions({ breaks: true, gfm: true });
    return marked.parse(text);
  }
  // Fallback: escape and preserve whitespace
  return '<p style="white-space:pre-wrap">' + esc(text) + '</p>';
}
</script>
</body>
</html>
"""
