from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from rag import Retriever, ask

retriever = Retriever(os.environ.get("DOCUMENTS_DIR", "/app/data/documents"))
PAGE = '''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Aurora Supply · RAG</title>
<style>body{max-width:900px;margin:40px auto;font:18px system-ui;padding:20px;background:#f4f5f7;color:#171f2c}textarea{width:100%;height:100px;font:inherit}button{padding:12px 25px;background:#c00;color:white;border:0;margin:15px 0}pre{white-space:pre-wrap;background:white;padding:25px}small{color:#495466}</style>
<h1>Aurora Supply</h1><p>Políticas + ferramentas MCP + previsão + LLM via MaaS.</p>
<small>Dados fictícios e históricos. Recuperação lexical TF-IDF. Nenhuma compra é executada.</small>
<p><textarea id="question">Devo repor AS-001? Consulte estoque e previsão, explique a política e a aprovação necessária.</textarea></p>
<button id="send">Consultar assistente</button><pre id="result">Pronto para o test drive.</pre>
<script>document.querySelector('#send').onclick=async()=>{const b=document.querySelector('#send'),r=document.querySelector('#result');b.disabled=true;r.textContent='Consultando fontes e ferramentas...';try{const x=await fetch('/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:document.querySelector('#question').value})});const d=await x.json();r.textContent=d.error||d.answer+'\\n\\nFontes: '+d.sources.map(x=>x.document_id).join(', ')+'\\nFerramentas: '+d.tools_used.join(', ')+'\\nTrace: '+(d.trace_id||'desativado');}catch(e){r.textContent='Falha ao acessar o assistente';}finally{b.disabled=false;}};</script></html>'''

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
        except (ValueError, json.JSONDecodeError):
            self.reply(400, {"error": "Pergunta ou JSON inválido"})
        except Exception as error:
            # Log type only: never reflect upstream bodies, credentials or request headers.
            print("request failed:", type(error).__name__, flush=True)
            self.reply(502, {"error": "Falha na integração. Verifique MaaS, MCP Gateway e MLflow; nenhuma resposta foi simulada."})
    def reply(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode(); self.send_response(code); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def log_message(self, format, *args):
        return

ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
