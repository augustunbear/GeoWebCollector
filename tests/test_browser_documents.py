import asyncio
from datetime import datetime, timezone
import os

import pytest

from geowebcollector.models import Status
from geowebcollector.models import Evidence, Rights, Permission, Quality
from geowebcollector.models import RequestContext

CONTEXT = RequestContext(request_id='browser-synthetic')


def document(html='<h1>Café 茶</h1>', allowed=True):
    from geowebcollector.browser import HtmlDocument
    rights = Rights(use=Permission.allowed if allowed else Permission.unknown, permitted_purpose='extract')
    evidence = Evidence(id='html-1', source_id='user', source_type='html_snapshot',
                        source_ref='synthetic supplied document', retrieved_at=datetime(2026, 11, 9, tzinfo=timezone.utc),
                        method_version='supplied-v1', rights=rights, quality=Quality(verification='unverified'))
    return HtmlDocument(html=html, evidence=evidence, purpose='extract')


def test_disabled_browser_does_not_launch():
    from geowebcollector.browser import BrowserExtractor
    async def scenario():
        async with BrowserExtractor() as extractor:
            return await extractor.extract(document(), {'name': 'h1'}, CONTEXT)
    assert asyncio.run(scenario()).status == Status.disabled


class Locator:
    @property
    def first(self):
        return self
    async def count(self):
        return 1
    async def evaluate(self, script, limit):
        return 'synthetic'[:limit]


class Page:
    async def set_content(self, html, **kwargs):
        return None
    def locator(self, selector):
        return Locator()


class Context:
    def __init__(self):
        self.closed = False
    async def route(self, pattern, handler):
        self.handler = handler
    async def new_page(self):
        return Page()
    async def close(self):
        self.closed = True


class Browser:
    def __init__(self):
        self.contexts = []
        self.options = []
        self.closed = False
    async def new_context(self, **options):
        self.options.append(options)
        ctx = Context()
        self.contexts.append(ctx)
        return ctx
    async def close(self):
        self.closed = True
        for ctx in self.contexts:
            await ctx.close()


def test_fresh_contexts_closed_and_rights_and_limits_checked_before_page_creation():
    from geowebcollector.browser import BrowserExtractor
    browser = Browser()
    async def launch():
        return browser
    async def scenario():
        async with BrowserExtractor(enabled=True, browser_factory=launch, max_input_bytes=100) as extractor:
            assert (await extractor.extract(document(allowed=False), {'name': 'h1'}, CONTEXT)).status == Status.unconfigured
            assert (await extractor.extract(document('x' * 101), {'name': 'h1'}, CONTEXT)).status == Status.invalid_input
            results = await asyncio.gather(*(extractor.extract(document(), {'name': 'h1'}, CONTEXT) for _ in range(2)))
            assert all(r.status == Status.ok and r.data.fields['name'] == 'synthetic' for r in results)
            assert all(c.closed for c in browser.contexts)
    asyncio.run(scenario())
    assert len(browser.contexts) == 2 and browser.closed
    assert all(o['java_script_enabled'] is False and o['service_workers'] == 'block' for o in browser.options)


def test_cancellation_closes_context_and_releases_slot():
    from geowebcollector.browser import BrowserExtractor
    browser = Browser()
    async def launch():
        return browser
    async def scenario():
        entered = asyncio.Event()
        class BlockingPage(Page):
            async def set_content(self, html, **kwargs):
                entered.set()
                await asyncio.Event().wait()
        original = browser.new_context
        async def blocking(**options):
            ctx = await original(**options)
            async def new_page():
                return BlockingPage()
            ctx.new_page = new_page
            return ctx
        browser.new_context = blocking
        async with BrowserExtractor(enabled=True, browser_factory=launch) as extractor:
            task = asyncio.create_task(extractor.extract(document(), {'name': 'h1'}, CONTEXT))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert browser.contexts[0].closed
            browser.new_context = original
            assert (await extractor.extract(document(), {'name': 'h1'}, CONTEXT)).status == Status.ok
    asyncio.run(scenario())


def test_cancel_during_context_creation_closes_browser_and_disables_session():
    from geowebcollector.browser import BrowserExtractor
    browser = Browser()
    async def launch():
        return browser
    async def scenario():
        entered = asyncio.Event()
        original = browser.new_context
        async def allocate_then_block(**options):
            ctx = await original(**options)
            entered.set()
            await asyncio.Event().wait()
            return ctx
        browser.new_context = allocate_then_block
        async with BrowserExtractor(enabled=True, browser_factory=launch) as extractor:
            task = asyncio.create_task(extractor.extract(document(), {'name': 'h1'}, CONTEXT))
            await entered.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert browser.closed and browser.contexts[0].closed
            assert (await extractor.extract(document(), {'name': 'h1'}, CONTEXT)).status == Status.unavailable
    asyncio.run(scenario())


def test_document_resource_requests_are_aborted_and_counted():
    from geowebcollector.browser import BrowserExtractor
    browser = Browser()
    aborted = []
    async def launch():
        return browser
    async def scenario():
        original = browser.new_context
        async def with_resource(**options):
            ctx = await original(**options)
            class ResourcePage(Page):
                async def set_content(self, html, **kwargs):
                    class Route:
                        async def abort(self):
                            aborted.append(True)
                    await ctx.handler(Route())
            async def new_page():
                return ResourcePage()
            ctx.new_page = new_page
            return ctx
        browser.new_context = with_resource
        async with BrowserExtractor(enabled=True, browser_factory=launch) as extractor:
            result = await extractor.extract(document(), {'name': 'h1'}, CONTEXT)
            assert result.status == Status.ok and result.data.blocked_requests == 1
            assert aborted == [True]
    asyncio.run(scenario())


@pytest.mark.skipif(os.environ.get('GEO_BROWSER_TESTS') != '1', reason='opt-in local Chromium check')
def test_real_chromium_extracts_without_executing_document_scripts_or_network():
    from geowebcollector.browser import BrowserExtractor
    async def scenario():
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            async def launch():
                return await p.chromium.launch(executable_path=os.environ.get('GEO_CHROMIUM_PATH') or None)
            async with BrowserExtractor(enabled=True, browser_factory=launch, max_field_chars=12) as extractor:
                html = '<h1>Café 茶</h1><p id="long">' + 'x'*20 + '</p><script>document.querySelector("h1").textContent="BAD"</script><img src="https://127.0.0.1/private">'
                result = await extractor.extract(document(html), {'name': 'h1', 'long': '#long', 'absent': '.missing'}, CONTEXT)
                assert result.status == Status.partial
                assert result.data.fields == {'name': 'Café 茶', 'long': 'x'*12, 'absent': None}
                assert result.data.document_sha256 and result.evidence[0].id == 'html-1'
                assert result.data.verification == 'unverified'
                assert result.data.blocked_requests >= 1
    asyncio.run(scenario())
