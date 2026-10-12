# T02 人物发现验证

日期：2026 年 10 月 12 日。范围：全书候选发现链路；不包含 T03 人格基线、T05 知情检索或聊天室。

实现：工作区迁移 15 增加七张构建、检查点、场景、人物与关联表，保持 B = book_id + source_version_id + build_id 的复合外键。迁移前使用 SQLite backup 保留 `.knowledge_index.db.pre-discovery-v15.bak`，已有备份不覆盖。模型请求和连接始终绑定创建任务的工作区。

边界：同工作区一项构建；每个处理单元最多 12 个片段，实际模型原文预算至多 4000 码点并受 context_window 限制，已知身份上下文至多 4000 字符。每单元最多两次服务层尝试，每次 180 秒硬超时，输出至多已配置模型额度与 4096 token 中的较小值。检查点原子保存；取消、删除或租约过期后的结果无法入库。取消后立即继续会先结束旧 worker，再启动新代数；重启后的过期任务可以手动恢复。自动补偿扫描属于 T10。

候选仅有名称、别名、出现状态及引文，不生成知识权限。referenced 不等同 active/silent，更不等同获知。单元内人物键复用身份；同名不同身份、群体和不明实体保留待复核。

实际模型联调遇到输出截断、非原文人名、码点算错和两个个体合并问题。当前按对应 Kimi Anthropic 端点把配置显示名 `K3` 规范成官方 API ID `k3`，只对人物提取请求设置 low 思考档位，写入构建指纹；其他聊天请求默认参数不变。[Kimi 模型 ID 与思考档位说明](https://www.kimi.com/code/docs/kimi-code/models.html)。偏移算错时只接受同段内唯一逐字引文重新定位，保留方法；不会用模糊或语义匹配替代引用校验。

最终真实 k3 样本来自 1000 码点原著摘录；验收脚本在 Windows 保存时转换换行，实际来源快照为 1020 码点、11 个片段，快照 SHA-256 已另行记录。提取石猴、玉帝、千里眼、顺风耳四个个体候选，以及仙卿、众猴两个待复核群体。记录见[模型联调](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-discovery-probe.json)。这是接口联调，不是全书人物召回、知情或人格评测。

完整《西游记》《红楼梦》分别遍历 3311 / 2665 片段及 322 / 275 检查点，末段传入且无重复。该替身只返回覆盖分组、不返回人物或知识；仅证明编排覆盖，见[完整语料遍历](F:/god/project/Octopus/docs/plans/book-character-agents/validation/discovery-corpus-coverage.json)。最初较大样本失败记录保留于[初始联调](F:/god/project/Octopus/docs/plans/book-character-agents/validation/discovery-probe-initial.json)。原始正文和临时脚本未提交。

验证命令：

```powershell
python -m pytest -q -rs --disable-warnings
python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_world.py backend/core/providers/anthropic_provider.py tests/test_book_discovery.py tests/test_book_source.py
python -m mypy backend/services/book_world backend/channels/desktop/handlers/book_world.py --follow-imports=skip
npm run build --prefix frontend
```

T02 共 17 项行为回归通过；最终完整项目测试 77 项通过，13 项跳过，12 条既有 Pydantic 弃用警告。Mypy 10 个源服务/Handler 文件、Ruff 和前端生产构建通过（最终 UI 版本 50.12 秒，已有大包与循环分块警告）。13 个既有浏览器测试因缺少 Playwright 被跳过，另用 agent-browser 隔离会话操作了实际来源与候选组件、WS Handler 和数据库。[候选面板](F:/god/project/Octopus/docs/plans/book-character-agents/validation/character-discovery.png)、[引文阅读](F:/god/project/Octopus/docs/plans/book-character-agents/validation/character-evidence-reader.png)已视觉检查。

规格轴与标准轴复核发现的单元内身份、长片段预算、重启恢复、取消继续与立即重试竞争均已修复。通过此阶段不意味着已有可聊天人物，下一阶段 T03。
