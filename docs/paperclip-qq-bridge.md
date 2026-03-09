# Paperclip + QQ + OpenClaw 闭环说明

> 文档：`docs/paperclip-qq-bridge.md`
> 更新：2026-03-09

---

## 当前部署形态

当前不是用 Paperclip 替代 OpenClaw，而是把 Paperclip 接在现有主入口后面，作为任务控制面与网页看板：

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents
                                                                       -> Paperclip 控制面 / 任务面板
```

当前现网参数：

- OpenClaw 主入口：`qqbot/default -> qq-main`
- Paperclip 内部地址：`http://127.0.0.1:3110`
- Paperclip 公网查看入口：`http://110.41.170.155/paperclip/`
- Paperclip 直连入口：`http://110.41.170.155:3100`（保留，但当前云侧端口未放行）
- Paperclip 运行用户：`paperclip`
- Paperclip 代码目录：`/home/paperclip/paperclip`
- Paperclip 数据目录：`/home/paperclip/paperclip-data`
- Paperclip viewer 凭据文件：`/root/.config/brain-secretary/paperclip-viewer.env`
- Paperclip 中文补丁脚本：`scripts/paperclip_ui_zh_patch.py`
- 本机 QQ / CLI 桥接 env：`ops/paperclip.local.env`

---

## 当前闭环能力

已经打通：

- 本机 `QQ / CLI -> Paperclip` 走 `local_trusted`，默认不再依赖 agent key
- Paperclip 自动创建 / 维护 3 个控制面 agent：
  - `qq-main`
  - `brain-secretary-dev`
  - `brain-secretary-review`
- 每个 Paperclip agent 都映射到对应 OpenClaw agent
- Paperclip viewer 通过 `nginx + basic auth` 对外提供只读/可操作网页入口
- QQ / CLI 的 `/pc-run` 会创建 `todo` issue，并自动触发对应 agent

当前 OpenClaw gateway 适配器使用固定 session key，避免出现：

```text
agent "xxx" does not match session key agent "main"
```

固定规则为：

- `qq-main` -> `agent:qq-main:paperclip`
- `brain-secretary-dev` -> `agent:brain-secretary-dev:paperclip`
- `brain-secretary-review` -> `agent:brain-secretary-review:paperclip`

---

## 一键部署步骤

### 1) 拉起 Paperclip 代码与依赖

```bash
bash scripts/paperclip_bootstrap.sh
```

默认会准备：

- 代码：`/home/paperclip/paperclip`
- 数据：`/home/paperclip/paperclip-data`
- 环境文件：`/home/paperclip/paperclip/.env.local`

### 2) 应用运行时与公网 viewer

```bash
bash scripts/paperclip_runtime_apply.sh
```

这个脚本会：

- 生成 / 修正 `.env.local`
- 从已发布的 `@paperclipai/server` 包提取 `ui-dist`
- 写入 `paperclip.service`
- 写入 `nginx` 的 `paperclip-public.conf`
- 生成 viewer basic auth 凭据
- 自动注入中文汉化补丁（`zh-patch.js`）
- 启动 `paperclip.service`
- 重载 `nginx`

### 3) 初始化 company / agents / 本地 env

```bash
python3 scripts/paperclip_seed.py --json
```

这个脚本会：

- 创建 / 复用 `Brain Secretary` company
- 创建 / 修正 3 个 Paperclip agent
- 给 `qq-main` 生成 agent key（保留给后续扩展）
- 生成本机桥接 env：`ops/paperclip.local.env`

---

## 本机桥接规则

本机 `QQ / CLI / 脚本` 推荐直接走：

```bash
QQ_BOT_PAPERCLIP_ENABLED=true
QQ_BOT_PAPERCLIP_API_BASE_URL=http://127.0.0.1:3110
QQ_BOT_PAPERCLIP_COMPANY_ID=<company-id>
QQ_BOT_PAPERCLIP_DEFAULT_ASSIGNEE_AGENT_ID=<agent-id>
```

默认 **不需要** `QQ_BOT_PAPERCLIP_API_KEY`，因为本机是 `local_trusted`。

只有在你未来把调用端放到别的机器上时，才考虑额外发 agent key / cookie。

---

## 常用验证命令

查看服务：

```bash
systemctl status paperclip.service
curl http://127.0.0.1:3110/api/health
```

查看公网 viewer：

```bash
source /root/.config/brain-secretary/paperclip-viewer.env
curl -u "$PAPERCLIP_VIEWER_USER:$PAPERCLIP_VIEWER_PASSWORD" http://127.0.0.1/paperclip/api/health
```

查看控制面：

```bash
python3 scripts/paperclip_cli.py status --json
python3 scripts/paperclip_cli.py agents --json
python3 scripts/paperclip_cli.py issues --json
```

创建并触发一个任务：

```bash
python3 scripts/paperclip_cli.py run   --agent brain-secretary-dev   --title "检查测试失败"   --description "先跑测试，再给建议"   --json
```

查看执行日志：

```bash
curl http://127.0.0.1:3110/api/companies/<company-id>/heartbeat-runs?limit=10
curl http://127.0.0.1:3110/api/heartbeat-runs/<run-id>/log
```

---

## QQ 指令映射

如果你走的是仓库里的辅助 `qq-bot/`，可直接发：

- `/pc-status`
- `/pc-agents`
- `/pc-issues`
- `/pc-issue BRA-4`
- `/pc-new 标题|描述|agent`
- `/pc-run agent|标题|描述`
- `/pc-wake agent 原因`
- `/pc-help`

推荐最常用的是：

```text
/pc-run brain-secretary-dev|检查 multimodal-retrieval 的测试失败|先跑测试，再给修复建议
```

---

## 与主 QQ 入口的关系

你的正式消息入口仍然是：

```text
qqbot/default -> qq-main
```

Paperclip 不替代它，只提供：

- 网页任务面板
- issue / run / wake 控制面
- agent 执行日志与可视化
- 未来的多项目任务池 / 审批 / 追踪

所以最推荐的日常用法还是：

1. 你继续在 QQ 找 `qq-main`
2. `qq-main` / 子 agent 在需要时调用 `scripts/paperclip_cli.py`
3. 你同时可以在网页端看任务与运行日志
