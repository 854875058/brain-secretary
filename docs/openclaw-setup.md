# OpenClaw 配置说明（qqbot 渠道）

> 更新：2026-03-07
> 当前现网 QQ 入口：OpenClaw 原生 `qqbot` 渠道

---

## 当前 agent 拓扑

| agent id | 角色 | workspace | 说明 |
|---|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` | 负责理解用户意图、调度子 agent、验收结果、统一回复 |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` | 负责主仓工程实施与部署变更 |
| `agent-hub-dev` | 次级项目工程子 agent | `/root/agent-hub` | 负责对照方案、实验验证、迁移参照 |

当前 QQ 渠道绑定：`qqbot:default -> qq-main`。

---

## 当前链路

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> QQ Bot -> QQ
```

说明：

- 当前 QQ 入口不再经过 `NapCat` 或 `qq-bot(FastAPI Bridge)`
- 真正的多 agent 协调发生在 OpenClaw 里的 `qq-main`
- 仓库里的 `qq-bot/` 仅保留为历史实现参考，不再是现网入口

---

## 关键配置

当前生效配置：`/root/.openclaw/openclaw.json`

关键点：

- `channels.qqbot.enabled = true`
- `plugins.allow = ["qqbot"]`
- `qq-main` 已绑定 `qqbot:default`
- `qq-main.subagents.allowAgents = ["brain-secretary-dev", "agent-hub-dev"]`
- `tools.agentToAgent.allow = ["qq-main", "brain-secretary-dev", "agent-hub-dev"]`
- `tools.sessions.visibility = "all"`

---

## 常用命令

### 安装 / 更新插件

```bash
openclaw plugins install @sliverp/qqbot@latest
```

### 配置 QQ 渠道

```bash
openclaw channels add --channel qqbot --token "<appid>:<clientSecret>"
```

### 绑定到 `qq-main`

```bash
openclaw agents bind --agent qq-main --bind qqbot:default
```

### 校验状态

```bash
openclaw channels list
openclaw agents bindings --json
openclaw agents list --bindings --json
openclaw status
```

---

## 修改配置后的建议动作

如果你改了 `/root/.openclaw/openclaw.json`：

```bash
openclaw config validate
systemctl --user restart openclaw-gateway.service
```

如果你升级了 `qqbot` 插件：

```bash
openclaw plugins install @sliverp/qqbot@latest
systemctl --user restart openclaw-gateway.service
```

---

## 现网注意事项

- 不要把 QQ 入口直接绑到子 agent
- 不要把 token / client secret / API key 抄进公开文档
- 当前 `channels.qqbot.allowFrom=["*"]` 会触发多用户信任边界警告；如果后续要收口，应改成显式白名单
- 旧 `NapCat -> qq-bot` 桥接链路已经退役；如非明确回滚，不要重新启用
