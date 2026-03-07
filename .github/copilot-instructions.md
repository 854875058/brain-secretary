# Copilot Instructions

When you modify files in this repository, treat Git submission as part of the task.

- Work inside `/root/brain-secretary` only unless the user explicitly expands scope.
- Do not commit runtime state, secrets, local databases, logs, inbox files, virtualenvs, or `/root/.openclaw/**`.
- After finishing code or documentation changes, and unless the user explicitly says not to, run:

```bash
bash scripts/git_sync.sh -m "<short commit message>"
```

- If you are unsure about the message, `bash scripts/git_sync.sh` is acceptable.
- This repository may auto-push after commit when `brain.autopush=true`.
