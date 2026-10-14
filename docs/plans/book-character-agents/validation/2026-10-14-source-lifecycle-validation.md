# T11 来源版本、局部删除与服务关闭验收

日期：2026-10-14。范围：生产存储、服务、桌面 WS 协议及实际 React 界面。原著权限和生命周期行为已通过；全书人格质量留待 T12。

迁移 27 新增可重试的清理记录。删除事务用独立连接先失效书籍、来源、构建、表达、自动任务和该书成员；保留 B、character_id、member_id、seat_index 与已发布聊天。混聊中其他书有效时保持 active，并跳过已失效来源；删除当前人物时，晚到正文、超时和传输错误均不能发布，剩余有效人物仍继续同一有限队列。最后来源失效才取消剩余任务并只读。

数据库清理先于文件删除：原文段不可逆变为空白并保留位置/哈希，知识与引文撤权并清空，私密档案、表达素材/嵌入、检查点、错误详情和普通图书馆 chunks/FTS/笔记载荷清除。晚到分块写入被数据库守卫拒绝。文件目标解析后必须位于当前书目目录；文件锁失败维持禁用并展示重试。并发重试按书籍串行，完成态不会被晚到错误覆盖。迁移备份仍遵循项目既有备份策略；这是应用载荷清理，未声称磁盘介质安全擦除。

新来源不替换旧房间，旧证据仍定位旧快照；新建房间使用用户选择的构建。来源列表区分当前、固定旧版和删除状态，历史消息保留名字并标注来源已删除。删除请求携带工作区身份，旧工作区相同局部 item_id 不能删除新工作区书目；前端丢弃过期列表、选择与房间状态。

关闭开始停止接收三类请求并排空在途操作；自动扫描和模型任务停止、租约失效，聊天轮次变为 interrupted，不会自动继续；表达暂停、未完成构建可恢复。等待已接受 PDF 解析线程后关闭 LibraryEngine 连接，短连接在上下文退出时关闭。重启读取持久状态并要求手动继续有限聊天窗口。

## 自动验证

- `python -m pytest tests/test_book_world_lifecycle.py -q --disable-warnings`：14 通过。覆盖局部/全部删除、文件失败与普通检索清除、reply/timeout/transport 晚结果、重复清理、并发元数据提交与删除回滚、旧来源引用、关闭与重启、关闭入口排空、工作区相同局部 ID。
- `python -m pytest -q --disable-warnings`：213 通过、13 项既有环境跳过、14 warnings，357.92 秒。此轮包含前 13 项生命周期用例；之后补充的相同局部 ID 用例与全部 14 项单独通过。
- BookWorld/BookRoom 与 book_world 包共 44 个显式文件 Mypy 通过；Ruff 覆盖该包、三个 Handler 及生命周期测试，通过。
- BookRoomManager、BookSingleChatModal、useBookSingleRoom、useLibrary、useLibraryWS 的 ESLint 通过；前端 Vite 生产构建通过，保留既有 circular chunk、静态/动态导入与大 chunk 警告。
- Standards/Spec 两轴只读复核：发现的五个问题全部修复并复核关闭。

## 实际操作

独立临时工作区经真实 LibraryEngine、RoomMembershipService、BookRoundService、BookRoomHandler/LibraryHandler 及 React BookRoomManager/BookSingleChatModal 联调。两个有相同展示名但不同 B/member_id 的人物先完成全体问候；模拟第一书文件锁，点击真实删除请求显示失败，只停用第一书人物；释放文件锁后点击“重试来源清理”，完成清理且不恢复人物；第二书独自回答新提交；删除第二书后输入、添加和重返禁用，历史名字与删除标记保留。

共 6 次受控生成/校验调用，真实模型调用 0；受控输出不用于人格质量结论。[实际请求、身份与消息记录](source-lifecycle-live-ui.json)、[文件失败与重试界面](source-cleanup-failed.png)、[全部删除后只读历史](source-all-removed-readonly.png)。

两部完整语料的真实自动构建另行保留进度与原始结果，目前均在发现阶段因姓名/别名证据不一致失败。累计追踪 24 次真实完成、83,667 个报告 total_tokens，包含两次 max_tokens 截断；该追踪跨多轮策略诊断，尚无全书人格发布，更不代表 T12 已通过。
