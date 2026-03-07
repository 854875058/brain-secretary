# Windows 本地项目 / 服务器 Agent 共享分支协作

> 文档: `docs/project-sync-branch-workflow.md`
> 更新: 2026-03-08

---

## 目标

当你的 **Windows 本地项目** 和 **服务器上的 OpenClaw agent** 都会改同一个仓库时，最稳的做法不是互相传压缩包，而是：

- 同一个远端仓库
- 同一个共享分支
- 双方都遵守“先拉后改、改完就推”的节奏

推荐分支命名：

- `sync/<project-name>`

例如：

- `sync/ragflow-ui`
- `sync/data-cleaner`
- `sync/brain-secretary-local`

---

## 为什么我建议共享分支

优点：

- 服务器 agent 改的代码，你 Windows 本地能立刻 `pull`
- 你本地改完再 `push`，服务器 agent 下次就能看到
- 所有改动都有 Git 历史，冲突也可追踪
- 最适合“人 + 本地 AI + 服务器 agent”一起改项目

风险：

- 双方同时改同一文件，还是会冲突
- 所以必须形成固定节奏：**开始前先 sync，结束后立刻 sync**

---

## 仓库里已经给你的工具

- 共享分支同步脚本：`scripts/project_sync.py`
- 示例配置：`ops/project-sync.example.json`

它支持：

- `status`：看每个项目当前分支、脏区、ahead/behind
- `prepare`：自动切到共享分支，不存在就创建
- `sync`：先拉、可选自动提交、再推送

---

## 配置方法

先复制一份配置：

```bash
cp ops/project-sync.example.json ops/project-sync.json
```

Windows 上把 `path` 改成你的本地项目路径；服务器上把 `path` 改成服务器对应仓库路径。

示例：

```json
{
  "projects": [
    {
      "name": "my-app",
      "path": "E:/work/my-app",
      "remote": "origin",
      "branch": "sync/my-app",
      "pull_rebase": true
    }
  ]
}
```

服务器可以是：

```json
{
  "projects": [
    {
      "name": "my-app",
      "path": "/root/projects/my-app",
      "remote": "origin",
      "branch": "sync/my-app",
      "pull_rebase": true
    }
  ]
}
```

关键点是：

- `name` 一样不一样都行，**最重要的是 branch 一样**
- Windows 和服务器都指向同一个远端仓库
- Windows 和服务器都跑 `sync/my-app`

---

## 推荐操作节奏

### Windows 本地开始工作前

```bash
python3 scripts/project_sync.py sync --config ops/project-sync.json --project my-app
```

### Windows 本地改完后

```bash
python3 scripts/project_sync.py sync \
  --config ops/project-sync.json \
  --project my-app \
  --commit "feat: 本地完成 XX 修改"
```

### 服务器 agent 开工前

先同步：

```bash
python3 scripts/project_sync.py sync --config ops/project-sync.json --project my-app
```

### 服务器 agent 改完后

```bash
python3 scripts/project_sync.py sync \
  --config ops/project-sync.json \
  --project my-app \
  --commit "fix: 服务器 agent 修复 XX 问题"
```

---

## 第一次准备

如果共享分支还没建好，先执行：

```bash
python3 scripts/project_sync.py prepare --config ops/project-sync.json --project my-app
```

再看状态：

```bash
python3 scripts/project_sync.py status --config ops/project-sync.json --project my-app
```

---

## 我对你这套协作方式的建议

最推荐的模式是：

- `main`：稳定分支
- `sync/<project>`：你、本地 AI、服务器 agent 的协同工作分支
- 稳定后再把 `sync/<project>` 合回 `main`

这样做比所有人都直接改 `main` 稳得多。

---

## 和 OpenClaw 的关系

如果服务器上的 OpenClaw agent workspace 指向这个项目仓库，那么：

- 它 `sync` 完之后看到的是最新代码
- 它提交/推送之后，你本地 `sync` 就能拿到

所以你原来想的“维护一个共同 Git 分支”，**我觉得是对的，而且是当前最靠谱的方案**。
