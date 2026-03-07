# 大脑秘书系统 (Brain Secretary)

> 版本: 0.1.0
> 创建日期: 2026-03-06
> 状态: Linux 现网可用 / 多 Agent 方案 B 已落地

---

## 项目定位

你通过 **QQ 私聊**给大脑下命令，大脑理解你的意图后，将任务分发给对应的 **真实子 Agent**，子 Agent 完成后向大脑汇报，大脑做**验收测试**，最终把结果回复给你。

当前采用的不是“单 agent 假装分工”，而是：

- `qq-main` 作为总协调大脑
- `brain-secretary-dev` 负责主项目工程实施
- `brain-secretary-review` 负责方案补充与验收复核

---

## 当前实际链路

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents(按需) -> qq-main -> QQ Bot -> QQ
```

---

## 当前正式 agent

| agent id | 角色 | workspace |
|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` |
| `brain-secretary-review` | 方案 / 验收子 agent | `/root/brain-secretary` |

---

## 核心功能

| 功能 | 说明 |
|---|---|
| QQ 接入 | 通过 OpenClaw 原生 `qqbot` 渠道接入 QQ |
| 大脑协调 | `qq-main` 解析自然语言、拆解任务、调度子 agent |
| 多 Agent 协作 | 真实使用 OpenClaw 子 agent / 多 agent 能力 |
| 工程实施 | 子 agent 在各自 workspace 内完成具体代码和文档修改 |
| 验收汇报 | 大脑对子 agent 结果进行核对并统一回复 |
| 统一运维 | 通过 `scripts/ops_manager.py` 管理服务启停、状态、日志 |

---

## 目录结构

```text
brain-secretary/
├── README.md
├── ARCHITECTURE.md
├── SETUP.md
├── CLAUDE.md
├── HANDOVER.md
├── AGENTS.md
├── TOOLS.md
├── brain/
├── agents/
├── qq-bot/
├── qq-bridge/
├── ops/
├── scripts/
└── docs/
```

---

## 当前关键运行事实

- OpenClaw 配置文件：`/root/.openclaw/openclaw.json`
- 脑 workspace：`/root/.openclaw/workspace`
- 当前 Linux 部署方式：`systemctl --user + nginx`
- 当前 QQ 渠道绑定：`qqbot:default -> qq-main`
- 当前关键端口：
  - OpenClaw 公网入口：`80`
  - OpenClaw 内部 Dashboard：`18789`
- `qq-bot/` 当前不是现网主入口，但已重新承担“多 QQ 辅助入口 / Windows 本地 QQ 对接”能力。

---

## 快速导航

- 想了解整体部署 → `SETUP.md`
- 想看当前运维方式 → `docs/systemd-ops.md`
- 想看 OpenClaw 多 Agent 配置 → `docs/openclaw-setup.md`
- 想看 Windows 本地三开 QQ 对接 → `docs/windows-local-qq-multi.md`
- 想看 Windows / 服务器项目双轨分支协作 → `docs/project-sync-branch-workflow.md`
- 想在 Windows 双击一键生成配置 → `scripts/windows_local_qq_quick_setup.bat`
- 想在 Windows 本地做自检 → `scripts/windows_local_qq_doctor.bat`
- 想手工查看桥接层记忆 → `scripts/memory_center.py`
- 想快速接手当前状态 → `HANDOVER.md`
- 想看自动化维护规则 → `CLAUDE.md`
- 想看 AI 自动提交约定 → `AI_AUTOCOMMIT.md`
- 想配置 GitHub 仓库与自动提交 → `docs/github-workflow.md`
- 想统一启停/状态/日志 → `scripts/ops_manager.py`
- 想看部署真源 → `ops/deployment_manifest.json`
