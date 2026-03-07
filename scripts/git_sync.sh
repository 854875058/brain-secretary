#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/git_sync.sh [-m "类型: 中文说明本次修改内容"]

Examples:
  bash scripts/git_sync.sh -m "feat: 新增 QQ Bridge 健康检查"
  bash scripts/git_sync.sh -m "docs: 更新部署说明文档"
USAGE
}

message=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    -m|--message)
      message="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Git repository not initialized. Run bash scripts/git_bootstrap.sh first." >&2
  exit 1
fi

if ! git config user.name >/dev/null 2>&1 || ! git config user.email >/dev/null 2>&1; then
  echo "git user.name or user.email is not configured. Run bash scripts/git_bootstrap.sh first." >&2
  exit 1
fi

git add -A

if git diff --cached --quiet; then
  echo "No changes to commit."
  exit 0
fi

if [ -z "$message" ]; then
  message="chore: 同步本次修改 $(date '+%Y-%m-%d %H:%M:%S')"
fi

if ! python3 - "$message" <<'PY'
import sys
text = sys.argv[1].strip()

def is_cjk(ch: str) -> bool:
    code = ord(ch)
    return (
        0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0x20000 <= code <= 0x2A6DF
        or 0x2A700 <= code <= 0x2B73F
        or 0x2B740 <= code <= 0x2B81F
        or 0x2B820 <= code <= 0x2CEAF
        or 0x2CEB0 <= code <= 0x2EBEF
        or 0x30000 <= code <= 0x3134F
    )

sys.exit(0 if any(is_cjk(ch) for ch in text) else 1)
PY
then
  echo "Commit message must include a Chinese summary of what changed, e.g. 'fix: 修复 qq-bot 路径问题'." >&2
  exit 1
fi

git commit -m "$message"
echo "Commit created."
