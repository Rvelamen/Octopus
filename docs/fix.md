 4. TTS 后台任务“孤儿化”风险

  问题：channels/desktop/channel.py:113 直接 asyncio.create_task(self._send_tts(...))，没有保留
  task 引用，也未做异常兜底。若 TTS 合成失败，异常可能被 asyncio 吞掉且难以排查。

  建议：使用一个 _tts_tasks: set[asyncio.Task] 来跟踪或在 create_task 时加
  <task>.add_done_callback(lambda t: t.exception() if t.exception() else None)
  来做日志兜底，防止未捕获异常静默消失。

  5. 无持久化消息队列，服务重启丢状态

  问题：core/events/bus.py 使用纯内存 asyncio.Queue。如果后端重启，正在流式输出中的消息、未处理
  的子代理结果、或工具调用状态全部丢失。

  建议：对核心队列引入持久化层（如 Redis / SQLite 持久队列，或至少
  spill-to-disk），实现降级恢复。长期看这是支撑多实例部署的前提。

  6. Agent 停止功能无法真正中断 I/O

  问题：AgentLoop._stop_current_task 是一个布尔标志，但在 LLM provider.chat_stream() 或工具
  execute() 等长耗时 I/O
  阻塞期间，代码并没有机会检查该标志，用户点击“停止”后往往要等几秒甚至几十秒才能生效。

  建议：在关键 I/O 点使用 asyncio.wait_for(...) 包裹一个“可取消”的 Future，或传入 asyncio.Event
  / CancellationToken，让用户停止请求能真正打断当前工具执行或 LLM 流。

  11. httpx 客户端未统一复用

  问题：core/providers/provider.py 每个 UnifiedProvider 实例都会新建
  httpx.AsyncClient。当并发高时会创建大量 TCP 连接。

  建议：将 httpx.AsyncClient 提升为全局/模块级单例，或至少提供显式的 close()
  生命周期管理，防止连接泄漏。



13. 请求级链路追踪（Trace ID）

  在整个 Agent loop、工具调用、子代理执行、LLM Provider 调用链中传递统一的
  trace_id。这对排查复杂多跳工具调用问题至关重要，也为前端展示“思考链路图”提供数据基础。


 5. 浏览器自动化与 Computer Use

  现状：web_fetch 只能抓取静态页面，无法与网页交互。

  建议：
  - 集成 Playwright 的完整能力（点击、输入、滚动、截图），封装成 browser_navigate,
  browser_click, browser_type, browser_screenshot 等工具。
  - 让 Agent 具备“像人一样浏览网页、填表、下载文件”的能力。
  - 更进一步，可以接入 Computer Use（如 Anthropic 的 computer-use 或 CUA），让 Agent
  能直接看屏幕截图并操作鼠标键盘。