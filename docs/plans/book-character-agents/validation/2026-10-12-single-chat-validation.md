# T06 原著约束单聊阶段验收

日期：2026 年 10 月 12 日。结论：T06 的存储、服务、桌面协议与单聊入口已贯通，阶段验证通过。全书人物质量、长期摘要、重置、多人调度和圆桌仍由后续任务交付；本记录不代表 T12 完成。

## 已交付行为

用户从可用人物档案进入单聊，显式选择可用聊天模型，提交后先看到回应/校验状态，再收到已校验的公开正文。可查看供读者核对的原文依据、停止轮次、超时后手动继续和重新打开历史。没有可用模型或来源时显示原因。

迁移 22/23 建立 room、sources、epochs、members、rounds、slots、messages 和 refs，包含完整关联、索引及发布保护。用户消息、轮次和槽位原子创建；人物正文、引用、短暂情绪、槽位完成和 cursor 原子发布。已执行迁移与已发布原著不改写。

上下文分区为公开身份、当前基线、当前问题/讨论快照、本人允许事实、安全表达样例及同 R 公共历史。模型不获得读者 quote_text、世界真相标签或完整旁白场景；原著素材不执行指令。表达不足保留空结果，不补外部人物知识。

候选最多两次生成，分别独立审查，仍失败可使用另行审查的未知回复。模型故障或校验失败明确终止，不公开原始 token。人物来源、epoch、成员代数、租约与单调时间在提交/执行/发布边界复核；过期、取消和来源失效不能迟到发布。

轮次保存模型记录与全部生成参数。恢复保留原预算、模型与表达策略，读取最新秒数建立新窗口；重复提交先找原轮次，不受后来调低的新默认预算阻挡。新请求仍检查当前配置。表达选择 v2 展开已保留词项中的短词；旧快照默认 v1，继续沿用原选择行为。

## 自动与界面验证

| 验证范围 | 实际结果 |
| --- | --- |
| 完整项目 pytest | `python -m pytest -q`：154 通过，13 跳过，14 警告；本任务新增 30 项房间/上下文/worker/Handler/模型配置行为案例 |
| 本模块类型 | `python -m mypy --follow-imports=skip --ignore-missing-imports backend/services/book_world backend/channels/desktop/handlers/book_room.py backend/channels/desktop/handlers/book_world.py`：33 文件通过 |
| Python lint | `python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_room.py tests/test_book_rooms.py`：通过 |
| 前端 lint | ESLint 检查新 modal/hook 及 CharacterDiscoveryPanel、CharacterPersonaModal、NarrativeSourcePanel：通过 |
| 生产构建 | `npm run build --prefix frontend`：通过，最终用时 1 分 31 秒 |
| 界面竞争 | [六项记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/single-chat-ui-races.json)：迟到 A 不覆盖 B、关闭后不重开、重开从服务端用时继续计时、不自动生成、迟到错误不污染新界面、模型/回退错误翻译正确 |
| 当前 WS 与真实历史重开 | [操作记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/single-chat-live-ui.json)：原著回复、未知回复、读者依据面板均可读；重开和取证前后模型调用仍为 10 |

回归覆盖幂等/冲突内容、完整来源范围、工作区伪造、公开/读者投影分离、引用原子性、有限改写、校验与模型故障、取消/删除/时间截止、保存参数恢复、非 chat 模型排除，以及完整正文中的否定自传。新增正例保留条件句、引述和有据否定经历。情绪模式只接受本人当前 emotion 基线，不能把 style 当作情绪依据；有据情绪与当前触发可发布，未审查情绪不落状态。

13 项跳过来自既有浏览器工具环境依赖。警告包含已有 Pydantic 配置弃用及临时配置数据库使用的 Python 3.12 datetime adapter 弃用。构建保留已有 CJS、循环 chunk、动态/静态重复导入与大包提示。

类型检查范围是上述显式模块；未递归检查整个旧 backend 的依赖类型。一次扩大 imported legacy 范围的检查报告 704 项错误/108 文件，不能称为全仓库类型通过，也不把这些错误当成已修复。

## 真实模型与有效表达对照

[界面模型记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-single-chat-probe.json)共 10 次实际 k3 调用。早期 v1/v2 诊断保留：v1 格式/回退失败，v2 将“我还没细看”错误视为 conversation。该消息未回写原著，也不计验收通过。

干净 v3 房间中，有据瀑布问题经生成/审查两次调用发布对应原著细节。手机问题的两条“从未见过/不曾见过”无据自传被拦截，第三次调用审查固定未知回复后发布。常见词面保护仅补充语义审查，不证明所有自由文本均零越界。

[表达对照记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-expression-chat-ab.json)使用《西游记》的精确摘录和受控已审档案，不评估自动提取准确率。素材为本人原句“我进去！我进去！”，包含原文范围、哈希及审查出处。

第一次四次运行发现长问题短词匹配不足，只有重复基线规则进入输入；保留为诊断。修复后重新完成有据/未知两组、四个独立干净房间：事实和基线相同，A 无对白、B 各有一条对白，均两次调用完成。累计素材调用 2、聊天调用 16，共 18，在表达 4/聊天 20 的总预算内；没有重置预算重新跑理想结果。

当前对照只完成 Codex 对完整正文及来源的检查，没有人工盲评。已知回答几乎相同；增强的未知回答先复读了自告奋勇原句，未证明相关性或自然度改善。Adapter 忽略所请求的 temperature=0，亦未提供可控 seed，不能声称确定性采样。表达增强继续默认关闭，完整质量结论与开启条件由 T12 决定。

## Standards

只读标准复核：“本次聚焦复核通过，未发现新增硬规范违规或需要整改的运行风险。确认原预算恢复不受最新默认预算影响；幂等预查与事务内复查共用内容冲突规则；表达选择 v1/v2 固定在轮次并传入上下文；情绪来源限定为 emotion；异步来源初始化受 generation 和请求序号保护。”

## Spec

只读规格复核：“此前 P2 已关闭：恢复和重复提交均先使用原快照预算，最新全局 128 不再阻挡原 4096 轮次；冲突内容仍被拒绝。本次三处修复未发现剩余阻塞：原预算、凭据解析和新秒数分开处理；表达选择版本固定于轮次，旧快照继续执行 v1，v2 未扩大事实允许集；情绪模式限定本人当前 emotion 基线，style 不再充任，保留有据情绪正例。真实 A/B 可作为接入证据；增强仍默认关闭的判断与验证协议一致。”

本轮标准轴 0 项、规格轴 1 项 P2 已关闭，最终各轴无剩余阶段阻塞。两个复核均未调用模型或修改代码，不替代运行验收。

## 后续任务

T07 建立带来源摘要及 epoch 重置，补长历史与情绪触发的持久记忆。T08/T09/T17 落实跨书多人、@、成员控制及主题/自由模式。T16 交付独立圆桌 Tab；T10/T11 落实自动编排和完整来源生命周期，最后由 T12 进行两书全路径及质量验收。

截图：[单聊](F:/god/project/Octopus/docs/plans/book-character-agents/validation/single-chat-v3.png)、[读者依据](F:/god/project/Octopus/docs/plans/book-character-agents/validation/single-chat-v3-evidence.png)。隔离语料、QA 传输替身、临时数据库和调用原始输入保留在忽略目录，生产全局模型偏好没有改动。
