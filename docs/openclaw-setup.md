# OpenClaw 配置指南

> 文档: `docs/openclaw-setup.md`
> 更新: 2026-03-07

---

## 当前实际环境

| 项目 | 值 |
|---|---|
| OpenClaw 版本 | `2026.3.2` |
| 安装方式 | npm 全局安装 |
| Node.js | `v25.2.1` |
| Gateway 内部端口 | `18789` |
| Dashboard 公网入口 | `http://110.41.170.155/` |
| Dashboard 内部入口 | `http://127.0.0.1:18789/` |
| 配置文件 | `/root/.openclaw/openclaw.json` |
| 状态目录 | `/root/.openclaw/` |
| 当前主模型 | `vllm/gpt-5.4` |
| QQ 入口 agent | `qq-main` |

> 说明：当前 Linux 现网已经把 OpenClaw 收敛到内部 `18789`，公网统一由 `nginx` 代理到 `80`。

---

## 当前多 Agent 结构

| agent id | 角色 | workspace | 说明 |
|---|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` | 负责理解用户意图、调度子 agent、验收结果、统一回复 |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` | 负责 `qq-bot`、OpenClaw 接入、部署文档、运维脚本 |
| `agent-hub-dev` | 次级项目工程子 agent | `/root/agent-hub` | 负责旧实现、原型验证、迁移参照 |

---

## 关键配置点

当前 `/root/.openclaw/openclaw.json` 已配置：

### 1) `qq-main` 可委派到真实子 agent

- `qq-main.subagents.allowAgents = ["brain-secretary-dev", "agent-hub-dev"]`

### 2) 开启跨 agent 协调能力

- `tools.agentToAgent.enabled = true`
- `tools.agentToAgent.allow = ["qq-main", "brain-secretary-dev", "agent-hub-dev"]`
- `tools.sessions.visibility = "all"`

### 3) 子 agent 默认运行策略

- `agents.defaults.subagents.maxConcurrent = 4`
- `agents.defaults.subagents.maxChildrenPerAgent = 4`
- `agents.defaults.subagents.archiveAfterMinutes = 240`
- `agents.defaults.subagents.thinking = low`
- `agents.defaults.subagents.runTimeoutSeconds = 900`

### 4) 工具权限策略

- `qq-main`：`coding` profile + 额外开放会话 / 子 agent 工具
- 子 agent：`coding` profile，但拒绝 `message / gateway / nodes / cron / browser / canvas` 等与当前任务无关工具

---
## Model Proxy 兼容性注意

当前多 agent 能否真正工作，不只取决于 `openclaw.json`，还取决于 model proxy 是否**透传** OpenClaw 发给模型的 `messages` 与 `tools`。

当前正确状态：

- 脚本：`/root/.openclaw/model-proxy.mjs`
- 环境：`/root/.openclaw/model-proxy.env`
- `PROXY_SYSTEM_PROMPT` 为空
- 代理不再删除 `tools` / `tool_choice` / `parallel_tool_calls`
- 代理不再丢弃 system / developer 消息（developer 在代理内归一为 system）

如果后续有人把代理改回“只保留 user/assistant + 删除 tools”，OpenClaw 会表现成“看起来有多 agent 配置，但实际不会调子 agent”。

---

## 当前 QQ 链路

```text
QQ -> NapCat -> qq-bot(FastAPI Bridge) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> qq-bot -> NapCat -> QQ
```

说明：

- 当前 QQ 入口仍然通过 `qq-bot`
- `qq-bot` 当前不是多 agent 调度器；它只是桥接层
- 真正的多 agent 协调发生在 OpenClaw 里的 `qq-main`

---

## QQ Bridge 配置约定

配置文件：`qq-bot/config.yaml`

关键项：

```yaml
openclaw:
  enabled: true
  agent_id: qq-main
  thinking: low

web:
  public_base_url: http://110.41.170.155
  history_require_token: true
  history_token: <仅写在本地配置，不写进文档>

evolution:
  auto_trigger: true
```

要求：

- 除非明确重构入口架构，不要把 `agent_id` 改成子 agent
- 用户的 QQ 消息应始终先进入 `qq-main`
- 用户可通过 `/evolve ...`、`/remember ...` 或自然语言“记住这个 / 写进规则 / 别再犯 / 你可以发图片”等触发自助进化
- 当需要给 QQ 发图时，`qq-main` 可以输出 `[[send_image]] <图片URL或file://路径>`，由桥接真正发送图片
- 当需要给 QQ 发视频时，`qq-main` 可以输出 `[[send_video]] <视频URL或file://路径>`，由桥接真正发送视频
- 当需要给 QQ 发语音时，`qq-main` 可以输出 `[[send_voice]] <语音URL或file://路径>`；如果只有文本内容，也可以直接输出 `[[send_tts]] 这里写文本`，由桥接本地合成语音并发送

---

## 常用检查命令

### 查看 agent 列表

```bash
openclaw agents list --bindings --json
```

### 校验配置

```bash
openclaw config validate
```

### 查看整体状态

```bash
openclaw status
```

### 查看健康状态

```bash
openclaw health
```

---

## 修改配置后的建议动作

如果你改了 `/root/.openclaw/openclaw.json`：

```bash
openclaw config validate
systemctl --user restart openclaw-gateway.service
```

如果你改了 `qq-bot/config.yaml`：

```bash
systemctl --user restart openclaw-qq-bridge.service
```

---

## 不要做的事

- 不要把 QQ 入口直接绑到子 agent
- 不要把 token / API key 抄进公开文档
- 不要让旧的 Windows 示例覆盖当前 Linux 现网事实
