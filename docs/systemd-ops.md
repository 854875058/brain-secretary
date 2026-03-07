# Linux 运维说明（systemd / nginx）

> 更新：2026-03-07
> 当前现网：`qqbot/default -> qq-main`

---

## 当前链路

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> QQ Bot -> QQ
```

说明：

- `openclaw-gateway.service` 承载 OpenClaw 主网关与 `qqbot` 渠道
- `qq-main` 负责理解用户意图、调度子 agent、验收结果、统一回复
- `nginx` 监听公网 `http://110.41.170.155:80/`，把 `/` 代理到 OpenClaw 内部 `127.0.0.1:18789`
- 历史 `qq-bot(FastAPI Bridge)` / `NapCat` 链路已退役，相关 systemd 服务已停用

---

## 当前服务

| 组件 | systemd unit | 作用 | 端口 |
|---|---|---|---|
| OpenClaw Model Proxy | `openclaw-model-proxy.service` | 模型代理 | - |
| OpenClaw Gateway | `openclaw-gateway.service` | OpenClaw 主网关 + `qqbot` 渠道 | `18789` |
| Public Proxy | `nginx.service` | 公网反代 | `80` |

### 已退役服务

| 组件 | unit | 当前状态 |
|---|---|---|
| OpenClaw QQ Bridge | `openclaw-qq-bridge.service` | disabled / inactive |
| NapCat QQ Client | `napcat-qq.service` | disabled / inactive |

---

## 推荐命令

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
python3 scripts/ops_manager.py restart backend
python3 scripts/ops_manager.py restart public_proxy
python3 scripts/ops_manager.py logs gateway -n 80
openclaw channels list
openclaw agents bindings --json
```

---

## 启停顺序

### 查看整体状态

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
```

### 启动后端

```bash
systemctl --user start openclaw-model-proxy.service
systemctl --user start openclaw-gateway.service
```

### 启动公网代理

```bash
systemctl start nginx
```

### 重启后端

```bash
python3 scripts/ops_manager.py restart backend
```

### 查看日志

```bash
python3 scripts/ops_manager.py logs gateway -n 80
```

---

## 关键检查

### 服务状态

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service
systemctl status nginx
```

### OpenClaw 渠道与绑定

```bash
openclaw channels list
openclaw agents bindings --json
openclaw agents list --bindings --json
openclaw status
```

### 端口

```bash
ss -lntp | rg ':80 |:18789 '
```

### HTTP

```bash
curl http://127.0.0.1:18789/
curl -I http://110.41.170.155/
curl -I http://110.41.170.155/chat-history
```

预期：

- `/` -> OpenClaw Dashboard / Gateway
- `/chat-history` -> `410 Gone`（历史入口已退役）

---

## 修改后该重启什么

### 改了 `/root/.openclaw/openclaw.json`

```bash
openclaw config validate
systemctl --user restart openclaw-gateway.service
```

### 改了 `/root/.openclaw/model-proxy.mjs` 或 `/root/.openclaw/model-proxy.env`

```bash
systemctl --user restart openclaw-model-proxy.service
```

### 改了 `/etc/nginx/sites-available/openclaw-public.conf`

```bash
nginx -t && systemctl reload nginx
```

---

## 关键路径

- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- QQ Bot 插件目录：`/root/.openclaw/extensions/qqbot`
- 当前插件来源：`@openclaw-china/qqbot`（npm）
- 脑 workspace：`/root/.openclaw/workspace`
- 运维脚本：`/root/brain-secretary/scripts/ops_manager.py`
- 运维真源：`/root/brain-secretary/ops/deployment_manifest.json`
- 公网反代配置：`/etc/nginx/sites-available/openclaw-public.conf`
- 旧桥接代码：`/root/brain-secretary/qq-bot/`

---

## 故障排查

### 1) `openclaw status` 显示 `QQ Bot` 未配置或非 `OK`

先看：

```bash
openclaw channels list
openclaw agents bindings --json
```

如果缺绑定，补：

```bash
openclaw agents bind --agent qq-main --bind qqbot:default
```

### 2) `openclaw status` 有 `allowFrom=["*"]` 警告

这不是宕机问题，但代表当前 QQ 渠道允许所有来源；如果要收口，需要改 `channels.qqbot.allowFrom`。

### 3) `openclaw plugins list` 里的 `qqbot` 版本看起来不对

`openclaw plugins list` 的版本列来自插件 manifest，可能显示为 `0.1.0`；这不代表安装失败。真实安装来源与版本以 `/root/.openclaw/openclaw.json` 的 `plugins.installs.qqbot` 和 `/root/.openclaw/extensions/qqbot/package.json` 为准。

### 4) 访问 `/chat-history` 返回 `410`

这是预期行为。历史聊天记录页面已随旧桥接链路退役。

### 5) 想确认旧服务确实下线

```bash
systemctl --user status openclaw-qq-bridge.service napcat-qq.service
```

预期：`disabled / inactive (dead)`。
