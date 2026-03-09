# Linux 运维说明（systemd / nginx）

> 更新：2026-03-09
> 当前现网：`qqbot/default -> qq-main`

---

## 当前链路

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> QQ Bot -> QQ

可选控制面：Paperclip 内部运行在 `127.0.0.1:3110`，公网优先经 `nginx` 的 `/paperclip/` 暴露（`:3100` 直连保留，但当前云侧端口未放行）
```

说明：

- `openclaw-gateway.service` 承载 OpenClaw 主网关与 `qqbot` 渠道
- `qq-main` 负责理解用户意图、调度子 agent、验收结果、统一回复
- `nginx` 监听公网 `http://110.41.170.155:80/`，把 `/` 代理到 OpenClaw 内部 `127.0.0.1:18789`
- `paperclip.service` 作为 system service 运行在 `127.0.0.1:3110`
- `nginx` 在 `http://110.41.170.155/paperclip/` 提供 Paperclip viewer，并加 basic auth
- `nginx` 仍保留 `http://110.41.170.155:3100/` 直连监听，但当前云侧端口未放行，公网通常超时
- 历史 `qq-bot(FastAPI Bridge)` / `NapCat` 链路已退役，相关 systemd 服务已停用

---

## 当前服务

| 组件 | systemd unit | 作用 | 端口 |
|---|---|---|---|
| OpenClaw Model Proxy | `openclaw-model-proxy.service` | 模型代理 | - |
| OpenClaw Gateway | `openclaw-gateway.service` | OpenClaw 主网关 + `qqbot` 渠道 | `18789` |
| Paperclip | `paperclip.service` | Paperclip 控制面 / issue / heartbeat | `3110` |
| Public Proxy | `nginx.service` | OpenClaw 根路径 + Paperclip `/paperclip/` + 3100 直连 | `80`, `3100` |

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
systemctl status paperclip.service
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
systemctl status paperclip.service
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
ss -lntp | rg ':80 |:3100 |:3110 |:18789 '
```

### HTTP

```bash
curl http://127.0.0.1:18789/
curl http://127.0.0.1:3110/api/health
source /root/.config/brain-secretary/paperclip-viewer.env && curl -u "$PAPERCLIP_VIEWER_USER:$PAPERCLIP_VIEWER_PASSWORD" http://127.0.0.1/paperclip/api/health
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

## NapCat 多实例示例（非现网入口）

现网入口仍然是 `qqbot/default -> qq-main`，但如果要给多个扫码 QQ 号做联调，使用：

```bash
python3 /root/brain-secretary/scripts/napcat_multi.py bootstrap --refresh-workdir
python3 /root/brain-secretary/scripts/napcat_multi.py status --json
python3 /root/brain-secretary/scripts/napcat_multi.py qr --json
python3 /root/brain-secretary/scripts/napcat_multi.py stop
```

默认示例目录：`/root/napcat-multi/{brain,tech,review}`。
桥接目录：`/root/qq-bot-multi/{brain,tech,review}`。

---

## 关键路径

- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- QQ Bot 插件目录：`/root/.openclaw/extensions/qqbot`
- 当前插件来源：`@openclaw-china/qqbot`（npm）
- 脑 workspace：`/root/.openclaw/workspace`
- 运维脚本：`/root/brain-secretary/scripts/ops_manager.py`
- 运维真源：`/root/brain-secretary/ops/deployment_manifest.json`
- NapCat 多实例脚本：`/root/brain-secretary/scripts/napcat_multi.py`
- QQ Bridge 多实例脚本：`/root/brain-secretary/scripts/qq_bot_multi.py`
- Windows 本地一键入口：`/root/brain-secretary/scripts/windows_local_qq_quick_setup.bat`
- Windows 本地三开脚手架：`/root/brain-secretary/scripts/windows_local_qq_multi.ps1`
- Windows 本地自检脚本：`/root/brain-secretary/scripts/windows_local_qq_doctor.ps1`
- Windows 本地自检批处理：`/root/brain-secretary/scripts/windows_local_qq_doctor.bat`
- Windows 本地远程应用脚本：`/root/brain-secretary/scripts/windows_local_qq_remote_apply.ps1`
- 桥接记忆中心脚本：`/root/brain-secretary/scripts/memory_center.py`
- 双轨分支同步脚本：`/root/brain-secretary/scripts/project_sync.py`
- Windows 项目自动跟踪脚本：`/root/brain-secretary/scripts/windows_project_autosync.ps1`
- Windows 项目自动跟踪批处理：`/root/brain-secretary/scripts/windows_project_autosync.bat`
- 双轨分支工作流文档：`/root/brain-secretary/docs/project-sync-branch-workflow.md`
- NapCat 多实例根目录：`/root/napcat-multi`
- QQ Bridge 多实例根目录：`/root/qq-bot-multi`
- Windows 本地三开文档：`/root/brain-secretary/docs/windows-local-qq-multi.md`
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

### 5) `qq-main` 能收消息但一直超时

优先检查模型代理是否已经应用了流式兼容修复：

```bash
systemctl --user status openclaw-model-proxy.service --no-pager -n 40
curl -sS http://127.0.0.1:18080/healthz
openclaw agent --agent qq-main --session-id qq-main-recover-test --message '只回复一个字：到' --thinking minimal --timeout 45 --json
```

如果这里卡住，优先看 `/root/.openclaw/model-proxy.mjs` 是否仍会：

- 把 `stream=true` 转成上游 JSON 再回放 SSE
- 把 `vllm/gpt-5.4` 改写成 `gpt-5.4`

### 6) 想确认旧服务确实下线

```bash
systemctl --user status openclaw-qq-bridge.service napcat-qq.service
```

预期：`disabled / inactive (dead)`。


## Paperclip viewer

当前 Paperclip 相关文件与端口：

- systemd unit：`paperclip.service`
- 运行目录：`/home/paperclip/paperclip`
- 数据目录：`/home/paperclip/paperclip-data`
- 内部 API：`127.0.0.1:3110`
- 公网 viewer：`110.41.170.155/paperclip/`
- 直连 listener：`110.41.170.155:3100`（保留，但当前云侧端口未放行）
- nginx 配置：`/etc/nginx/sites-available/paperclip-public.conf`
- viewer 凭据：`/root/.config/brain-secretary/paperclip-viewer.env`

常用命令：

```bash
systemctl status paperclip.service
journalctl -u paperclip.service -n 80 --no-pager
python3 scripts/paperclip_seed.py --json
python3 scripts/paperclip_cli.py status --json
python3 scripts/paperclip_cli.py issues --json
```
