# 部署手册

> 文档: `SETUP.md`
> 更新: 2026-03-07

---

## 当前推荐部署方式

当前现网 Linux 环境推荐使用：

- `systemctl --user` 托管 OpenClaw 关键进程
- OpenClaw 采用 **方案 B**：`qq-main` 协调大脑 + 多个真实子 agent
- QQ 接入走 OpenClaw 原生 `qqbot` 渠道

Windows 仍可手工启动，但以 Linux 常驻方案为主。

---

## 当前 OpenClaw agent 布局

| agent id | 角色 | workspace |
|---|---|---|
| `qq-main` | 协调大脑 | `/root/.openclaw/workspace` |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` |

当前 QQ 渠道绑定：`qqbot:default -> qq-main`。

配置位置：`/root/.openclaw/openclaw.json`

---

## 前置条件

### Linux 现网

- OpenClaw 已安装
- OpenClaw model proxy 已可用
- `qqbot` 插件已安装
- QQ Bot 渠道 token 已配置到 OpenClaw
- root 用户已开启 `linger`

### Windows 手工方案

- OpenClaw 已安装
- `qqbot` 插件已安装
- Python 3 已安装（仅仓库脚本需要时）

---

## Linux 部署步骤（推荐）

### 1) 查看整体状态

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
```

### 2) 配置 QQ 渠道（如首次部署）

```bash
openclaw plugins install @sliverp/qqbot@latest
openclaw channels add --channel qqbot --token "<appid>:<clientSecret>"
openclaw agents bind --agent qq-main --bind qqbot:default
```

### 3) 启动后端

```bash
systemctl --user start openclaw-model-proxy.service
systemctl --user start openclaw-gateway.service
```

### 4) 启动公网代理

```bash
systemctl start nginx
```

### 5) 检查状态

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service
systemctl status nginx
openclaw channels list
openclaw agents bindings --json
openclaw status
```

### 6) 检查端口

```bash
ss -lntp | rg ':80 |:18789 '
```

---

## 日常运维

优先使用统一运维脚本：

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
python3 scripts/ops_manager.py restart backend
python3 scripts/ops_manager.py restart public_proxy
python3 scripts/ops_manager.py logs gateway -n 80
```

详细 Linux 运维：`docs/systemd-ops.md`

---

## Windows 手工启动（兼容保留）

### 1) 启动 OpenClaw

```powershell
openclaw gateway --port 18789
```

### 2) 安装并配置 `qqbot` 渠道

```powershell
openclaw plugins install @sliverp/qqbot@latest
openclaw channels add --channel qqbot --token "<appid>:<clientSecret>"
openclaw agents bind --agent qq-main --bind qqbot:default
```

### 3) 校验

```powershell
openclaw channels list
openclaw agents bindings --json
openclaw status
```

---

## 快速验证

```bash
openclaw channels list
openclaw agents bindings --json
openclaw agents list --bindings --json
openclaw status
curl http://127.0.0.1:18789/
```

---

## 关键文件

- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- QQ Bot 插件目录：`/root/.openclaw/extensions/qqbot`
- 脑 workspace：`/root/.openclaw/workspace`
- 主仓：`/root/brain-secretary`
- 运维脚本：`scripts/ops_manager.py`
- 运维真源：`ops/deployment_manifest.json`
- OpenClaw 配置文档：`docs/openclaw-setup.md`
- Linux 运维文档：`docs/systemd-ops.md`
- 旧桥接代码：`qq-bot/`（历史实现，非现网入口）

---

## 退役说明

- `openclaw-qq-bridge.service`：已停用
- `napcat-qq.service`：已停用
- `/chat-history` 与 `/api/chat-history`：已退役，公网返回 `410`
