# Linux `systemd` 运维手册

> 文档: `docs/systemd-ops.md`
> 更新: 2026-03-07
> 适用环境: 当前 `/root` Linux 部署

---

## 目的

这份文档记录当前实际在线环境的运行基线，重点解决三类问题：

- 后续维护时，应该用什么命令管理进程
- 当前 QQ / OpenClaw / NapCat 的实际链路是什么
- 当前多 agent 结构如何落地、修改后该重启什么

如果仓库里其他文档仍保留 Windows 手工启动示例，以本文件记录的 **当前 Linux 现网运行方式** 为准。

---

## 当前实际链路

```text
QQ -> NapCat -> qq-bot(FastAPI Bridge) -> OpenClaw(qq-main) -> 子 agents -> qq-main -> qq-bot -> NapCat -> QQ
```

其中：

- `NapCat` 负责承接 QQ 客户端与 OneBot 能力
- `qq-bot` 监听 `http://127.0.0.1:8000/qq/message`
- `nginx` 监听公网 `http://110.41.170.155:80/`，把 `/` 代理到 OpenClaw 内部 `127.0.0.1:18789`，把 `/chat-history*` 代理到 `127.0.0.1:8000`
- `qq-bot` 把消息交给 OpenClaw agent `qq-main`
- `qq-main` 在 OpenClaw 内部调度真实子 agent
- 最终结果再经 `qq-bot` / NapCat 回复给 QQ

---

## 统一运维脚本

当前推荐把启停、重启、状态、端口和日志操作统一收口到：`scripts/ops_manager.py`。

常用命令：

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
python3 scripts/ops_manager.py restart backend
python3 scripts/ops_manager.py logs bridge -n 80
```

脚本的数据真源：`ops/deployment_manifest.json`

---

## 当前运行基线

当前环境采用 **root 用户的用户级 `systemd`** 托管，而不是前台 shell 常驻。

关键结论：

- OpenClaw / qq-bot / NapCat 使用 `systemctl --user`，公网代理 `nginx` 使用 `systemctl`
- 不要再手工前台跑 `python main.py`
- 不要再手工前台跑 `/root/Napcat/opt/QQ/qq`
- 如果改了 OpenClaw 配置，优先重启 `openclaw-gateway.service`
- 如果改了 `qq-bot/config.yaml`，优先重启 `openclaw-qq-bridge.service`
- `root` 已开启 `linger`，所以即使 SSH 断开，用户级服务也会继续运行

查看 `linger` 状态：

```bash
loginctl show-user root -p Linger
```

---

## 服务清单

| 服务 | Unit | 作用 | Unit 文件 | 关键端口 |
|---|---|---|---|---|
| OpenClaw Model Proxy | `openclaw-model-proxy.service` | OpenClaw 模型兼容代理 | `/root/.config/systemd/user/openclaw-model-proxy.service` | 内部使用 |
| OpenClaw Gateway | `openclaw-gateway.service` | OpenClaw 主网关 + 多 agent 运行时 | `/root/.config/systemd/user/openclaw-gateway.service` | `18789` |
| OpenClaw QQ Bridge | `openclaw-qq-bridge.service` | `qq-bot/main.py` 常驻服务 | `/root/.config/systemd/user/openclaw-qq-bridge.service` | `8000` |
| Public Reverse Proxy | `nginx.service` | 公网统一入口，代理 OpenClaw 与聊天记录页 | `/lib/systemd/system/nginx.service` | `80` |
| NapCat QQ Client | `napcat-qq.service` | 无头 QQ / NapCat 进程 | `/root/.config/systemd/user/napcat-qq.service` | `3000`、`6099` |

说明：

- `openclaw-gateway.service` 与 `openclaw-model-proxy.service` 由 OpenClaw 安装流程创建
- `openclaw-qq-bridge.service` 负责启动 `/root/brain-secretary/qq-bot/main.py`
- `nginx.service` 负责把公网 `80` 端口分流到 OpenClaw 与聊天记录页
- `napcat-qq.service` 通过 `/root/Napcat/start-qq.sh --qq 2230906690` 启动无头 QQ
- 当前生效的 OneBot 账号级配置文件是 `/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11_2230906690.json`

---

## 当前多 Agent 运行事实

当前正式 agent：

- `qq-main` → 协调大脑
- `brain-secretary-dev` → 主项目工程子 agent
- `agent-hub-dev` → 次级项目工程子 agent

查看命令：

```bash
openclaw agents list --bindings --json
```

当前生效配置文件：`/root/.openclaw/openclaw.json`

---

## 日常管理命令

### 1) 查看状态

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service openclaw-qq-bridge.service napcat-qq.service
systemctl status nginx
```

### 2) 启动 / 重启

