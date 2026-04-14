<div align="center">

# Brain Secretary

**大脑秘书 — AI 多智能体编排助手**

*Multi-agent orchestration system powered by QQ messaging and OpenClaw framework*

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![OpenClaw](https://img.shields.io/badge/OpenClaw-Multi_Agent-FF4500)](https://openclaw.dev/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet_4.6-D97757?logo=anthropic)](https://anthropic.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

---

## Overview

传统 AI 助手只能单轮对话，无法处理需要多步骤协作的复杂任务。当任务涉及代码编写、审查验收、部署运维时，单一 Agent 力不从心。

Brain Secretary 通过 **QQ 消息入口** + **OpenClaw 多智能体编排** 构建了完整的任务协作系统。用户在 QQ 私聊中发送自然语言指令，系统自动理解意图、分解任务、派发给专业子 Agent 执行，最终将结果汇总回 QQ。支持 **24 小时自动演进守护**，项目在无人值守时持续自我优化。

```
┌─────────────────────────────────────────────────────────────┐
│                     QQ Private Chat                          │
├─────────────────────────────────────────────────────────────┤
│              OpenClaw Orchestration (qq-main)                 │
├──────────────┬──────────────────┬────────────────────────────┤
│  Dev Agent   │  Review Agent    │  Auto-Evolve Daemon        │
│  代码开发     │  审查验收         │  24h 自动演进               │
├──────────────┴──────────────────┴────────────────────────────┤
│         Paperclip (Task Control Plane) + Git + DB            │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### Multi-Agent Orchestration
基于 OpenClaw 框架的真实多智能体协作（非角色扮演模拟）。`qq-main` 作为总协调器理解意图、分解任务，`brain-secretary-dev` 负责代码开发，`brain-secretary-review` 负责审查验收。

### QQ Native Integration
通过 OpenClaw 原生 `qqbot` 通道接收 QQ 消息，无需额外 HTTP 桥接。支持私聊指令、任务状态查询、执行结果推送。

### Auto-Evolution Daemon
24 小时自动演进守护进程，在无人值守时持续分析项目状态、发现改进点、自动提交优化。双分支工作流（`work/` 人工分支 + `agent/` AI 分支）确保安全隔离。

### Paperclip Task Control Plane
集成 Paperclip 任务管理平台，自动投射多 Agent 协作过程为可视化任务流。支持任务追踪、进度查看、协作回放。

### Unified Operations Management
统一运维管理脚本 `ops_manager.py`，一键管理所有服务的启停、状态查看、日志查询。配合 systemd 实现生产级服务管理。

### Knowledge & Memory
内置私有知识库与聊天记录管理，Agent 可检索历史对话与项目文档，实现上下文连续的长期协作。

## Tech Stack

```
Entry Layer                       Orchestration                    Infrastructure
─────────────────                 ─────────────────               ─────────────────
QQ (OpenClaw qqbot)               OpenClaw Framework               Linux + systemd
NapCat (Auxiliary)                Claude Sonnet 4.6 (LLM)         nginx (Reverse Proxy)
                                  GPT-5.1 (Fallback)              SQLite (aiosqlite)

Application                       Operations
─────────────────                 ─────────────────
FastAPI + Uvicorn                 Paperclip (Task UI)
APScheduler (Cron)                Git Auto-Sync
httpx (HTTP Client)               Dual-Branch Workflow
```

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        QQ Private Chat                            │
│                    (User sends natural language)                   │
├──────────────────────────────────────────────────────────────────┤
│                   OpenClaw qqbot/default Channel                   │
├──────────────────────────────────────────────────────────────────┤
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              qq-main (Primary Coordinator)                   │  │
│  │  Intent Understanding → Task Decomposition → Dispatch        │  │
│  └──────┬──────────────────────┬───────────────────┬───────────┘  │
│         │                      │                   │               │
│  ┌──────▼──────┐  ┌───────────▼────────┐  ┌──────▼───────────┐  │
│  │ Dev Agent   │  │  Review Agent      │  │ Auto-Evolve      │  │
│  │ 代码开发     │  │  审查验收           │  │ 24h 自动演进      │  │
│  └──────┬──────┘  └───────────┬────────┘  └──────┬───────────┘  │
│         └──────────────────────┴──────────────────┘               │
│                              │                                     │
├──────────────────────────────┼─────────────────────────────────────┤
│  ┌───────────┐  ┌────────────▼──┐  ┌───────────┐  ┌───────────┐  │
│  │ Paperclip │  │  Git Repos    │  │  SQLite   │  │  systemd  │  │
│  │ (Task UI) │  │  (Code Store) │  │  (State)  │  │ (Service) │  │
│  └───────────┘  └───────────────┘  └───────────┘  └───────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone
git clone https://github.com/854875058/brain-secretary.git
cd brain-secretary

# 2. Install dependencies
cd qq-bot && pip install -r requirements.txt && cd ..

# 3. Configure
cp qq-bot/config.example.yaml qq-bot/config.yaml
# Edit config.yaml: set QQ account, OpenClaw API, LLM keys

# 4. Start (Linux production)
python scripts/ops_manager.py start all

# Or start QQ bot directly
cd qq-bot && python main.py
```

## Project Structure

```
brain-secretary/
├── qq-bot/                          # QQ Bot application
│   ├── main.py                      # FastAPI entry point
│   ├── bot/
│   │   ├── agent_team.py            # Multi-agent state machine
│   │   ├── openclaw_client.py       # OpenClaw API client
│   │   ├── paperclip_client.py      # Paperclip integration
│   │   ├── private_kb.py            # Private knowledge base
│   │   ├── chat_history.py          # Chat history management
│   │   ├── task_db.py               # Task database
│   │   └── memory_center.py         # Memory management
│   ├── config.yaml                  # Runtime configuration
│   └── requirements.txt             # Python dependencies
├── scripts/                         # Operations scripts
│   ├── ops_manager.py               # Unified service management
│   ├── git_sync.sh                  # Git auto-sync
│   └── paperclip_projection_daemon.py
├── ops/                             # Deployment configuration
│   ├── deployment_manifest.json     # Deployment truth source
│   ├── auto-evolve.json             # Auto-evolution config
│   └── systemd/                     # systemd unit files
├── docs/                            # Documentation
├── ARCHITECTURE.md                  # System architecture
├── CLAUDE.md                        # AI collaboration rules
└── HANDOVER.md                      # Handover documentation
```

## Usage

| Command | Description |
|---------|-------------|
| `python scripts/ops_manager.py start all` | 启动所有服务 |
| `python scripts/ops_manager.py stop all` | 停止所有服务 |
| `python scripts/ops_manager.py status` | 查看服务状态 |
| `python qq-bot/main.py` | 单独启动 QQ Bot |
| `python scripts/git_sync.sh` | 手动触发 Git 同步 |

### QQ Commands

| 指令 | 功能 |
|------|------|
| 自然语言任务描述 | 自动理解意图并派发 Agent 执行 |
| `状态` / `status` | 查看当前任务执行状态 |
| `日志` / `logs` | 查看最近操作日志 |

## License

MIT
