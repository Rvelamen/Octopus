# Browser Automation Tools

浏览器自动化模块，为 Octopus Agent 提供浏览器控制能力。

## 功能特性

- ✅ **导航到 URL**：控制浏览器访问网页
- ✅ **页面快照**：获取无障碍树快照和交互元素列表
- ✅ **元素交互**：点击、输入、获取文本
- ✅ **JavaScript 执行**：在页面上执行自定义脚本
- ✅ **截图**：捕获页面截图（base64 编码）
- ✅ **会话管理**：多会话隔离，自动清理
- ✅ **自动清理**：会话超时和关闭清理

## 架构设计

```
backend/tools/browser/
├── __init__.py              # 模块入口
├── base.py                  # 浏览器后端抽象接口
├── local_playwright.py      # 本地 Playwright 浏览器后端
├── tool.py                  # 浏览器工具主类（所有工具函数）
├── registration.py          # 工具注册到 ToolRegistry
└── README.md                # 本文档
```

### 设计模式

采用**多后端架构**（参考 Hermes Agent）：

```
BrowserTool (工具层)
    ↓
BrowserBackend (抽象接口)
    ↓
LocalPlaywrightBackend (具体实现)
```

**优势**：
- 易于扩展新的后端（如云服务 Browserbase）
- 工具层与后端解耦
- 统一的会话管理

## 安装依赖

```bash
# 安装 Playwright
pip install playwright

# 安装 Chromium 浏览器
playwright install chromium
```

## 使用方式

### 1. Agent 自动使用

浏览器工具已自动注册到 ToolRegistry，Agent 可直接使用：

```python
# Agent 对话中自动识别
用户："请访问 https://example.com 并获取页面内容"

Agent 会自动调用：
1. browser_navigate(url="https://example.com")
2. browser_snapshot(session_id="...")
3. 返回页面内容
```

### 2. 工具列表

#### browser_navigate
导航到 URL。

```json
{
  "url": "https://example.com",
  "session_id": "browser_123"  // 可选，为空时自动创建
}
```

#### browser_snapshot
获取页面快照（无障碍树）。

```json
{
  "session_id": "browser_123"
}
```

返回：
```json
{
  "success": true,
  "url": "https://example.com",
  "title": "Example Domain",
  "snapshot": "[document]...\n  [heading] Example Domain\n  [paragraph] This domain...",
  "elements": [
    {"ref": "@e0", "tag": "a", "text": "More information...", "visible": true}
  ],
  "element_count": 1
}
```

#### browser_click
点击元素。

```json
{
  "element_ref": "@e0",  // 或 CSS 选择器 "a"
  "session_id": "browser_123"
}
```

#### browser_type
输入文本。

```json
{
  "element_ref": "input#search",
  "text": "Hello World",
  "session_id": "browser_123"
}
```

#### browser_get_text
获取元素文本。

```json
{
  "element_ref": "h1",
  "session_id": "browser_123"
}
```

#### browser_execute_js
执行 JavaScript。

```json
{
  "script": "document.title",
  "session_id": "browser_123"
}
```

#### browser_screenshot
截图。

```json
{
  "session_id": "browser_123",
  "full_page": false
}
```

返回 base64 编码的截图图片。

#### browser_close
关闭会话。

```json
{
  "session_id": "browser_123"
}
```

## 会话管理

### 自动创建
不传 `session_id` 时自动创建：
```json
{
  "url": "https://example.com"
  // session_id 为空，自动创建 "browser_{timestamp}"
}
```

### 会话隔离
每个 `session_id` 对应独立的浏览器上下文（Browser Context），互不干扰。

### 自动清理
- 会话超时（5 分钟无活动）自动清理
- 调用 `browser_close` 立即清理
- Agent 关闭时自动清理所有会话

## 元素引用

支持多种元素定位方式：

1. **索引引用**：`@e0`, `@e1`, `@e5`（从 snapshot 的 elements 列表获取）
2. **CSS 选择器**：`a`, `input#search`, `.btn-primary`
3. **XPath**：`//div[@class='content']`

## 测试

运行测试：

```bash
# 运行所有浏览器工具测试
pytest tests/test_browser_tool.py -v

# 运行特定测试
pytest tests/test_browser_tool.py::TestBrowserToolRegistration::test_get_tool_definitions -v
```

## 扩展现有后端

添加新的浏览器后端（如云服务）：

1. 继承 `BrowserBackend` 接口
2. 实现所有抽象方法
3. 在 `BrowserTool` 中切换后端

示例：

```python
from .base import BrowserBackend

class CloudBrowserBackend(BrowserBackend):
    async def initialize(self):
        # 初始化云服务客户端
        pass
    
    async def create_session(self, session_id):
        # 创建云浏览器会话
        pass
    
    # ... 实现其他方法
```

## 参考资料

- [Playwright Python API](https://playwright.dev/python/)
- [Hermes Agent Browser Tool](https://github.com/NousResearch/hermes-agent)
- [Accessibility Tree](https://developer.mozilla.org/en-US/docs/Web/Accessibility/Accessibility_tree)
