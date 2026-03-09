# Windows 本地项目 / 服务器 Agent 双轨分支协作

> 文档: `docs/project-sync-branch-workflow.md`
> 更新: 2026-03-08

---

## 目标

你这个场景里，**不适合**让服务器 agent 和你白天本地开发都直接改同一个工作分支。

更稳的方式是：

- `main`：稳定分支
- `work/<project>`：你白天、本地 AI 的日常开发分支
- `agent/<project>`：晚上服务器上的大脑 / 方案 / 技术 agent 的单独工作分支
- 如果要做 24 小时自动进化，守护进程也只允许在 `agent/<project>` 工作，不能直接碰 `main`

推荐命名示例：

- `main`
- `work/multimodal-retrieval`
- `agent/multimodal-retrieval`

---

## 为什么要双轨

你的实际需求是两种完全不同的动作：

### 白天

- 你本人在 Windows 本地写代码
- 你会自己提交 commit
- 你希望本地代码能自动收到远端更新

### 晚上

- 让服务器上的 agent 拉最新项目
- 检查项目问题
- 跑测试 / 跑命令 / 给改进建议
- 必要时直接改代码并提交

这两类动作混在同一个工作分支里，很容易互相打架。

所以更稳的结构就是：

- **你的代码进 `work/<project>`**
- **agent 的改动进 `agent/<project>`**
- **你第二天再决定要不要把 agent 的改动吸收到 `work/<project>`**
- **确认稳定后，再从 `work/<project>` 合到 `main`**

---

## 现在仓库里已经给你的工具

- 双轨同步脚本：`scripts/project_sync.py`
- Windows 自动跟踪脚本：`scripts/windows_project_autosync.ps1`
- Windows 双击入口：`scripts/windows_project_autosync.bat`
- 示例配置：`ops/project-sync.example.json`
- 现网示例配置：`ops/project-sync.json`
- 自动进化配置：`ops/auto-evolve.json`

`project_sync.py` 现在支持这些动作：

- `status`
- `prepare-work`
- `update-work`
- `sync-work`
- `prepare-agent`
- `sync-agent`
- `review-agent`
- `promote-agent`

兼容旧命令：

- `prepare` = `prepare-work`
- `sync` = `sync-work`

---

## 配置方法

先复制配置：

```bash
cp ops/project-sync.example.json ops/project-sync.json
```

然后把项目改成你的真实仓库路径。

Windows 示例：

```json
{
  "projects": [
    {
      "name": "multimodal-retrieval",
      "path": "E:/work/multimodal-retrieval",
      "remote": "origin",
      "stable_branch": "main",
      "work_branch": "work/multimodal-retrieval",
      "agent_branch": "agent/multimodal-retrieval",
      "pull_rebase": true
    }
  ]
}
```

服务器示例：

```json
{
  "projects": [
    {
      "name": "multimodal-retrieval",
      "path": "/root/projects/multimodal-retrieval",
      "remote": "origin",
      "stable_branch": "main",
      "work_branch": "work/multimodal-retrieval",
      "agent_branch": "agent/multimodal-retrieval",
      "pull_rebase": true
    }
  ]
}
```

关键点：

- Windows 和服务器都指向同一个远端仓库
- Windows 和服务器都认识同一组分支名
- 你白天只动 `work/<project>`
- agent 晚上只动 `agent/<project>`

---

## 白天怎么做

### 第一次准备你的工作分支

```bash
python3 scripts/project_sync.py prepare-work --config ops/project-sync.json --project multimodal-retrieval
```

### 平时本地开发

你一直在 `work/multimodal-retrieval` 上写代码。

改完后同步：

```bash
python3 scripts/project_sync.py sync-work \
  --config ops/project-sync.json \
  --project multimodal-retrieval \
  --commit "feat: 白天完成一轮本地开发"
```

---

## 白天不想手动拉怎么办

这个就是你刚才说的重点：**不应该每次都手动 pull。**

Windows 本地可以直接跑自动跟踪：

```bat
scripts\windows_project_autosync.bat multimodal-retrieval 120
```

或者：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/windows_project_autosync.ps1 `
  -Project multimodal-retrieval `
  -IntervalSeconds 120
