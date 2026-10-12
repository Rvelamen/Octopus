# T18 图书馆 TXT 导入与叙事全文来源

状态：已实施并验证，2026 年 10 月 12 日。阶段：M1。

用户在图书馆上传 PDF 或 TXT。TXT 可直接阅读、准备全文、分页浏览及定位原著，林间图书馆的 TXT 书目也可打开内嵌阅读器。

## 前置依赖

[T01 全文来源](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/01-narrative-source.md)。原 T13 的 TXT 部分按用户要求提前为本任务，EPUB 仍留在 T13。

## 交付与验证

- [x] HTTP 上传与 WS 创建支持大小写 PDF/TXT 后缀，保留旧 temp_pdf_path 请求兼容。
- [x] UTF-8、UTF-8 BOM、BOM UTF-16、GB18030 严格解码，拒绝空文件和伪装的二进制。
- [x] TXT 使用 main.txt 附件及独立哈希，保持 pdf_sha256 为空，复用工作区来源表，不新建按书数据库。
- [x] 原文偏移与规范化全文偏移分开，均按 Unicode 码点计数；补充平面字符与 CRLF 回归通过。
- [x] 上传携带工作区身份，创建/列表/读取按请求捕获当前工作区；切换后旧上传被拒绝，异步阶段不改根路径。
- [x] 成功发布后清理本次受控上传临时文件；发布异常将条目标记为 failed，不保持永久 pending。
- [x] TXT 不加载 PDF 缩略图，文字阅读与引用高亮、分页及林间图书馆入口接通。

51 项设置、来源、TXT、Handler 和上传边界测试通过；新增源服务的 Mypy 和 Ruff 通过。前端构建及浏览器操作验证记录见[验证说明](F:/god/project/Octopus/docs/plans/book-character-agents/validation/2026-10-12-source-validation.md)。

## 两部验收书籍

取自用户指定 tennessine/corpus，固定提交 c5ce96aca36c6a3cb4da5f0ff7d2d5fa30c32aea：《西游记》《红楼梦》。完整文件在临时验收工作区导入，3311 和 2665 个片段均完整遍历，最后片段可回溯原文；哈希和完整性结果见[语料记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/corpus-sources.json)。重复回目保留原文，章节标记不是权威章节划分。

本任务验证导入、存储和阅读，不证明人物提取或真实模型人设质量；后续按 T02 至 T12 验收。
