# 部署手册

> 文档: `SETUP.md`
> 更新: 2026-03-16

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
| `auto-evolve-main` | 自动进化专用内部协调 agent | `/root/.openclaw/workspace` |
| `brain-secretary-dev` | 主项目工程子 agent | `/root/brain-secretary` |
| `brain-secretary-review` | 方案 / 验收子 agent | `/root/brain-secretary` |

当前 QQ 渠道绑定：`qqbot:default -> qq-main`。
自动进化内部链路：`openclaw-project-auto-evolve.service -> auto-evolve-main -> 子 agents`。

配置位置：`/root/.openclaw/openclaw.json`

当前主模型：`penguin/claude-sonnet-4-6`。
备注：2026-03-10 已将默认模型从 `gpt-5.1` 切走，因为上游 distributor 连续返回 `503 No available channel for model gpt-5.1`。

另外，仓库已新增 `AgentTeam` 状态图骨架与私有知识库统一入口，用于后续把复杂业务流收敛到标准状态总线、私有记忆检索和 review 闭环；当前它是开发骨架，不是独立常驻服务。

---

## 前置条件

### Linux 现网

- OpenClaw 已安装
- OpenClaw model proxy 已可用
- `qqbot` 插件（`@openclaw-china/qqbot`）已安装
- QQ Bot 渠道 token 已配置到 OpenClaw
- root 用户已开启 `linger`

### Windows 手工方案

- OpenClaw 已安装
- `qqbot` 插件（`@openclaw-china/qqbot`）已安装
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
openclaw plugins install @openclaw-china/qqbot
openclaw channels add --channel qqbot --token "<appid>:<clientSecret>"
openclaw config set channels.qqbot.markdownSupport false
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

## AgentTeam 状态图骨架（开发入口）

如果你要在当前仓库里继续进化“私有知识库 + 状态管理 + 多 Agent 协同”这条线，优先从以下文件入手：

- 文档：`docs/agent-team-state-graph.md`
- 私有知识库模块：`qq-bot/bot/private_kb.py`
- 状态图协调模块：`qq-bot/bot/agent_team.py`
- Demo 脚本：`scripts/agent_team_demo.py`
- 隔离单测：`tests/test_agent_team.py`

本地 mock 验证：

```bash
python3 scripts/agent_team_demo.py --mode mock --json
python3 -m unittest tests.test_agent_team -v
```

如果你想直接走 OpenClaw 节点而不是 mock：

```bash
python3 scripts/agent_team_demo.py --mode openclaw --context "请把这份 PDF 财务报表转成 Markdown 并提取关键指标"
```

注意：

- 它当前不会替代现网 `qqbot/default -> qq-main` 主链路
- 它也不是新的 systemd 服务
- 它的目标是给后续多 agent 业务流提供统一骨架，而不是引入第二套生产入口

---

## Paperclip 可选接入（QQ / OpenClaw 后方调度层）

如果你想在现有 `QQ -> OpenClaw` 后面再加一层任务编排 / 网页看板，可以接入 Paperclip。

仓库里已经补了：

- 文档：`docs/paperclip-qq-bridge.md`
- Bootstrap 脚本：`scripts/paperclip_bootstrap.sh`
- 运行时部署脚本：`scripts/paperclip_runtime_apply.sh`
- Seed 脚本：`scripts/paperclip_seed.py`
- CLI：`scripts/paperclip_cli.py`
- 自动投影守护脚本：`scripts/paperclip_projection_daemon.py`
- 自动投影安装脚本：`scripts/paperclip_projection_apply.sh`
- 环境变量示例：`ops/paperclip.env.example`

最小步骤：

```bash
bash scripts/paperclip_bootstrap.sh
bash scripts/paperclip_runtime_apply.sh
python3 scripts/paperclip_seed.py --json
bash scripts/paperclip_projection_apply.sh
```

当前默认部署结果：

- Paperclip 代码：`/home/paperclip/paperclip`
- Paperclip 数据：`/home/paperclip/paperclip-data`
- 内部 API：`http://127.0.0.1:3110`
- 公网 viewer：`http://110.41.170.155/paperclip/`（推荐，走 `nginx /paperclip/ + basic auth`）
- viewer 默认会注入中文汉化补丁，页面刷新后即可看到中文 UI
- viewer 凭据：`/root/.config/brain-secretary/paperclip-viewer.env`
- 本机桥接 env：`ops/paperclip.local.env`
- `qq-main` 子 agent 协同会自动投影到 Paperclip 父子 issue
- 这些投影 issue 默认是纯展示态，不会再次唤醒 Paperclip agent

