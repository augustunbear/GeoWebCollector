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

## 本地 Playground

在仓库根目录安装 Python 3.12、依赖及 Chromium，然后启动：

```bash
python -m pip install -e '.[test]'
python -m playwright install chromium
python -m geowebcollector.playground
```

打开 <http://127.0.0.1:8766>，自带 HTML 样本可直接运行。选择“HTML 多字段提取”，可修改 HTML、CSS Selector、使用目的、超时及文档/字段上限。勾选使用权确认后运行；结果显示每个字段、缺失提示、来源、状态、耗时和外部请求拦截次数，支持复制请求与响应。所有操作均离线，**没有网址导航、网站自动发现或菜单识别**。对自有 HTML 的使用权由操作者负责。

Chromium 每次提取使用新上下文，禁止 JavaScript、Service Worker、下载和外部请求。Playground 只监听本机回环地址，不要转发到公网。如 Chromium 缺失，运行上述安装命令；使用系统 Chromium 时可设置 `GEO_CHROMIUM_PATH=/usr/bin/chromium`。超时或输入太大时缩小 HTML、选择器数或调整页面中的受限参数。新增能力需在 `playground.py` 显式注册参数 Schema、示例与受限适配器，并配对应测试；不接受任意函数调用。
