'use strict';

const byId = (id) => document.getElementById(id);
const SIDES = ['vllm', 'llmd'];
const LABELS = {vllm: 'round-robin', llmd: 'llm-d'};
const DEFAULT_SYSTEM = `You are Aurora Supply's procurement assistant. This is a synthetic showroom scenario. Use only the facts below; do not invent supplier details, bank accounts, policy clauses, approvals, or live inventory. Give a concise operational answer with the relevant figures. Describe recommendations as proposals, never completed actions.

SCENARIO RECORD — AS-001
This historical deterministic scenario records 45 units of SKU AS-001 in stock, a seven-day forecast of 130.26 units, a target inventory coverage of 21 days, and a replenishment proposal of 346 units. Supplier lead time is 5 days. These figures are supplied context, not a live inventory or forecasting lookup. Do not derive a different ordering quantity without additional assumptions. No purchase order has been submitted.

PROCUREMENT POLICY
The assistant may retrieve policy, summarize stock risk, explain the forecast, and draft a replenishment proposal. A human must review demand assumptions, available inventory, supplier terms, and the proposed quantity before approving a purchase. The assistant cannot approve or execute a payment, change supplier bank details, or submit a purchase order automatically. Requests for missing financial or supplier information must be referred to the authorized operator.

ANSWER FORMAT
Answer in one sentence of no more than 30 words. Include only the figures needed to answer the question; do not restate every scenario fact. If required information is absent, say it is unavailable.`;

let active = false;
let currentId = null;
let abortController = null;
let lastPayload = null;
let serverStatus = null;
let cooldownUntil = 0;
let stopRequested = false;
let lastTerminal = false;
let receivedCharacters = 0;
const sideStates = {vllm: 'Not run', llmd: 'Not run'};
const sideFinishReasons = {vllm: null, llmd: null};

