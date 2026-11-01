---
name: code-task-workflow
description: "代码任务全流程编排：非琐碎代码任务按五阶段推进（问清需求、写成规格、拆小任务、实现与验收、复盘），琐碎修改（单个交付文件、小 diff、无歧义）走快路径直接完成，单点任务（只写测试 / 只 review / 只访谈 / 只定位根因）让位给对应专项技能；阶段操作卡与编码纪律按需加载——进入某阶段读 references/phases.md 对应章节，涉及代码变更先读 references/coding-style.md，涉及防御性代码加读 references/defensive-code.md。适用：新功能实现、bug 修复、跨文件重构、配置或脚本变更、从需求到规格 / 工单 / 实现 / 验证的完整交付，或用户说“走工作流”“按流程来”“代码任务工作流”“完整做这个任务”“code workflow”“do this properly”。不适用：只做 code review、只写测试、只做需求访谈、只定位根因、纯知识问答、只运行现有测试并报告——这些让位给对应专项技能。Produces: 方案调研与复用三选一建议（直接用 / 改造 / 从零写）、规格文档、带依赖声明的工单、真实测试输出与验收证据、复盘清单。"
version: 1.7.0
agent_created: true
---

# 代码任务工作流（Code Task Workflow）

你是编排器，不亲自提供各阶段的方法论。你的职责：判定任务走哪条路径、按正确顺序推进阶段、在每个阶段门口核实退出条件、在正确的时机把控制权交还给用户。本文件只做路由：各场景的规则正文在 references/ 下按需加载，未列入路由的文件不会被加载；新增规则文件时同步补入路由。

> **底线：先跑通一个小任务端到端，再考虑多 agent 并行。**

## 0. 编码纪律（全路径适用，正文见 references/coding-style.md）

以下优先级链是全局裁定规则，适用于三条路径（快路径 / 让位 / 完整工作流）的每一次代码变更：

```text
用户明确要求
> 仓库 AGENTS.md / CLAUDE.md 与项目规范
> code-task-workflow 门控（G1-G7）
> 阶段协议方法
> 通用建议
```

- **总纲：每次执行任务遵循 Karpathy guidelines 四原则**：开工前调用 Skill `karpathy-guidelines` 逐条对照执行。Karpathy 状态全程只记录两种：`loaded`（已加载并对照执行）或 `unavailable_reported`（不可用且已显式报告）。技能不可用时在汇报中如实标注，**不阻塞最小流程**，按编码纪律正文执行。
- **编码纪律正文按需加载**：凡涉及代码变更——快路径动手前、bugfix 压缩路径动手前、完整工作流进入阶段④ 前——Read [references/coding-style.md](references/coding-style.md)（一次任务读一次）。若改动会新增校验、判空、try/except、锁、默认值等防御性代码，或需 review 此类改动，同时 Read [references/defensive-code.md](references/defensive-code.md)。成功标准与验收证据同时由 G1-G7 门控及快路径证据要求强制。

五个阶段依次为：① 问清需求 → ② 写成规格 → ③ 拆小任务 → ④ 实现与验收 → ⑤ 复盘改进。每阶段详细操作卡见 [references/phases.md](references/phases.md)，进入某阶段时读对应章节。

## 1. 路径判定

接到任务先判定走哪条路径：**快路径**（琐碎，直接干）、**让位**（单点任务，交给专项技能）、**完整工作流**（其余全部）。

### 1.1 快路径豁免

**全部满足**以下判定字段时走快路径，直接干活：

```text
deliverable_files = 1     # 交付文件：代码、README/文档、配置、脚本
new_surface = false       # 不引入新接口、新数据结构
new_dependency = false    # 不引入新依赖
ambiguity = false         # 无行为歧义（没有“谁会用、失败怎么办、边界在哪”这类问题）
estimated_diff < 10       # 预计 diff 小于 10 行；机械替换类任务豁免此条（见下）
one_check = true          # 一次运行 / 测试即可验证结果
```

**口径**：

- “单个交付文件”指产品交付物文件（代码、README/文档、配置、脚本）；**为验证而新增或修改的测试文件不计入**该数量。
- **机械替换类豁免**：全局重命名、批量文本替换（如全库 python → python3）不扩散改动语义，按 1 处变更计，**豁免 `estimated_diff < 10` 条件**——只要仍满足 `deliverable_files = 1` 且 `one_check = true` 即可走快路径。该豁免只适用于纯机械替换，替换中掺杂逻辑修改即失效。
- 快路径同样必须留下验证证据：最小成功标准（判定做完的判据）、Karpathy 状态、真实验证证据（diff / grep / 测试输出）。bug 修复走快路径仍须附回归测试并真实通过。
- 重命名 / 改名类任务默认按快路径处理，“重构”字样本身不改变判定；仅当其改动扩散、超出上述合取条件（如调用点散落多文件）时才离开快路径。

**正例**：README 中 python 命令改为 python3——机械替换、单交付文件、一次 grep 可验证，走快路径：不创建规格、工单或访谈记录，但记录最小成功标准、Karpathy 状态和验证证据。

