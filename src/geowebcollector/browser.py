"""Optional offline HTML extraction, inspired by MarketLens browser lifecycle.

Acquisition belongs to the consumer. Supplied documents cannot execute scripts
or make external requests. Browser contexts are never reused across documents.
"""
from __future__ import annotations

import asyncio
from hashlib import sha256
import math

from pydantic import Field

from .models import FrozenModel, Issue, Result, Status, Evidence, RequestContext


class HtmlDocument(FrozenModel):
    html: str = Field(max_length=1_000_000)
    evidence: Evidence
    purpose: str = Field(min_length=1, max_length=128)


class BrowserExtraction(FrozenModel):
    fields: dict[str, str | None]
    document_sha256: str
    blocked_requests: int = Field(default=0, ge=0)
    method_version: str = 'html-selectors-v1'
    verification: str = 'unverified'


async def _close(resource):
    """Settle resource release before propagating cancellation."""
    task = asyncio.create_task(asyncio.wait_for(resource.close(), timeout=5))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


class BrowserExtractor:
    def __init__(self, *, enabled=False, max_concurrency=1, deadline_s=10.0,
                 max_input_bytes=1_000_000, max_field_chars=2000, browser_factory=None):
        integers = (max_concurrency, max_input_bytes, max_field_chars)
        if (any(isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in integers)
                or max_concurrency > 4 or max_input_bytes > 1_000_000 or max_field_chars > 10_000
                or isinstance(deadline_s, bool) or not math.isfinite(deadline_s) or not 0 < deadline_s <= 60):
            raise ValueError('invalid browser limits')
        self.enabled, self.deadline_s = enabled, deadline_s
        self.max_input_bytes, self.max_field_chars = max_input_bytes, max_field_chars
        self._slots = asyncio.Semaphore(max_concurrency)
        self._factory = browser_factory
        self._browser = self._driver = None
        self._active = False

    async def __aenter__(self):
        if self._active:
            raise RuntimeError('browser session already active')
        self._active = True
        if self.enabled:
            try:
                async with asyncio.timeout(self.deadline_s):
                    if self._factory is not None:
                        self._browser = await self._factory()
                    else:
                        from playwright.async_api import async_playwright
                        self._driver = await async_playwright().start()
                        self._browser = await self._driver.chromium.launch()
            except asyncio.CancelledError:
                await self.__aexit__(None, None, None)
                raise
            except Exception:
                await self.__aexit__(None, None, None)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if self._browser is not None:
                await _close(self._browser)
        finally:
            self._browser = None
            try:
                if self._driver is not None:
                    await asyncio.wait_for(self._driver.stop(), timeout=5)
            finally:
                self._driver = None
                self._active = False

    async def extract(self, document: HtmlDocument, selectors: dict[str, str],
                      context: RequestContext) -> Result[BrowserExtraction]:
        def fail(status, code):
            return Result[BrowserExtraction](status=status, data=None, context=context,
                                              issues=(Issue(code=code, message_key=f'browser.{code}'),))
        if not self.enabled:
            return fail(Status.disabled, 'disabled')
        try:
            document = HtmlDocument.model_validate(document)
            if (not isinstance(selectors, dict) or not 1 <= len(selectors) <= 20 or
                    any(not isinstance(k, str) or not 1 <= len(k) <= 64 or
                        not isinstance(v, str) or not v.strip() or len(v) > 256 for k, v in selectors.items()) or
                    len(document.html.encode('utf-8')) > self.max_input_bytes):
                return fail(Status.invalid_input, 'input_limit')
        except (ValueError, TypeError):
            return fail(Status.invalid_input, 'invalid_document')
        if not document.evidence.rights.allows('use', document.purpose):
            return fail(Status.unconfigured, 'rights_not_approved')
        if not self._active or self._browser is None:
            return fail(Status.unavailable, 'browser_unavailable')
        fields, issues = {}, []
        blocked_requests = 0
        try:
            async with asyncio.timeout(self.deadline_s):
                async with self._slots:
                    # If allocation is interrupted before the context handle is
                    # returned, its ownership is uncertain. Close the session
                    # rather than reuse a browser with an unreachable context.
                    browser = self._browser
                    if browser is None:
                        return fail(Status.unavailable, 'browser_unavailable')
                    try:
                        browser_context = await browser.new_context(
                            java_script_enabled=False, service_workers='block', accept_downloads=False)
                    except BaseException:
                        self._browser = None
                        await _close(browser)
                        raise
                    try:
                        async def block(route):
                            nonlocal blocked_requests
                            await route.abort()
                            blocked_requests += 1
                        await browser_context.route('**/*', block)
                        page = await browser_context.new_page()
                        await page.set_content(document.html, wait_until='load',
                                               timeout=int(self.deadline_s * 1000))
                        for key, selector in selectors.items():
                            locator = page.locator(selector)
                            count = await locator.count()
                            if not count:
                                fields[key] = None
                                issues.append(Issue(code='missing_field', message_key='browser.missing_field',
                                                    safe_params={'field': key}))
                                continue
                            # Bound transfer from browser to Python before reading text.
                            text = await locator.first.evaluate(
                                '(el, limit) => (el.textContent || "").trim().slice(0, limit)',
                                self.max_field_chars + 1)
                            fields[key] = text[:self.max_field_chars] or None
                            if len(text) > self.max_field_chars or count > 1 or not fields[key]:
                                issues.append(Issue(code='ambiguous_or_truncated_field',
                                                    message_key='browser.ambiguous_or_truncated_field',
                                                    safe_params={'field': key}))
                    finally:
                        await _close(browser_context)
        except Exception:
            return fail(Status.unavailable, 'extraction_failed')
        data = BrowserExtraction(fields=fields, document_sha256=sha256(document.html.encode()).hexdigest(),
                                 blocked_requests=blocked_requests)
        return Result[BrowserExtraction](status=Status.partial if issues else Status.ok, data=data,
                                          context=context, issues=tuple(issues), evidence=(document.evidence,))
