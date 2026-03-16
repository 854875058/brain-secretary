# 大脑核心模块

> 原位置：`brain/README.md`
> 更新：2026-03-16
> 状态：概念说明文档，不是当前现网主运行时代码目录

---

## 当前定位

当前系统里的“大脑”已经不是仓库里的独立程序，而是运行在 OpenClaw 里的协调 agent：

- agent id：`qq-main`
- workspace：`/root/.openclaw/workspace`
- 主入口绑定：`qqbot:default -> qq-main`

如果需要了解当前真实运行方式，优先看：

1. `../../CLAUDE.md`
2. `../../HANDOVER.md`
3. `../openclaw-setup.md`
4. `../systemd-ops.md`
5. `../../ops/deployment_manifest.json`

---

## 当前大脑职责

`qq-main` 负责：

- 理解用户意图
- 判断是直接回答，还是委派子 agent
- 把工程实施任务派给 `brain-secretary-dev`
- 把方案补充和验收复核任务派给 `brain-secretary-review`
- 汇总执行结果并统一回复给用户

在自动进化场景下，协调职责由 `auto-evolve-main` 承担，但它不接 QQ 主入口流量。

---

## 当前边界

大脑负责：

- 意图理解
- 任务拆解
- 任务路由
- 结果汇总
- 验收闭环

大脑不直接负责：

- 现网工程实现细节
- 部署脚本的具体修改
- 项目仓库里的具体代码修复
- Paperclip 控制面的内部实现

这些工作默认由子 agent 或外围脚本完成。

---

## 相关真源

- `../../README.md`
- `../../ARCHITECTURE.md`
- `../openclaw-setup.md`
- `../systemd-ops.md`
- `../../HANDOVER.md`
