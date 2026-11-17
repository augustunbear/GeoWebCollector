"""Local, loopback-only playground. No site navigation or arbitrary execution."""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .browser import BrowserExtractor, HtmlDocument
from .models import Evidence, Rights, Permission, Quality, RequestContext

SAMPLE = '<!doctype html><html><h1>示例咖啡馆</h1><p class="city">纽伦堡</p><p class="menu">咖啡 3 €</p></html>'

class ExtractInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    html: str = Field(min_length=1, max_length=1_000_000, description='已获准使用的 HTML 文档；内置样本可直接测试')
    selectors: dict[str, str] = Field(min_length=1, max_length=20, description='字段名到 CSS Selector 的映射')
    purpose: str = Field(default='local-demo', min_length=1, max_length=128, description='本次使用目的')
    authorized: bool = Field(default=False, description='确认拥有本次 HTML 的使用权')
    deadline_s: float = Field(default=10, gt=0, le=30, description='浏览器超时秒数')
    max_input_bytes: int = Field(default=100_000, ge=1, le=1_000_000, description='HTML 字节上限')
    max_field_chars: int = Field(default=2000, ge=1, le=10_000, description='每字段字符上限')

BROWSER_SLOT = threading.BoundedSemaphore(1)
REGISTRY = {
    'extract_html': {
        'name': 'HTML 多字段提取', 'category': '浏览器提取',
        'description': '用隔离的 Chromium 从已提供的 HTML 提取 CSS Selector 字段；缺失字段为 null。不会访问网址。',
        'schema': ExtractInput.model_json_schema(),
        'example': {'html': SAMPLE, 'selectors': {'title': 'h1', 'city': '.city', 'missing': '.absent'},
                    'purpose': 'local-demo', 'authorized': True},
        'mode': 'offline', 'dependencies': ['playwright', 'Chromium'], 'api_key': False,
        'permission': '须确认 HTML 使用权；JavaScript、Service Worker、下载及外部请求均被阻止。',
        'status': 'executable', 'reason': '内置 HTML 样本可直接运行。',
    },
}

def catalog():
    return REGISTRY

async def extract(params):
    request = ExtractInput.model_validate(params)
    if not request.authorized:
        raise ValueError('请先确认 HTML 使用权')
    evidence = Evidence(id='local-test', source_id='manual', source_type='user_supplied',
        source_ref='local-playground', retrieved_at=datetime.now(timezone.utc),
        method_version='playground-v1',
        rights=Rights(use=Permission.allowed, permitted_purpose=request.purpose),
        quality=Quality(verification='unverified'))
    document = HtmlDocument(html=request.html, evidence=evidence, purpose=request.purpose)
    async with BrowserExtractor(enabled=True, deadline_s=request.deadline_s,
                                max_input_bytes=request.max_input_bytes,
                                max_field_chars=request.max_field_chars) as extractor:
        result = await extractor.extract(document, request.selectors,
                                         RequestContext(request_id='local-playground'))
    return result.model_dump(mode='json')

def execute(name, params):
    if name not in REGISTRY:
        raise ValueError('Unknown operation')
    return asyncio.run(extract(params))

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(35)
    def _headers(self, status, mime, length):
        self.send_response(status)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(length))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
    def _local(self):
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        port = str(self.server.server_port)
        if host in ('127.0.0.1:' + port, 'localhost:' + port):
            return origin is None or origin == 'http://' + host
        name = os.getenv('CODESPACE_NAME', '')
        domain = os.getenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN', '')
        # Only this codespace's exact HTTPS forwarding host is accepted.
        if (os.getenv('CODESPACES') != 'true' or
            not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', name) or
            not re.fullmatch(r'[a-z0-9]+(?:[.-][a-z0-9]+)*', domain)):
            return False
        expected = f'{name}-{port}.{domain}'
        return host == expected and (origin is None or origin == 'https://' + expected)
    def do_GET(self):
        if not self._local(): self.send_error(403); return
        if self.path == '/':
            body = files('geowebcollector').joinpath('playground.html').read_bytes()
            mime = 'text/html; charset=utf-8'
        elif self.path == '/playground.js':
            body = files('geowebcollector').joinpath('playground.js').read_bytes()
            mime = 'text/javascript; charset=utf-8'
        elif self.path == '/api/operations':
            body = json.dumps({'operations': catalog()}, ensure_ascii=False).encode()
            mime = 'application/json'
        else: self.send_error(404); return
        self._headers(200, mime, len(body)); self.wfile.write(body)
    def do_POST(self):
        if not self._local(): self.send_error(403); return
        if self.path != '/api/run': self.send_error(404); return
        start = time.monotonic()
        try:
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                raise ValueError('Content-Type must be application/json')
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 1_100_000: raise ValueError('Invalid request size')
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict) or set(body) - {'operation', 'params', 'live'} or not {'operation', 'params'} <= set(body) or body.get('live', False) is not False:
                raise ValueError('Invalid request shape')
            if not BROWSER_SLOT.acquire(blocking=False):
                raise ValueError('浏览器正在运行另一个任务')
            try:
                data = execute(body['operation'], body['params'])
            finally:
                BROWSER_SLOT.release()
            result = {'ok': True, 'data': data, 'source': 'user_supplied_html',
                      'elapsed_ms': round((time.monotonic() - start) * 1000)}
            status = 200
        except (ValueError, TypeError, KeyError, ValidationError, json.JSONDecodeError) as exc:
            result = {'ok': False, 'error': type(exc).__name__, 'message': str(exc)[:400],
                      'elapsed_ms': round((time.monotonic() - start) * 1000)}
            status = 400
        except Exception:
            result = {'ok': False, 'error': 'unavailable', 'message': '浏览器不可用；请安装 Chromium 并重试。',
                      'elapsed_ms': round((time.monotonic() - start) * 1000)}
            status = 503
        content = json.dumps(result, ensure_ascii=False).encode()
        self._headers(status, 'application/json', len(content)); self.wfile.write(content)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', args.port), Handler) as server:
        print(f'Collector playground: http://127.0.0.1:{server.server_port}')
        server.serve_forever()

if __name__ == '__main__': main()
