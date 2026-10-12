# 全文来源与 TXT 阶段验证

日期：2026 年 10 月 12 日。范围：T01 与 T18。验收工作区为仓库 tmp/book-corpus-workspace，未把实验记录写入用户生产书库。

运行检查：

```powershell
python -m pytest tests/test_book_room_timeout_settings.py tests/test_book_source.py tests/test_book_text_source.py tests/test_book_world_handler.py tests/test_library_text_upload.py -q
python -m mypy backend/services/book_world/source.py backend/services/book_world/text_source.py --follow-imports=skip
python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_world.py backend/channels/desktop/handlers/library.py backend/api/routes/library_upload.py tests/test_book_text_source.py tests/test_library_text_upload.py tests/conftest.py
npm run build --prefix frontend
```

后端 51 项通过。Mypy 两个源服务文件及上述 Ruff 检查通过。12 条 Pydantic 弃用警告来自已有配置模块，未阻断测试。最终界面改动后的前端生产构建通过（7 分 8 秒）；原有循环分块和大包警告仍在。

从用户给定仓库获取两部完整文本并固定提交，记录原始 SHA-256。完整解析保留短对白及尾部，分页遍历全部片段；末段定位使用未经换行转换的原始解码文本核对。TXT 的 12000 字符阅读窗口与原文高亮通过真实 SourceService + WS Handler 的浏览器联调。

浏览器操作路径：打开《西游记》→ 浏览片段 → 定位 → 阅读并高亮原文 → 切换《红楼梦》→ 实际上传完整 TXT → 准备全文。界面证据：[原文阅读](F:/god/project/Octopus/docs/plans/book-character-agents/validation/txt-reader.png)、[上传后全文就绪](F:/god/project/Octopus/docs/plans/book-character-agents/validation/txt-upload-source-ready.png)。浏览器使用隔离会话与临时工作区，无模型调用。

审查标准轴发现临时文件清理、失败 pending 状态和清理失败误报三项问题，已修复；规格轴发现工作区切换、TXT 弹窗限制和元数据编辑后丢失格式三项问题，已修复。相应新增回归通过。检索索引缺失时使用精确检索，未建立新持久索引。

人物发现、原著知情和人格忠实度尚未进入本次范围，不能把全文就绪当作人物 Agent 已可用。下一步 T02。
