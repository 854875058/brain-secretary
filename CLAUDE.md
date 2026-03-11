# CLAUDE.md

> 本文件给后续助手 / Claude / Codex / 自动化运维流程读取。
> 更新: 2026-03-11

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
- `auto-evolve-main`：自动进化专用内部协调 agent，workspace=`/root/.openclaw/workspace`
- `brain-secretary-dev`：主项目工程子 agent，workspace=`/root/brain-secretary`
- `brain-secretary-review`：方案 / 验收子 agent，workspace=`/root/brain-secretary`

### 当前 QQ 入口规则

- 当前主 QQ 消息链路：`QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents`，子 agent 协同会自动投影到 Paperclip 父子 issue
- 当前显式绑定：`qqbot:default -> qq-main`
- 自动进化内部链路：`openclaw-project-auto-evolve.service -> OpenClaw(auto-evolve-main) -> 子 agents`
- 辅助多 QQ 链路：`NapCat(instance) -> QQ Bridge(instance) -> OpenClaw(target agent)`
- 不要为了“省事”把 OpenClaw 原生主入口直接切到子 agent，那会破坏统一协调层
- 仓库里的 `qq-bot/` 仍不是现网主入口，但现在作为多扫码 QQ 辅助入口重新启用

### 协调规则

- `qq-main` 负责：理解意图、拆任务、派任务、验收结果、统一回复
- `auto-evolve-main` 负责：按 `ops/auto-evolve.json` 周期性驱动注册项目做内部自动进化，但不承接 QQ 入口流量
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
- `auto-evolve-main.subagents.allowAgents = ["brain-secretary-dev", "brain-secretary-review"]`
- `tools.agentToAgent.enabled = true`
- `tools.agentToAgent.allow = ["qq-main", "auto-evolve-main", "brain-secretary-dev", "brain-secretary-review"]`
- `tools.sessions.visibility = "all"`
- `agents.defaults.subagents.*` 已配置并发、超时、归档等默认值
- 当前默认模型为 `penguin/claude-sonnet-4-6`
- 2026-03-10 起不再默认走 `gpt-5.1`，因为上游 distributor 多次返回 `503 No available channel for model gpt-5.1`
- `model-proxy.mjs` 必须透传 `messages` / `tools`，不能再删掉 tool calling 字段

---

## 当前约定

- Linux 当前部署方式：`systemd --user(OpenClaw + projection + auto-evolve)` + `systemd(Paperclip)` + `nginx`
- Linux 当前 OpenClaw 配置文件：`/root/.openclaw/openclaw.json`
- Linux 当前现网关键服务：
  - `openclaw-model-proxy.service`
  - `openclaw-gateway.service`
  - `openclaw-paperclip-projection.service`
  - `openclaw-project-auto-evolve.service`
  - `nginx.service`
- Linux 当前已退役服务：
  - `openclaw-qq-bridge.service`（已停用）
  - `napcat-qq.service`（已停用）
- 关键服务分组：
  - `frontend` = `public_proxy`
  - `backend` = `model_proxy + gateway + paperclip + paperclip_projection + project_auto_evolve`
  - `all` = 当前平台全部关键组件
- 不要优先手工 `kill` 进程；先尝试统一运维脚本
- 不要把密钥、token、私密配置直接写入文档

## GitHub 维护规则

- 当前只维护 `/root/brain-secretary` 这一套主 GitHub 仓库。
- 不要把 `/root/.openclaw`、`qq-bot/config.yaml`、`qq-bot/logs/`、运行态数据库、收件箱和虚拟环境提交到远端。
- 一次修改完成后，如果用户没有明确禁止，必须执行：`bash scripts/git_sync.sh -m "<类型: 中文说明本次修改内容>"`
- 自动推送开关使用仓库配置 `brain.autopush`；开启后 post-commit hook 会在本地提交后自动尝试推送 `origin`。
- 初次配置 Git 用户、远端和代理，优先执行：`bash scripts/git_bootstrap.sh`
- 对不读取 `CLAUDE.md` 的工具，补充说明见：`docs/github-workflow.md`、`.github/copilot-instructions.md`、`.cursorrules`

---

## 当前关键文件