```

它底层会执行：

```bash
python3 scripts/project_sync.py update-work --config ops/project-sync.json --project multimodal-retrieval
```

行为是：

- 如果当前就在 `work/<project>` 且工作区干净：自动拉最新远端改动
- 如果当前就在 `work/<project>` 但你还有未提交改动：**跳过，不覆盖你的现场**
- 如果你当前在别的分支且工作区不干净：会直接报错，防止误切分支

所以这已经比“自己手动 pull”聪明很多了。

---

## 晚上 agent 怎么做

### 1) 先准备 agent 分支

在服务器项目仓库里：

```bash
python3 scripts/project_sync.py prepare-agent --config ops/project-sync.json --project multimodal-retrieval
```

这个动作会做几件事：

- 先同步 `work/multimodal-retrieval`
- 再切到 `agent/multimodal-retrieval`
- 如果 agent 分支不存在，就从 work 分支创建
- 如果 agent 分支存在，就拉远端并把最新 work 分支并进来

### 2) 让 agent 干活

如果你不想手工每晚触发，也可以直接开守护：

```bash
python3 scripts/project_auto_evolve_daemon.py once --project tower-eye --json
bash scripts/project_auto_evolve_apply.sh
```

它会自动：

- 先准备 `work/<project>` 和 `agent/<project>`
- 确保主分支（如 `main`）被保护，不允许自动提交/推送
- 驱动 `qq-main` 自己找活、派技术号、拉验收号、自动返工
- 最终只把改动落到 `agent/<project>`

### 2) 让 agent 干活

接下来你的大脑 / 技术 / 方案 agent 就在 `agent/multimodal-retrieval` 里跑：

- 查问题
- 跑测试
- 跑脚本
- 做改进
- 写 commit

### 3) agent 改完后同步

```bash
python3 scripts/project_sync.py sync-agent \
  --config ops/project-sync.json \
  --project multimodal-retrieval \
  --commit "fix: 夜间 agent 修复一轮多模态检索问题"
```

这一步只会推到：

- `agent/multimodal-retrieval`

不会碰你的 `work/multimodal-retrieval`。

---

## 第二天怎么看 agent 改了什么

直接执行：

```bash
python3 scripts/project_sync.py review-agent --config ops/project-sync.json --project multimodal-retrieval
python3 scripts/project_sync.py promote-agent --config ops/project-sync.json --project multimodal-retrieval
```

它会给你：

- `agent` 相对 `work` 的独有 commits
- `work` 相对 `agent` 的独有 commits
- diff stat

你也可以直接在 GitHub 上看：

- `work/multimodal-retrieval...agent/multimodal-retrieval`

---

## 第二天怎么吸收 agent 的成果

最推荐：**你先 review，再手动决定怎么合并**。

如果你确认 agent 分支这轮改动没问题，可以直接用一条命令把它合回 `work/<project>`：

```bash
python3 scripts/project_sync.py promote-agent \
  --config ops/project-sync.json \
  --project multimodal-retrieval
```

如果 `work/<project>` 在 review 后你又继续写了新代码，`promote-agent` 也可能像普通 Git merge 一样产生冲突；这时按正常冲突解决流程处理即可。

如果你想自己手工合并，也可以：

```bash
git checkout work/multimodal-retrieval
git merge --no-ff agent/multimodal-retrieval
```

然后再同步：

```bash
python3 scripts/project_sync.py sync-work \
  --config ops/project-sync.json \
  --project multimodal-retrieval \
  --commit "merge: 吸收夜间 agent 的改进结果"
```

最后等这一阶段稳定，再把：

- `work/multimodal-retrieval -> main`

---

## 推荐节奏

### 白天开始工作前

```bash
python3 scripts/project_sync.py prepare-work --config ops/project-sync.json --project multimodal-retrieval
```

### 白天开发过程中

- 自动跟踪脚本一直跑
- 你自己正常写代码、commit

### 白天下班前

```bash
python3 scripts/project_sync.py sync-work \
  --config ops/project-sync.json \
  --project multimodal-retrieval \
  --commit "feat: 白天收工前同步工作分支"
```

### 晚上 agent 开工前

```bash
python3 scripts/project_sync.py prepare-agent --config ops/project-sync.json --project multimodal-retrieval
```

### 晚上 agent 收工后

```bash
python3 scripts/project_sync.py sync-agent \
  --config ops/project-sync.json \
  --project multimodal-retrieval \
  --commit "fix: 夜间 agent 完成一轮排查与改进"
```

### 第二天早上 review

```bash
python3 scripts/project_sync.py review-agent --config ops/project-sync.json --project multimodal-retrieval
```

---

## 你这套模式的本质

一句话概括：

- `main` = 稳定线
- `work/<project>` = 你白天的正式开发线
- `agent/<project>` = 晚上 agent 的独立试验 / 巡检 / 改进线

这样你就不会再遇到：

- 白天本地代码和晚上服务器代码互相覆盖
- agent 直接改坏你的工作分支
- 第二天一上班还得自己手动猜哪里该 pull

这就是最适合你当前模式的结构。
