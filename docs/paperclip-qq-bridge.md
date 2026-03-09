# Paperclip + QQ + OpenClaw 最小闭环

> 文档: `docs/paperclip-qq-bridge.md`
> 更新: 2026-03-09

---

## 目标

这套接法不是把你现有的 QQ 入口推倒重来，而是：

- QQ 继续作为唯一自然语言入口
- OpenClaw 继续负责大脑 / 子 agent 协调
- Paperclip 额外负责任务编排、issue 管理、heartbeat 唤醒

也就是说：

```text
QQ -> OpenClaw(qq-main) -> brain-secretary-dev -> Paperclip -> OpenClaw Gateway Agents
```

同时，老的 `qq-bot/` 辅助入口也新增了直接操作 Paperclip 的 `/pc-*` 指令，方便你做兼容联调。

---

## 仓库里新增了什么

- Paperclip CLI：`scripts/paperclip_cli.py`
- Paperclip bootstrap 脚本：`scripts/paperclip_bootstrap.sh`
- QQ Bridge Paperclip 客户端：`qq-bot/bot/paperclip_client.py`
- QQ Bridge Paperclip 命令：`qq-bot/bot/paperclip_commands.py`
- 环境变量示例：`ops/paperclip.env.example`

---

## 先把 Paperclip 拉下来

```bash
bash scripts/paperclip_bootstrap.sh
```

默认会：

- 克隆 / 更新 `https://github.com/paperclipai/paperclip`
- 安装依赖（走 `corepack pnpm`）
- 生成本地运行用的 `.env.local`

默认目录：

- 代码：`/root/paperclip`
- 数据：`/root/paperclip-data`

---

## 本机启动 Paperclip

```bash
cd /root/paperclip
set -a
source .env.local
set +a
corepack pnpm dev:once
```

默认监听：

- `http://127.0.0.1:3100`

说明：

- 这里默认用 `local_trusted`，适合先在服务器内网和 QQ / OpenClaw 做联调
- 等你后面真要公网开放，再单独补认证和反代

---

## QQ / CLI 怎么连 Paperclip

推荐用环境变量，不要把真实 key 写进 Git：

```bash
export QQ_BOT_PAPERCLIP_ENABLED=true
export QQ_BOT_PAPERCLIP_API_BASE_URL=http://127.0.0.1:3100
export QQ_BOT_PAPERCLIP_COMPANY_ID=<paperclip-company-id>
export QQ_BOT_PAPERCLIP_API_KEY=<paperclip-api-key>
export QQ_BOT_PAPERCLIP_DEFAULT_ASSIGNEE_AGENT_ID=<paperclip-agent-id>
```

如果你当前是本机 `local_trusted` 联调，也可以先不填 `QQ_BOT_PAPERCLIP_API_KEY`。

---

## CLI 用法（给 OpenClaw agent / 终端 / 脚本调用）

查看状态：

```bash
python3 scripts/paperclip_cli.py status --json
```

看 agent：

```bash
python3 scripts/paperclip_cli.py agents --json
```

看 issues：

```bash
python3 scripts/paperclip_cli.py issues --json
```

创建 issue：

```bash
python3 scripts/paperclip_cli.py create \
  --title "检查 multimodal-retrieval 的测试失败原因" \
  --description "先跑测试，再给修复建议" \
  --agent brain-secretary-dev \
  --json
```

创建并立即唤醒：

```bash
python3 scripts/paperclip_cli.py run \
  --agent brain-secretary-dev \
  --title "检查 multimodal-retrieval 的测试失败原因" \
  --description "先跑测试，再给修复建议" \
  --json
```

---

## QQ Bridge 兼容指令

如果你走的是本仓库 `qq-bot/` 辅助入口，可以直接发：

- `/pc-status`
- `/pc-agents`
- `/pc-issues`
- `/pc-issue PAP-39`
- `/pc-new 标题|描述|agent`
- `/pc-run agent|标题|描述`
- `/pc-wake agent 原因`
- `/pc-help`

推荐最常用的是：

```text
/pc-run brain-secretary-dev|检查 multimodal-retrieval 的测试失败|先跑测试，再给修复建议
```

---

## 和你当前主 QQ 入口怎么配合

你现在正式入口是：

```text
qqbot/default -> qq-main
```

这条链路本身不需要替换。

最推荐的做法是：

1. 你继续在 QQ 里找 `qq-main`
2. `qq-main` 把需要工程落地 / 调用 Paperclip 的事情派给 `brain-secretary-dev`
3. `brain-secretary-dev` 直接在仓库里调用 `scripts/paperclip_cli.py`
4. 结果再回给你

这样你只有一个 QQ 入口，但后端已经多了一层 Paperclip 任务编排。

---

## 推荐下一步

如果你准备把 Paperclip 真接到现网协作闭环，下一步是：

1. 启动 Paperclip
2. 创建一个公司
3. 在 Paperclip 里注册 3 个 `openclaw_gateway` agent：
   - `qq-main`
   - `brain-secretary-dev`
   - `brain-secretary-review`
4. 再让 QQ 指令直接创建 issue + wake agent

等这一步做完，你的夜间巡检 / 方案派单 / 验收回收就更像真正的调度系统了。
