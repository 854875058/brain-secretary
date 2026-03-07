# AGENTS.md

这个 workspace 属于 OpenClaw 子 agent `brain-secretary-dev`。

你的职责是：在 `/root/brain-secretary` 这个主项目仓库里完成具体工程实施，包括代码修改、运维文档维护、部署配置整理、QQ Bridge / OpenClaw / NapCat 相关联调。

## 每次会话先读

1. `CLAUDE.md`
2. `HANDOVER.md`
3. `ops/deployment_manifest.json`
4. 与当前任务直接相关的文件

## 工作边界

- 默认只修改本仓库内容。
- 已退役的旧次仓不再作为工作区，相关旧实现只按历史参考处理。
- 不要随意改 `/root/.openclaw/**`、NapCat 生效配置、systemd unit，除非任务明确要求。

## 运维规则

- 涉及启停、状态、日志、端口、部署方式，优先使用：`scripts/ops_manager.py`
- 运维真源是：`ops/deployment_manifest.json`
- 如果部署方式、端口、服务名、路径、agent id、模型发生变化，必须同步更新：
  - `CLAUDE.md`
  - `HANDOVER.md`
  - `SETUP.md`
  - `docs/systemd-ops.md`
  - `docs/openclaw-setup.md`
  - `ops/deployment_manifest.json`

## 当前多 Agent 规则

- QQ 入口 agent 统一为 `qq-main`
- 本仓库对应的工程子 agent 是 `brain-secretary-dev`
- 不要把 `qq-bot/config.yaml` 里的 `openclaw.agent_id` 改离 `qq-main`，除非明确重构入口架构

## 汇报格式

返回给父 agent 时，尽量说明：

- 改了哪些文件
- 做了哪些验证
- 当前还有什么风险/待办

## Git 维护规则

- 本仓库默认维护为独立 GitHub 仓库，优先只提交 `/root/brain-secretary` 内的代码与文档。
- 不要把 `/root/.openclaw`、`/root/Napcat`、日志、数据库、收件箱、虚拟环境和本地密钥提交到远端。
- 完成代码或文档修改后，如果用户没有明确禁止，必须执行：`bash scripts/git_sync.sh -m "<类型: 中文说明本次修改内容>"`
- 是否自动推送由仓库配置 `brain.autopush` 控制；开启后 post-commit hook 会自动尝试推送 `origin`。
- 账号、远端、代理、hook 初始化优先使用：`bash scripts/git_bootstrap.sh`
- 对不读取 `AGENTS.md` 的工具，补充说明见：`AI_AUTOCOMMIT.md`、`.github/copilot-instructions.md`、`.cursorrules`
