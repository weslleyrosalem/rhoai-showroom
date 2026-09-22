from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from rag import Retriever, ask, GuardrailBlocked

retriever = Retriever(os.environ.get("DOCUMENTS_DIR", "/app/data/documents"))
PAGE = '''<!doctype html><html lang="en-US"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aurora Supply · Test drive</title>
<style>:root{font-family:system-ui,sans-serif;color:#172332;background:#f3f5f7}*{box-sizing:border-box}body{margin:0}header{background:#172332;color:white;padding:28px max(6vw,24px);border-bottom:5px solid #e00}header small{letter-spacing:.16em;color:#b7c7d8}h1{font-size:38px;margin:10px 0}main{max-width:1100px;margin:32px auto;padding:0 24px;display:grid;grid-template-columns:1fr 1.25fr;gap:24px}section{background:white;border:1px solid #d8dfe6;border-radius:12px;padding:26px;box-shadow:0 4px 12px #17233208}h2{margin-top:0;font-size:23px}label{display:block;font-weight:650;margin:18px 0 8px}select,textarea{width:100%;font:inherit;border:1px solid #9ba9b8;border-radius:5px;padding:12px}textarea{height:180px;resize:vertical;line-height:1.5}button{background:#c00;color:white;font:inherit;border:0;border-radius:5px;padding:13px 22px;cursor:pointer}button:disabled{opacity:.6;cursor:wait}.muted,small{color:#4e6175;line-height:1.6}.chip{display:inline-block;background:#eaf1f6;color:#304b65;border-radius:20px;padding:5px 10px;margin:4px 5px 0 0;font-size:13px}.answer{white-space:pre-wrap;line-height:1.65;min-height:180px}.status{padding:10px 0;font-size:14px;color:#3a5e50}code{font-size:12px;overflow-wrap:anywhere}footer{padding:0 24px 30px;text-align:center;color:#526477;font-size:13px}a{color:#075ba5}#decision{white-space:pre-line;border:1px solid #adc6b8;border-radius:6px;padding:12px}#meta{border-top:1px solid #e2e7ed;margin-top:20px;padding-top:15px} @media(max-width:750px){main{grid-template-columns:1fr}h1{font-size:30px}}</style>
<header><small>OPENSHIFT AI · SHOWROOM</small><h1>Aurora Supply</h1><p>From demand forecasting to an explainable decision.</p></header>
<main><section><h2>Take the wheel</h2><p class="muted">Explore policies, inventory, and demand forecasts. The assistant prepares a proposal for human approval.</p><label for="sku">Catalog product</label><select id="sku"><option>AS-001</option><option>AS-002</option><option>AS-003</option><option>AS-004</option><option>AS-005</option><option>AS-006</option><option>AS-007</option><option>AS-008</option></select><label for="question">Your question</label><textarea id="question" maxlength="4000">Should I replenish AS-001? Check stock and the forecast, then explain the policy and required approval.</textarea><p><button id="send">Ask the assistant →</button></p><small>Also try: “What is the return deadline?” or “Who approves purchases above 5,000?”</small></section>
<section aria-live="polite"><h2>A decision with evidence</h2><div id="status" class="status">Ready for your test drive.</div><div id="decision" hidden class="status"></div><p class="muted">AI-generated explanation — verify its claims against the sources and tool-calculated proposal.</p><div id="answer" class="answer muted">Your explanation will appear here with its sources and tool calls.</div><div id="meta" hidden><strong>Sources consulted</strong><div id="sources"></div><p><strong>MCP tools</strong><br><span id="tools"></span></p><p><strong>MLflow trace</strong><br><code id="trace"></code></p><p id="usage" class="muted"></p></div></section></main>
<footer>Synthetic, historical data · Lexical TF-IDF retrieval · NeMo Guardrails · MCP Gateway · MaaS · MLflow<br>No purchases are executed. Tools report the forecast time period.</footer>
<script>const q=document.querySelector('#question'),b=document.querySelector('#send'),status=document.querySelector('#status'),answer=document.querySelector('#answer');document.querySelector('#sku').onchange=e=>{q.value='Should I replenish '+e.target.value+'? Check stock and the forecast, then explain the policy and required approval.';};b.onclick=async()=>{b.disabled=true;status.textContent='Checking safety, sources, and tools…';document.querySelector('#meta').hidden=true;document.querySelector('#decision').hidden=true;answer.textContent='';try{const x=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q.value})}),d=await x.json();if(!x.ok)throw new Error(d.error||'The request could not be completed');answer.classList.remove('muted');answer.textContent=d.answer;status.textContent='✓ Input/output safety checks passed · Factual review required';const sources=document.querySelector('#sources');sources.replaceChildren();d.sources.forEach(s=>{const el=document.createElement('span');el.className='chip';el.textContent=s.document_id;sources.appendChild(el);});document.querySelector('#tools').textContent=d.tools_used.join(', ')||'No tools needed';document.querySelector('#trace').textContent=d.trace_id||'Unavailable';document.querySelector('#usage').textContent='Model: '+d.model+' · Tokens: '+(d.usage.total_tokens||'not reported');document.querySelector('#meta').hidden=false;const decision=document.querySelector('#decision');if(d.decision){const v=d.decision,f=v.forecast||{};const num=x=>new Intl.NumberFormat('en-US',{maximumFractionDigits:2}).format(x),role=({operations_manager:'Operations manager',assigned_buyer:'Assigned buyer'})[v.approval_role]||'Human review required';decision.textContent='Tool-calculated proposal: '+num(v.recommended_quantity)+' units × '+num(v.unit_price)+' = '+num(v.estimated_total)+' demo currency units\\nApproval: '+role+' · Stock: '+num(v.stock)+' · Target: '+num(v.target_stock)+' units\\nHistorical forecast: '+(f.forecast_origin||'unavailable')+' · Horizon: '+(f.horizon_days??'unavailable')+' days · Inventory coverage target: '+v.coverage_days+' days\\nSynthetic data · No order created';decision.hidden=false;}}catch(e){status.textContent='Request not completed';answer.textContent=e.message;}finally{b.disabled=false;}};</script></html>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/healthz":
            self.reply(200, {"status": "ok", "retrieval": "TF-IDF", "documents": len(retriever.documents)})
        elif self.path == "/":
            data = PAGE.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
        else:
            self.reply(404, {"error": "Not found"})
    def do_POST(self):
        if self.path != "/ask":
            return self.reply(404, {"error": "Not found"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if size <= 0 or size > 16384:
                return self.reply(400, {"error": "Invalid request size"})
            body = json.loads(self.rfile.read(size))
            self.reply(200, ask(body.get("question"), retriever))
        except GuardrailBlocked:
            self.reply(422, {"error": "Content blocked by guardrails. Rephrase your question without personal data or automatic purchase instructions."})
        except (ValueError, json.JSONDecodeError):
            self.reply(400, {"error": "Invalid question or JSON"})
        except Exception as error:
            # Log type only: never reflect upstream bodies, credentials or request headers.
            print("request failed:", type(error).__name__, flush=True)
            self.reply(502, {"error": "An integration failed. Check MaaS, MCP Gateway, and MLflow. No response was simulated."})
    def reply(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, format, *args):
        return

ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
