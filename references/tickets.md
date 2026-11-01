# 工单状态与并行升级

适用：完整工作流阶段③ 拆票后落状态、阶段④ 每票状态流转、或评估 G7 并行升级时读取。门控编号 G4 / G7 的定义见 SKILL.md 第 5 节 Gate Registry；流程压缩的豁免口径见 SKILL.md 第 3 节。

**工单状态机**（仅约束完整工作流的工单；快路径与 bugfix 压缩路径不强制落全状态，见 SKILL.md 第 3 节流程压缩）：

```text
draft -> approved -> implementing -> verified -> reviewed -> walkthrough-approved -> done
```

- `draft`：拆票产出；`approved`：G4 通过；`implementing`：实现开始；`verified`：G5 真实验证通过；`reviewed`：code-review 完成且问题已处理；`walkthrough-approved`：G6 用户走查确认；`done`：最终 commit 完成。
- **只有 `done` 的票才能解除下游 Blocked by**；阶段⑤ 只有所有票为 `done` 后才能进入。
- 未通过 G5 / G6 的票不得标记 `done`，也不得解除下游依赖。

**并行升级条件（G7）——全部满足才可从 implement 串行切换到 implement-spec 多 agent 并行**：

1. 至少 1 张票已端到端跑通（真实测试通过，非“应该没问题”）；
2. 依赖图明确，每张待做票的 Blocked by 均已 `done` 或不存在；
3. 用户明确同意并行；
4. 宿主具备 worktree + 集成分支 + subagent + merge 能力（协议见 implement-spec 磁盘文件）。

任一不满足 → 继续串行。

**并行事件规则**（事件日志可核查）：

- 首票 E2E gate 通过前 `implementer_spawn = 0`，`worktree_create = 0`；
- `reviewer_spawn` 可以存在，但 reviewer 不得修改实现（reviewer 是只读角色，**不计入 implementer 并行**）；
- G7 未通过前不得启动 implement-spec；
- 未通过 G5 / G6 的票不能标记 done，也不能解除下游依赖。