如果后续要让 QQ / OpenClaw 调它，本机联调默认直接用 `local_trusted`：

```bash
export QQ_BOT_PAPERCLIP_ENABLED=true
export QQ_BOT_PAPERCLIP_API_BASE_URL=http://127.0.0.1:3110
export QQ_BOT_PAPERCLIP_COMPANY_ID=<company-id>
export QQ_BOT_PAPERCLIP_DEFAULT_ASSIGNEE_AGENT_ID=<agent-id>
```

然后你就可以：

```bash
python3 scripts/paperclip_cli.py status --json
python3 scripts/paperclip_cli.py agents --json
python3 scripts/paperclip_projection_daemon.py once --json
python3 scripts/paperclip_cli.py run --agent brain-secretary-dev --title "检查测试失败" --description "先跑测试再给建议" --json
```

---

## NapCat 多实例扫码示例（辅助测试）

这套路径不是现网入口，只用于你要的 3 个独立扫码 QQ 示例：

- 根目录：`/root/napcat-multi`
- NapCat 管理脚本：`scripts/napcat_multi.py`
- QQ Bridge 管理脚本：`scripts/qq_bot_multi.py`
- 映射关系：`brain -> qq-main`、`tech -> brain-secretary-dev`、`review -> brain-secretary-review`
- 对应桥接端口：`8011 / 8012 / 8013`

常用命令：

```bash
python3 scripts/qq_bot_multi.py bootstrap --json
python3 scripts/qq_bot_multi.py status --json
python3 scripts/napcat_multi.py qr --json
python3 scripts/napcat_multi.py stop
```


---

## Windows 本地三开 QQ（推荐）

如果云服务器扫码容易触发 QQ 风控，推荐改成：

- Windows 本地运行 `QQ + NapCat`
- 服务器运行 `QQ Bridge + OpenClaw`
- 通过 `Tailscale` 把两边接到同一内网

对应脚本与文档：

- Windows 一键入口：`scripts/windows_local_qq_quick_setup.bat`
- Windows 脚手架：`scripts/windows_local_qq_multi.ps1`
- Windows 自检脚本：`scripts/windows_local_qq_doctor.ps1`
- Windows 自检批处理：`scripts/windows_local_qq_doctor.bat`
- Windows 远程应用脚本：`scripts/windows_local_qq_remote_apply.ps1`
- 服务器桥接脚本：`scripts/qq_bot_multi.py`
- 详细说明：`docs/windows-local-qq-multi.md`
- 示例 profile：`ops/windows-local-qq-profile.example.json`

典型流程：

```bat
scripts\windows_local_qq_quick_setup.bat
```

或者手动执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_local_qq_multi.ps1 `
  -ServerBridgeHost <服务器 Tailscale IP>
```

Windows 脚本生成完 `server-bridge-profile.json` 后，在服务器执行：

```bash
python3 scripts/qq_bot_multi.py import-profile --profile ops/windows-local-qq-profile.json --json
python3 scripts/qq_bot_multi.py restart --json
```

生成目录里还会带上 `run-doctor.bat`，在你把 3 个本地 NapCat 配好后，双击它就能检查本机 `3001/3002/3003` 和服务器 `8011/8012/8013`。
如果你本机能 SSH 到服务器，双击输出目录里的 `apply-remote.bat` 就能自动上传 `profile` 并在服务器执行导入 / 重启 / 状态检查。

---

## Windows / 服务器项目双轨分支（推荐）

如果你本机 Windows 白天自己写代码，晚上又要让服务器上的 OpenClaw agent 跑检查 / 测试 / 改进，推荐改成：

- `main`：稳定分支
- `work/<project>`：你白天、本地 AI 的日常开发分支
- `agent/<project>`：晚上服务器 agent 的独立工作分支

相关文件：

- 文档：`docs/project-sync-branch-workflow.md`
- 双轨同步脚本：`scripts/project_sync.py`
- 双轨配置：`ops/project-sync.json`
- 自动进化配置：`ops/auto-evolve.json`（支持 `session_mode=fresh`，默认每轮 fresh session）
- 自动进化守护脚本：`scripts/project_auto_evolve_daemon.py`
- 自动进化安装脚本：`scripts/project_auto_evolve_apply.sh`
- 主分支保护脚本：`scripts/git_branch_guard.py`
- Windows 自动跟踪脚本：`scripts/windows_project_autosync.ps1`
- Windows 双击入口：`scripts/windows_project_autosync.bat`
- 示例配置：`ops/project-sync.example.json`

