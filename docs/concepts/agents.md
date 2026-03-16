# 子 Agent 模块

> 原位置：`agents/README.md`
> 更新：2026-03-16
> 状态：角色说明文档，不代表当前仓库里存在一套独立 agent 服务源码

---

## 当前已落地的子 agent

当前真实参与协作的子 agent 只有两类：

| agent id | 角色 | workspace | 当前职责 |
|---|---|---|---|
| `brain-secretary-dev` | 工程实施子 agent | `/root/brain-secretary` | 代码修改、联调排障、部署配置、文档维护 |
| `brain-secretary-review` | 方案 / 验收子 agent | `/root/brain-secretary` | 第二意见、风险提醒、验收复核 |

它们都由 OpenClaw 调度，不是这个目录下的独立二进制或单独服务。

---

## 当前协作方式

主协作链路是：

```text
qq-main -> brain-secretary-dev / brain-secretary-review -> qq-main
```

自动进化链路是：

```text
auto-evolve-main -> brain-secretary-dev / brain-secretary-review
```

协作约束：

- `qq-main` 负责总协调，不直接退化为子 agent
- `brain-secretary-dev` 负责实施和验证
- `brain-secretary-review` 负责复核和第二意见
- 只要发生子 agent 协作，过程就会被投影到 Paperclip

---

## 本文档和早期规划的关系

仓库早期设想过把不同任务封装成更细粒度 agent，例如：

- dataset-agent
- crawler-agent
- doc-agent
- ragflow-agent

这些设想目前仍可作为未来扩展方向，但不是当前现网 agent 拓扑。

当前判断 agent 结构时，优先以：

1. `../../CLAUDE.md`
2. `../../HANDOVER.md`
3. `../openclaw-setup.md`
4. `../../ops/deployment_manifest.json`

为准。
