# 需求文档（Brain Secretary）

> 创建：2026-03-06  
> 维护者：你 + 本仓库协作的 AI（Codex / OpenClaw）  
> 目标：把需求“写死”，避免口口相传导致跑偏

---

## 1. 项目目标（What）

把 QQ 私聊/群聊里的自然语言指令，交给 **OpenClaw 上运行的“大脑”**去理解、记忆、分发与验收，然后把结果再通过 QQ 回复给你。

你关心的是：**稳定、可持续迭代、具备记忆与任务闭环**，而不是一次性脚本。

---

## 2. 现状与问题（Why）

### 2.1 现状

- 仓库里目前存在一个可用的旧版 `qq-bot/`：NapCat → FastAPI →（直接调用中转 API / 或跑 `claude` CLI）→ NapCat 回复。
- `brain/`、`agents/` 目前只有规划文档，尚未落地可运行的大脑/子 Agent。

### 2.2 你明确提出的问题（2026-03-06）

- **不借助 OpenClaw 容易出问题**：核心是“没有记忆功能”等，导致工作很不稳定。
- 你的决定：**现在就迁移到 OpenClaw 可用**，以 OpenClaw 作为大脑与记忆/会话承载。

---

## 3. 关键需求（Must Have）

### 3.1 使用 OpenClaw 作为“大脑”

- QQ 的所有核心交互（对话、任务理解、任务执行/分发、总结汇报）默认都应走 OpenClaw，而不是直接请求第三方 Chat Completions。
- 系统需要能在“同一会话”里持续对话：**有上下文、有连续性**。

### 3.2 记忆能力

至少两层：

1. **会话记忆**：同一个 QQ 私聊/群聊对话，需要对应到 OpenClaw 的 `session-id`，保证多轮对话连续。
2. **项目记忆**：需要有“长期可检索”的项目记忆（如：路径、约定、偏好、待办、关键决策），建议落在工作区的 `MEMORY.md` / `memory/*.md`（供 OpenClaw memory 工具检索）。

### 3.3 需求文档长期维护

- 本文件 `REQUIREMENTS.md` 作为“需求真源（source of truth）”
- 任何新增要求/变更，都要追加记录（含日期、原因、影响）

---

## 4. 非功能需求（Should Have）

- **可观测性**：日志清晰（至少：接收到的事件、路由结果、OpenClaw 调用耗时/错误）
- **安全边界**：默认只响应管理员 QQ（或白名单），避免 bot 被陌生人诱导执行危险任务
- **可恢复性**：OpenClaw 不可用时要有明确提示，而不是“无响应”
- **可扩展性**：后续可以把同级目录（PDF-Excel、ragflow 等）封装成子 Agent

---

## 5. 当前实现策略（How，阶段性决定）

> 这是“立刻可用优先”的阶段策略，后续可替换为更纯粹的 NapCat → OpenClaw 直连渠道（若能实现）。

- **短期（现在）**：保留一个轻量 QQ Bridge 服务（FastAPI），负责：
  - 接收 NapCat OneBot 11 事件
  - 为每个 QQ 会话生成稳定的 OpenClaw `session-id`
  - 通过 `openclaw agent ... --session-id ... --json` 调用 OpenClaw
  - 把 OpenClaw 的回复再发回 QQ
- **中期**：把“子 Agent”逐步抽成独立服务/进程，Brain（OpenClaw）负责分发与验收
- **长期**：如果 OpenClaw 能直接接 OneBot/QQ（插件/渠道），移除中间桥接层

---

## 6. 约定（Conventions）

- 语言：中文
- 风格：直接给结论，少废话（除非你要求解释）
- 任务闭环：每个任务要有“开始 / 进行中 / 结果 / 验收结论”

---

## 7. Backlog（待办列表）

### P0（立即）
- [ ] QQ → OpenClaw 调用链路跑通（私聊、群聊@）
- [ ] 会话 `session-id` 设计并固化
- [ ] 补齐 OpenClaw 工作区 bootstrap 文件：`SOUL.md`、`IDENTITY.md`、`OPERATING_PROFILE.md`、`MEMORY.md`

### P1（很快）
- [ ] 大脑路由：把不同类型任务分发到子 Agent（至少“项目修复/转换/爬虫/RAG”四类）
- [ ] 验收测试框架：每类任务都有合格标准
- [ ] 管理命令：查看最近任务 / 重置会话 / 查看 OpenClaw 状态

### P2（以后）
- [ ] NapCat → OpenClaw 原生渠道/插件（移除桥接层）
- [ ] 多 Agent 并行与互斥策略
- [ ] 任务历史与产物持久化（SQLite / JSON / 统一工件目录）