- 运维脚本：`scripts/ops_manager.py`
- 运维清单：`ops/deployment_manifest.json`
- 项目注册表：`ops/project_registry.json`
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
- Windows 本地一键入口：`scripts/windows_local_qq_quick_setup.bat`
- Windows 本地三开脚手架：`scripts/windows_local_qq_multi.ps1`
- Windows 本地自检脚本：`scripts/windows_local_qq_doctor.ps1`
- Windows 本地自检批处理：`scripts/windows_local_qq_doctor.bat`
- Windows 本地远程应用脚本：`scripts/windows_local_qq_remote_apply.ps1`
- 桥接记忆中心脚本：`scripts/memory_center.py`
- 双轨分支同步脚本：`scripts/project_sync.py`
- 双轨分支配置：`ops/project-sync.json`
- 自动进化配置：`ops/auto-evolve.json`
- 自动进化守护脚本：`scripts/project_auto_evolve_daemon.py`
- 自动进化安装脚本：`scripts/project_auto_evolve_apply.sh`
- 主分支保护脚本：`scripts/git_branch_guard.py`
- 项目注册表脚本：`scripts/project_registry.py`
- Windows 项目自动跟踪脚本：`scripts/windows_project_autosync.ps1`
- Windows 项目自动跟踪批处理：`scripts/windows_project_autosync.bat`
- 双轨分支工作流文档：`docs/project-sync-branch-workflow.md`
- Paperclip 桥接文档：`docs/paperclip-qq-bridge.md`
- Paperclip CLI：`scripts/paperclip_cli.py`
- Paperclip 中文补丁：`scripts/paperclip_ui_zh_patch.py`
- Paperclip 自动投影脚本：`scripts/paperclip_projection_daemon.py`
- Paperclip 自动投影安装脚本：`scripts/paperclip_projection_apply.sh`
- Paperclip 自动投影 unit：`ops/systemd/openclaw-paperclip-projection.service`
- Paperclip 代码目录：`/home/paperclip/paperclip`
- Paperclip 数据目录：`/home/paperclip/paperclip-data`
- Paperclip 内部地址：`http://127.0.0.1:3110`
- Paperclip 公网 viewer：`http://110.41.170.155/paperclip/`
- Paperclip viewer 凭据：`/root/.config/brain-secretary/paperclip-viewer.env`
- Paperclip 本机桥接 env：`ops/paperclip.local.env`
- Paperclip Bootstrap：`scripts/paperclip_bootstrap.sh`
- Paperclip 运行时部署：`scripts/paperclip_runtime_apply.sh`
- Paperclip Seed：`scripts/paperclip_seed.py`
- NapCat 多实例根目录：`/root/napcat-multi`
- QQ Bridge 多实例根目录：`/root/qq-bot-multi`
- Windows 本地三开文档：`docs/windows-local-qq-multi.md`
- 已退役历史页面：`/chat-history`、`/api/chat-history`（公网返回 `410`）
- 旧桥接代码：`qq-bot/`（仅历史参考，不是现网入口）

---

## QQ 自助进化入口

- 现网 QQ 入口已切换到 OpenClaw `qqbot` 渠道；QQ 实时对话仍由 `qq-main` 协调，项目自动进化闭环改由 `auto-evolve-main` + 子 agent 完成
- `qq-main` 收到“自助进化 / 记住这个 / 写进规则 / 完成一件告诉我一件”这类诉求时，应优先：
  - 拆解任务
  - 必要时委派 `brain-secretary-dev`
  - 完成后回推进展
  - 把长期结论固化到规则 / 记忆 / 文档
- 仓库里的 `qq-bot` 自助进化实现已转为历史实现，不再作为现网入口依赖

## 修复 / 热修默认动作

- 修复 / 恢复类任务默认先直接动手，不要为明显修复动作反复追问用户
- 修完后必须先自验证，再对外汇报“已修复 / 已恢复 / 已可用”
- 未经验证，不要把计划、推测或未执行动作表述成完成事实

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
- 当前主链路默认使用 `penguin/claude-sonnet-4-6`；`model-proxy.mjs` 主要保留给 OpenAI-compatible 备用源兼容
- `model-proxy.mjs` 已兼容 `stream=true -> 上游 JSON -> 本地 SSE`，历史上也支持把 `vllm/gpt-5.4` 转成上游可识别的 `gpt-5.4`
- `scripts/napcat_multi.py` 已生成 3 个隔离的扫码示例目录：`/root/napcat-multi/{brain,tech,review}`
- 旧 `NapCat / qq-bot(FastAPI Bridge)` 现网服务已停用
- `/chat-history` 与 `/api/chat-history` 已在公网明确返回 `410`，避免旧入口残留 502

## 当前已知风险

- `openclaw status` 仍会提示：`channels.qqbot.allowFrom=["*"]`，这是多用户信任边界风险
- `openclaw status` 仍会提示：`dangerouslyDisableDeviceAuth=true` 与认证限流未配置
- `openclaw plugins list` 的版本列取自插件 manifest，可能与 npm 包版本不同；排障时以 `plugins.installs.qqbot` 与 `/root/.openclaw/extensions/qqbot/package.json` 为准


## Paperclip 当前状态

- Paperclip 现在作为 `QQ/OpenClaw` 后面的任务控制面，不替代 `qqbot/default -> qq-main` 主入口
- 当前服务：`paperclip.service`（systemd system service）
- 当前自动投影服务：`openclaw-paperclip-projection.service`（systemd user service）
- 当前内部地址：`http://127.0.0.1:3110`
- 当前公网 viewer：`http://110.41.170.155/paperclip/`，经 `nginx /paperclip/ + basic auth` 暴露（`:3100` 直连保留，但当前云侧端口未放行）
- 本机 `QQ / CLI -> Paperclip` 默认走 `local_trusted`，不再依赖本地 agent key
- 当前 Paperclip 控制面 agent：`qq-main`、`brain-secretary-dev`、`brain-secretary-review`
- 当前 OpenClaw gateway session key 固定为：`agent:<openclaw_agent_id>:paperclip`
- `qq-main` / `auto-evolve-main` 只要调用了子 agent，自动投影服务就会把协同过程镜像成 Paperclip 父子 issue
- 当前已新增项目 24 小时自动进化守护：按 `ops/auto-evolve.json` 周期性驱动 `auto-evolve-main` 主动巡检项目，并强制只在 agent 分支工作
- 自动进化每轮默认使用 fresh session，并会在正式开跑前先修复 `main / work / agent` 边界，避免旧超时上下文和串分支
- 投影 issue 默认不分配 assignee，只用于网页观战，避免在 Paperclip 里重复执行
- 投影服务会忽略 Paperclip 自身 wake event，避免递归回灌