典型命令：

```bash
python3 scripts/project_sync.py prepare-work --config ops/project-sync.json --project multimodal-retrieval
python3 scripts/project_sync.py sync-work --config ops/project-sync.json --project multimodal-retrieval
python3 scripts/project_sync.py prepare-agent --config ops/project-sync.json --project multimodal-retrieval
python3 scripts/project_sync.py sync-agent --config ops/project-sync.json --project multimodal-retrieval
python3 scripts/project_sync.py review-agent --config ops/project-sync.json --project multimodal-retrieval
python3 scripts/project_sync.py promote-agent --config ops/project-sync.json --project multimodal-retrieval

如果你想让服务器上的 `auto-evolve-main` 24 小时自动给某个项目找活 / 改代码 / 验收下一轮，可以再启用：

```bash
python3 scripts/project_auto_evolve_daemon.py status --json
python3 scripts/project_auto_evolve_daemon.py doctor --json
python3 scripts/project_auto_evolve_daemon.py watchdog --json
python3 scripts/project_auto_evolve_daemon.py once --project tower-eye --dry-run --json
python3 scripts/project_auto_evolve_daemon.py once --project tower-eye --json
bash scripts/project_auto_evolve_apply.sh
```

`project_auto_evolve_apply.sh` 会自动补齐 / 校正 `auto-evolve-main`、校验 OpenClaw 配置并重启 gateway。
`doctor` 会一次汇总守护服务状态、`qq-main` 会话污染看门狗，以及零副作用 `dry-run` 预演，适合故障后先做自检。
守护现在自带 `qq-main` 主会话污染看门狗；如果检测到自动进化前缀重新占用 `qq-main` 主会话，会自动熔断跳过本轮。
`once --dry-run` 是零副作用预演，不会修改仓库或安装 hook。

当前现成示例已经为 `Tower-Eye` 配好：

- 仓库目录：`/root/projects/Tower-Eye`
- 稳定分支：`main`（受保护，不允许自动提交/推送）
- work 分支：`work/tower-eye`
- 夜间 agent 分支：`agent/tower-eye`
```

Windows 如果不想手动 pull，可直接跑：

```bat
scripts\windows_project_autosync.bat multimodal-retrieval 120
```

## Windows 手工启动（兼容保留）

### 1) 启动 OpenClaw

```powershell
openclaw gateway --port 18789
```

### 2) 安装并配置 `qqbot` 渠道

```powershell
openclaw plugins install @openclaw-china/qqbot
openclaw channels add --channel qqbot --token "<appid>:<clientSecret>"
openclaw config set channels.qqbot.markdownSupport false
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
- 当前插件来源：`@openclaw-china/qqbot`（npm）
- 脑 workspace：`/root/.openclaw/workspace`
- 主仓：`/root/brain-secretary`
- 运维脚本：`scripts/ops_manager.py`
- 运维真源：`ops/deployment_manifest.json`
- OpenClaw 配置文档：`docs/openclaw-setup.md`
- Linux 运维文档：`docs/systemd-ops.md`
- NapCat 多实例脚本：`scripts/napcat_multi.py`
- QQ Bridge 多实例脚本：`scripts/qq_bot_multi.py`
- Windows 本地一键入口：`scripts/windows_local_qq_quick_setup.bat`
- Windows 本地三开脚手架：`scripts/windows_local_qq_multi.ps1`
- Windows 本地自检脚本：`scripts/windows_local_qq_doctor.ps1`
- Windows 本地自检批处理：`scripts/windows_local_qq_doctor.bat`
- Windows 本地远程应用脚本：`scripts/windows_local_qq_remote_apply.ps1`
- 双轨分支同步脚本：`scripts/project_sync.py`
- Windows 项目自动跟踪脚本：`scripts/windows_project_autosync.ps1`
- Windows 项目自动跟踪批处理：`scripts/windows_project_autosync.bat`
- 双轨分支工作流文档：`docs/project-sync-branch-workflow.md`
- NapCat 多实例根目录：`/root/napcat-multi`
- QQ Bridge 多实例根目录：`/root/qq-bot-multi`
- Windows 本地三开文档：`docs/windows-local-qq-multi.md`
- 旧桥接代码：`qq-bot/`（历史实现，非现网入口）

---

## 退役说明

- `openclaw-qq-bridge.service`：已停用
- `napcat-qq.service`：已停用
- `/chat-history` 与 `/api/chat-history`：已退役，公网返回 `410`
