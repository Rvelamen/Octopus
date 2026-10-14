# T16 圆桌聊天室验证

2026-10-14 完成独立导航、持久房间路由、真实服务联调、圆桌和公开消息投影。人物模型与用户语料质量不属于本次受控交互结论。

## 实际交付

- `App.jsx` 提供与林间图书馆并列的人物聊天室入口；书目人物可进入独立页面创建房间。`BookRoomManager` 复用分页目录与房间创建，快捷人物查询不受目录第一页限制。
- `useBookRoom` 复用 `useBookSingleRoom` 的唯一消息集和发布时间，右栏与头顶同 ID/seq、同揭示游标；只接收已发布正文。初始化/重连读取历史不加入实时气泡，历史可主动定位。轮次读取放在消息补拉后，投影另外排除已发布槽位的旧进度。
- 服务端 `open_room` 只引导读取当前 epoch，修改仍要求完整工作区、room_id、expected_epoch。实际 WebSocket 错误保留 code，另一操作重置后清除旧消息并最多重新读取一次；不自动重发提交、重置或成员变更。
- `get_member_profile` 按当前 R 与 member_id 查询固定 B，只返回公开身份；不返回原著断言、私密依据、人设或记忆。右栏依据仍由原有读者入口单独读取，不交给 renderer。
- 座位复用 T08 已落地迁移 22/23、不可改绑触发器和空闲扩容事务，无新增迁移。移除保留空椅，重返和 epoch 重置不重排。32 人全体仍有 32 槽位。
- Babylon renderer 与业务分离，共享木色/基础 mesh 构件；普通消息不重建场景。卸载释放 render loop、观察器、事件、scene 与 engine。支持缩放、全景、聚焦、拖动右栏、二维座位及窄屏。
- 可访问日志单独追加一次完整公开消息，逐字 DOM 不重复播报；减少动态效果直接显示全文。尚未用实际读屏设备检验语音体验。

## 自动检查

- `python -m pytest tests/test_book_room_scene.py tests/test_book_group_rooms.py tests/test_book_room_queue.py -q --disable-warnings`：23 通过（新增公开档案用例前）。
- `python -m pytest tests/test_book_room_scene.py tests/test_book_rooms.py tests/test_book_world_handler.py -q --disable-warnings`：41 通过（含最终 4 项场景/档案测试）。以上命令有重叠，不相加作为独立用例数。
- `node --test frontend/src/pages/BookRooms/sceneProjection.test.mjs`：3 通过，覆盖公开投影、容量几何及“发布槽位压过旧进度”竞态。
- Ruff 通过；`python -m mypy --follow-imports=skip --ignore-missing-imports backend/services/book_world backend/channels/desktop/handlers/book_room.py backend/channels/desktop/handlers/book_world.py`：44 文件通过。
- 新增 BookRooms 目录、共享 hook 与对话组件 ESLint 通过。`tsc -p frontend/tsconfig.json --noEmit` 通过；修正既有 Markdown 链接组件把可选 href/children 推断为必填的类型声明，不改变运行行为。
- 最终前端生产构建通过，87 秒；保留既有循环分块、混合导入与大包警告。`git diff --check` 通过。
- SQL 草案 177 项检查通过；仅内存契约验证，单列于实际服务与浏览器结果。
- 两轴只读审查发现同步竞态、错误码丢失、代数恢复、公开档案/播报缺口，已修复并复核通过；档案迟到失败也按成员和 epoch 限制。

## 浏览器操作与限制

[结构化记录](roundtable-live-ui.json)区分早期路由传输夹具与最终生产 `WebSocketProvider` 路径；均使用真实 React、当前 Handler、SQLite 与隔离来源，模型提供器明确为受控替身。累计受控调用 15 次，真实模型调用 0。

已操作创建/切换/刷新房间、同名跨书人物、@、禁言、移除与重返、原文依据、普通/全体队列与恢复。最终 native WS 重验：同消息采样 3 次、0 不一致；减少动态效果下可访问日志只新增 1 个全文节点；旁路重置 epoch 3→4，实际 rejection 保留 stale_room_epoch，自动恢复后旧正文/气泡为 0。早期正常逐字采样也保持同游标。新消息前后渲染实例未因正文重建。

定向人物生成时，通过实际 LibraryEngine 删除其隔离来源再释放被挂起结果：该人物变为空椅并标记来源删除，槽位 `no_comment/source_unavailable`，无迟到人物正文，另一书来源仍 active，房间保持 active。见[删除中断](roundtable-source-deleted.png)。[公开档案](roundtable-public-profile.png)使用当前房间固定来源，不展示私密材料。

1/4/8/16/32 人均在同一桌面中保有独立座位。Windows 本机 headless Chromium 观测约 45–61 FPS：32 人 565 mesh；这是短时环境观测，不是性能承诺。上下文丢失测试后 32 个二维座位、canvas 0、累计 created=disposed=4、active=0；800px 视口无页面横向溢出，见[降级截图](roundtable-native-fallback.png)。历史房间刷新/重连不批量重播气泡。长中文、遮挡折叠、人物列表与窄屏定向入口见[长消息](roundtable-live-bubble.png)、[窄屏](roundtable-narrow-directed.png)、[32 人](roundtable-32-seats.png)。

原林间图书馆实际组件、阅读与受控思考者问答回归见[阅读](library-reader-regression.png)、[问答](library-thinker-regression.png)，没有真实模型调用。完整应用开关、两部全书人格、六种讨论组合与真实模型质量仍由 T17/T12 完成，不能用这些受控结果代替。

后续 T17 显式加 `--ext .js,.jsx,.mjs` 扩大了圆桌 JSX 的 ESLint 覆盖，发现原宽度分隔控件的 a11y 规则告警，已改为有原生键盘行为的 range。此前仅目录命令通过不能表述为已完整扫描全部 JSX；修正后的全部圆桌 JSX 检查通过。
