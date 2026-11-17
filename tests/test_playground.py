"""Registry, HTTP and safety checks for the local HTML playground."""
import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest
from geowebcollector.playground import catalog, execute, Handler


def test_extractor_registered():
    op = catalog()['extract_html']
    assert op['example']['selectors']['title'] == 'h1'
    assert op['schema']['properties']['authorized']['type'] == 'boolean'
    assert op['status'] == 'executable' and op['mode'] == 'offline'


def test_no_unapproved_html():
    with pytest.raises(ValueError): execute('extract_html', {**catalog()['extract_html']['example'], 'authorized': False})
    with pytest.raises(ValueError): execute('__dict__', {})
    with pytest.raises(ValueError): execute('extract_html', {**catalog()['extract_html']['example'], 'unexpected': 'x'})


def test_http_assets_and_validation():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    def request(method, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        conn.request(method, path, body=data, headers=headers or {})
        response=conn.getresponse(); body=response.read(); status=response.status; content=response.getheader('Content-Type'); conn.close()
        return status, body, content
    try:
        assert request('GET','/')[0] == 200
        assert b'playground.js' in request('GET','/')[1]
        assert b'copy-response' in request('GET','/playground.js')[1]
        status,body,mime=request('GET','/api/operations')
        assert status==200 and mime=='application/json' and 'extract_html' in json.loads(body)['operations']
        headers={'Content-Type':'application/json'}
        req={'operation':'extract_html','params':{**catalog()['extract_html']['example'],'authorized':False},'live':False}
        assert request('POST','/api/run',json.dumps(req),headers)[0]==400
        assert request('POST','/api/run',json.dumps({**req,'live':True}),headers)[0]==400
        assert request('POST','/api/run',json.dumps(req),{**headers,'Origin':'http://evil.test'})[0]==403
        assert request('POST','/api/run',json.dumps(req),{**headers,'Host':'evil.test'})[0]==403
    finally:
        server.shutdown();server.server_close();thread.join()


def test_codespaces_private_forwarded_host(monkeypatch):
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    def request(host,origin=None,method='GET'):
        conn=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=5)
        headers={'Host':host}
        if origin is not None: headers['Origin']=origin
        if method=='POST':
            headers['Content-Type']='application/json'
            body=json.dumps({'operation':'extract_html','params':{'authorized':False}})
            conn.request('POST','/api/run',body=body,headers=headers)
        else:
            conn.request('GET','/api/operations',headers=headers)
        response=conn.getresponse();response.read();status=response.status;conn.close()
        return status
    host=f'example-space-{server.server_port}.app.github.dev'
    try:
        assert request(host)==403
        monkeypatch.setenv('CODESPACES','true')
        monkeypatch.setenv('CODESPACE_NAME','example-space')
        monkeypatch.setenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev')
        assert request(host)==200
        assert request(host,'https://'+host)==200
        assert request(host,'https://'+host,method='POST')==400  # Accepted host; rejected input.
        for invalid_host,origin in [(host,'http://'+host),(host,'https://evil.test'),
                                    (host+'.evil.test',None),
                                    (f'example-space-{server.server_port+1}.app.github.dev',None),
                                    ('evil.app.github.dev',None)]:
            assert request(invalid_host,origin)==403
        monkeypatch.setenv('GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN','app.github.dev.evil.test')
        assert request(host)==403
        monkeypatch.delenv('CODESPACES')
        assert request(host)==403
        assert request(f'localhost:{server.server_port}')==200
    finally:
        server.shutdown();server.server_close();thread.join()


def test_sample_chromium_when_opted_in():
    import os
    if os.environ.get('GEO_BROWSER_TESTS') != '1':
        pytest.skip('opt-in real Chromium test')
    result=execute('extract_html', catalog()['extract_html']['example'])
    assert result['status']=='partial'
    assert result['data']['fields']['title']=='示例咖啡馆'
    assert result['data']['fields']['missing'] is None
    assert result['evidence'][0]['source_id']=='manual'


def test_timeout_and_size_limits_without_chromium():
    from geowebcollector.playground import ExtractInput
    from pydantic import ValidationError
    example=catalog()['extract_html']['example']
    for change in ({'deadline_s': 0}, {'deadline_s': 61}, {'max_input_bytes': 0},
                   {'max_field_chars': 10_001}, {'html': ''}):
        with pytest.raises(ValidationError): ExtractInput.model_validate({**example, **change})


def test_extractor_public_method_is_registered():
    import inspect
    from geowebcollector.browser import BrowserExtractor
    methods={name for name,fn in inspect.getmembers(BrowserExtractor,inspect.iscoroutinefunction) if not name.startswith('_')}
    registered={'extract' if key=='extract_html' else key for key in catalog()}
    assert methods == registered
    assert catalog()['extract_html']['status']=='executable'
