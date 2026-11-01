# 技能调用适配器（invocation adapter）

适用：首次调用外部技能（通道 A 或通道 B）、需要解析协议路径、解析失败或怀疑宿主能力缺失时读取。本文件的解析规则由 SKILL.md 第 4 节路由进入；门控编号以 SKILL.md 第 5 节 Gate Registry 的 G1-G7 为准。

技能分两类调用通道，解析规则如下：

**通道 A — Skill 工具直接调用**（宿主提供 Skill API，且技能 frontmatter 的 `name` 可被解析）：

> 调用 Skill 工具（skill: `tdd`），在以下 seam 处驱动实现：<列出 seam>。仅在这些 seam 写测试先行代码。

**通道 B — 磁盘协议**（grill-with-docs / to-spec / to-tickets / implement / implement-spec / retro 设置了 disable-model-invocation，不能经 Skill 工具调用）：

> Read `<skills-root>/<物理目录>/SKILL.md`，严格按该协议执行。协议内含的用户确认环节必须原样保留，不得跳过或自动化。产出物路径按 SKILL.md 第 2 节的 tracker 回退规则调整。

**解析规则**（按序裁定）：

1. **逻辑技能**按 frontmatter 的 `name` 解析（经 Skill API 调用）。
2. **磁盘协议技能**按物理目录解析（Read 文件）。
3. **逻辑名与物理目录映射**：逻辑名 `domain-modeling` 的物理目录为 `domain-modeling-2`。通道 A 用逻辑名调 Skill API；通道 B 磁盘读取必须用物理目录，禁止直接拼逻辑名。
4. 有 Skill API 时优先走通道 A；无 Skill API（或解析失败）时按通道 B Read 对应 SKILL.md，执行内联最小流程。
5. **互斥**：grill-with-docs 与直接调用 grilling / domain-modeling 互斥——同一任务只走其一，不得重复访谈、不得重复写 ADR。
6. **递归依赖检查**：进入协议前检查其声明的上游依赖是否可用——retro → writing-for-agents；tdd → tests.md / mocking.md（若协议引用）；implement-spec → 宿主 worktree / subagent / merge 能力。缺失时按本文件解析规则第 7 条降级。
7. **协议文件存在 ≠ 宿主能力存在**：宿主不支持 worktree、后台 subagent 或 merge 时，自动回退到 implement 串行，不启动 implement-spec。
8. **关键依赖缺失时**，在首次可见状态消息中标注“已降级”，说明缺失路径、受影响阶段和替代流程，不得静默跳过。

**`<skills-root>` 解析（可移植规则，禁止写死宿主路径）**：协议技能与本技能同级安装——取本 SKILL.md 自身的所在目录，其父目录即 `<skills-root>`。示例：本技能装在 `~/.workbuddy/skills/code-task-workflow/` 时为 `~/.workbuddy/skills`；装在 `~/.zcode/skills/code-task-workflow/` 时为 `~/.zcode/skills`。下表仅为路径形态示例，任何 harness 按上式解析，不做宿主假设。

| 阶段 | 磁盘协议路径（`<skills-root>` 按上式解析） |
|---|---|
| ① | `<skills-root>/grill-with-docs/SKILL.md` |
| ② | `<skills-root>/to-spec/SKILL.md` |
| ③ | `<skills-root>/to-tickets/SKILL.md` |
| ④ | `<skills-root>/implement/SKILL.md`（并行时换 implement-spec） |
| ⑤ | `<skills-root>/retro/SKILL.md` |

**路径解析失败的处理**：执行通道 B 前先解析协议路径。若无法确定本技能所在目录、或 `<skills-root>/<name>/SKILL.md` 不存在，**报告失败的具体路径与原因，并按 SKILL.md 第 7 节降级为内联最小流程**（首条可见状态消息标注“已降级”），不得静默跳过、也不得凭猜测的协议继续。

若读到的协议与本技能门控冲突，以更严格的门控为准。
