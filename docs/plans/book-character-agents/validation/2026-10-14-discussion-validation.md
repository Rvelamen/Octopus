# T17 讨论配置与公共总结验证

2026-10-14。存储、服务、协议和界面链路已实现，确定性行为已验证；真实模型回复未通过，T17 的合理回应条款保持未关闭，T12 全书质量验收未开始完成判定。

## 已实现行为

- `RoomDiscussionService` 以 R 与 expected_discussion_revision 做短事务 CAS；Unicode 首尾空白规范化、200/1000 码点上限、topic 非空、free 清空主题/目标，非法值整体拒绝。活跃/暂停/中断轮次禁止修改；不改变成员、座位、epoch、原著或已存房间记忆。
- 新轮次使用服务端讨论快照，恢复保持原快照。新 UI 每次提交携带期望版本；旧客户端省略版本时按已确认设计使用当前配置并返回实际快照。重试原 client_turn_id 使用原配置，不因后续换题重新发言。
- free/topic 与 natural/directed/all 独立。当前问题与保存主题决定本轮人数，公开历史只帮助排序；允许集、基线和表达权限不扩大。新 `character-chat-v6` 明确主题是材料、合理推演/未知/听说规则，旧轮次仍保留原提示词版本。
- 圆桌与既有对话面板提供讨论配置、状态、目标和公共总结。完成后“再讨论一轮”用新 turn ID、当前讨论配置及原发言方式启动一次有限轮；恢复只继续原队列，两者分开。
- 迁移 22/23 已有配置和冻结触发器，不重写历史迁移。迁移 28 备份后创建 `book_room_summary_jobs`，R 外键、幂等 client_summary_id、单活跃总结索引及 generation。
- 总结启动立即 ACK，后台至多两次生成/独立复核调用，普通秒数快照，至多处理 40 条新公共消息。候选不进入状态接口。最终正文仍写带出处的房间记忆，保留说话者、类型和引用；through_seq 和未覆盖数量明确展示，不宣称每次覆盖整段长聊天。
- 取消、重置、最后来源删除和重启撤销总结授权；重启标 interrupted、不自动重跑。发布时在同一 SQLite 事务内检查当前 R、工作区、active、截止时间与 job generation，并写入已校验总结和任务 completed。提交后取消返回 completed，不能误报已取消却新增正文。
- 启动、None 返回、异常和启动前取消均清理后台句柄；同连接聊天的停止、禁言和重置不等待总结模型。

## 检查

- 最新专项 `python -m pytest tests/test_book_discussion.py -q --disable-warnings`：10 通过。覆盖真实服务六种组合、Unicode/CAS/旧客户端、queued/paused/interrupted、快照恢复、正文/总结隔离、拒绝/超时/工作区/readonly、启动即取消、提交后取消、任务恢复与来源删除。
- 最终六文件广域回归（discussion、room_memory、room_queue、group_rooms、world_lifecycle、room_scene）：65 通过，12 警告，279.26 秒；专项已包含在其中，不相加。
- Ruff 通过；`mypy --follow-imports=skip --ignore-missing-imports` 的 book_world 与两个 Handler 共 47 文件通过。
- ESLint 显式覆盖 `.js,.jsx,.mjs` 的全部 BookRooms 与共享讨论/对话/hook，通过；前端 tsc 与生产构建通过（121 秒，既有分块/混合导入/大包警告保留）。
- SQL 草案 177 项内存检查通过，新任务表 DDL 已纳入契约；该数目不代表新增 177 项任务测试。实际迁移/外键与取消范围由服务临时库验证。
- 两轴审查发现并修复：串行连接等待总结、旧客户端规范偏差、缺少再讨论操作、readonly/部分总结、启动清理及发布/取消状态竞争。复核确认关闭。

## 实际界面

生产 `WebSocketProvider`、当前 React、真实 Handler/SQLite 加明确受控 provider，使用隔离短篇，真实模型调用 0。此部分不作为人格质量结论。

[结构化配置/新轮/总结记录](discussion-native-ui.json)验证 topic 保存后跨轮保持；“再讨论一轮”产生不同 round_id，epoch 仍为 1。切回 free 后 revision=2、topic/goal=null，成员 ID/座位逐项相同。截图：[主题](discussion-topic-ui.png)、[公共总结](discussion-public-summary.png)。

[同连接停止记录](discussion-controls-ui.json)把总结 provider 挂起后，仍可提交另一聊天、在约 521ms 内停止该轮，并取消总结；释放挂起响应后没有新总结替换已保存版本。见[停止控制](discussion-stop-controls.png)。最初的同步等待版本因此被替换；该修正不是靠延长窗口掩盖。最终原子提交和启动前取消的精确竞争窗口由自动测试补充。

## 真实模型失败，仍需推进

[完整探针](real-model-discussion-probe.json)使用既有《西游记》《红楼梦》摘录人物（含受控提取准备，非全书人物），真实 k3、v6、独立干净房间。固定上限 10 次调用，实际启动 9 次，剩余 1 次不追跑；7 次完成响应记录 9854 total_tokens，另列 6656 cache_read_input_tokens。两次审查取消没有 usage，不能据已报告用量推断供应商全部计费。

两题均在普通 60 秒窗口内未完成校验发布，round_timeout 暂停，人物正文均为 0：

1. 住处题的第一次审查使用 1/2/3 ordinal，违反 0 起始契约；修复后的审查在窗口末取消。人物稀疏允许集中没有陈设，不把拒绝陈设细节本身称为全书未知能力通过。
2. 电灯听说题的候选加入松明火把、夜间环境和未亲见/从未见过等无依据自传；独立审查与本地检查拒绝，改写也未通过，回退审查到时取消。

没有发布这些候选，边界阻止此次泄露；用户可用回复交付失败，不能用拒绝率、队列成功、审查调用存在或截图证明人物质量。两部完整书籍的自动发现也仍 failed，数据库核对为 5/3 次调用，见[全书进度](full-book-automatic-progress.json)。下一步诊断发现和审查格式/时延问题，使用新版本与独立预算复验；保留本次失败，不延长原实验或重跑直至变绿。原 60+24 项评测、全书复核和首版开关仍按 T12 执行。

后续只读重放最后 8 份全书发现响应：4 份通过当前生产校验器，4 份因当前名字/别名不在引文或既有人物无无歧义别名而拒绝。具体反例见[发现诊断](full-book-discovery-diagnosis.json)。旧临时脚本错误地把 segment 字典传给接受字符串的 resolve_span 所产生的 slice 异常已排除，不作为生产错误。该诊断没有额外模型调用。

后续版本已修复名字输入、审查 ordinal/预算和完整正文覆盖，并新增有限定点修复、删除竞争保护及明确否定经历检查。真实探针已有发布，但仍有语义审查漏检；当前两部 v10 全书构建仍失败，T17/T12 保持未验收。完整预算、失败、误拒、回归和界面证据见[模型契约诊断与加固](2026-10-14-model-contract-validation.md)。
