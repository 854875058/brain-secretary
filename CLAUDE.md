# CLAUDE.md

> 本文件给后续助手 / Claude / Codex / 自动化运维流程读取。
> 更新: 2026-03-07

---

## 运维规则

- 任何涉及本项目部署、启停、重启、状态检查、日志检查、端口检查的问题，**优先使用统一运维脚本**：`scripts/ops_manager.py`
- 统一运维脚本的数据真源是：`ops/deployment_manifest.json`
- 如果用户询问“当前怎么启动 / 怎么停止 / 端口是多少 / 模型是什么 / 关键脚本和数据在哪里”，优先先读：
  - `CLAUDE.md`
  - `HANDOVER.md`
  - `docs/systemd-ops.md`
  - `docs/openclaw-setup.md`
  - `ops/deployment_manifest.json`

---

## OpenClaw 多 Agent 规则

当前采用**方案 B：真正的多 agent 协同 + 协调大脑**。

### 当前 agent 拓扑

- `qq-main`：总协调大脑，workspace=`/root/.openclaw/workspace`
- `brain-secretary-dev`：主项目工程子 agent，workspace=`/root/brain-secretary`
- `agent-hub-dev`：次级项目工程子 agent，workspace=`/root/agent-hub`

### 当前 QQ 入口规则

- QQ 消息链路：`QQ -> NapCat -> qq-bot -> OpenClaw(qq-main)`
- `qq-bot/config.yaml` 中的 `openclaw.agent_id` 必须保持为 `qq-main`，除非明确重构入口架构
- 不要为了“省事”把 QQ 入口直接切到子 agent，那会破坏统一协调层

### 协调规则

- `qq-main` 负责：理解意图、拆任务、派任务、验收结果、统一回复
- `brain-secretary-dev` 负责主仓工程实施：QQ Bridge、OpenClaw 接入、运维脚本、部署文档、NapCat 联调
- `agent-hub-dev` 负责次级仓工程实施：旧机器人实现、对照方案、实验验证、迁移参照
- 如果任务跨两个仓库、涉及架构对比、迁移整合、多点核对，默认由 `qq-main` 并行调度两个子 agent

### OpenClaw 配置关键点

当前生效配置文件：`/root/.openclaw/openclaw.json`

关键设置包括：

- `qq-main.subagents.allowAgents = ["brain-secretary-dev", "agent-hub-dev"]`
- `tools.agentToAgent.enabled = true`
- `tools.sessions.visibility = "all"`
- `agents.defaults.subagents.*` 已配置并发、超时、归档等默认值
- `model-proxy.mjs` 必须透传 `messages` / `tools`，不能再删掉 tool calling 字段
- `model-proxy.env` 中不要再设置“忽略内部工具指令”之类的破坏性系统提示

---

## 当前约定

- Linux 当前部署方式：`systemd --user`
- Linux 当前 NapCat 快速登录账号：`2230906690`
- Linux 当前账号级 OneBot 配置文件：`/root/Napcat/opt/QQ/resources/app/app_launcher/napcat/config/onebot11_2230906690.json`
- Linux 当前 OpenClaw 配置文件：`/root/.openclaw/openclaw.json`
- Windows 约定部署方式：手工进程 / 脚本拉起
- 关键服务分组：
  - `frontend` = `napcat`
  - `backend` = Linux 下 `model_proxy + gateway + bridge`，Windows 下 `gateway + bridge`
  - `all` = 当前平台全部关键组件
- 不要优先手工 `kill` 进程；先尝试统一运维脚本
- 不要把密钥、token、私密配置直接写入文档

## GitHub 维护规则

- 推荐把 `/root/brain-secretary` 作为主 GitHub 仓库；`/root/agent-hub` 如需长期维护再单独建仓。
- 不要把 `/root/.openclaw`、`/root/Napcat`、`qq-bot/config.yaml`、`qq-bot/logs/`、运行态数据库、收件箱和虚拟环境提交到远端。
- 一次修改完成后，如果用户没有明确禁止，优先执行：`bash scripts/git_sync.sh -m "<简短提交说明>"`
- 自动推送开关使用仓库配置 `brain.autopush`；开启后 post-commit hook 会在本地提交后自动尝试推送 `origin`。
- 初次配置 Git 用户、远端和代理，优先执行：`bash scripts/git_bootstrap.sh`

