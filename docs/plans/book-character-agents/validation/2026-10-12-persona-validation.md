# T03 原著档案与逻辑 Agent 验证

日期：2026 年 10 月 12 日。范围：从 T02 候选生成带原著断言、获知权限、人格基线及固定策略的逻辑 Agent。T05 人物查询、T06 回复及聊天室不在本阶段。

工作区迁移 16 增加六张知识/证据/权限/投影/基线表，首次保留 `.knowledge_index.db.pre-persona-v16.bak`。复合外键及触发器拒绝跨构建引用、他人人格授权、错误引文和未通过的基线；已发布档案、知识、检查点和配置冻结。子构建保留来源与 lineage，但复制人物/场景为新 UUID，不回写旧候选。

处理分为逐字检查、独立模型调用的语义/获知审查、原子发布。命题与真值分开；只有明确修正才连接旧信念，historical 不与 current 竞争，冲突保留 unknown。动机、价值和情绪等缺项不补全。仅提及不能授权，代词需要逐字人名锚点和语义归属；安全投影不通过时清空原文摘录。生命边界跨单元携带，死亡/时序不明阻止新授权；生前或复活后例外需本单元时间证据，倒叙死亡不会撤销当前复活。

构建绑定创建时的工作区和完整模型配置，采用租约、有限重试和检查点。每个单元最多两次抽取/审查尝试（最多四次服务层模型请求），每次显式 180 秒超时并续租；JSON 输入长度限制为两倍原文预算，输出遵守模型额度上限。阶段进度只统计已验证 evidence 单元。失败、未解身份、拒绝项及基线冲突明确标为 partial_published。

逻辑 Agent 使用 `book:<build_id>:<character_id>`，不登记到通用助手；工具为空，知识限定本人允许集，房间记忆保留为后续独立层。公开档案只有身份，读者档案可展示更完整原文；读取后者不代表人物知情。

17 项阶段行为回归通过，覆盖私有信息、假引文/外来身份、支持拒绝、信念修正与历史/冲突、跨单元死亡与复活倒叙、源快照损坏、取消迟到结果、发布回滚、冻结、幂等和部分覆盖。最终完整项目测试 94 项通过、13 项跳过、12 条既有 Pydantic 弃用警告。Mypy 14 个源服务及 Handler、Ruff 和前端生产构建通过（最终界面版本 1 分 2 秒，既有循环分块与大包警告）；13 个既有浏览器测试缺 Playwright，另用 agent-browser 隔离会话验证实际组件、WS Handler、原著定位和高亮。

真实 k3 使用已有 SHA-256 固定的 1020 码点《西游记》来源摘录；2 个证据单元、6 次实际调用，发布石猴 ready，玉帝/千里眼/顺风耳 sparse；仙卿/众猴保持 needs_review。另有 1 个支持拒绝项及 1 个不确定基线，正确部分发布。见[模型记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-persona-probe.json)、[读者档案](F:/god/project/Octopus/docs/plans/book-character-agents/validation/persona-reader-archive.png)、[原著高亮](F:/god/project/Octopus/docs/plans/book-character-agents/validation/persona-evidence-reader.png)。这只证明样本接口链路；全书人格忠实度、知情召回和语义越界由 T12 人工评测，不能用替身或单次模型审查代替。

复核标准轴发现进度提前满额和详情迟到覆盖，规格轴另发现死亡边界缺上下文、历史状态丢失和倒叙覆盖；均已修复并记录回归。检索服务暂不可用时使用精确 rg，未创建新索引。

```powershell
python -m pytest -q -rs --disable-warnings
python -m mypy backend/services/book_world backend/channels/desktop/handlers/book_world.py --follow-imports=skip
python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_world.py backend/services/knowledge_migrations.py tests/test_book_persona.py
npm run build --prefix frontend
```
