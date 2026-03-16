# 文档索引

> 目录：`docs/`
> 更新：2026-03-16
> 说明：这里收纳运行手册、概念说明、历史兼容资料和归档文档。顶层只保留最关键的总览与接手文件。

---

## 建议阅读顺序

### 接手和现网真源

1. `../CLAUDE.md`
2. `../HANDOVER.md`
3. `../ops/deployment_manifest.json`
4. `systemd-ops.md`
5. `openclaw-setup.md`
6. `../SETUP.md`

### 系统总览

- `../README.md`
- `../ARCHITECTURE.md`
- `../REQUIREMENTS.md`

---

## 文档分层

### 运行与部署

- `systemd-ops.md`：Linux 现网运维
- `openclaw-setup.md`：OpenClaw agent / 渠道 / Paperclip 约束
- `paperclip-qq-bridge.md`：Paperclip 相关接入
- `windows-local-qq-multi.md`：Windows 本地多 QQ 方案
- `project-sync-branch-workflow.md`：双轨分支与自动进化协作
- `github-workflow.md`：Git 和自动提交约定
- `napcat-setup.md`：NapCat 相关说明

### 概念说明

- `concepts/brain.md`：当前大脑角色与边界
- `concepts/agents.md`：当前子 agent 角色与协作边界

### 历史兼容

- `legacy/qq-bridge.md`：旧桥接链路与辅助入口背景说明
- `../qq-bot/README.md`：辅助桥接层实现说明

### 归档资料

- `archive/`：已归档专题文档
- `presentations/`：展示和分享材料

---

## 顶层文件为什么还保留

以下文件仍然放在仓库顶层，是因为它们承担“总入口 / 工作区兼容入口 / 接手真源”的角色：

- `README.md`
- `CLAUDE.md`
- `HANDOVER.md`
- `SETUP.md`
- `ARCHITECTURE.md`
- `REQUIREMENTS.md`
- `OPERATING_PROFILE.md`
- `MEMORY.md`
- `SOUL.md`
- `IDENTITY.md`

如果要判断仓库结构，不要把本地工作区生成文件和历史兼容目录当成正式主线。
