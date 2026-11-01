# 五阶段操作卡

每张卡包含：目标 / 动作序列 / 调用指令 / 交接物 / 出口 checklist / 常见失败。主文件 SKILL.md 的路由表按阶段编号索引到本文件。手动型技能（磁盘协议调用）的路径表与解析规则见 SKILL.md 第 4 节；门控以 SKILL.md 第 5 节 Gate Registry 的 G1-G7 唯一编号引用。

## 阶段① 问清需求

**目标**：把"要做什么"聊到没有关键歧义——谁会用、怎样算做完、失败怎么办、这次不做什么。

**动作序列**

1. 先自查：列出悬而未决的问题，标出哪些能从代码、文档、现有测试中找到答案 → 自己读代码回答，**不把查资料变成问用户**。
2. 交互效果光聊定不下来（布局、流程、手感）→ 调用 Skill `prototype` 做一个可运行的小原型，体验后再决定。
3. 调用 Skill `grilling` 对剩余问题逐条访谈；涉及领域词汇、边界概念 → 调用 Skill `domain-modeling`（通道 B 磁盘读取时用物理目录 `domain-modeling-2`，见 SKILL.md 第 4 节）沉淀 ADR 与词汇表。
4. **方案调研**（新项目 / 新功能 / 新独立模块时执行；bug 修复与既有架构内的小改动跳过）：先检索再写码。用 GitHub 搜索与网络搜索，以已澄清的需求为关键词，找可直接使用或二次开发的开源项目。对候选逐项分析：是否仍在维护（最近提交 / release / issue 活跃度、是否归档）、部署是否简单、哪些功能可直接复用、哪些地方需要修改、License 是否与本项目兼容。产出三选一建议——**直接使用 / 基于改造 / 从零开发**——并给出最快跑通 MVP 的路径。**建议与依据交用户拍板**（G2，hard gate）。检索工具不可用时如实告知、标注"未做方案调研"，由用户决定继续或停止。既有架构内的小型功能增强，调研可在 1–2 次检索内收口、无需展开完整候选分析（见 SKILL.md 第 3 节流程压缩）。
5. （用户明确要求完整版时）Read `grill-with-docs` 的 SKILL.md（路径见 SKILL.md 第 4 节）按其协议执行；grill-with-docs 与直接调用 grilling / domain-modeling 互斥，不得重复访谈。

**调用指令模板**

> 调用 Skill 工具（skill: `grilling`），围绕以下未决问题逐条访谈用户：<清单>。代码可答的问题已自行回答，依据见：<文件/行>。

**交接物**：澄清记录（问题 → 答案 → 依据）；方案调研记录（候选项目 → 维护 / 部署 / 复用点 / 修改点 / License 分析 → 三选一建议）；领域词汇表与 ADR（若走了 domain-modeling）。

**出口 checklist**

- [ ] 谁会用、使用场景明确
- [ ] 成功标准（怎样算做完）明确
- [ ] 失败路径（权限、空状态、异常、重试）明确
- [ ] 范围边界（这次不做什么）明确
- [ ] G1：用户对以上逐条确认
- [ ] G2（仅新项目 / 新功能 / 新独立模块）：复用决策经用户确认

**常见失败**：一路点头接受 AI 的建议；把代码能答的问题拿去问用户；跳过方案调研从零重造现成轮子（Token 与时间白费）；不查维护状态与 License 就引入外部项目；为省 Token 强行套用不合需求的项目；未定义失败路径就进入规格。

## 阶段② 写成规格

**目标**：把已确认的讨论固化为规格——覆盖四个语义必需字段。不再访谈，不发明新需求。

**动作序列**

1. Read `to-spec` 的 SKILL.md（路径见 SKILL.md 第 4 节），按协议执行；无 tracker 配置时注入本地文件模式（见 SKILL.md 第 2 节），规格写 `docs/specs/<slug>.md`。
2. 探索代码库现状（若阶段① 尚未充分探索）；全文使用项目领域词汇，尊重既有 ADR。
3. 规划测试 seam：优先既有 seam，能用高层不用低层，新 seam 提在最高处；**seam 方案交用户确认**（G3，hard gate）。
4. 按 canonical schema 写规格并发布：tracker 配置存在 → 按 tracker 发布并打 ready-for-agent 标签；否则本地写 `docs/specs/<slug>.md` 并注明本地文件模式。

