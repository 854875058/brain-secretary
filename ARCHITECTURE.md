# 系统架构详解

> 文档：`ARCHITECTURE.md`
> 更新：2026-03-16
> 说明：本文件描述当前已落地架构；早期 `NapCat -> FastAPI -> OpenClaw` 单主链路方案现在只保留为历史兼容和辅助入口参考。

---

## 一、架构总览

当前系统围绕 OpenClaw 多 agent 运行，分成三层：

| 层 | 组件 | 作用 |
|---|---|---|
| 入口层 | `qqbot/default`、辅助 NapCat/QQ Bridge 实例 | 接收 QQ 消息并把入口统一交给指定 agent |
| 协调层 | `qq-main`、`auto-evolve-main` | 负责主会话协调与自动进化协调 |
| 执行层 | `brain-secretary-dev`、`brain-secretary-review`、Paperclip、项目双轨分支 | 负责工程实施、验收复核、协同投影与项目闭环 |

---

## 二、现网主链路

当前正式 QQ 主链路是：

```text
QQ Bot (qqbot/default)
  -> OpenClaw(qq-main)
  -> 子 agents(按需调用)
  -> qq-main
  -> QQ Bot
  -> QQ
```

其中：

- `qq-main` 负责理解意图、拆任务、委派子 agent、汇总结果、统一回复
- 真实工程实施优先由 `brain-secretary-dev` 承接
- 方案补充和验收复核由 `brain-secretary-review` 承接
- 只要 `qq-main` 调用了子 agent，协同过程就会被自动投影到 Paperclip 父子 issue

---

## 三、自动进化链路

项目自动进化使用独立协调脑，不和 QQ 主会话混用：

```text
openclaw-project-auto-evolve.service
  -> OpenClaw(auto-evolve-main)
  -> brain-secretary-dev / brain-secretary-review
  -> agent 分支提交
  -> Paperclip 投影
```

关键约束：

- `auto-evolve-main` 只给自动进化守护使用，不绑定 `qqbot/default`
- 自动进化默认使用 fresh session，避免旧上下文污染
- 自动进化前会先修复 `main / work / agent` 分支边界
- 当前注册项目以 `ops/auto-evolve.json`、`ops/project-sync.json`、`ops/project_registry.json` 为准

---

## 四、辅助多 QQ 链路

除现网主入口外，仓库还保留辅助多 QQ 联调链路：

```text
NapCat(instance)
  -> QQ Bridge(instance)
  -> OpenClaw(target agent)
```

默认映射：

- `brain` -> `qq-main`
- `tech` -> `brain-secretary-dev`
- `review` -> `brain-secretary-review`

这条链路用于：

- 多 QQ 号扫码联调
- Windows 本地 `QQ + NapCat`，服务器侧 `QQ Bridge + OpenClaw`
- 特定辅助入口测试

它不是当前现网主入口。

---

## 五、当前 agent 拓扑

| agent id | 角色 | workspace |
|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` |
| `auto-evolve-main` | 自动进化专用内部协调 agent | `/root/.openclaw/workspace` |
| `brain-secretary-dev` | 工程实施子 agent | `/root/brain-secretary` |
| `brain-secretary-review` | 方案 / 验收子 agent | `/root/brain-secretary` |

关键规则：

- `qqbot/default` 只能绑定到 `qq-main`
- 不要为了省事把主入口直接绑到子 agent
- `project_auto_evolve` 不得直接占用 `qq-main` 主会话

---

## 六、关键支撑系统

### 1. OpenClaw

- 当前生效配置：`/root/.openclaw/openclaw.json`
- 当前默认模型：`penguin/claude-sonnet-4-6`
- `model-proxy.mjs` 主要保留给 OpenAI-compatible 备用源兼容，必须透传 `messages` / `tools`

### 2. 统一运维

- 运维统一入口：`scripts/ops_manager.py`
- 运维真源：`ops/deployment_manifest.json`
- Linux 推荐部署方式：`systemd --user(OpenClaw + projection + auto-evolve)` + `systemd(Paperclip)` + `nginx`

### 3. Paperclip

- 角色：QQ/OpenClaw 后方的任务控制面和协同投影面板
- 内部地址：`http://127.0.0.1:3110`
- 公网 viewer：`http://110.41.170.155/paperclip/`
- 默认只做展示和控制面，不替代主 QQ 入口

### 4. 项目双轨分支

- 项目真源：`ops/project_registry.json`
- 双轨配置：`ops/project-sync.json`
- 自动进化配置：`ops/auto-evolve.json`
- 目标：把“白天人工开发”和“夜间 agent 自动进化”拆到不同分支

---

## 七、历史兼容说明

仓库内仍保留一些历史或概念文档：

- `qq-bot/`：旧桥接实现，现作为历史参考和辅助多 QQ 桥接层
- `docs/legacy/qq-bridge.md`：早期接入层说明
- `docs/concepts/brain.md`、`docs/concepts/agents.md`：概念说明文档，不代表当前运行时源码边界

如果这些文档与现网说明冲突，优先级按以下顺序判断：

1. `CLAUDE.md`
2. `HANDOVER.md`
3. `ops/deployment_manifest.json`
4. `docs/systemd-ops.md`
5. `docs/openclaw-setup.md`

---

## 八、当前主要风险

- `channels.qqbot.allowFrom=["*"]` 仍是多用户信任边界风险
- `dangerouslyDisableDeviceAuth=true` 和认证限流未配置，仍有安全告警
- 文档中仍保留部分 2026-03-06 到 2026-03-07 的早期规划表述，阅读时需要区分“历史方案”和“当前实现”
