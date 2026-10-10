# 书籍人物 Agent 理论复核与主题 / 自由聊天设计

日期：2026 年 10 月 10 日。状态：设计复核与首版补充，尚未实现运行时。

## 复核结论

现有“原著证据 → 人物允许知识 → 人物回复 → 校验 → 有限轮次发布”方向成立，能找到认知 Agent、角色扮演和多人对话研究的支持。但这属于参考理论与工程约束的组合，不能宣称已经实现完整 BDI/OCC 系统，或已证明人物不会越界。

复核前，natural / directed / all 只规定谁发言，natural 已提供自由讨论的调度基础；主题聊天缺少持久主题、模式切换、轮次快照和验收规则。本次将 free / topic 补为独立的讨论方式，保留原有发言方式。两种讨论方式均列入首版 T17，当前生产系统尚未支持人物聊天运行时。

## 理论与研究依据

以下均为一手出版物或官方文档。表中的工程对应是本次设计推论，不是论文对 Octopus 的实验结果。

| 依据 | 支持的思想 | 对当前设计的应用与边界 |
| --- | --- | --- |
| Rao / Georgeff，BDI，ICMAS 1995，[论文](https://cdn.aaai.org/ICMAS/1995/ICMAS95-042.pdf) | 信念、目标和意图共同参与行为选择 | 已有信念与固定基线；补充有原著依据的动机/价值优先级及本次对话意图。采用轻量映射，不引入完整符号规划器 |
| Fagin 等，Reasoning About Knowledge，1995，[出版方](https://direct.mit.edu/books/monograph/1825/Reasoning-About-Knowledge) | 从不同 Agent 的视角讨论知识及对他人知识的理解 | 保持世界事实、人物信念、本人知情和公开听说分离；数据库允许集是工程落实，不是完整认识逻辑证明 |
| Ortony / Clore / Collins，情绪评价理论，2022 第二版，[章节](https://www.cambridge.org/core/books/abs/cognitive-structure-of-emotions/appraisal-the-value-system-and-primary-sources-of-intensity/A42C0763DCFB4AF678BF0F26EA422085) | 事件对目标的影响、行为与规范的关系、对象偏好参与情绪评价 | 情绪候选记录触发消息和原著模式依据，动态情绪留在本房间；不把一句“你很生气”直接写成新人格 |
| Park 等，Generative Agents，2023，[论文](https://arxiv.org/abs/2304.03442) | 记录经历、检索、反思和规划可用于形成可信行为 | 用于房间记忆和摘要；用户要求固定原著基线，因此不沿用开放世界中持续改写所有信念/关系的行为 |
| Ran 等，BookWorld，ACL 2025，[论文](https://aclanthology.org/2025.acl-long.773/) | 从小说构造人物世界并组织互动具有直接研究先例 | 支持自动构建路线；其故事生成评测不能替代本项目的私密知情隔离、跨书交流或交互验收 |
| Sacks / Schegloff / Jefferson，1974，[原文](https://www.conversationanalysis.org/wp-content/uploads/2019/06/04_Sacks_Schegloff_Jefferson_A_simplest_systematics_fir_the_organization_of_turn-taking_for_conversation_Language_.pdf)，AutoGen [选人](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/selector-group-chat.html)与[终止](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html) | 对话需要话轮组织；多 Agent 系统可将选人和终止条件分开 | 主持人调度、@ 定向、顺序消息和有限轮次有依据；每轮至多三人、每人一次和 60/300 秒是项目设计值，不是理论推导 |
| Wang 等，InCharacter，ACL 2024，[论文](https://aclanthology.org/2024.acl-long.102/) | 人物忠实度还应评测价值、人格表现，不能只检查名字和措辞 | 增加情境访谈、两难选择和重复提问一致性；量表可作辅助，不能无依据给文学人物填完整人格分数 |
| Liu 等，Tell Me What You Don’t Know，Findings ACL 2025，[论文](https://aclanthology.org/2025.findings-acl.311/) | 角色模型面临上下文知识与参数知识冲突，拒答和过度拒答都需评估 | 原著允许集不等于抹去模型预训练知识；增加未知事实、错误前提、跨书信息和非冲突问题测试。首版不采用其模型表示编辑方案 |

## Agent 设计修正

角色持久基线增加“动机/目标与价值优先级”的显式槽位，用现有 trait、belief、relation 等断言及人物获知权限提供依据。基线槽位可标注 goal、value_priority、emotion_pattern 等用途，不新增无出处设定。未能抽取的项为 unknown，不能为了组成 BDI 三项而补造人物欲望。

运行时在受限上下文中选择本次对话行为，如回答、询问、质疑、安慰、回避或沉默。保存的是行为类别与依据 ID，供校验及调度使用；不要求保存模型隐藏推理。原著动机是稳定依据，对话意图是本次行为，二者不能混用。

情绪候选包含 trigger_message_ids 与 pattern_claim_ids，分别指向当前房间同 epoch 的已发布消息和本人可用原著模式。校验后才能更新成员 ephemeral_state，生成失败或停止不保留未批准情绪；房间重置清除。首版不加入持续关系演化，也不默认计算未经验证的情绪数值公式。

允许的自由表达包括寒暄、提问、对眼前公开对话的回应和有原著价值依据的情境推演，不要求原书出现问题的原句。对具体事件、自传经历、他人秘密和世界设定的断言仍需依据。未知现代事物可以请求解释，用户解释归为房间听说；不能自称在原著生活中亲历。

发布校验继续覆盖正文实际断言及遗漏，不能通过把内容标成 conversation / inference 绕过检查。语义人设一致性和参数知识泄漏属于真实模型质量风险，SQL 结构测试不证明已解决。

## 两层聊天方式

| 讨论方式 | 内容范围与用户操作 | 自动选人依据 | 结束规则 |
| --- | --- | --- | --- |
| 自由聊天 free，默认 | 没有固定主题，可闲聊、追问或转换话题 | 当前问题、最近公开对话、公开人物相关性与发言公平性 | 每次用户提交一轮，结束后等待用户 |
| 主题聊天 topic | 用户设置主题，可填写讨论目标，如“选择与命运”；跨轮保留并在顶部展示 | 当前主题加本次问题，仍只使用公开选人信息 | 同样一轮结束等待用户；用户可主动继续、换题或结束主题 |

两种方式都支持 natural（自动选择至多三人）、directed（@ 一个或多个）和 all（@全体）。例如“主题聊天 + @全体”是一种有效组合。“自由”只取消固定主题，不取消原著范围、禁言、人数/消息预算或用户秒数上限；时间设置仍由发言方式 directed/natural/all 选择。

主题是讨论材料，不是人物新知识或高优先级系统指令。涉及书外信息时只引用本房间公开听说。主题聊天允许不同观点和短暂插话；偏题时给轻量回归提示，不伪造所有人物达成共识，也不为迎合主题给人物补充世界知识。

“继续”对 paused / interrupted 轮次只处理原剩余队列；已 completed 后用户点击“再讨论一轮”才创建新轮次。两种方式均无自动连续互聊，前一人物的发言不启动额外轮次。总结是用户主动操作，只总结本 epoch 公共消息，保留观点归属、分歧及不确定性，不写入原著；内部主持人不另占人物座位。

## 存储与协议

book_rooms 增加 discussion_mode（free/topic）、discussion_topic、discussion_goal 和 discussion_revision。free 时主题及目标为空，topic 时主题为非空文本；目标可为空。服务端校验长度，首版主题上限为 200 个 Unicode 码点，目标为 1000 个码点，非法更新不截断或部分保存。

book_room_rounds 增加 discussion_snapshot_json，记录 revision、mode、topic、goal。每个新轮次由服务端从房间构造快照，发布后和手动恢复时不改变。模型不能声明或更新模式。房间配置保存 expected_discussion_revision，更新与创建轮次在短事务中互斥；存在 queued/running/paused/interrupted 轮次时返回 room_busy，需结束当前轮后再换模式或主题。

book_room set_discussion 输入 room_id、expected_epoch、expected_discussion_revision、discussion_mode、topic、goal。get 返回讨论配置；submit_turn 扩展 expected_discussion_revision，mode 继续表示原有发言方式，服务端派生快照。旧客户端未传新版本条件时使用当前配置，并明确返回实际快照；新版界面必须传 expected 值。新主题和模式不改变 room_id 或 epoch，不清空历史或重新生成 Agent。

原著检索始终固定本人 CanonicalScope；主题只影响允许集中的相关性排序。房间摘要和消息仍按 R 隔离，主题版本不是新的权限边界，旧主题的房间经历仍可被当前人物记住。用户需要全新记忆时单独重置房间。

## 界面与实施

圆桌顶部新增“自由聊天 / 主题聊天”切换。主题模式展开主题和可选目标；右侧输入栏保留独立的“自动选人 / @ 人物 / @全体”。模式切换不自动发送消息或改变座位，忙时显示当前轮需先结束。当前轮次显示所使用的主题快照，而非误用后来编辑的草稿。

T03 补充有依据的动机/价值槽位，T06 补充对话行为与情绪触发的校验，T08 保持选人与话题解耦。新增 [T17](F:/god/project/Octopus/docs/plans/book-character-agents/tasks/17-discussion-modes.md) 落实配置、轮次快照、两种模式、界面及恢复；T12 同时等待 T17 并执行真实模式组合评测。

验收必须分别检查主题相关性、自由转换话题、个人视角与人格稳定性。固定样本覆盖 free/topic × natural/directed/all 六种组合、暂停恢复、换题冲突、同名 @、禁言移除和跨书未知信息。真实模型增加目标冲突、情绪触发、参数知识诱导和合理问题过度拒答，不用一种综合分数掩盖任何边界失败。