快路径动作：直接实现 → 运行验证 → 汇报结果。汇报首行注明：`已走快路径，跳过工作流。原因：<逐条对照判定清单的结论>`。

### 1.2 单点任务让位

任务只涉及一个专项能力时，让位给对应技能，不走本工作流：

- 只写测试 → Skill `tdd`；
- 只做代码审查 → Skill `code-review`；
- 只做需求访谈 / 方案压力测试 → Skill `grilling`；
- 只定位一个 bug 的根因 → Skill `systematic-debugging` / `diagnosing-bugs`。

判定标准：该任务的产出**就是**那个专项能力的产物本身，而非其产物服务于更大的交付。拿不准（例如“写测试”是完整功能开发的一部分）→ 按完整工作流处理，在对应阶段调用专项技能。若输入含实现成分（如“顺手改掉”“一并修掉”“把明显的小问题改掉”），产出已不止是审查产物本身，不得纯让位 `code-review`，按完整工作流处理、在阶段④ 调用 `code-review`。

### 1.3 进工作流

快路径与让位都不适用 → 进入完整工作流，先做第 2 节的前置检查。

## 2. 前置检查

进入阶段 ① 之前完成两项检查，结果在**首次可见状态消息**中报告：

1. **git 仓库**：运行 `git rev-parse --is-inside-work-tree`。不是仓库 → 询问用户是否由你执行 `git init`（经确认后初始化并继续；用户拒绝则工作流暂停在起点）。
2. **issue tracker**：检查 `docs/agents/issue-tracker.md` 是否存在。
   - 存在 → 读取并按其配置使用 tracker。
   - 不存在 → **不阻塞，本地 Markdown 即正式 fallback**：规格写 `docs/specs/<slug>.md`，工单写 `.scratch/<slug>/issues/<NN>-<slug>.md`（若 to-tickets 协议自身的本地路径约定存在，以其为准）。**发现缺失时立即报告**“未配置 tracker，使用本地文件模式”，不得写“下次汇报”；`/setup-matt-pocock-skills` 仅作为升级建议提及，**不是继续工作的前置条件**。
   - 调用 to-spec / to-tickets / code-review 时，把 tracker fallback 状态（本地文件模式 + 产出路径）作为输入注入，这些协议技能须接受该注入而非要求 tracker 配置。

## 3. 五阶段路由表

| 阶段 | 入口条件 | 核心动作 | 出口门槛（gate） | 调用方式 |
|---|---|---|---|---|
| ① 问清需求 | 任务进入工作流 | 代码能回答的自己读代码；交互效果存疑 → prototype；新项目 / 新功能 / 新独立模块：检索已有开源方案，产出复用三选一建议；其余逐条访谈用户 | G1 需求确认；新项目 / 新功能 / 新独立模块另加 G2 复用决策 | Skill：`grilling`、`domain-modeling`、`prototype`；磁盘协议：grill-with-docs |
| ② 写成规格 | G1 通过（及 G2，若适用） | 综合对话成规格，不再访谈、不发明新需求 | 规格含四个语义必需字段（见 phases.md canonical schema，标题允许别名）且 G3 seam 确认 | 磁盘协议：to-spec |
| ③ 拆小任务 | 规格已确认 | 纵向切片，每票可独立演示，显式声明 Blocked by | G4 工单拆分与依赖确认 | 磁盘协议：to-tickets |
| ④ 实现与验收 | 工单确认（G4），待做票的 Blocked by 均为 done | 一次一小票，固定执行序列见 phases.md 阶段④：baseline → TDD → 验证 → review → 走查 → done | G5 真实验证与 review 完成（证据类）+ G6 用户走查确认 | Skill：`tdd`、`code-review`、`verification-before-completion`；磁盘协议：implement |
| ⑤ 复盘改进 | **所有工单状态为 done**（完整工作流） | 读执行记录找：导航费劲 / 引用过时 / 重复犯错 / 需要判断的经验 | 产出可执行改进清单（测试 / lint / CI / 项目规范）并交用户取舍 | 磁盘协议：retro |

拆票示例（反馈功能）：A 提交成功（表单→接口→存储→提示）→ B 失败重试 → C 历史记录（Blocked by A）。按用户行为切片，不按技术层切片。根票的 Blocked by 声明为 `None`，不得留空。

**流程压缩**：完整五阶段允许按任务类型省略部分环节，但**门控与验收证据要求不可省略**：

- bug 修复类：跳过方案调研（阶段① 动作 4），规格降为**轻量规格**（五节：Reproduction / Root Cause / Fix / Regression Test / Out of Scope，模板见 phases.md），仍须附回归测试并真实通过（G5）与用户走查（G6）。bugfix 压缩路径不强制落 references/tickets.md 的七态工单状态，但 G5 / G6 的实质证据不可省。
- 既有架构内的小型功能增强：方案调研可在 1–2 次检索内收口，无需展开完整候选分析；
- 其余任务走完整五阶段。压缩了什么，在汇报中注明。

## 4. 技能调用适配器（路由入口）

