# AI 自动提交规则

> 更新: 2026-03-07

这个仓库默认要求 AI 在完成修改后自动提交 Git；如果远端已配置且 `brain.autopush=true`，提交后会自动尝试推送。

## 默认规则

- 只在 `/root/brain-secretary` 内改动。
- 不提交 `/root/.openclaw/**`、本地密钥、运行态数据库、日志、收件箱、虚拟环境和现网私密配置。
- 完成代码、脚本、文档或配置修改后，如果用户没有明确禁止，必须执行：

```bash
bash scripts/git_sync.sh -m "<简短提交说明>"
```

- 如果不确定提交说明，可直接省略 `-m`，脚本会生成默认说明：

```bash
bash scripts/git_sync.sh
```

## 推荐提交说明

- `feat: ...` 新功能
- `fix: ...` 缺陷修复
- `docs: ...` 文档更新
- `refactor: ...` 重构
- `ops: ...` 运维或部署调整
- `chore: ...` 杂项维护

## 首次检查

开始工作前可快速确认：

```bash
git status --short --branch
git config --bool --get brain.autopush
git remote -v
```

## 结束检查

完成提交后可快速确认：

```bash
git log --oneline -n 1
git status --short --branch
```
