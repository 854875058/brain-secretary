# OpenClaw 配置说明（qqbot 渠道）

> 更新：2026-03-07
> 当前现网 QQ 入口：OpenClaw 原生 `qqbot` 渠道

---

## 当前 agent 拓扑

| agent id | 角色 | workspace | 说明 |
|---|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` | 负责理解用户意图、调度子 agent、验收结果、统一回复 |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` | 负责主仓工程实施与部署变更 |
| `brain-secretary-review` | 方案 / 验收子 agent | `/root/brain-secretary` | 负责方案补充、验收视角与第二意见 |

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
- `channels.qqbot.markdownSupport = false`
- `plugins.installs.qqbot.spec = "@openclaw-china/qqbot"`
- `qq-main.subagents.allowAgents = ["brain-secretary-dev", "brain-secretary-review"]`
- `tools.agentToAgent.allow = ["qq-main", "brain-secretary-dev", "brain-secretary-review"]`
- `tools.sessions.visibility = "all"`

---

## 常用命令

### 安装 / 更新插件

```bash
openclaw plugins install @openclaw-china/qqbot
```

### 配置 QQ 渠道

```bash
openclaw channels add --channel qqbot --token "<appid>:<clientSecret>"
openclaw config set channels.qqbot.markdownSupport false
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
openclaw plugins install @openclaw-china/qqbot
openclaw config validate
systemctl --user restart openclaw-gateway.service
```

---

## 现网注意事项

- 不要把 QQ 入口直接绑到子 agent
- 不要把 token / client secret / API key 抄进公开文档
- 当前 `channels.qqbot.allowFrom=["*"]` 会触发多用户信任边界警告；如果后续要收口，应改成显式白名单
- 旧教程里提到的 `@sliverp/qqbot`、`qgbot`、`ggbot` 都按历史/笔误处理；现网统一使用 `@openclaw-china/qqbot`
- 旧 `NapCat -> qq-bot` 桥接链路已经退役；如非明确回滚，不要重新启用

## 兼容迁移说明

- 如果机器上已经存在旧版本地 `qqbot` 目录，不要先删插件再重启 Gateway；配置校验会因为 `qqbot` 渠道缺失而报 `unknown channel id: qqbot`
- 旧版目录与新包同名时，直接再次执行 `openclaw plugins install` 可能会遇到 `plugin already exists`；先备份 `/root/.openclaw/openclaw.json`，再做原位替换或在干净环境安装
- 迁移完成后，确认 `/root/.openclaw/openclaw.json` 中存在 `plugins.installs.qqbot`，并重启 `openclaw-gateway.service`
- `openclaw plugins list` 里的版本列来自 `openclaw.plugin.json`，可能与 npm 包版本不同；以 `plugins.installs.qqbot` 或 `/root/.openclaw/extensions/qqbot/package.json` 为准


## 模型代理兼容修复

当前 `/root/.openclaw/model-proxy.mjs` 额外承担两件兼容工作：

- OpenClaw 发 `stream=true` 时，代理会改成上游 JSON 请求，再把返回结果回放成 SSE
- OpenClaw 发 `vllm/gpt-5.4` 时，代理会自动改写为上游可识别的 `gpt-5.4`

如果 QQ 渠道能收消息但长时间不回，优先先检查这里。

---

## NapCat 多实例扫码示例（辅助测试）

为多 QQ 号联调准备的 3 个隔离实例目录：`/root/napcat-multi/{brain,tech,review}`。

- `brain` -> `qq-main`
- `tech` -> `brain-secretary-dev`
- `review` -> `brain-secretary-review`

常用命令：

```bash
python3 /root/brain-secretary/scripts/napcat_multi.py bootstrap --refresh-workdir
python3 /root/brain-secretary/scripts/napcat_multi.py status --json
python3 /root/brain-secretary/scripts/napcat_multi.py qr --json
```


## 辅助扫码 QQ 入口

除 OpenClaw 原生 `qqbot/default` 主入口外，还补了一层辅助扫码 QQ 入口：

```text
NapCat(instance) -> QQ Bridge(instance) -> OpenClaw(target agent)
```

默认映射：

- `brain` -> `qq-main`
- `tech` -> `brain-secretary-dev`
- `review` -> `brain-secretary-review`

相关脚本：

- `scripts/napcat_multi.py`
- `scripts/qq_bot_multi.py`
