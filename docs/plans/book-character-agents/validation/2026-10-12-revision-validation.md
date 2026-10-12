# T04 人物纠错验证

日期：2026 年 10 月 12 日。范围：同来源修订、原文依据审查、原著重新提取、读者扩展和实际纠错组件；尚未实现人物聊天。

迁移 17 在工作区知识库新增 book_revision_heads、book_revisions、book_user_extensions，执行前保存 .pre-revisions-v17.bak。头版本与编辑序号分开：预占编辑不替换可用构建；发布须在同一事务内再次比较序号。既有迁移与已发布原著不修改。修订保留 lineage 供回溯，新版人物使用新 ID，断言/获知路径/基线全部从原文重新提取。

## 确定性检查

14 项公共服务和桌面 Handler 回归覆盖别名、合并、原文缺失/语义拒绝、请求幂等、并发模型审查后的单一赢家、后续编辑覆盖、归属成功与拒绝、同段无关特征、同义错误残留、未确认的纠正身份、跨书人物/原文拒绝、读者扩展隔离和慢审查期间同连接刷新。独立语义 revision_checks 与结构、目标、类别、原文及允许关系共同决定归属完成；任意失败或遗漏阻止发布。

完整项目测试：108 通过、13 跳过、12 条既有 Pydantic 弃用警告。跳过项属于未安装 Playwright 的既有 browser_tool 测试，不作为功能通过证据。Mypy 17 文件与 Ruff 通过；CharacterRevisionModal、CharacterPersonaModal、CharacterDiscoveryPanel 的 ESLint 无错误/警告。NarrativeSourcePanel 既有同步 effect 状态重置触发 ESLint 规则，未将它列入本次无错误结论。前端生产构建通过，耗时 1 分 6 秒，保留既有循环分块、大包与混合导入警告。完整 SQL 契约内存检查仍为 177 项，区别于实际服务回归。

```powershell
python -m pytest -q -rs --disable-warnings
python -m mypy backend/services/book_world backend/channels/desktop/handlers/book_world.py --follow-imports=skip
python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_world.py backend/services/knowledge_migrations.py tests/test_book_revisions.py
npm run build --prefix frontend
python docs/plans/book-character-agents/storage-schema-check.py
```

## 模型与浏览器联调

使用隔离工作区的 1020 码点《西游记》摘录及原有 T03 发布档案。浏览器运行实际 NarrativeSourcePanel 与人物纠错组件，经真实 WS Handler 保存石猴的读者扩展、提交有原文依据的姓名修订、查看版本差异与旧档案。截图：[纠错原文表单](F:/god/project/Octopus/docs/plans/book-character-agents/validation/revision-source-form.png)、[最终修订差异](F:/god/project/Octopus/docs/plans/book-character-agents/validation/revision-published-diff.png)、[读者扩展](F:/god/project/Octopus/docs/plans/book-character-agents/validation/revision-reader-extension.png)。仅加载实际组件的隔离页面，不代表整个桌面应用已做完整回归。

第一轮 4096 token 任务发生两次截断，暴露“修订对象未确认而其他人物部分成功”的发布问题。该探针产生的 3fb0030b 构建记录仅作诊断；最终代码要求纠错对象独立确认且 ready/sparse，否则失败并保留原头。确定性负例已验证保护，不将旧代码探针当作通过。

最终受控任务 c2da28c8 使用 8192 token 输出预算、180 秒单次上限，不修改全局模型设置；6 次实际 k3 调用，2 个证据单元均通过。修订对象玉皇大天尊玄穹高上帝为 sparse；石猴及其余身份状态、部分发布原因按实际报告保留。原 T03 六人物的状态、断言数量与基线逐项对照既有黄金记录一致。见 [实际模型记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-revision-probe.json)。报告序列化曾读取不存在的公共哈希字段，已从完成构建、已捕获调用和 T03 黄金记录恢复，没有重复模型调用。

## 复核与后续边界

code-review 标准轴发现模型审查阻塞串行 WS，已改为固定根路径的受控后台请求；新增公共 Handler 回归证明模型等待时同连接仍可刷新。规格轴发现仅靠 key/引文重叠无法确认同一命题修复，已加入独立语义复核与两种反例，两轴复核关闭原问题。

T04 固定原著版本与人物身份，不写房间绑定；实际旧房间不自动切换的端到端场景随 T06/T11 验证。当前实验只覆盖摘录和接口链路，不代表全书知情召回、人格忠实度或零语义越界；完整书籍与真实模型评测由 T12 负责。
