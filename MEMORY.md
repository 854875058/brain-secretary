# MEMORY.md - 项目长期记忆（Brain Secretary）

> 说明：这里存放“长期稳定”的事实、约定、关键决策。  
> 需要更细粒度内容时放到 `memory/*.md`。

## 项目基本信息

- 项目名：Brain Secretary（大脑秘书系统）
- 仓库目录：`E:\朗驰\软研院\AI数据集项目开发\测试文件夹\brain-secretary\`
- 创建日期：2026-03-06

## 关键决策（2026-03-06）

- 必须迁移到 OpenClaw 可用：因为不借助 OpenClaw 容易出问题（尤其缺少记忆/上下文）。
- 阶段性实现策略：先用本地 QQ Bridge（FastAPI）把 NapCat 事件转发到 `openclaw agent`，保证立刻可用；后续再考虑 NapCat → OpenClaw 原生渠道/插件化直连。
- 当前 Linux 实际部署方式已定为：**root 用户级 `systemd` 常驻**，统一管理 `openclaw-gateway`、`openclaw-model-proxy`、`openclaw-qq-bridge`、`napcat-qq` 四类关键进程。
- 当前维护入口约定：先看 `HANDOVER.md`，再看 `docs/systemd-ops.md`；不要再以旧的“前台 shell 挂进程”方式作为默认运维方法。

## 文档真源

- 需求真源：`REQUIREMENTS.md`
- 架构说明：`ARCHITECTURE.md`
- 部署手册：`SETUP.md`
- 交接文档：`HANDOVER.md`
- 运维真源：`docs/systemd-ops.md`