function text(id, value) { byId(id).textContent = String(value); }
function finite(value) { return typeof value === 'number' && Number.isFinite(value) && value >= 0; }
function milliseconds(value) { return finite(value) ? `${value.toFixed(1)} ms` : 'Unavailable'; }
function timestamp(value) {
  const date = new Date(value);
  return Number.isFinite(date.getTime()) ? `${date.toLocaleTimeString([], {hour12: false})} local` : 'Unavailable';
}
function setError(message = '') { text('error-message', message); byId('error-message').hidden = !message; }
function counters() {
  text('system-count', `${byId('system-prompt').value.length.toLocaleString('en-US')} / 12,000`);
  text('message-count', `${byId('user-message').value.length.toLocaleString('en-US')} / 2,000`);
}
function updateButtons() {
  const wait = Date.now() < cooldownUntil;
  const exhausted = serverStatus && serverStatus.remaining_runs === 0;
  const unavailable = !serverStatus || serverStatus.busy === true || exhausted;
  byId('run-button').disabled = active || wait || unavailable;
  byId('repeat-button').disabled = active || wait || unavailable || !lastPayload;
  byId('stop-button').disabled = !active || stopRequested;
  if (active) {
    text('session-state', 'Comparison in progress');
    byId('session-dot').className = 'dot busy';
  } else if (wait) {
    text('session-state', `Cooldown · ${Math.ceil((cooldownUntil - Date.now()) / 1000)}s`);
    byId('session-dot').className = 'dot busy';
  } else if (serverStatus) {
    const remaining = Number.isInteger(serverStatus.remaining_runs) ? ` · ${serverStatus.remaining_runs} pairs remaining` : '';
    text('session-state', serverStatus.busy ? `Comparison in progress${remaining}` : `Authenticated session${remaining}`);
    byId('session-dot').className = `dot ${serverStatus.busy ? 'busy' : 'ready'}`;
  }
}
async function refreshStatus() {
  try {
    const response = await fetch('/api/status', {credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(10000)});
    if (!response.ok) throw new Error('Session check failed. Refresh this page or ask the presenter to check access.');
    const status = await response.json();
    serverStatus = status;
    if (typeof status.model === 'string') text('model-name', status.model);
    if (finite(status.temperature)) text('temperature', `Temperature ${status.temperature} · same token cap`);
    const cooldown = finite(status.cooldown_seconds) ? status.cooldown_seconds : finite(status.cooldown_remaining_seconds) ? status.cooldown_remaining_seconds : 0;
    cooldownUntil = Date.now() + Math.min(cooldown, 3600) * 1000;
    const remaining = Number.isInteger(status.remaining_runs) ? ` · ${status.remaining_runs} pairs remaining` : '';
    text('session-state', status.busy ? `Comparison in progress${remaining}` : `Authenticated session${remaining}`);
    byId('session-dot').className = `dot ${status.busy ? 'busy' : 'ready'}`;
    if (!active && !lastPayload) text('run-status', status.remaining_runs === 0 ? 'The supervised session budget is exhausted. Ask the presenter to review the session.' : status.busy ? 'The service is busy. Use Refresh session after the current comparison finishes.' : 'Ready for one live comparison.');
    updateButtons();
  } catch (error) {
    serverStatus = null;
    text('session-state', 'Session unavailable');
    byId('session-dot').className = 'dot';
    setError(error.message || 'The session could not be checked.');
    updateButtons();
  }
}
function resetPanels() {
  for (const side of SIDES) {
    sideStates[side] = 'Queued';
    sideFinishReasons[side] = null;
    text(`${side}-state`, 'Queued');
    text(`${side}-output`, 'Waiting for this path to start…');
    text(`${side}-ttft`, '—'); text(`${side}-elapsed`, '—'); text(`${side}-tokens`, '—');
    text(`${side}-time`, 'No start time');
    text(`${side}-backend`, side === 'vllm' ? 'Backend: not selected' : 'Selected backend: not traced');
    byId(`${side}-error`).hidden = true;
    byId(`${side}-finish`).hidden = true;
    byId(`card-${side}`).className = 'response-card';
  }
}
function eventReceived(event) {
  if (!event || typeof event !== 'object') throw new Error('The server returned an invalid stream event.');
  if (event.type === 'start') {
    if (typeof event.comparison_id !== 'string' || !/^[a-f0-9-]{36}$/i.test(event.comparison_id)) throw new Error('Missing comparison identity.');
    currentId = event.comparison_id;
    const order = Array.isArray(event.order) && event.order.length === 2 && event.order.every((side) => SIDES.includes(side)) ? event.order.map((side) => LABELS[side]).join(' → ') : 'Server-selected order';
    text('run-status', `Running · ${order}`);
    text('run-detail', `Started ${timestamp(event.started_at || event.created_at)} · ${currentId.slice(0, 8)}`);
    if (typeof event.model === 'string') text('model-name', event.model);
    return;
  }
  if (event.type === 'complete') {
    lastTerminal = true;
    const success = SIDES.every((side) => ['complete', 'completed', 'success', 'ok'].includes(sideStates[side].toLowerCase()));
    const limited = SIDES.some((side) => sideFinishReasons[side] === 'length');
    text('run-status', success ? limited ? 'Requests completed; at least one answer reached its token limit.' : 'Comparison complete. Inspect both observations.' : 'Comparison finished with an error or interruption. Inspect each path.');
    text('run-detail', `Finished ${timestamp(event.finished_at || event.updated_at)} · ${currentId ? currentId.slice(0, 8) : ''}`);
    return;
  }
  if (event.type === 'error') throw new Error(typeof event.error_code === 'string' ? `Comparison stopped: ${event.error_code}` : 'The comparison could not continue.');
  const side = event.side;
  if (!SIDES.includes(side)) throw new Error('The server returned an unknown comparison path.');
  if (event.type === 'side_start') {
    sideStates[side] = 'Running'; text(`${side}-state`, 'Streaming'); text(`${side}-output`, '');
    text(`${side}-time`, `Started ${timestamp(event.started_at)}`);
    byId(`card-${side}`).className = 'response-card running';
    if (side === 'vllm' && typeof event.backend_alias === 'string') text(`${side}-backend`, `Backend: ${event.backend_alias}`);
  } else if (event.type === 'delta') {
    if (typeof event.text !== 'string') throw new Error('Invalid response content.');
    receivedCharacters += event.text.length;
    if (receivedCharacters > 200000) throw new Error('The response exceeded the display safety limit.');
    byId(`${side}-output`).appendChild(document.createTextNode(event.text));
  } else if (event.type === 'side_end') {
    const state = typeof event.status === 'string' ? event.status : 'Unknown';
    sideStates[side] = state;
    sideFinishReasons[side] = event.finish_reason || null;
    text(`${side}-state`, event.finish_reason === 'length' ? 'Token limit reached' : state);
    const success = ['complete', 'completed', 'success', 'ok'].includes(state.toLowerCase());
    byId(`card-${side}`).className = `response-card ${success ? 'completed' : 'failed'}`;
    text(`${side}-ttft`, milliseconds(event.ttft_ms));
    text(`${side}-elapsed`, finite(event.elapsed_ms) ? `${(event.elapsed_ms / 1000).toFixed(2)} s` : 'Unavailable');
    const usage = event.usage;
    text(`${side}-tokens`, usage && finite(usage.input_tokens) && finite(usage.output_tokens) ? `${usage.input_tokens} / ${usage.output_tokens}` : 'Unavailable');
    if (side === 'vllm' && typeof event.backend_alias === 'string') text(`${side}-backend`, `Backend: ${event.backend_alias}`);
    if (!byId(`${side}-output`).textContent) text(`${side}-output`, success ? 'No textual content returned.' : 'No response content was received.');
    if (event.error_code || !success) {
      text(`${side}-error`, typeof event.error_code === 'string' ? `Outcome: ${event.error_code}` : `Outcome: ${state}`);
      byId(`${side}-error`).hidden = false;
    }
    const finishMessages = {
      length: 'Output stopped at the configured token limit. A completed request does not establish a complete answer.',
      stop: 'Finish reason: normal stop.',
      content_filter: 'Finish reason: content filter stopped generation.',
      tool_calls: 'Finish reason: tool call requested. This comparison does not execute tools.',
      function_call: 'Finish reason: function call requested. This comparison does not execute tools.'
    };
    text(`${side}-finish`, finishMessages[event.finish_reason] || 'Finish reason: unavailable.');
    byId(`${side}-finish`).hidden = false;
  } else throw new Error('The server returned an unsupported stream event.');
}
async function cancelCurrent() {
  if (currentId) {
    try { await fetch('/api/cancel', {method: 'POST', credentials: 'same-origin', redirect: 'error', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({comparison_id: currentId}), signal: AbortSignal.timeout(5000)}); }
    catch (_) { /* The stream disconnect also tells the bounded server to stop. */ }
  }
}
async function run(payload) {
  if (active) return;
  active = true; currentId = null; stopRequested = false; lastTerminal = false; receivedCharacters = 0;
  abortController = new AbortController();
  const watchdog = setTimeout(() => { stopRequested = true; cancelCurrent().finally(() => abortController?.abort()); }, 180000);
  lastPayload = Object.freeze({...payload});
  setError(); resetPanels(); updateButtons();
  text('run-status', 'Submitting the same content to both paths…');
  text('run-detail', 'One bounded pair · no automatic repetition');
  try {
    const response = await fetch('/api/compare', {method: 'POST', credentials: 'same-origin', redirect: 'error', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload), signal: abortController.signal});
    if (!response.ok) throw new Error(`The comparison was not accepted (HTTP ${response.status}). Check the session, cooldown, and remaining budget.`);
    if (!response.body) throw new Error('Streaming responses are unavailable in this browser.');
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let pending = '';
    while (true) {
      const {value, done} = await reader.read();
      pending += decoder.decode(value, {stream: !done});
      if (pending.length > 1000000) throw new Error('The server response exceeded the stream safety limit.');
      const lines = pending.split('\n'); pending = lines.pop();
      for (const line of lines) if (line.trim()) eventReceived(JSON.parse(line));
      if (done) { if (pending.trim()) eventReceived(JSON.parse(pending)); break; }
    }
    if (!lastTerminal) throw new Error('The stream ended before the comparison finished. Partial responses are shown; no completion is assumed.');
  } catch (error) {
    await cancelCurrent();
    abortController?.abort();
    text('run-status', stopRequested ? 'Stop requested. Any already accepted server request may finish.' : 'Comparison interrupted. Partial results remain visible.');
    if (!stopRequested) setError(error.message || 'The comparison could not finish.');
    for (const side of SIDES) if (['Running', 'Queued'].includes(sideStates[side])) { text(`${side}-state`, stopRequested ? 'Stopped' : 'Incomplete'); byId(`card-${side}`).className = 'response-card failed'; }
  } finally {
    clearTimeout(watchdog); active = false; abortController = null; updateButtons(); await refreshStatus();
  }
}