**规格 canonical schema（本节是规格结构的唯一事实源）**

规格的结构不强制单一标题形态，但以下四个**语义必需字段**必须存在且非空。gate 与 evaluator 一律按语义检查（经 alias 表映射），不做字面标题匹配：

| 语义字段 | 含义 | 可映射的标题别名 |
|---|---|---|
| User Behavior | 用户视角的问题与解法（问题是什么、解成什么样、谁受益） | Problem Statement、Solution、User Stories |
| Constraints | 约束：技术、兼容、依赖、已定的实现决策 | Constraints、Implementation Decisions |
| Test Plan | 测试方式：seam、用例、验收标准 | Test Plan、Testing Decisions |
| Out of Scope | 这次不做什么 | （无别名，必须明确存在） |

**模板（四节形态，适用于从零撰写）**：

```markdown
## Problem Statement   # 用户视角的问题（→ User Behavior）
## Solution            # 用户视角的解法（→ User Behavior）
## Constraints         # 约束：技术、兼容、依赖（→ Constraints）
## Test Plan           # 测试方式：seam、用例、验收标准（→ Test Plan）
## Out of Scope        # 这次不做什么
```

**映射示例**：to-spec 协议产出的七节规格（Problem Statement / Solution / User Stories / Implementation Decisions / Testing Decisions / Out of Scope / Further Notes）按 alias 表映射后四个语义字段齐全，是合法规格——Problem Statement + Solution + User Stories 映射为 User Behavior，Implementation Decisions 映射为 Constraints，Testing Decisions 映射为 Test Plan，Out of Scope 原样命中，Further Notes 为附加节不参与判定。

**语义校验规则**：一个规格合法，当且仅当经 alias 表映射后四个语义字段均存在且非空。SKILL.md 阶段② 出口 gate 与 eval 断言按此规则判定；标题变体（中英文、分节更细）不导致合法规格被误判。

**bugfix 轻量规格模板**（bug 修复类流程压缩专用，见 SKILL.md 第 3 节；不强制落七态工单状态，但 G5 / G6 实质不可省）：

```markdown
## Reproduction      # 复现：命令、真实错误输出、退出码
## Root Cause        # 根因说明
## Fix               # 最小修复方案
## Regression Test   # 原始症状的回归测试（必须真实通过）
## Out of Scope      # 这次不做什么
```

**出口 checklist**

- [ ] 经 alias 表映射后四个语义字段齐全且非空，内容全部来自已确认的对话
- [ ] G3：seam 方案经用户确认
- [ ] 已发布（tracker 或本地路径），路径已告知用户

**常见失败**：规格夹带访谈没确认过的新决策；按字面标题机械匹配、把别名义规格误判不合格；seam 越切越碎；忘记声明本地文件模式。

## 阶段③ 拆小任务

**目标**：规格 → 可独立演示的纵向切片，依赖显式，完成可判定。

**动作序列**

1. Read `to-tickets` 的 SKILL.md（路径见 SKILL.md 第 4 节），按协议执行。无 tracker 时注入本地文件模式：`.scratch/<slug>/issues/<NN>-<slug>.md`，每票一个文件，Blocked by 以文本声明。
2. 按"用户行为"切片，不按技术层切片：表单+接口+存储+成功提示是一票，不是四票。
3. 找 prefactor 机会——"先让改动变容易，再做容易的改动"，但每张 prefactor 票同样要能验证。
4. **工单清单与依赖关系交用户确认**（G4，hard gate）。
5. 确认后各票落状态 `approved`（状态机见 SKILL.md 第 6 节）；根票 Blocked by 声明为 `None`，不得留空。

**拆分检查三问**：每票能演示吗？依赖明确吗？完成可判定吗？

