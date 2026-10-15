# 失败重建后保留原著档案历史入口

实际v4档案试验创建了一个来自原始发现版本的新子构建，提取失败且未发布。旧已发布版本和Agent仍在数据库中，但人物面板只为当前已发布版本、或父为已发布版本的提取任务加载历史上下文；此类失败子构建的父为discovery_complete，导致旧版下拉入口消失。

## 修复及行为证据

构建查询增加只读`history_build_id`，限定**当前书籍、当前来源、有效已发布/部分发布构建**。界面借它加载版本列表，继续显示当前失败构建及其人物，不自动切到成功版本掩盖失败。审计变化仅在上下文与所选构建一致时显示，不能把锚点旧版的修订记录标成当前失败版。

没有新增授权、写操作或迁移。纠正仍要求已发布档案及匹配头版本/revision；选择历史不让失败草稿变为可编辑的原著，也不生成聊天调用。页面代数和请求序号保护保持。

4项失败前新增回归先复现缺失字段；修复后修订模块**18项通过**，覆盖queued/failed/cancelled保留当前状态并回溯、跨书与新来源不能复用旧锚点。两轴复核无阻塞。

## 实际浏览器操作

通过生产NarrativeSourcePanel、CharacterDiscoveryPanel、档案弹层与实际WS Handler读取原生记录，检查：

- [修复前](persona-v4-failed-before-history.png)失败子构建0/2、旧版入口缺失；[修复后](persona-v4-history-failed-fixed.png)失败和不可发布原因继续展示，版本入口恢复。
- 切到[旧已发布版本](persona-v4-history-old-version.png)，打开[石猴旧档案](persona-v4-history-old-archive.png)，可看到原有基线与可用状态；再选失败版本仍为0/2，不显示旧版审计变化。
- 切到另一部书，历史入口清空，没有残留上一书的档案上下文；两书实际全来源失败/检查点分别保留，见[西游记](v16-source-checkpoint-xiyou.png)、[红楼梦](v16-source-checkpoint-red.png)。

[DOM及服务证明](history-anchor-ui-proof.json)将选择状态、版本、基线显示与实际旧Agent哈希关联，所有断言通过，旧Agent仍与提取前哈希一致。[只读请求](history-anchor-ui-read-audit.json)模型调用0；QA拒绝构建/重试等写操作。首次旧档案侧栏的表达状态读请求被QA拦截，随后仅放行get_expression_set/list_expression_materials并重开验证，最终截图没有该QA错误；没有绕过生产权限。临时浏览器与QA服务已关闭。

这是实际组件和保存记录的操作验证，未冒充完整Electron导航、模型质量或新失败档案的发布成功。

## 最终验证

完整项目**464通过、13项既有环境跳过、14项既有警告，575.82秒**（本地`tmp/history-anchor-final-project.log`）。限定模块、两个Handler与评测入口Mypy55文件、Ruff、相关组件ESLint、前端类型和生产构建通过；构建保留既有大块体积警告。未宣称全仓follow-imports=silent类型无错误。

T04历史回溯回归已修复；T17/T12的真实模型及完整全书要求仍未通过，见[本轮原生结果](2026-10-15-grouped-discovery-persona-validation.md)。
