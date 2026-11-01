# 评测与回归（eval 契约）

适用：维护或回归本技能的评测、修改 evals 或 scripts、解读 run-log 与成本画像时读取。文件路由与命令入口见 SKILL.md 第 8 节。

本技能的可回归验证由 `evals/` 承担：`evals/evals.json`（场景与断言）、`evals/schema.json`（契约）、`evals/fixtures/`（可复现夹具）、`scripts/validate_evals.py`（契约校验）、`scripts/run_evals.py`（运行与 run-log 归档）。

- 快速校验：`python scripts/validate_evals.py`。
- 运行：`python scripts/run_evals.py --all --repeat 3 --baseline` / `--with-skill`。
- 成本画像（tokens / tool_calls / latency 与 50% 退化报警）**仅在 eval runner 中采集**；普通代码任务不因 `timing.json` / `benchmark.json` 缺失而阻塞。
- 触发测试集（路由正反例）与 manual 类 eval 的运行语义见 `evals/schema.json` 的 `runner_mode` 字段：manual 结果不得伪装成机器通过。
