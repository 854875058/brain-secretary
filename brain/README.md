# 大脑核心模块

> 目录：`brain/`
> 更新：2026-03-16
> 状态：概念说明目录，不是当前现网主运行时代码目录

---

## 当前定位

当前系统里的“大脑”已经不是本目录下的一个独立程序，而是运行在 OpenClaw 里的协调 agent：

- agent id：`qq-main`
- workspace：`/root/.openclaw/workspace`
- 主入口绑定：`qqbot:default -> qq-main`

如果需要了解当前真实运行方式，优先看：

1. `CLAUDE.md`
2. `HANDOVER.md`
3. `docs/openclaw-setup.md`
4. `docs/systemd-ops.md`
5. `ops/deployment_manifest.json`

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

## 本目录的作用

`brain/` 目前保留为概念和说明目录，主要用于：

- 补充大脑职责说明
- 存放后续可能抽象出来的提示词、路由约定或设计文档
- 给接手者一个“这个仓库里的 brain 指什么”的说明入口

它不是当前运行时真源。

---

## 相关真源

- 总体说明：`README.md`
- 架构说明：`ARCHITECTURE.md`
- 当前 OpenClaw 配置：`docs/openclaw-setup.md`
- 当前运维方式：`docs/systemd-ops.md`
- 当前交接状态：`HANDOVER.md`