---

## 当前关键文件

- 运维脚本：`scripts/ops_manager.py`
- 运维清单：`ops/deployment_manifest.json`
- 交接文档：`HANDOVER.md`
- Linux 运维文档：`docs/systemd-ops.md`
- OpenClaw 配置文档：`docs/openclaw-setup.md`
- 部署手册：`SETUP.md`
- QQ Bridge 配置：`qq-bot/config.yaml`
- 媒体验证素材：`qq-bot/data/openclaw-test-file.txt`、`qq-bot/data/openclaw-test-voice.wav`、`qq-bot/data/openclaw-test-video.mp4`
- 聊天记录页面：`http://110.41.170.155/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- 聊天记录 JSON：`http://110.41.170.155/api/chat-history?user_id=854875058&token=<qq-bot/config.yaml:web.history_token>`
- 聊天记录页现支持：任务清单、任务状态概览、日期筛选、任务筛选、子 Agent 协作筛选
- 任务清单现会自动吸收 qq-main → 子 Agent 完成回执，补充状态、验证与备注，且播种不会再覆盖后续真实进度
- OpenClaw 公网入口：`http://110.41.170.155/`
- OpenClaw 内部入口：`http://127.0.0.1:18789/`
- OpenClaw 配置：`/root/.openclaw/openclaw.json`
- Model Proxy 脚本：`/root/.openclaw/model-proxy.mjs`
- Model Proxy 环境：`/root/.openclaw/model-proxy.env`

---

## QQ 自助进化入口

- QQ 发文件能力已接入：`qq-bot` 支持处理 `[[send_file]] <文件URL或file://路径>`
- QQ 发语音能力已接入：`qq-bot` 支持处理 `[[send_voice]] <语音URL或file://路径>`，并转换为 NapCat OneBot `record` 段发送
- QQ 文本转语音能力已接入：`qq-bot` 支持处理 `[[send_tts]] 这里写文本`，桥接层会本地调用 `ffmpeg+flite` 生成 16k 单声道 WAV，再按 `record` 语音发送到 QQ
- QQ 多模态输入整理已接入：收到图片/文件/语音/视频时，会把可用的本地路径、文本摘录、OCR/元数据整理进 OpenClaw 提示词
- QQ 巡检入口已接入：支持 `/patrol` 和自然语言“巡检/自诊断/检查服务状态”等触发跨平台运维报告


- `qq-bot` 异步完成回推已增加游标保护，避免服务重启后把旧的子 agent 完成消息重复推回 QQ

- 显式命令：`/evolve ...`、`/remember ...`
- 自然语言触发：`记住这个`、`写进规则`、`别再犯`、`以后都按这个来`
- 触发后应优先把改进真正写入规则 / 记忆 / 文档，而不是只口头回复
- QQ 发图能力已经接入：`qq-bot` 支持处理 `[[send_image]] <图片URL或file://路径>`
- QQ 发视频能力已做最小接入：`qq-bot` 支持处理 `[[send_video]] <视频URL或file://路径>`，并转换为 NapCat OneBot `video` 段发送

## 统一入口

推荐命令：

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
python3 scripts/ops_manager.py restart backend
python3 scripts/ops_manager.py restart public_proxy
python3 scripts/ops_manager.py logs bridge -n 80
```

Windows 推荐：

```powershell
py -3 scripts\ops_manager.py info
py -3 scripts\ops_manager.py status all
py -3 scripts\ops_manager.py start all
```

---

## 变更纪律

如果你修改了以下内容：

- systemd unit
- Windows 启动命令
- OpenClaw / Bridge / NapCat 端口
- 模型配置
- agent id / workspace / 子 agent 拓扑
- 关键脚本与数据目录

必须同步更新：

- `CLAUDE.md`
- `HANDOVER.md`
- `SETUP.md`
- `docs/openclaw-setup.md`
- `docs/systemd-ops.md`
- `ops/deployment_manifest.json`

不要只改一处然后把其余文档留成旧状态。
