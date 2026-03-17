# QQ Bridge（历史兼容 / 辅助多入口）

> 目录：`qq-bot/`
> 更新：2026-03-16
> 状态：现网主入口已迁移；本目录保留为历史兼容实现和辅助桥接层

---

## 当前定位

本目录里的 FastAPI QQ Bridge 不是当前现网主入口。

当前现网主链路是：

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents
```

`qq-bot/` 当前主要承担三类用途：

- 历史实现参考
- 辅助多 QQ 桥接入口
- Windows 本地 QQ / NapCat 方案的服务器侧桥接能力

---

## 当前仍可提供的能力

作为辅助桥接层，`qq-bot/` 仍然保留以下能力：

- NapCat OneBot 11 事件接收
- 为桥接会话生成稳定的 OpenClaw `session-id`
- 调用 OpenClaw 并把回复回发到 QQ
- 为新的 `bot/agent_team.py` 状态图协调框架提供会话、记忆和 OpenClaw 调用基础
- 基础管理命令
- 记忆沉淀与 watchdog
- Paperclip 兼容桥接命令
- 外部 AgentTeam 状态 / 任务 / 需求桥接命令（`/at-*`）

如果你需要现网主入口，请不要直接从这里理解系统主架构。

---

## 当前推荐使用方式

### 现网主入口

优先使用 OpenClaw 原生 `qqbot` 渠道，相关文档见：

- `docs/README.md`
- `docs/openclaw-setup.md`
- `docs/systemd-ops.md`
- `HANDOVER.md`

### 辅助多 QQ 入口

优先通过仓库脚本管理，而不是手工把 `qq-bot/main.py` 当主服务长期运行：

```bash
python3 scripts/qq_bot_multi.py bootstrap --json
python3 scripts/qq_bot_multi.py status --json
python3 scripts/napcat_multi.py qr --json
```

### 外部 AgentTeam Bridge

如果你想把其他项目里的 AgentTeam 接到当前 QQ 入口，配置：

- `QQ_BOT_AGENTTEAM_ENABLED=true`
- `QQ_BOT_AGENTTEAM_API_BASE_URL=http://127.0.0.1:8090/api/agents`

然后就可以在 QQ 里使用：

- `/at-status`
- `/at-tasks`
- `/at-task 任务编号`
- `/at-requests`
- `/at-new 标题|描述|优先级|验收标准`

### Windows 本地 QQ / NapCat

优先看：

- `docs/windows-local-qq-multi.md`
- `scripts/windows_local_qq_quick_setup.bat`
- `scripts/windows_local_qq_multi.ps1`
- `scripts/windows_local_qq_remote_apply.ps1`

---

## 配置边界

- `qq-bot/config.yaml` 更适合作为单实例基线配置和辅助桥接参考
- 仓库默认不应把 `qq-bot/config.yaml` 的 `openclaw.agent_id` 改离 `qq-main`，除非明确重构入口架构
- 多实例桥接的实际 agent 映射应优先由 `scripts/qq_bot_multi.py` 生成和维护
- `qq-bot/logs/`、运行态数据库、密钥与 token 不应提交到远端

---

## 何时使用本目录

适合使用 `qq-bot/` 的场景：

- 调试或复盘历史桥接逻辑
- 搭建辅助扫码入口
- 配合 Windows 本地 NapCat 做联调
- 检查桥接层命令、记忆和 Paperclip 兼容行为

不适合使用本目录的场景：

- 判断现网主入口架构
- 判断当前正式部署方式
- 直接作为“唯一生产入口”理解整个系统

---

## 目录结构

```text
qq-bot/
├── main.py
├── config.yaml
├── requirements.txt
├── bot/
└── data/
```

如果需要了解本目录的具体能力实现，直接从 `bot/` 下的模块开始看；如果需要判断“现在系统到底怎么跑”，优先回到主仓文档真源。

桥接层的历史背景说明见：`docs/legacy/qq-bridge.md`。
