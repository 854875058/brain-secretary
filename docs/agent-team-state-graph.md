# AgentTeam 状态图架构

> 更新：2026-03-16
> 目标：给当前仓库补上一套可复用的 state graph 多 Agent 协调骨架，而不是继续堆散落脚本。

---

## 新增内容

本次新增了两层核心能力：

- `qq-bot/bot/private_kb.py`
  - 私有知识库统一入口
  - 默认接入 `MEMORY.md`、`memory/*.md`、`ops/project_registry.json`
  - 支持从桥接层记忆账本检索并向长期记忆回写
- `qq-bot/bot/agent_team.py`
  - `TeamState` 状态总线
  - `Research -> Execute -> Review` 状态图节点
  - review 打回 execution 的闭环路由
  - 节点级 session 隔离
  - OpenClaw 节点和 mock 节点的统一调用方式

另外补了：

- `scripts/agent_team_demo.py`：本地 demo 入口
- `tests/test_agent_team.py`：隔离单测

---

## 这套骨架解决了什么

### 1. 状态管理统一

以前仓库里有会话、记忆、任务、自动进化状态，但没有统一的“多 Agent 流水线状态总线”。
现在 `TeamState` 统一持有：

- 原始需求
- 私有知识库检索结果
- 中间步骤
- 最终结果
- 当前状态
- review 打回次数
- 附加元数据

### 2. 私有知识库不再只是一堆 Markdown

以前记忆系统已经能存，但“如何在 agent team 里统一检索”没有标准入口。
现在 `CombinedPrivateKnowledgeBase` 会同时检索：

- 桥接层记忆账本
- `MEMORY.md`
- `memory/*.md`
- `ops/project_registry.json`

后续如果真要上 ChromaDB / FAISS，只需要继续实现新的 `KnowledgeSource`。

### 3. 多 Agent 协作不再靠人工拼 prompt

现在 coordinator 明确按状态流转：

```text
researching -> coding -> reviewing -> done
                      \-> coding (review 打回时)
```

这样做的价值：

- 不会无限乱跳
- 每一步都有记录
- review 可以回路，但有次数上限
- 每个节点都有独立 session 命名空间

---

## 默认节点分工

- `需求架构师`
  - 检索私有知识库
  - 提炼规则和计划
- `执行工程师`
  - 结合研究结果和反馈产出交付物
- `验收复核员`
  - 判断是否通过
  - 必要时打回执行节点
  - 可把通过后的长期规则写回记忆中心

---

## 怎么跑

### 1. 跑 mock demo

```bash
python scripts/agent_team_demo.py --mode mock --json
```

### 2. 走 OpenClaw 真节点

```bash
python scripts/agent_team_demo.py --mode openclaw --context "请把这份 PDF 财务报表转成 Markdown 并提取关键指标"
```

---

## 适合下一步塞进去的业务逻辑

优先推荐这几类最脏、最吃隐性规则的流程：

1. PDF / Word / 报表转结构化 Markdown 或 JSON
2. 项目仓库诊断 -> 修复 -> 验收闭环
3. QQ 运维巡检 -> 故障定位 -> 修复建议 -> 结果回推
4. 多模态输入处理时的本地规则注入

这些任务都有一个共同点：不是“单次问答”，而是“要带状态、带知识、带验收回路”的流水线。
