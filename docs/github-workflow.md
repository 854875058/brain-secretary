# GitHub 维护工作流

> 文档: `docs/github-workflow.md`
> 更新: 2026-03-07

---

## 推荐边界

当前最适合作为主 GitHub 仓库的是：`/root/brain-secretary`

原因：

- 这里已经包含主项目代码、部署文档、运维脚本和 QQ Bridge
- `/root/.openclaw` 属于运行时配置和大脑工作区，不适合直接整体入库
- `/root/Napcat` 属于 QQ 客户端运行环境，也不适合整体入库
- 当前只维护 `/root/brain-secretary` 这一套主仓代码。

---

## 已准备好的仓库能力

本仓库已经补好以下 Git 维护能力：

- `.gitignore`：默认排除日志、数据库、收件箱、虚拟环境、IDE 文件和本地配置
- `scripts/git_bootstrap.sh`：初始化 Git、设置账号、远端、代理、hook 和自动推送开关
- `scripts/git_sync.sh`：一条命令完成暂存并提交
- `.githooks/post-commit`：当 `brain.autopush=true` 时，提交后自动尝试推送到 `origin`

---

## 一次性初始化

### 方案 A：SSH 直连 GitHub

```bash
cd /root/brain-secretary
bash scripts/git_bootstrap.sh \
  --name "你的 Git 名称" \
  --email "你的 Git 邮箱" \
  --remote "git@github.com:你的账号/brain-secretary.git" \
  --auto-push on
```

如果你还没有 SSH key，可先执行：

```bash
ssh-keygen -t ed25519 -C "你的 Git 邮箱"
cat ~/.ssh/id_ed25519.pub
```

把公钥加到 GitHub 账户后，再测试：

```bash
ssh -T git@github.com
```

### 方案 B：HTTPS + 代理

如果你当前网络访问 GitHub 需要代理，优先使用 HTTPS：

```bash
cd /root/brain-secretary
bash scripts/git_bootstrap.sh \
  --name "你的 Git 名称" \
  --email "你的 Git 邮箱" \
  --remote "https://github.com/你的账号/brain-secretary.git" \
  --proxy "http://127.0.0.1:7890" \
  --auto-push on
```

如果之后不再需要代理，可清理：

```bash
cd /root/brain-secretary
bash scripts/git_bootstrap.sh --clear-proxy
```

---

## 第一次提交与推送

完成初始化后，执行：

```bash
cd /root/brain-secretary
bash scripts/git_sync.sh -m "chore: 初始化仓库并导入当前代码"
```

如果已经打开 `--auto-push on`，post-commit hook 会自动推送；否则你可以手工执行：

```bash
git push -u origin main
```

---

## 共享分支联动（Windows 本地项目 <-> 服务器 agent）

如果你本机 Windows 和服务器上的 OpenClaw agent 都会改同一个项目，最推荐的方式是维护一个共同的 `sync/<project>` 分支。

仓库里已经补了：

- 文档：`docs/project-sync-branch-workflow.md`
- 脚本：`scripts/project_sync.py`
- 示例配置：`ops/project-sync.example.json`

典型流程：

```bash
python3 scripts/project_sync.py prepare --config ops/project-sync.json --project my-app
python3 scripts/project_sync.py sync --config ops/project-sync.json --project my-app
python3 scripts/project_sync.py sync --config ops/project-sync.json --project my-app --commit "feat: 完成一次联动修改"
```

## AI 自动提交约定

提交说明建议统一使用中文，直接说明“这次提交改了什么”，推荐格式：`类型: 中文概述本次修改内容`。

例如：`fix: 修复 QQ Bot 请求超时后的连接复用问题`。

后续让 AI 修改代码时，可以直接要求它遵循这条规则：

```text
改完后自动执行 bash scripts/git_sync.sh -m "<类型: 中文说明本次修改内容>"
```

仓库里的 `AGENTS.md`、`CLAUDE.md`、`AI_AUTOCOMMIT.md` 等文件都已经补了这条约定，方便后续助手读取并执行。

只要同时满足下面 3 个条件，就会接近“改完自动提交并推送”：

1. Git 仓库已初始化
2. `user.name` / `user.email` 已配置
3. `brain.autopush=true` 且 `origin` 可正常认证

---

## 不建议入库的内容

以下内容建议继续保持本地：

- `/root/.openclaw/**`
- `/root/Napcat/**`
- `qq-bot/config.yaml`
- `qq-bot/logs/**`
- `qq-bot/data/inbox/**`
- `qq-bot/data/tasks.db`
- 各类虚拟环境、缓存目录、IDE 状态文件

如果后续需要把配置模板公开，建议新增脱敏示例文件，例如 `qq-bot/config.example.yaml`，而不是直接提交现网配置。
