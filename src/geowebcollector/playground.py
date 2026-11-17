"""Standalone local-only browser extraction playground."""
import asyncio
import json
from datetime import datetime,timezone
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from importlib.resources import files
from .browser import BrowserExtractor,HtmlDocument
from .models import Evidence,Rights,Permission,Quality,RequestContext
def catalog():
    return {"extract_html":{"description":"Extract CSS selectors from supplied HTML using isolated Chromium; no website navigation","example":{"html":"<h1>Hello world</h1>","selectors":{"title":"h1"},"purpose":"local-demo"}}}
async def extract(params):
    html=params["html"];selectors=params["selectors"];purpose=params.get("purpose","local-demo")
    ev=Evidence(id="local-test",source_id="manual",source_type="user_supplied",source_ref="local-playground",
        retrieved_at=datetime.now(timezone.utc),method_version="playground-v1",
        rights=Rights(use=Permission.allowed,permitted_purpose=purpose),quality=Quality(verification="unverified"))
    doc=HtmlDocument(html=html,evidence=ev,purpose=purpose)
    async with BrowserExtractor(enabled=True) as extractor:
        return (await extractor.extract(doc,selectors,RequestContext(request_id="local-playground"))).model_dump(mode="json")
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path=="/":
            content=files("geowebcollector").joinpath("playground.html").read_bytes();mime="text/html; charset=utf-8"
        elif self.path=="/api/operations":
            content=json.dumps({"operations":catalog()}).encode();mime="application/json"
        else:self.send_error(404);return
        self.send_response(200);self.send_header("Content-Type",mime);self.send_header("Content-Length",str(len(content)));self.end_headers();self.wfile.write(content)
    def do_POST(self):
        if self.path!="/api/run":self.send_error(404);return
        try:
            length=int(self.headers.get("Content-Length","0"))
            if not 0<length<=100000:raise ValueError("Invalid request size")
            req=json.loads(self.rfile.read(length))
            if req.get("operation")!="extract_html":raise ValueError("Unknown operation")
            result={"ok":True,"data":asyncio.run(extract(req["params"]))};status=200
        except Exception as e:
            result={"ok":False,"error":type(e).__name__,"message":str(e)[:400]};status=400
        content=json.dumps(result).encode();self.send_response(status);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(content)));self.end_headers();self.wfile.write(content)
def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument("--port",type=int,default=8766);a=p.parse_args()
    with ThreadingHTTPServer(("127.0.0.1",a.port),Handler) as server:
        print(f"Collector playground: http://127.0.0.1:{a.port}");server.serve_forever()
if __name__=="__main__":main()
