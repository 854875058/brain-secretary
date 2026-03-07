# 部署手册

> 文档: `SETUP.md`
> 更新: 2026-03-07

---

## 当前推荐部署方式

当前**现网 Linux 环境**推荐使用：

- `systemctl --user` 托管 OpenClaw / qq-bot / NapCat
- OpenClaw 采用 **方案 B**：`qq-main` 协调大脑 + 多个真实子 agent
- QQ 接入继续走 `NapCat -> qq-bot -> OpenClaw`

Windows 仍可手工启动，但以 Linux 常驻方案为主。

---

## 当前 OpenClaw agent 布局

| agent id | 角色 | workspace |
|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` |
| `agent-hub-dev` | 次级项目工程子 agent | `/root/agent-hub` |

QQ Bridge 当前固定把消息送给：`qq-main`

配置位置：`/root/.openclaw/openclaw.json`

---

## 前置条件

### Linux 现网

- OpenClaw 已安装
- OpenClaw model proxy 已可用
- Python 3 已安装
- NapCat 已安装并可无头启动
- root 用户已开启 `linger`

### Windows 手工方案

- OpenClaw 已安装
- Python 3 已安装
- NapCat / QQ 已安装

---

## Linux 启动顺序（推荐）

### 1) 查看整体状态

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
```

### 2) 启动后端

```bash
systemctl --user start openclaw-model-proxy.service
systemctl --user start openclaw-gateway.service
systemctl --user start openclaw-qq-bridge.service
```

### 3) 启动前端 QQ / NapCat

```bash
systemctl --user start napcat-qq.service
```

### 4) 检查服务状态

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service openclaw-qq-bridge.service napcat-qq.service
```

### 5) 检查端口

```bash
ss -lntp | rg ':80 |:8000 |:6099 |:3000 '
```

### 6) 如果 NapCat 还未登录 QQ

查看：

- `/root/Napcat/qq.log`
- `/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png`

---

## OpenClaw 多 Agent 配置说明

当前生效配置已经完成以下事项：

- 创建 `qq-main` 协调脑
- 创建 `brain-secretary-dev` 与 `agent-hub-dev` 两个真实子 agent
- 开启 `qq-main -> 子 agent` 的委派能力
- 开启跨 agent 会话可见性与 agent-to-agent 能力
- 配置子 agent 默认并发、超时、归档策略

查看命令：

```bash
openclaw agents list --bindings --json
openclaw config validate
```

文档见：`docs/openclaw-setup.md`

---

## QQ Bridge 配置

配置文件：`qq-bot/config.yaml`

当前关键约定：

- `openclaw.enabled: true`
- `openclaw.agent_id: qq-main`
- `openclaw.thinking: low`
- NapCat 回调入口：`http://127.0.0.1:8000/qq/message`
- 聊天记录公网页：`http://110.41.170.155/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- 聊天记录公网 API：`http://110.41.170.155/api/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- OpenClaw 公网入口：`http://110.41.170.155/`
- OpenClaw 内部入口：`http://127.0.0.1:18789/`
- QQ 自助进化命令：`/evolve ...`、`/remember ...`
- QQ 发图约定：OpenClaw 输出 `[[send_image]] <图片URL或file://路径>` 时，桥接会发送图片消息
- QQ 发视频约定：OpenClaw 输出 `[[send_video]] <视频URL或file://路径>` 时，桥接会发送视频消息
- QQ 发语音约定：OpenClaw 输出 `[[send_voice]] <语音URL或file://路径>` 时，桥接会发送语音；若只给文本，也可输出 `[[send_tts]] 这里写文本`，由桥接本地合成语音后发送

---

## 日常运维

优先使用统一运维脚本：

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
python3 scripts/ops_manager.py restart backend
python3 scripts/ops_manager.py restart public_proxy
python3 scripts/ops_manager.py logs bridge -n 80
```

详细 Linux 运维：`docs/systemd-ops.md`

---

## Windows 手工启动（兼容保留）

### 1) 启动 OpenClaw

```powershell
openclaw gateway --port 18789
```

### 2) 启动 QQ Bridge

```powershell
cd qq-bot
py -3 main.py
```

### 3) 启动 NapCat / QQ

按本地安装方式启动 QQ 与 NapCat，并确保 OneBot HTTP POST 指向：

- `http://127.0.0.1:8000/qq/message`

### 4) 运维脚本（Windows）

```powershell
py -3 scripts\ops_manager.py info
py -3 scripts\ops_manager.py status all
py -3 scripts\ops_manager.py start all
```

---

## 快速验证

### OpenClaw

```bash
openclaw agents list --bindings --json
openclaw status
```

### QQ Bridge

```bash
curl http://127.0.0.1:8000/
```

### NapCat

```bash
curl http://127.0.0.1:3000/get_login_info
```

---

## 关键文件

- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- 脑 workspace：`/root/.openclaw/workspace`
- 主仓：`/root/brain-secretary`
- 次仓：`/root/agent-hub`
- 运维脚本：`scripts/ops_manager.py`
- 运维真源：`ops/deployment_manifest.json`
- OpenClaw 配置文档：`docs/openclaw-setup.md`
- Linux 运维文档：`docs/systemd-ops.md`
