# T07 房间记忆与独立重置阶段验收

日期：2026 年 10 月 13 日。范围：来源摘要、作用域召回、房间短暂状态、独立重置、桌面协议和实际单聊界面。人物仍绑定已有原著 B；本阶段没有安装第三方运行库，没有新增原著授权。

## 交付与存储

迁移 24 新增 book_room_summaries/book_summary_sources，并保留迁移前备份。摘要绑定 R＝room_id＋epoch、through_seq 与实际公开消息；复合外键、消息范围触发器及不可变保护拒绝串房、串代数和修改已接受摘要。服务只保存通过结构核验及独立语义审查的候选，原著表没有写入路径。

摘要保存说话者、成员 ID、1–6 个原消息 ID 和 room_hearsay/inference/conversation 类型。首次至少 40 条消息开始摘要；每次压缩至多 20 条完整消息，留下最近 20 条，输入上限 18,000 UTF-8 字节；输出最多 12 项、每项 300 码点。字节上限是保守容量策略，不是实际 token 统计。摘要生成与独立审查各一次，使用原轮次的秒数、取消、成员权限和租约检查；失败后等待手动操作。

预算不足时按当前问题相关性和新近顺序整项舍弃旧摘要，保留项不能改写；舍弃数量进入输入记录，原消息仍可在同 R 召回。人物上下文最多取六项摘要/六条原文召回，摘要覆盖的查询内容避免重复原文，其他召回可裁剪。当前问题、原著基线、必要事实及情绪触发原文受保护。

重置事务撤销旧租约和槽位、创建新 active epoch、推进全体成员代数并清空短暂状态，保留来源、人物、座位和 next_seq。旧数据暂存也不可读；后台清理失败不撤销成功确认，后续 get_room 重试。恢复旧轮仍使用原问题/模型/讨论快照；公共历史、摘要和情绪以当次 room.next_seq 为统一可见界限。

新轮保存 room-memory-v2 提示词版本，明确直接自述也是听者收到的说法、序号范围须被全部出处支持；旧轮缺字段默认为 v1。两版均保留，暂停/继续不能换用新版。

## 行为和工程检查

| 检查 | 结果及实际范围 |
| --- | --- |
| 记忆回归 | 新增 17 项，另在已有情绪用例增加一项旧失败轮恢复参数；公共服务、worker、WS 与已约定的临时 SQLite 契约夹具 |
| 完整项目 pytest | `python -m pytest -q --disable-warnings`：172 通过、13 跳过、14 警告，213.36 秒 |
| Python 类型 | `python -m mypy --follow-imports=skip --ignore-missing-imports backend/services/book_world backend/channels/desktop/handlers/book_room.py backend/channels/desktop/handlers/book_world.py`：35 个显式文件通过；未宣称全仓类型无错误 |
| Python lint | `python -m ruff check backend/services/book_world backend/channels/desktop/handlers/book_room.py tests/test_book_room_memory.py tests/test_book_rooms.py`：通过 |
| 前端 lint | 两个单聊文件、CharacterPersonaModal、CharacterDiscoveryPanel、NarrativeSourcePanel：ESLint 通过 |
| 生产构建 | `npm run build`：通过，57.10 秒；既有循环分块、静态/动态导入和大包警告保留 |
| 两轴只读复核 | Spec、Standards 的四个 P2 均关闭；未发现新增阻挡 T07 完成的缺陷 |

新增回归验证恢复后的摘要来源、跨房/代数拒绝、错误说话者、晚于快照的来源、原著升级拒绝、输入篡改、取消/超时发布回滚及原著基线不变。四个实际失败先复现再修复：成功重置被清理失败误报、12 项旧摘要与 4000 码点新消息竞争导致永久卡住、六条长回忆被全部保护导致容量失败、旧轮恢复无法读取后续情绪触发。

跨书成员采用临时 SQLite 夹具建立合法来源绑定，公共 ContextBuilder 验证同房摘要共享与各自 CanonicalScope；reset_memory 验证两成员一起推进代数、座位/来源/基线不变。这是存储/服务契约验证，公开群聊创建、成员选择和跨书真实人物互动仍由 T08/T12 完成。

## 界面与实际协议

[延迟传输竞态记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/room-memory-ui-races.json)使用真实单聊组件及受控传输，验证重置清空历史/摘要、旧证据不重开、旧记忆失败不污染新代数、重开不触发生成。初次确实复现了迟到错误，新 Hook 在每次 await 后检查请求代数并丢弃旧异常后通过。

[实际 WS 记录](F:/god/project/Octopus/docs/plans/book-character-agents/validation/room-memory-live-ui.json)使用已迁移的隔离语料工作区与真实 Handler：重启服务后恢复三项摘要、说话者及四条原消息出处；界面重置到 epoch＝2，next_seq＝46，历史和摘要为空；再次打开仍为空，旧 epoch 请求被拒绝，人物 B 保留。没有额外模型调用。截图为 [出处](F:/god/project/Octopus/docs/plans/book-character-agents/validation/room-memory-live-sources.png)、[重置](F:/god/project/Octopus/docs/plans/book-character-agents/validation/room-memory-live-reset.png)、[重开](F:/god/project/Octopus/docs/plans/book-character-agents/validation/room-memory-live-reopen.png)。

## 真实模型结果和限制

[真实 k3 探针](F:/god/project/Octopus/docs/plans/book-character-agents/validation/real-model-room-memory-probe.json)沿用既有石猴原著摘录 B，种入 42 条受控公开用户消息；不代表全书人物、多角色或真实用户长聊。调用预算固定为七次，开始前持久计数，含初版的两次失败；全局模型与秒数设置未改。

初版生成了只引用部分序号却声称整个范围发生的摘要，独立审查正确拒绝该项，同时误把用户直接自述判为不能使用 room_hearsay；没有发布摘要或人物正文。v2 明确类型定义并忽略占位话题后，三项摘要正确保留“用户自称青禾”“门也许开着、尚未确认位置”“区分猜测和确认的请求”，独立审查通过，through_seq＝20。

随后两次人物候选使用了不符合当前回复契约的来源分类：房间消息推测被标为需要原著 claim/evidence 的 inference；还出现无依据否定亲历表述。两次都因来源结构被拒绝，有限链路最终独立审查并发布了固定未知回退，窗口用时 57.344 秒。正文没有错误确认门或发布未审查候选，但可回答的用户代号被误拒，**回忆问答质量未通过**。原著基线在探针前后保持相同，预算已经耗尽，不重跑以追求理想结果。

模型/摘要类型与回复来源分类转换、可回答部分优先回应及未知表达的自传边界进入 T12 的误拒/完整正文案例。当前已验证功能链路与来源保护，未证明真实模型回忆效果、人格忠实度或 ChatHaruhi 表达增强收益；无人工盲评。表达增强仍默认关闭，不能以安全回退或替身测试替代质量门槛。

## 迁移和回滚

本迁移只新增房间派生记忆结构，不修改已执行迁移或原著数据。应用降级前停止运行轮次并保存工作区数据库；恢复 migration 24 的备份会丢失之后新增的聊天/其他工作区写入，不能直接在活跃工作区覆盖。保留新增表而关闭新版记忆配置可继续读取旧聊天，但不是数据库完整降级。没有对真实生产工作区执行回滚。