```bash
systemctl --user start openclaw-model-proxy.service
systemctl --user start openclaw-gateway.service
systemctl --user start openclaw-qq-bridge.service
systemctl --user start napcat-qq.service
systemctl start nginx

systemctl --user restart openclaw-gateway.service openclaw-qq-bridge.service napcat-qq.service
systemctl restart nginx
```

### 3) 停止

```bash
systemctl stop nginx
systemctl --user stop napcat-qq.service
systemctl --user stop openclaw-qq-bridge.service
systemctl --user stop openclaw-gateway.service
systemctl --user stop openclaw-model-proxy.service
```

### 4) 修改 Unit 文件后重载

```bash
systemctl --user daemon-reload
systemctl daemon-reload
```

---

## 关键文件位置

### 代码与配置

- 仓库根目录：`/root/brain-secretary`
- 次级仓库：`/root/agent-hub`
- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- Model Proxy 脚本：`/root/.openclaw/model-proxy.mjs`
- Model Proxy 环境：`/root/.openclaw/model-proxy.env`
- 脑 workspace：`/root/.openclaw/workspace`
- QQ Bridge 入口：`/root/brain-secretary/qq-bot/main.py`
- QQ Bridge 配置：`/root/brain-secretary/qq-bot/config.yaml`
- NapCat 启动脚本：`/root/Napcat/start-qq.sh`

### `systemd` Unit 文件

- `/root/.config/systemd/user/openclaw-model-proxy.service`
- `/root/.config/systemd/user/openclaw-gateway.service`
- `/root/.config/systemd/user/openclaw-qq-bridge.service`
- `/root/.config/systemd/user/napcat-qq.service`
- `/lib/systemd/system/nginx.service`

### 日志与临时文件

- NapCat 总日志：`/root/Napcat/qq.log`
- `qq-bot` 日志目录：`/root/brain-secretary/qq-bot/logs/`
- NapCat 二维码图片：`/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/cache/qrcode.png`

### Web / HTTP 入口

- OpenClaw Dashboard 公网入口：`http://110.41.170.155/`
- OpenClaw Gateway 内部入口：`http://127.0.0.1:18789/`
- QQ Bridge 健康检查：`http://127.0.0.1:8000/`
- 聊天记录页面：`http://110.41.170.155/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- 聊天记录 JSON：`http://110.41.170.155/api/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- QQ 发图测试图：`file:///root/brain-secretary/qq-bot/data/openclaw-test-image.png`
- NapCat HTTP API：`http://127.0.0.1:3000/`
- NapCat WebUI：`http://127.0.0.1:6099/webui?token=<见日志>`

---

## 健康检查

### 服务状态

```bash
systemctl --user status openclaw-model-proxy.service openclaw-gateway.service openclaw-qq-bridge.service napcat-qq.service
systemctl status nginx
```

### 端口监听

```bash
ss -lntp | rg ':80 |:18789 |:8000 |:6099 |:3000 '
```

### OpenClaw 整体状态

```bash
openclaw status
openclaw health
openclaw config validate
```

### QQ Bridge 健康检查

```bash
curl http://127.0.0.1:8000/
```

### QQ 自助进化触发

- 显式命令：`/evolve ...`、`/remember ...`
- 自然语言自动触发：`记住这个`、`写进规则`、`别再犯`、`以后都按这个来`

### NapCat 登录信息

```bash
curl http://127.0.0.1:3000/get_login_info
```

---

## 常见修改后的重启建议

### 改了 OpenClaw agent / 工具 / 多 agent 配置

```bash
openclaw config validate
systemctl --user restart openclaw-gateway.service
```

### 改了 model proxy 脚本或环境

```bash
systemctl --user restart openclaw-model-proxy.service
systemctl --user restart openclaw-gateway.service
```

### 改了 `qq-bot/config.yaml` 或桥接代码

```bash
systemctl --user restart openclaw-qq-bridge.service
```

### 改了公网代理配置

```bash
nginx -t
systemctl restart nginx
```

### 改了 NapCat / OneBot 配置

```bash
systemctl --user restart napcat-qq.service
```

---

## 已知现象与排查建议

### 1) `qq-bot` 日志出现 `发送私聊消息失败: All connection attempts failed`

通常表示：

- NapCat 的 HTTP API 端口尚未就绪
- QQ 还没完成登录
- `qq-bot/config.yaml` 里的 `napcat.url` 与 NapCat 实际监听端口不一致

先检查：

```bash
tail -f /root/Napcat/qq.log
ss -lntp | rg ':3000 |:6099 '
```

### 2) `qq-bot` 日志出现 `No such file or directory: 'wmic'`

这是 `qq-bot` 里某个监控逻辑沿用了 Windows 命令，在 Linux 上会报这个错误。

当前观察：

- 该报错不会阻止 `qq-bot` 主服务启动
