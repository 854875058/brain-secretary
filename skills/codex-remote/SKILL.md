---
name: codex-remote
description: 当用户要远程控制服务器上的 Codex CLI、查看或驱动 tmux 里的 `codex` 会话、向 Codex 发送任务、读取 Codex 输出、批准 Codex 继续、停止 Codex、查看 Codex 当前做到哪一步时使用。适用于“让 Codex 看下/改下/跑下”“查看 Codex 现在状态”“给 Codex 发一句话”“帮我替 Codex 回车/发 y”等请求。
---

# 远程控制 Codex

## 适用 agent

- 优先给具备终端/执行能力的工程 agent 使用，例如：`brain-secretary-dev`
- 不要指望 `qq-main` 直接在本地终端里控制 tmux；`qq-main` 更适合做路由与汇总，再委派给工程 agent

## 目标会话

- 默认 tmux session：`codex`
- 默认仓库目录：`/root/brain-secretary`
- 先复用现有 `codex` 会话；不存在时再创建：

```bash
tmux has-session -t codex 2>/dev/null || tmux new-session -d -s codex "cd /root/brain-secretary && codex"
```

## 标准流程

1. 先抓当前屏幕，确认 Codex 在做什么：

```bash
tmux capture-pane -t codex -p | tail -n 120
```

2. 读取当前 pane 路径，确认是不是在目标仓库：

```bash
tmux display-message -p -t codex '#{pane_current_path}'
```

3. 根据状态决定动作：
- 如果 Codex 正在等待输入 / 确认，再发送最小必要输入
- 如果 Codex 停在提示符，可以直接发送任务
- 如果当前路径不是 `/root/brain-secretary`，先明确告知用户偏差，再决定是否切换目录或新建会话

4. 发送文本时分两步，避免粘贴或多行异常：

```bash
tmux send-keys -t codex -l -- "请在 /root/brain-secretary 中处理 ..."
sleep 0.1
tmux send-keys -t codex Enter
```

5. 发完等待 2-5 秒，再抓输出：

```bash
sleep 3
tmux capture-pane -t codex -p | tail -n 120
```

## 常用动作

### 查看当前状态

```bash
tmux capture-pane -t codex -p | tail -n 120
```

### 查看当前目录

```bash
tmux display-message -p -t codex '#{pane_current_path}'
```

### 给 Codex 发送任务

```bash
tmux send-keys -t codex -l -- "<任务文本>"
sleep 0.1
tmux send-keys -t codex Enter
```

### 给 Codex 回车 / 确认

```bash
tmux send-keys -t codex Enter
tmux send-keys -t codex y Enter
tmux send-keys -t codex n Enter
```

### 中断当前任务

```bash
tmux send-keys -t codex C-c
```

## 安全边界

- 涉及 `rm`、`git push`、重启服务、覆盖配置、批量修改等破坏性操作时，不要替用户擅自确认；先复述并确认意图。
- 如果用户只是想“看下 Codex 做到哪了”，只抓输出和总结，不要额外发送新任务。
- 如果 Codex 已经在执行任务，不要叠加第二个复杂任务；先看当前任务是否结束或先中断。

## 回复风格

- 先说明准备发送给 Codex 的动作
- 然后汇报：Codex 当前状态 / 当前目录 / 已发送内容 / 最新输出 / 下一步建议
- 需要用户拍板时，明确说“是否继续发 y / 是否中断 / 是否改发新任务”
