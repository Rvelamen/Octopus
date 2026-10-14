# T08 跨书多人房间验证

2026 年 10 月 14 日完成存储、服务、桌面协议与界面链路。复用 T06/T07 的迁移 22–24，不改已执行迁移。来源与成员固定完整 B，房间交流固定 R；规划只读取公开身份、已审查别名及发言机会，不读取私有人设、引文或旁白。

新增 RoomMembershipService、RoomCharacterCatalog、有限选人和队列推进。每书固定一个构建，创建幂等、加人事务、来源冲突拒绝、固定座位和成员代数接通。directed 以 member_id 固定顺序；natural 按相关性和发言机会默认至多三人，无关话题只邀请一人。mention_only 不自动参与，muted 包括 @ 都不发言。移除、模式变化撤销旧槽位与当前租约；处理器锁定交接并保留已用秒数，其他成员继续本轮剩余窗口。经审查的 no_comment 有槽位记录，不产生空正文。

BookRoomManager 提供跨书创建、分页选人、旧房间重开与加人，群聊面板提供定向选择、成员控制、身份标签、回复对象和公开消息出处。人物消息仅在校验并原子发布后返回；下一位以自己的允许集读取前一位公开发言，引用类型保持 room_hearsay。

## 验证证据

- `python -m pytest tests/test_book_group_rooms.py -q --disable-warnings`：13 通过。含公共修订/发布建立的别名选人、同名 member_id、双客户端禁言交接、旧结果拒绝、独立取证、公平静默、原子创建、来源冲突与单秒窗口累计。
- Ruff 通过；`python -m mypy --follow-imports=skip --ignore-missing-imports backend/services/book_world backend/channels/desktop/handlers/book_room.py backend/channels/desktop/handlers/book_world.py`：39 个显式文件通过。首次扩大 follow-imports 的检查耗时过长，终止后沿用此前明确的 skip 范围，未宣称全仓类型无错误。
- BookRoomManager、BookSingleChatModal、useBookSingleRoom 的 ESLint 通过。LibraryTab 有四项既有错误和一项警告，其六行入口增量未引入该类错误，未报告整个 LibraryTab lint 通过。
- 生产构建通过，保留既有循环分块、静态/动态导入与大包警告。两轴只读复核各发现一项 P2，均修复：列表迟到覆盖和公开别名选人缺失；复核确认关闭。
- 实际 React + 当前 WS Handler 在隔离语料工作区重开既有两书消息、查看出处、禁言、移除、重新加入，并通过界面选择黛玉和石猴创建新房间。见 [已发布交流](group-room-live-messages.png) 与 [创建](group-room-live-created.png)。重开和成员控制没有新模型调用。
- 实际组件的受控传输竞态：旧刷新 A 延迟、新刷新 B 先完成，随后 A 返回；新房间与新游标仍保留。该验证仅证明界面竞态，不是模型或完整应用验收。

完整项目 `python -m pytest -q --disable-warnings`：185 通过、13 项既有环境跳过、14 警告，327.77 秒。跳过项不计为功能通过。

## 真实模型与质量限制

[真实 k3 记录](real-model-group-chat-probe.json)在 2026 年 10 月 13 日保留固定 16 次预算中的 13 次实际调用，总计记录 21757 token；本轮不重复调用以追求更好结果。完整两书来源仍可读取，但人物构建和交流使用石猴洞府及黛玉读书摘录。

自动红楼梦准备的四次人物/修复调用均未取得可发布人物；包括所有权、结构或知情证据问题。随后采用明确标注的受控原著说话事实提取，仍经未改动的真实独立模型审查，形成稀疏人物。这不证明自动提取质量。

群聊五次调用及一次显式有限窗口继续后，石猴发布问候，黛玉根据石猴公开消息接续问候；后者正确保留听说引用，但无根据地将用户称为“姑娘”，独立审查漏判。v5 加入中性称呼边界，以剩余预算中两次调用在新房间定向黛玉复验，发布“青禾，你好。”；这是小样本修复验证，不是跨书整体质量通过。原著基线前后相同，未做人工盲评，表达增强仍默认关闭。

T08 的确定性权限和链路验收通过；自动提取、完整正文审查、全书召回、人格忠实度和多人关联性进入 T12。T09 的 all/暂停/重启恢复和 T16 独立 Tab/3D 尚待交付。