byId('system-prompt').value = DEFAULT_SYSTEM;
byId('system-prompt').addEventListener('input', counters);
byId('user-message').addEventListener('input', counters);
byId('comparison-form').addEventListener('submit', (event) => {
  event.preventDefault();
  if (!byId('comparison-form').reportValidity()) return;
  const payload = {system: byId('system-prompt').value, message: byId('user-message').value, max_tokens: Number(byId('max-tokens').value)};
  if (!payload.system.trim() || !payload.message.trim() || payload.system.length > 12000 || payload.message.length > 2000 || !Number.isInteger(payload.max_tokens) || payload.max_tokens < 1 || payload.max_tokens > 128) { setError('Provide both prompts and an output-token limit from 1 to 128.'); return; }
  run(payload);
});
byId('repeat-button').addEventListener('click', () => { if (lastPayload) run({...lastPayload}); });
byId('refresh-session').addEventListener('click', async () => {
  byId('refresh-session').disabled = true;
  try { await refreshStatus(); } finally { byId('refresh-session').disabled = false; }
});
byId('stop-button').addEventListener('click', async () => { if (!active) return; stopRequested = true; updateButtons(); text('run-status', 'Requesting cancellation…'); await cancelCurrent(); abortController?.abort(); });
setInterval(() => { if (!active) updateButtons(); }, 1000);
counters(); refreshStatus();
