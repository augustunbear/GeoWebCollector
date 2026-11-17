# GeoWebCollector

Independent, rights-gated Playwright HTML document extractor migrated from GeoIntelligenceCore. It accepts caller-supplied HTML; **it does not navigate sites, discover websites, crawl Google Maps, or execute page scripts**.

Install: `pip install -e '.[test]'` and `python -m playwright install chromium`.

```python
from geowebcollector import BrowserExtractor, HtmlDocument, Evidence, Rights, Permission, Quality, RequestContext
# Supply approved HTML and explicit purpose-bound evidence before extracting.
```

Tests: `python -m pytest -q`; Chromium: `GEO_BROWSER_TESTS=1 python -m pytest -q tests/test_browser_documents.py`.

Source: augustunbear/GeoIntelligenceCore, selective MarketLens adaptation (upstream MIT); see THIRD_PARTY_NOTICES.md. Website acquisition rights remain the caller's responsibility.

## Local API Playground (experimental)

Install Chromium with `python -m playwright install chromium`, run `python -m geowebcollector.playground` and open `http://127.0.0.1:8766`. Paste authorized HTML and CSS selectors to exercise Chromium. Do not expose this development-only server publicly.
