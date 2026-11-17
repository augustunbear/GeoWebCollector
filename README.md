# GeoWebCollector

Independent, rights-gated Playwright HTML document extractor migrated from GeoIntelligenceCore. It accepts caller-supplied HTML; **it does not navigate sites, discover websites, crawl Google Maps, or execute page scripts**.

Install: `pip install -e '.[test]'` and `python -m playwright install chromium`.

```python
from geowebcollector import BrowserExtractor, HtmlDocument, Evidence, Rights, Permission, Quality, RequestContext
# Supply approved HTML and explicit purpose-bound evidence before extracting.
```

Tests: `python -m pytest -q`; Chromium: `GEO_BROWSER_TESTS=1 python -m pytest -q tests/test_browser_documents.py`.

Source: augustunbear/GeoIntelligenceCore, selective MarketLens adaptation (upstream MIT); see THIRD_PARTY_NOTICES.md. Website acquisition rights remain the caller's responsibility.

## Playground：本地或私有 Codespaces

在仓库根目录安装 Python 3.12、依赖及 Chromium，然后启动：

```bash
python -m pip install -e '.[test]'
python -m playwright install chromium
python -m geowebcollector.playground
```

打开 <http://127.0.0.1:8766>，自带 HTML 样本可直接运行。选择“HTML 多字段提取”，可修改 HTML、CSS Selector、使用目的、超时及文档/字段上限。勾选使用权确认后运行；结果显示每个字段、缺失提示、来源、状态、耗时和外部请求拦截次数，支持复制请求与响应。所有操作均离线，**没有网址导航、网站自动发现或菜单识别**。对自有 HTML 的使用权由操作者负责。

Chromium 每次提取使用新上下文，禁止 JavaScript、Service Worker、下载和外部请求。Playground 只监听本机回环地址，不要转发到公网。如 Chromium 缺失，运行上述安装命令；使用系统 Chromium 时可设置 `GEO_CHROMIUM_PATH=/usr/bin/chromium`。超时或输入太大时缩小 HTML、选择器数或调整页面中的受限参数。新增能力需在 `playground.py` 显式注册参数 Schema、示例与受限适配器，并配对应测试；不接受任意函数调用。

### 在线打开（GitHub Codespaces）

1. 在本仓库 GitHub 页面点击 **Code → Codespaces → Create codespace on main**。首次创建会安装 Python、依赖和 Chromium；启动时自动运行 Playground。
2. 在 **Ports** 面板找到 **8766**，确认 **Port Visibility = Private**，点击网址在浏览器打开。直接运行内置 HTML 示例即可；无需真实网站。
3. 重新启动 Codespace 后会再次启动服务。若启动失败，在终端运行 `bash .devcontainer/start-playground.sh`，查看 `/tmp/geowebcollector-playground.log`。Codespace 停止后页面不可访问；用量取决于 GitHub 账户额度。

Codespaces 网址只在对应 Codespace 的环境中通过精确 Host/Origin 校验；服务器仍监听 `127.0.0.1`。**不要将端口改为 Public/Organization，也不要输入未获授权或敏感的 HTML。** HTML 在当前 Codespace 中处理；此仓库不提供多用户登录、长期在线服务或网址采集。首次安装 Chromium 需要联网且可能耗时。
