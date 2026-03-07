#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/git_sync.sh [-m "commit message"]

Examples:
  bash scripts/git_sync.sh -m "feat: add QQ bridge health check"
  bash scripts/git_sync.sh -m "docs: refresh deployment notes"
EOF
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
  message="chore: sync updates $(date '+%Y-%m-%d %H:%M:%S')"
fi

git commit -m "$message"
echo "Commit created."
