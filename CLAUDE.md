# CLAUDE.md

> 本文件给后续助手 / Claude / Codex / 自动化运维流程读取。
> 更新: 2026-03-07

---

## 运维规则

- 任何涉及本项目部署、启停、重启、状态检查、日志检查、端口检查的问题，优先使用统一运维脚本：`scripts/ops_manager.py`
- 统一运维脚本的数据真源是：`ops/deployment_manifest.json`
- 如果用户询问“当前怎么启动 / 怎么停止 / 端口是多少 / 模型是什么 / 关键脚本和数据在哪里”，优先先读：
  - `CLAUDE.md`
  - `HANDOVER.md`
  - `docs/systemd-ops.md`
  - `docs/openclaw-setup.md`
  - `ops/deployment_manifest.json`

---

## OpenClaw 多 Agent 规则

当前采用方案 B：真正的多 agent 协同 + 协调大脑。

### 当前 agent 拓扑

- `qq-main`：总协调大脑，workspace=`/root/.openclaw/workspace`
- `brain-secretary-dev`：主项目工程子 agent，workspace=`/root/brain-secretary`
- `brain-secretary-review`：方案 / 验收子 agent，workspace=`/root/brain-secretary`

### 当前 QQ 入口规则

- 当前主 QQ 消息链路：`QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents`
- 当前显式绑定：`qqbot:default -> qq-main`
- 辅助多 QQ 链路：`NapCat(instance) -> QQ Bridge(instance) -> OpenClaw(target agent)`
- 不要为了“省事”把 OpenClaw 原生主入口直接切到子 agent，那会破坏统一协调层
- 仓库里的 `qq-bot/` 仍不是现网主入口，但现在作为多扫码 QQ 辅助入口重新启用

### 协调规则

- `qq-main` 负责：理解意图、拆任务、派任务、验收结果、统一回复
- `brain-secretary-dev` 负责主仓工程实施：OpenClaw 接入、运维脚本、部署文档、现网迁移与工程改造
- 旧的次级实验仓已退役；如需旧实现对照，直接参考历史资料，不再派发到独立次仓。

### OpenClaw 配置关键点

当前生效配置文件：`/root/.openclaw/openclaw.json`

关键设置包括：

- `channels.qqbot.enabled = true`
- `plugins.allow = ["qqbot"]`
- `qq-main` 已绑定 `qqbot:default`
- `channels.qqbot.markdownSupport = false`
- `plugins.installs.qqbot.spec = "@openclaw-china/qqbot"`
- `qq-main.subagents.allowAgents = ["brain-secretary-dev", "brain-secretary-review"]`
- `tools.agentToAgent.enabled = true`
- `tools.sessions.visibility = "all"`
- `agents.defaults.subagents.*` 已配置并发、超时、归档等默认值
- `model-proxy.mjs` 必须透传 `messages` / `tools`，不能再删掉 tool calling 字段

---

## 当前约定

- Linux 当前部署方式：`systemd --user` + `nginx`
- Linux 当前 OpenClaw 配置文件：`/root/.openclaw/openclaw.json`
- Linux 当前现网关键服务：
  - `openclaw-model-proxy.service`
  - `openclaw-gateway.service`
  - `nginx.service`
- Linux 当前已退役服务：
  - `openclaw-qq-bridge.service`（已停用）
  - `napcat-qq.service`（已停用）
- 关键服务分组：
  - `frontend` = `public_proxy`
  - `backend` = `model_proxy + gateway`
  - `all` = 当前平台全部关键组件
- 不要优先手工 `kill` 进程；先尝试统一运维脚本
- 不要把密钥、token、私密配置直接写入文档

## GitHub 维护规则

- 当前只维护 `/root/brain-secretary` 这一套主 GitHub 仓库。
- 不要把 `/root/.openclaw`、`qq-bot/config.yaml`、`qq-bot/logs/`、运行态数据库、收件箱和虚拟环境提交到远端。
- 一次修改完成后，如果用户没有明确禁止，必须执行：`bash scripts/git_sync.sh -m "<类型: 中文说明本次修改内容>"`
- 自动推送开关使用仓库配置 `brain.autopush`；开启后 post-commit hook 会在本地提交后自动尝试推送 `origin`。
- 初次配置 Git 用户、远端和代理，优先执行：`bash scripts/git_bootstrap.sh`
- 对不读取 `CLAUDE.md` 的工具，补充说明见：`AI_AUTOCOMMIT.md`、`.github/copilot-instructions.md`、`.cursorrules`

---

## 当前关键文件

- 运维脚本：`scripts/ops_manager.py`
- 运维清单：`ops/deployment_manifest.json`
- 交接文档：`HANDOVER.md`
- Linux 运维文档：`docs/systemd-ops.md`
- OpenClaw 配置文档：`docs/openclaw-setup.md`
- 部署手册：`SETUP.md`
- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- OpenClaw 插件目录：`/root/.openclaw/extensions/qqbot`
- 当前插件来源：`@openclaw-china/qqbot`（npm）
- OpenClaw 公网入口：`http://110.41.170.155/`
- OpenClaw 内部入口：`http://127.0.0.1:18789/`
- NapCat 多实例脚本：`scripts/napcat_multi.py`
- QQ Bridge 多实例脚本：`scripts/qq_bot_multi.py`
- NapCat 多实例根目录：`/root/napcat-multi`
- QQ Bridge 多实例根目录：`/root/qq-bot-multi`
- 已退役历史页面：`/chat-history`、`/api/chat-history`（公网返回 `410`）
- 旧桥接代码：`qq-bot/`（仅历史参考，不是现网入口）

---

## QQ 自助进化入口

- 现网 QQ 入口已切换到 OpenClaw `qqbot` 渠道，因此实际自助进化闭环由 `qq-main` + 子 agent 完成
- `qq-main` 收到“自助进化 / 记住这个 / 写进规则 / 完成一件告诉我一件”这类诉求时，应优先：
  - 拆解任务
  - 必要时委派 `brain-secretary-dev`
  - 完成后回推进展
  - 把长期结论固化到规则 / 记忆 / 文档
- 仓库里的 `qq-bot` 自助进化实现已转为历史实现，不再作为现网入口依赖

## 统一入口

推荐命令：

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

## 当前已验证事实

- `qqbot` 插件已安装并加载
- `plugins.installs.qqbot` 已记录标准 npm 安装来源：`@openclaw-china/qqbot`
- `QQ Bot default` 渠道已配置并启用
- `qqbot:default -> qq-main` 绑定已生效
- `brain-secretary-review` 已加入 OpenClaw agent 列表，并允许被 `qq-main` 协调调用
- `model-proxy.mjs` 已兼容 `stream=true -> 上游 JSON -> 本地 SSE`，并会把 `vllm/gpt-5.4` 转成上游可识别的 `gpt-5.4`
- `scripts/napcat_multi.py` 已生成 3 个隔离的扫码示例目录：`/root/napcat-multi/{brain,tech,review}`
- 旧 `NapCat / qq-bot(FastAPI Bridge)` 现网服务已停用
- `/chat-history` 与 `/api/chat-history` 已在公网明确返回 `410`，避免旧入口残留 502

## 当前已知风险

- `openclaw status` 仍会提示：`channels.qqbot.allowFrom=["*"]`，这是多用户信任边界风险
- `openclaw status` 仍会提示：`dangerouslyDisableDeviceAuth=true` 与认证限流未配置
- `openclaw plugins list` 的版本列取自插件 manifest，可能与 npm 包版本不同；排障时以 `plugins.installs.qqbot` 与 `/root/.openclaw/extensions/qqbot/package.json` 为准