**出口 checklist**

- [ ] 每票独立可演示
- [ ] Blocked by 显式声明（根票写 `None`），依赖链成立
- [ ] 每票有可判定的完成标准
- [ ] G4：用户确认拆分粒度与顺序

**常见失败**：按技术层拆票（前端票 / 后端票）；依赖没写导致并行踩空；一票大到无法演示；根票 Blocked by 留空而非显式 `None`。

## 阶段④ 实现与验收

**目标**：一票一票实现，每票都有真实验证证据，验收后才算完成。

**动作序列（单票，固定顺序执行）**

1. 记录票开始前的 **baseline commit**（或 integration tip），作为本票 review 与回退的 fixed point；票状态置 `implementing`。
2. 调用 Skill `tdd`，在已确认（G3）的 seam 上测试先行。
3. 运行类型检查（项目有配置才跑）、单票测试；整票完成跑一次完整测试套件。
4. 执行 **fresh verification**：保存实际运行的命令、完整 stdout/stderr、退出码及 passed/failed/skipped 数量。旧输出、部分测试和 agent 自报成功均不可替代。
5. 调用 Skill `verification-before-completion` 对照核查；证据不齐不得进入下一步。
6. 调用 Skill `code-review`（Standards + Spec 两轴），**必须传入**：fixed point（步骤 1 的 baseline commit）、spec 路径、ticket 路径、tracker fallback 状态。reviewer 是只读角色，不得修改实现，也不计入 implementer 并行。
7. 处理 review 发现的问题或说明不处理的原因；改动涉及实现 → 回到步骤 4 重新 fresh verification。
8. G5 达成（票状态 `verified` → `reviewed`）后，请求用户人工走查（G6，hard gate）：告诉用户怎么跑、操作什么、预期看到什么。
9. 用户确认后票状态置 `walkthrough-approved`；最后 commit，票状态置 `done`。
10. **只有 `done` 的票解除下游 Blocked by**；未通过 G5 / G6 的票不得 `done`，也不得解除下游。

**并行升级**：满足 SKILL.md 第 6 节 G7 全部条件后，Read `implement-spec` 的 SKILL.md（路径按 SKILL.md 第 4 节的模式）按协议执行（worktree + 集成分支 + 实现者子代理 + context pointer 沟通）。并行事件规则（首票 E2E 前 `implementer_spawn = 0`、`worktree_create = 0`；reviewer 不得改实现；G7 未通过不得启动 implement-spec）见 SKILL.md 第 6 节。

**出口 checklist（每票）**

- [ ] G5：fresh verification 证据齐（命令原文、完整 stdout/stderr、退出码、passed/failed/skipped 计数）
- [ ] G5：code-review 完成且问题已处理或说明
- [ ] G6：用户走查确认
- [ ] 未验证项已列出
- [ ] 票状态已置 `done`，commit 完成

**常见失败**：测试通过就单方面宣称"完成"（没走查）；引用旧输出或编造测试输出充数；code-review 未传 fixed point 导致 review 范围失控；未经 G7 确认就并行；把 reviewer 子代理计入并行。

## 阶段⑤ 复盘改进

**目标**：从执行记录里找过程问题，让下次少走弯路。任务成功也值得复盘。

**入口**：完整工作流下，**所有工单状态为 `done`** 才能进入本阶段。

**动作序列**

1. Read `retro` 的 SKILL.md（路径见 SKILL.md 第 4 节），按协议执行（读会话记录 / 执行日志）。
2. 按类别找候选问题：

| 遇到的问题 | 怎么改 |
|---|---|
| 查找费劲 | 补清楚入口、目录说明与相关文档 |
| 参考过时 | 更新或移除误导 agent 的旧资料 |
| 重复犯错 | 能自动判断的规则变成测试、lint 或 CI 检查 |
| 需要判断 | 把有证据的经验写进项目规范 |

3. 改进候选按严重度排序交用户取舍。
4. 原则：**用真实执行记录改流程，不靠堆更多提示词。**

**出口 checklist**

