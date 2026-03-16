# MEMORY.md - 项目长期记忆（Brain Secretary）

> 说明：这里存放“长期稳定”的事实、约定、关键决策。
> 需要更细粒度内容时放到 `memory/*.md`。
> 更新：2026-03-16

## 项目基本信息

- 项目名：Brain Secretary（大脑秘书系统）
- 当前 Windows 工作区：`E:\AI数据集项目\brain-secretary\`
- Linux 现网主仓：`/root/brain-secretary`
- 创建日期：2026-03-06

## 当前稳定事实（2026-03-16）

- 现网主 QQ 入口已经切换到 OpenClaw 原生 `qqbot` 渠道，当前主链路是：`qqbot/default -> qq-main`
- 当前采用真实多 agent 协同，而不是单 agent 伪分工：
  - `qq-main`：总协调大脑
  - `auto-evolve-main`：自动进化专用内部协调 agent
  - `brain-secretary-dev`：工程实施子 agent
  - `brain-secretary-review`：方案 / 验收子 agent
- `auto-evolve-main` 只给守护脚本和定时自动进化使用，不承接 QQ 主入口流量
- `qq-bot/` 不再是现网主入口；当前定位是历史实现参考 + 辅助多 QQ 桥接层
- Paperclip 现在位于 `QQ/OpenClaw` 后方，承担协同投影和任务控制面，不替代 `qqbot/default -> qq-main`
- Linux 当前推荐部署方式是：`systemd --user(OpenClaw + projection + auto-evolve)` + `systemd(Paperclip)` + `nginx`
- 运维统一入口是 `scripts/ops_manager.py`，运维真源是 `ops/deployment_manifest.json`

## 关键决策

### 2026-03-06

- 必须迁移到 OpenClaw 可用：因为不借助 OpenClaw 容易出问题，尤其缺少稳定记忆和上下文。
- 先保证“可用”和“可运维”，再逐步抽象大脑、子 agent 和辅助系统。

### 2026-03-10 到 2026-03-11

- 默认主模型切到 `penguin/claude-sonnet-4-6`，不再默认走 `gpt-5.1`，原因是上游 distributor 多次返回 `503 No available channel for model gpt-5.1`
- 现网主入口正式收敛到 OpenClaw 原生 `qqbot` 渠道
- 自动进化主脑独立为 `auto-evolve-main`，避免占用 `qq-main` 主会话
- `qq-main` / `auto-evolve-main` 的子 agent 协同过程统一投影到 Paperclip 父子 issue

## 文档真源

- 总规则与接手须知：`CLAUDE.md`
- 当前运行状态与交接：`HANDOVER.md`
- 运维真源：`ops/deployment_manifest.json`
- Linux 运维：`docs/systemd-ops.md`
- OpenClaw 配置与 agent/渠道约束：`docs/openclaw-setup.md`
- 部署手册：`SETUP.md`
- 项目定位与仓库映射：`ops/project_registry.json`
- 长期工作画像与用户偏好：`OPERATING_PROFILE.md`

## 项目定位约定

- 命中 `ops/project_registry.json` 的项目时，优先从注册表定位仓库、路径和分支，不要先追问用户
- 用户口中的“铁塔 / 铁塔项目 / 铁塔多模态检索”默认指：`https://github.com/854875058/Tower-Eye`
- `Tower-Eye` 当前双轨约定：
  - 稳定分支：`main`
  - 白天工作分支：`work/tower-eye`
  - 夜间 agent 分支：`agent/tower-eye`
- 自动进化默认只准在 `agent/tower-eye` 上找活、改动、验收、提交，不能直接改 `main`
- 对缺依赖、缺测试工具、仓库未克隆、路径可自动定位这类可恢复阻塞，默认由内部技术链路自行补齐，不先甩回给用户

## 工作闭环约定

- 修复 / 恢复类任务默认先直接动手，再自验证，再汇报
- 没有验证过的动作和结果，不能当成“已完成”对外表述
- 如果用户提到部署、端口、服务名、agent id、workspace、模型、QQ 渠道绑定，优先以 `CLAUDE.md`、`HANDOVER.md`、`docs/systemd-ops.md`、`docs/openclaw-setup.md`、`ops/deployment_manifest.json` 为准
