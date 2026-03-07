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
- `brain-secretary-review`
  - 角色：方案 / 验收子 agent
  - workspace：`/root/brain-secretary`

当前生效 OpenClaw 配置文件：`/root/.openclaw/openclaw.json`

关键配置已包含：

- `channels.qqbot.enabled=true`
- `plugins.allow=["qqbot"]`
- `qq-main.subagents.allowAgents`
- `tools.agentToAgent.enabled=true`
- `tools.sessions.visibility=all`
- `model-proxy.mjs` 会把 OpenClaw 的流式请求转成上游 JSON 再回放为 SSE
- `model-proxy.mjs` 会把 `vllm/gpt-5.4` 转成上游可识别的 `gpt-5.4`

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

- OpenClaw 原生主入口继续统一打到 `qq-main`
- 多 agent 协作仍以 OpenClaw 内部委派为主
- 另外新增 3 个辅助扫码 QQ 入口：`brain / tech / review`
- 这 3 个辅助入口通过 `NapCat(instance) -> QQ Bridge(instance) -> OpenClaw(target agent)` 接入
- 仓库里的 `qq-bot/` 仍不是现网主入口，但现在承担辅助扫码 QQ 层

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
- 当前插件来源：`@openclaw-china/qqbot`（npm）
- OpenClaw 公网入口：`http://110.41.170.155/`
- NapCat 多实例脚本：`/root/brain-secretary/scripts/napcat_multi.py`
- NapCat 多实例根目录：`/root/napcat-multi`
- OpenClaw 内部入口：`http://127.0.0.1:18789/`
- 旧桥接代码：`/root/brain-secretary/qq-bot/`
- 已退役历史页面：`http://110.41.170.155/chat-history`、`http://110.41.170.155/api/chat-history`（返回 `410`）

---

## 已验证事实

- `qqbot` 插件已安装并能被 Gateway 加载
- `plugins.installs.qqbot` 已记录标准 npm 安装来源：`@openclaw-china/qqbot`
- `QQ Bot default` 渠道已配置、启用
- `qqbot:default -> qq-main` 绑定已生效
- `openclaw-qq-bridge.service` 已停用并禁用
- `napcat-qq.service` 已停用并禁用
- 公网 `/chat-history` 与 `/api/chat-history` 已明确返回 `410`，不再依赖桥接服务

---

## 已知问题

- `openclaw status` 当前仍有安全告警：`dangerouslyDisableDeviceAuth=true`、未配置 auth rate limit
- `channels.qqbot.allowFrom=["*"]` 代表当前 QQ Bot 渠道允许所有来源；如果后续收口，需要改成显式白名单
- `openclaw plugins list` 的版本列取自插件 manifest，可能与 npm 包版本不同；排障时以 `plugins.installs.qqbot` 与 `/root/.openclaw/extensions/qqbot/package.json` 为准

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


---

## NapCat 多实例示例（辅助测试）

这组示例目录不是现网入口，只用于多 QQ 号扫码联调：

- `brain`：`大脑号` -> `qq-main`
- `tech`：`技术号` -> `brain-secretary-dev`
- `review`：`方案验收号` -> `brain-secretary-review`

目录位置：`/root/napcat-multi`

常用命令：

```bash
python3 scripts/napcat_multi.py bootstrap --refresh-workdir
python3 scripts/napcat_multi.py status --json
python3 scripts/napcat_multi.py qr --json
python3 scripts/napcat_multi.py stop
```


---

## QQ Bridge 多实例（辅助扫码入口）

新增脚本：

- `scripts/napcat_multi.py`
- `scripts/qq_bot_multi.py`

新增根目录：

- `/root/napcat-multi`
- `/root/qq-bot-multi`

默认映射：

- `brain`：大脑号 -> `qq-main`
- `tech`：技术号 -> `brain-secretary-dev`
- `review`：方案验收号 -> `brain-secretary-review`

常用命令：

```bash
python3 scripts/qq_bot_multi.py bootstrap --json
python3 scripts/qq_bot_multi.py status --json
python3 scripts/napcat_multi.py qr --json
```