- [ ] 至少检查了导航、自动化检查、编码规范三类
- [ ] 每个改进项有明确落点（哪个文件 / 哪个检查 / 哪份规范）
- [ ] 用户确认取舍

**常见失败**：复盘变成表扬会；改进项没有落点；把需要判断的经验硬塞给自动化检查。

## 降级操作卡：外部技能缺失时的内联最小流程

> 触发条件（见 SKILL.md 第 7 节）：某阶段技能文件缺失、损坏，或通道 B 协议路径（按 SKILL.md 第 4 节 `<skills-root>` 规则解析）解析失败，或第 4 节解析规则第 6 条的递归依赖缺失。此时不调用对应外部技能，按本卡以本技能内联指引跑通五阶段最小流程。

**目标**：在专项技能不可用时仍跑通"访谈 → 规格 → 拆票 → 实现+验证 → 复盘"，保住门控与验收证据底线，产出质量不低于本卡"交接物"列出的质量下限。

**动作序列**

1. 先标注：**首次可见状态消息**固定为"已降级（缺失：<技能名 / 路径>）"，并列出缺失清单与受影响阶段，不隐藏降级事实。
2. 按阶段内联最小步骤推进：
   - ① 问清需求：自行逐条访谈用户，问清"谁会用 / 怎样算做完 / 失败怎么办 / 这次不做什么"（套用 SKILL.md 第 5 节门控指令模板）；新项目 / 新功能 / 新独立模块仍须做方案调研（G2）；交互效果存疑时不能调 prototype，改为文字描述决策并请用户确认。
   - ② 写成规格：按本文件阶段② canonical schema 在本地写 `docs/specs/<slug>.md`（可写简版，但经 alias 表映射后四个语义字段必须齐）；bug 修复类用轻量规格五节模板。
   - ③ 拆小任务：按"用户行为"纵向切片，逐票显式声明 Blocked by（根票写 `None`）；无 to-tickets 协议时每票写一个 `.scratch/<slug>/issues/<NN>-<slug>.md`。
   - ④ 实现与验收：测试先行 → 运行真实测试并引用输出 → 自查 diff（替代 code-review 两轴，G5 证据标准不变）→ 请求人工走查（G6）。
   - ⑤ 复盘改进：按本文件阶段⑤ 三类（导航 / 自动化 / 规范）检查并列改进落点（可只列清单）。
3. **user-confirmation 类门控（G1 / G2 / G3 / G4 / G6 / G7）在降级态下仍必须停下等用户**；G5 为 evidence-based 门控，照常按证据判定，不因降级放松。并行升级默认关闭（无 implement-spec 协议即无 worktree 编排，G7 的宿主能力条件不满足），除非用户明确要求且宿主能力核实可用。

**交接物**（质量下限——"必须产出"与"可省"分列）

- 必须产出：访谈澄清记录（问题 → 答案 → 依据）；简版规格（四语义字段齐）；工单清单（每票含 Blocked by）；**真实测试输出原文**（引用，不编造；bug 修复类须含回归测试且真实通过）；未验证项清单；走查请求与用户确认记录。
- 可省（相对完整流程）：方案调研的完整候选分析（可收口为 1–2 次检索，或如实标注"未做方案调研"）；prototype 交互原型；domain-modeling 的 ADR / 词汇表；tracker 发布动作与标签；复盘改进的自动化落地（可仅列清单）。

**出口 checklist**

- [ ] 首条可见状态消息已标注"已降级"并列出缺失技能 / 路径
- [ ] 五阶段最小步骤均已执行（可压缩，但 user-confirmation 门控与 G5 证据不可省）
- [ ] 简版规格经 alias 表映射后四语义字段齐
- [ ] 工单每票含 Blocked by（根票写 `None`），完成可判定
- [ ] 真实测试输出已引用，未验证项已列出
- [ ] G6：用户走查已请求并获确认

**常见失败**：把"已降级"藏着不标（用户误以为走的是完整流程）；拿降级当借口跳过门控或省略真实测试；缺失技能只报一个却漏报其余；用编造的测试输出充数。
