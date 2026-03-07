# Copilot Instructions

When you modify files in this repository, treat Git submission as part of the task.

- Work inside `/root/brain-secretary` only unless the user explicitly expands scope.
- Do not commit runtime state, secrets, local databases, logs, inbox files, virtualenvs, or `/root/.openclaw/**`.
- After finishing code or documentation changes, and unless the user explicitly says not to, run:

```bash
bash scripts/git_sync.sh -m "<type: 中文说明本次修改内容>"
```

- Use a Chinese summary for what changed in this commit; if you are unsure, `bash scripts/git_sync.sh` is acceptable and will generate a Chinese default message.
- This repository may auto-push after commit when `brain.autopush=true`.
