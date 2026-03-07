# HANDOVER.md

> 给后续接手的助手 / Claude / Codex 读
> 更新: 2026-03-07

---

## 一句话状态

当前现网 QQ 入口已经从 `NapCat -> qq-bot` 迁移到 OpenClaw 原生 `qqbot` 渠道，并保持 **方案 B：`qq-main` 协调大脑 + 多个真实子 agent**。

---

## 接手时先读这些

1. `CLAUDE.md`
2. `docs/systemd-ops.md`
3. `docs/openclaw-setup.md`
4. `SETUP.md`
5. `ops/deployment_manifest.json`

---

## 当前 OpenClaw agent 拓扑

- `qq-main`
  - 角色：协调大脑
  - workspace：`/root/.openclaw/workspace`
  - 当前 QQ 渠道绑定：`qqbot:default`
- `brain-secretary-dev`
  - 角色：主项目工程子 agent
  - workspace：`/root/brain-secretary`

当前生效 OpenClaw 配置文件：`/root/.openclaw/openclaw.json`

关键配置已包含：

- `channels.qqbot.enabled=true`
- `plugins.allow=["qqbot"]`
- `qq-main.subagents.allowAgents`
- `tools.agentToAgent.enabled=true`
- `tools.sessions.visibility=all`

---

## 当前关键服务

- `openclaw-model-proxy.service`
- `openclaw-gateway.service`
- `nginx.service`

全部使用：

```bash
systemctl --user ...
```

不要误用系统级：

```bash
systemctl ...
```

`nginx.service` 仍是系统级例外。

---

## 当前实际链路

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> QQ Bot -> QQ
```

说明：

- QQ 入口继续统一打到 `qq-main`
- 多 agent 协作在 OpenClaw 内部完成
- 旧 `qq-bot(FastAPI Bridge)` 与 `NapCat` 现网服务已停用
- 仓库里的 `qq-bot/` 仅保留为历史实现参考，不再承担现网入口职责

---

## 统一运维入口

后续接手时，优先先跑：

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
openclaw channels list
openclaw agents bindings --json
```

不要第一反应就直接手工敲 `systemctl` 或前台拉起进程。

---

## 先做这几个检查

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service
systemctl status nginx
openclaw channels list
openclaw agents bindings --json
openclaw status
curl http://127.0.0.1:18789/
ss -lntp | rg ':80 |:18789 '
```

---

## 关键路径

- 主仓：`/root/brain-secretary`
- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- 脑 workspace：`/root/.openclaw/workspace`
- 运维真源：`/root/brain-secretary/ops/deployment_manifest.json`
- QQ Bot 插件目录：`/root/.openclaw/extensions/qqbot`
- OpenClaw 公网入口：`http://110.41.170.155/`
- OpenClaw 内部入口：`http://127.0.0.1:18789/`
- 旧桥接代码：`/root/brain-secretary/qq-bot/`
- 已退役历史页面：`http://110.41.170.155/chat-history`、`http://110.41.170.155/api/chat-history`（返回 `410`）

---

## 已验证事实

- `qqbot` 插件已安装并能被 Gateway 加载
- `QQ Bot default` 渠道已配置、启用
- `qqbot:default -> qq-main` 绑定已生效
- `openclaw-qq-bridge.service` 已停用并禁用
- `napcat-qq.service` 已停用并禁用
- 公网 `/chat-history` 与 `/api/chat-history` 已明确返回 `410`，不再依赖桥接服务

---

## 已知问题

- `openclaw status` 当前仍有安全告警：`dangerouslyDisableDeviceAuth=true`、未配置 auth rate limit
- `channels.qqbot.allowFrom=["*"]` 代表当前 QQ Bot 渠道允许所有来源；如果后续收口，需要改成显式白名单
- `qqbot` 通过本地扩展目录加载，当前会看到 provenance / 本地信任提示，不影响运行

---

## 接手时不要做的事

- 不要把 QQ 入口从 `qq-main` 改到子 agent，除非在做明确架构变更
- 不要把 token / client secret / API key 抄进文档或聊天
- 不要为了“临时验证”重新启用 `openclaw-qq-bridge.service` 与 `napcat-qq.service`，除非是在做明确回滚

---

## 如果你改了部署

如果后续修改了端口、服务名、启动方式、日志路径、agent id、workspace、子 agent 拓扑或 QQ 渠道绑定，请同步更新：

- `CLAUDE.md`
- `HANDOVER.md`
- `SETUP.md`
- `docs/openclaw-setup.md`
- `docs/systemd-ops.md`
- `ops/deployment_manifest.json`