技能分两类调用通道：**通道 A — Skill 工具直接调用**（宿主提供 Skill API，且技能 frontmatter 的 `name` 可被解析）；**通道 B — 磁盘协议**（grill-with-docs / to-spec / to-tickets / implement / implement-spec / retro 等设置了 disable-model-invocation 的技能，Read 其 SKILL.md 执行）。

通道调用指令模板、解析规则（含逻辑名与物理目录映射、互斥、递归依赖检查、能力降级）、`<skills-root>` 定位与各阶段磁盘路径表见 [references/invocation.md](references/invocation.md)——**首次调用外部技能或走通道 B 前读取**；路径解析失败时同样按该文件处理（报告具体路径与原因，按第 7 节降级，不得静默跳过或凭猜测的协议继续）。

## 5. Gate Registry（唯一门控注册表）

所有门控以 G1-G7 唯一编号引用，SKILL.md、phases.md、降级操作卡与 eval 断言一律使用该编号，不再使用“六处门控”等模糊计数。`type` 字段区分两类门控，证据形态与判定方式不同：

- **user-confirmation**：必须停下来等用户。任何“我假设没问题”都算执行错误，即使代码正确。
- **evidence-based**：由真实证据判定（命令输出、文件 diff、事件日志），机器可核查，不需要用户参与；用户口头认可不能替代证据。

| Gate | 名称 | type | 触发条件 | 通过标准 |
|---|---|---|---|---|
| G1 | 需求确认 | user-confirmation | 任务进入阶段① | 用户逐条确认：谁会用 / 怎样算做完 / 失败怎么办 / 这次不做什么 |
| G2 | 复用决策 | user-confirmation | 仅新项目 / 新功能 / 新独立模块 | 三选一建议（直接使用 / 基于改造 / 从零开发）与依据交用户拍板；禁止跳过调研直接从零写，禁止未经确认引入外部项目 |
| G3 | 测试 seam 确认 | user-confirmation | 阶段② 写实现前 | 计划的 seam 方案交用户确认 |
| G4 | 工单拆分确认 | user-confirmation | 阶段③ 拆票后 | 工单清单与 Blocked by 依赖关系经用户点头 |
| G5 | 真实验证与 review 完成 | evidence-based | 阶段④ 每票实现后 | fresh verification 证据（命令、完整 stdout/stderr、退出码、passed/failed/skipped 计数）+ code-review 完成且问题已处理或说明；旧输出、部分测试、agent 自报成功均不可替代 |
| G6 | 用户人工走查确认 | user-confirmation | 阶段④ 每票 G5 通过后 | 用户确认走查（告知运行命令、操作步骤、预期结果）；未获确认不得宣称该票完成 |
| G7 | 并行升级确认 | user-confirmation | 从 implement 串行切 implement-spec 前 | references/tickets.md 的并行升级条件全部满足，含用户明确同意与宿主能力核实 |

门控指令模板：

> **[门控-G<x>-等待用户]** 在此停止。把 <问题清单 / seam 方案 / 工单拆分 / 走查请求 / 复用决策> 交给用户，收到回复后才能继续。禁止代替用户回答，禁止把未经验证的假设当作通过。

**合并提问**：多个 user-confirmation 门控可合并为一次提问（例如 G1 与 G2 一次问完），但每一项确认都必须得到用户的明确回应，不得因合并而省略任何一项。evidence-based 门控不参与合并提问，由证据独立判定。

## 6. 工单状态与并行升级（路由入口）

完整工作流的工单按七态状态机流转（`draft → approved → implementing → verified → reviewed → walkthrough-approved → done`），状态语义、G7 并行升级条件与并行事件规则见 [references/tickets.md](references/tickets.md)——**阶段③ 拆票落状态、阶段④ 每票流转或评估并行升级前读取**。底线：只有 `done` 的票解除下游 Blocked by；阶段⑤ 要求所有票 `done`。

## 7. 失败与回退

- **测试失败 / 行为异常**：调用 Skill `systematic-debugging` 或 `diagnosing-bugs`，走根因定位，不基于猜测连续改代码。
- **需求中途变更**：回到阶段① 澄清变更部分，规格追加修订记录（不推翻重写），受影响工单重新拆分。
- **阶段技能文件缺失或损坏 / 通道 B 路径解析失败 / 关键依赖缺失**：报告缺失路径，降级为内联最小流程（访谈 → 规格 → 拆票 → 实现+验证 → 复盘），并在**首次可见状态消息**标注“已降级”；降级操作卡与产出质量下限见 references/phases.md 的“降级操作卡”。
- **用户中途喊停**：记录当前阶段、已完成交接物的位置、下一步动作，保留交接记录，便于随时恢复。

## 8. 评测与回归（eval 契约）

本技能的可回归验证由 `evals/` 承担：`evals/evals.json`（场景与断言）、`evals/schema.json`（契约）、`evals/fixtures/`（可复现夹具）、`scripts/validate_evals.py`（契约校验）、`scripts/run_evals.py`（运行与 run-log 归档）。契约字段、runner_mode 语义与命令用法见 [references/eval-contract.md](references/eval-contract.md)（维护评测时读取）。
