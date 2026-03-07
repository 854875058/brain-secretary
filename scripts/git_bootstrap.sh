#!/usr/bin/env bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

usage() {
  cat <<'EOF'
Usage:
  bash scripts/git_bootstrap.sh [options]

Options:
  --name <value>          Set git user.name
  --email <value>         Set git user.email
  --remote <value>        Add or update origin remote
  --proxy <value>         Set http.proxy and https.proxy
  --clear-proxy           Remove http.proxy and https.proxy
  --scope <local|global>  Config scope, default: local
  --auto-push <on|off>    Enable post-commit auto push, default: off
  -h, --help              Show this help

Examples:
  bash scripts/git_bootstrap.sh \
    --name "Your Name" \
    --email "you@example.com" \
    --remote "git@github.com:YOU/brain-secretary.git" \
    --auto-push on

  bash scripts/git_bootstrap.sh \
    --name "Your Name" \
    --email "you@example.com" \
    --remote "https://github.com/YOU/brain-secretary.git" \
    --proxy "http://127.0.0.1:7890"
EOF
}

scope="local"
name=""
email=""
remote_url=""
proxy_url=""
clear_proxy="false"
auto_push="off"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --name)
      name="${2:-}"
      shift 2
      ;;
    --email)
      email="${2:-}"
      shift 2
      ;;
    --remote)
      remote_url="${2:-}"
      shift 2
      ;;
    --proxy)
      proxy_url="${2:-}"
      shift 2
      ;;
    --clear-proxy)
      clear_proxy="true"
      shift
      ;;
    --scope)
      scope="${2:-}"
      shift 2
      ;;
    --auto-push)
      auto_push="${2:-}"
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

if [ "$scope" != "local" ] && [ "$scope" != "global" ]; then
  echo "--scope only supports local or global" >&2
  exit 1
fi

if [ "$auto_push" != "on" ] && [ "$auto_push" != "off" ]; then
  echo "--auto-push only supports on or off" >&2
  exit 1
fi

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git init -b main
else
  current_branch="$(git branch --show-current 2>/dev/null || true)"
  if [ -z "$current_branch" ]; then
    git symbolic-ref HEAD refs/heads/main >/dev/null 2>&1 || true
  fi
fi

git branch -M main >/dev/null 2>&1 || true
git config core.hooksPath .githooks

if [ "$scope" = "global" ]; then
  config_cmd=(git config --global)
else
  config_cmd=(git config)
fi

if [ -n "$name" ]; then
  "${config_cmd[@]}" user.name "$name"
fi

if [ -n "$email" ]; then
  "${config_cmd[@]}" user.email "$email"
fi

if [ -n "$proxy_url" ]; then
  "${config_cmd[@]}" http.proxy "$proxy_url"
  "${config_cmd[@]}" https.proxy "$proxy_url"
fi

if [ "$clear_proxy" = "true" ]; then
  "${config_cmd[@]}" --unset-all http.proxy >/dev/null 2>&1 || true
  "${config_cmd[@]}" --unset-all https.proxy >/dev/null 2>&1 || true
fi

if [ -n "$remote_url" ]; then
  if git remote get-url origin >/dev/null 2>&1; then
    git remote set-url origin "$remote_url"
  else
    git remote add origin "$remote_url"
  fi
fi

if [ "$auto_push" = "on" ]; then
  git config --bool brain.autopush true
else
  git config --bool brain.autopush false
fi

echo "Repository: $repo_root"
echo "Branch: $(git branch --show-current 2>/dev/null || echo main)"
echo "Hooks path: $(git config core.hooksPath)"
echo "Auto push: $(git config --bool --get brain.autopush || echo false)"

if git config user.name >/dev/null 2>&1; then
  echo "user.name: $(git config user.name)"
else
  echo "user.name: <unset>"
fi

if git config user.email >/dev/null 2>&1; then
  echo "user.email: $(git config user.email)"
else
  echo "user.email: <unset>"
fi

if git remote get-url origin >/dev/null 2>&1; then
  echo "origin: $(git remote get-url origin)"
else
  echo "origin: <unset>"
fi

if git config http.proxy >/dev/null 2>&1; then
  echo "http.proxy: $(git config http.proxy)"
fi

if git config https.proxy >/dev/null 2>&1; then
  echo "https.proxy: $(git config https.proxy)"
fi

if [ -z "$remote_url" ]; then
  echo "Tip: rerun with --remote to bind GitHub repository."
fi

if ! git config user.name >/dev/null 2>&1 || ! git config user.email >/dev/null 2>&1; then
  echo "Tip: set --name and --email before first commit."
fi
