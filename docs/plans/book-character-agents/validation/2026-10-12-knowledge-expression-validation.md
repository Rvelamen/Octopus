# T05 人物知识与表达素材验证

日期：2026 年 10 月 12 日。范围：人物允许知识、当前基线、表达派生集、桌面协议与人物详情预览；尚未实现聊天回复或质量 A/B。

## 存储与权限

迁移 18 建立按人物视角投影的中文 FTS，迁移 19/20 建立表达集、素材、规范化出处和发布冻结保护。后续迁移 21 保留空引文的已授权 style 基线：只有当前本人 style 命题可以生成规则，不能生成对白。每项迁移保存对应工作区数据库备份，不修改既有迁移与已发布原著。

CanonicalScope 绑定工作区、书籍、来源、构建、人物与策略。知识检索在排序及 LIMIT 前联接获知权限、断言及可见证据；FTS 不可用时仅扫描相同允许集合。返回允许命题和安全引文，空引文保留命题与定位元数据，不返回原始引文或世界真相标签。普通查询只使用当前信念，显式回顾才可取历史信念。

表达集有独立指纹、配置、检查点、调用预算、租约与状态，不写原著断言、权限或基线。对白须逐字定位于本人允许引文，并独立审查说话者、安全、当前基线及事实覆盖。选中样例的 fact/stance 引用须属于本次允许知识或当前基线；已知但本次未取的事实不能借样例进入上下文。来源删除立即禁用相关知识和表达，完整载荷清理留在 T11。

## 行为验证

新增 16 项服务与桌面协议回归。覆盖空引文命题/基线、当前和历史信念、同段秘密、跨书与工作区、FTS 故障、非原句/外国引用/说话者拒绝、样例事实的正反例、预算暂停、排队重启、取消迟到、来源删除、慢模型期间知识查询，以及两个客户端取消/重试的竞争窗口。

复核发现并修复三个边界：空引文被错误当成无权限；失败检查点写入缺少事务 fencing；排队恢复和多个客户端控制可能误停替代工作器。失败检查点现用写事务，异常退出写入校验有效租约；同一表达任务的控制、旧工作器停止与新调度串行执行，退出只清除自身登记。标准轴和规格轴最终复核关闭已报告问题。

完整项目测试 **124 通过、13 跳过、12 条既有警告**。跳过项为既有缺少 Playwright 的 browser_tool 测试，不计成功。Mypy 22 源文件、Ruff、三个修改组件的 ESLint 通过。前端生产构建通过，保留既有循环分块、大包和混合导入警告。

```powershell
python -m pytest -q --disable-warnings
python -m mypy backend/services/book_world backend/channels/desktop/handlers/book_world.py --follow-imports=skip
python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_world.py backend/services/knowledge_migrations.py tests/test_book_knowledge.py
npm run build --prefix frontend
```

## 实际模型与界面

使用隔离工作区、已有 T04 构建 c2da28c8 及 1020 码点《西游记》摘录，SHA-256 为 c723212e0b0d4044892e3eb9c34ceab2ef0d429955fa89d0f8abf39e75184f18，没有在用户主工作区导入测试资料。

石猴表达探针使用真实 k3、4096 token 输出预算，单窗口最多 2 单元和 8 次调用。实际 1 单元、2 次完整调用，模型返回空素材，未改变原著档案。唯一非空安全引文属于众猴发言，不能用作石猴台词。记录见[受控模型探针](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-expression-probe.json)。报告读取公共哈希字段的错误仅影响序列化，已从完成任务及已捕获响应恢复，没有重复付费调用。

浏览器加载实际 NarrativeSourcePanel、人物详情与知识面板，经真实 WebSocket Handler 查询“瀑布”，显示石猴允许命题和众猴约定的安全引文；查询“花果山”未找到相关依据。允许命题的原文位置可打开 TXT 定位。切换人物后输入和结果清空，不复用旧人物预览。界面区分原著素材目录与本次选中的样例，并展示构建、取消、恢复和零素材结果。

浏览器另为玉皇大天尊玄穹高上帝启动表达构建：实际 2 次调用后 1 个单元失败，表达集 partial、0 素材；人物原著仍可查询。此路径未捕获模型原始响应，尚未确立具体无效输出原因，不能宣称通过表达质量验证。见[界面构建记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/expression-ui-probe.json)及[部分完成提示](F:/god/project/Octopus/docs/plans/book-character-agents/validation/knowledge-sparse-expression.png)。

以上是实际组件隔离联调，不代表完整桌面应用回归。正向对白、独立审查和事实用途过滤目前由确定性 Provider 验证；真实样本尚未产出可用对白。T06 接入上下文与消息发布，T12 用同模型 60 项原有边界问题＋24 项表达质量问题做 A/B；在完整评测前不宣称已提升聊天质量。
