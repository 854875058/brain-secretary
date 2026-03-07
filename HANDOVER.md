# HANDOVER.md

> 给后续接手的助手 / Claude / Codex 读
> 更新: 2026-03-07

---

## 一句话状态

当前这套 QQ -> NapCat -> `qq-bot` -> OpenClaw 链路已经在 Linux 上稳定跑通，并且已经切换到 **方案 B：`qq-main` 协调大脑 + 多个真实子 agent**。

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
- `brain-secretary-dev`
  - 角色：主项目工程子 agent
  - workspace：`/root/brain-secretary`
- `agent-hub-dev`
  - 角色：次级项目工程子 agent
  - workspace：`/root/agent-hub`

当前生效 OpenClaw 配置文件：`/root/.openclaw/openclaw.json`

关键配置已包含：

- `qq-main.subagents.allowAgents`
- `tools.agentToAgent.enabled=true`
- `tools.sessions.visibility=all`
- `agents.defaults.subagents.*`

---

## 当前关键服务

- `openclaw-model-proxy.service`
- `openclaw-gateway.service`
- `openclaw-qq-bridge.service`
- `napcat-qq.service`

全部使用：

```bash
systemctl --user ...
```

不要误用系统级：

```bash
systemctl ...
```

---

## 当前实际链路

```text
QQ -> NapCat -> qq-bot(FastAPI Bridge) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> qq-bot -> NapCat -> QQ
```

说明：

- `qq-bot` 目前仍是 QQ 接入层，不要直接废掉
- QQ 入口继续统一打到 `qq-main`
- 多 agent 协作在 OpenClaw 内完成，而不是在 `qq-bot` 里手搓假路由

---

## 统一运维入口

后续接手时，优先先跑：

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
```

不要第一反应就直接手工敲 `systemctl`、`taskkill` 或前台拉起进程。

---

## 先做这几个检查

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service openclaw-qq-bridge.service napcat-qq.service
systemctl status nginx
openclaw agents list --bindings --json
openclaw status
curl http://127.0.0.1:8000/
ss -lntp | rg ':80 |:18789 |:8000 |:6099 |:3000 '
```

---

## 关键路径

- 主仓：`/root/brain-secretary`
- 次仓：`/root/agent-hub`
- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- 脑 workspace：`/root/.openclaw/workspace`
- 运维真源：`/root/brain-secretary/ops/deployment_manifest.json`
- QQ Bridge 配置：`/root/brain-secretary/qq-bot/config.yaml`
- 聊天记录页面：`http://110.41.170.155/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- 聊天记录 JSON：`http://110.41.170.155/api/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- 聊天记录页现支持：任务清单、任务状态概览、日期筛选、任务筛选、子 Agent 协作筛选
- 任务清单现会自动同步子 Agent 完成回执；`capability_seed` 只补首建，不再反复覆盖已写入的真实验证/备注
- OpenClaw 公网入口：`http://110.41.170.155/`
- OpenClaw 内部入口：`http://127.0.0.1:18789/`
- NapCat 启动脚本：`/root/Napcat/start-qq.sh`
- NapCat 快速登录账号：`2230906690`
- 当前生效 OneBot 配置：`/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11_2230906690.json`
- NapCat 日志：`/root/Napcat/qq.log`
- NapCat 二维码：`/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png`

---

## 已验证事实

- QQ 发文件能力已接入：`qq-bot` 支持处理 `[[send_file]] <文件URL或file://路径>`
- QQ 发语音能力已接入：`qq-bot` 支持处理 `[[send_voice]] <语音URL或file://路径>`，并转换为 NapCat OneBot `record` 段发送
- QQ 文本转语音能力已接入：`qq-bot` 支持处理 `[[send_tts]] 这里写文本`，桥接层会本地调用 `ffmpeg+flite` 生成 16k 单声道 WAV，再按 `record` 语音发送到 QQ
- QQ 多模态输入整理已接入：收到图片/文件/语音/视频时，会把可用的本地路径、文本摘录、OCR/元数据整理进 OpenClaw 提示词
- QQ 巡检入口已接入：支持 `/patrol` 和自然语言“巡检/自诊断/检查服务状态”等触发跨平台运维报告


- `qq-bot` 已补异步完成回推游标，服务重启后不会再把历史子 agent 完成消息整批重放到 QQ

- QQ 自助进化触发链已接入：`/evolve ...`、`/remember ...`、自然语言“记住这个 / 写进规则 / 别再犯 / 你可以发图片 / 让你能发图片”等
- QQ 发图链路已接入：OpenClaw 可通过 `[[send_image]] <图片URL或file://路径>` 让桥接真正发送图片
- QQ 发视频链路已做最小接入：OpenClaw 可通过 `[[send_video]] <视频URL或file://路径>` 让桥接发送视频段（底层走 NapCat OneBot `video`）
- NapCat 当前登录 QQ：`2230906690 / 浅笑心柔`
- NapCat HTTP API 已可用：`127.0.0.1:3000`
- `qq-bot` 已能把 OpenClaw 回复发回 QQ
- 当前 QQ Bridge 配置指向 OpenClaw agent：`qq-main`

---

## 已知问题

- `qq-bot` 定时扫描里会报 `wmic` 缺失，这是 Linux 上的已知非阻断告警
- 如果 `qq-bot` 报 `All connection attempts failed`，优先怀疑 NapCat 还没登录或 `3000` 端口没起来
- `openclaw security audit` 当前有安全告警，公网暴露前必须先处理认证和限流

---

## 接手时不要做的事

- 不要把 `qq-bot/config.yaml` 里的密钥直接抄进文档或聊天
- 不要把 `openclaw-gateway.service` 里的 token 明文贴出去
- 不要同时保留手工前台进程和 `systemd` 进程
- 不要把 QQ 入口从 `qq-main` 改到子 agent，除非在做明确架构变更

---

## 如果你改了部署

如果后续修改了端口、服务名、启动方式、日志路径、agent id、workspace 或子 agent 拓扑，请同步更新：

- `CLAUDE.md`
- `HANDOVER.md`
- `SETUP.md`
- `docs/openclaw-setup.md`
- `docs/systemd-ops.md`
- `ops/deployment_manifest.json`

否则下一次接手时很容易被旧信息误导。
