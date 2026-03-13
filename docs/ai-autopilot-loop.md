# AI 自动闭环

> 文档：`docs/ai-autopilot-loop.md`
> 目标：把 `brain-secretary` 收敛成“AI 干活，AI 复核，人只看异常”的最小闭环

---

## 闭环目标

默认目标不是让人盯着 AI 一步步执行，而是让系统自己完成以下链路：

1. 自动挑一个高价值、低风险、可验证的小任务。
2. 按 `qq-main -> brain-secretary-dev -> brain-secretary-review` 的思路推进。
3. 默认执行最小验证，不把可恢复问题先甩给用户。
4. 只在确实需要人类授权、业务取舍或存在异常时再上报。

---

## 当前机制

`scripts/project_auto_evolve_daemon.py` 已补上这几层约束：

- 结构化任务契约：每轮自动进化会把项目目标、分支边界、验证要求、输出字段写进 prompt。
- 结构化结果报告：最终回复要求附带 `AUTO_EVOLVE_REPORT_BEGIN ... AUTO_EVOLVE_REPORT_END` 包裹的 JSON 对象。
- review 证据校验：守护脚本会读取 OpenClaw 转录，检查 `brain-secretary-review` 是否真的参与并回推结果。
- 异常优先通知：如果缺结构化报告、缺 review 证据、仍有待补验证、仍请求人工介入，都会记为需要关注的异常。
- 默认异常拦截：当本轮存在异常时，`sync-agent` 会改成 `--no-push`，避免未经复核的结果直接推进远端。

---

## auto-evolve 配置

`ops/auto-evolve.json` 现在支持这几个字段：

- `review_required`
  - 默认 `true`
  - 要求本轮必须有 `brain-secretary-review` 的真实协作证据。

- `require_structured_report`
  - 默认 `true`
  - 要求最终回复必须附带结构化 JSON 报告。

- `notify_mode`
  - 可选：`exceptions_only` / `full`
  - 默认 `exceptions_only`
  - 当前主要用于把状态理解为“默认静默，只看异常”。

---

## 常用命令

```bash
python3 scripts/project_auto_evolve_daemon.py status --json
python3 scripts/project_auto_evolve_daemon.py doctor --json
python3 scripts/project_auto_evolve_daemon.py watchdog --json
python3 scripts/project_auto_evolve_daemon.py exceptions --json
python3 scripts/project_auto_evolve_daemon.py once --project tower-eye --dry-run --json
```

解释：

- `status`
  - 看完整状态，包含项目状态、watchdog 和异常摘要。

- `doctor`
  - 做一次守护自检，同时附带 dry-run 预演和异常统计。

- `watchdog`
  - 只看 `qq-main` 会话污染 / 配置漂移熔断。

- `exceptions`
  - 只看当前需要人工关注的异常，适合做“人只看异常”的统一入口。

- `once --dry-run`
  - 只预演，不真正驱动自动进化 agent，适合检查 prompt 和分支边界。

---

## 人的职责

这套闭环要成立，人的职责应该收敛成四件事：

- 定目标：决定哪些项目值得持续自动推进。
- 定规则：决定哪些目录能改、哪些命令能跑、哪些情况必须停下来问人。
- 看异常：只处理 `exceptions` 命令列出的阻塞项。
- 做取舍：授权、业务判断、风险接受与否。

其余事情尽量让系统自己做完。
