#!/usr/bin/env bash
set -euo pipefail

TARGET_DIR="${PAPERCLIP_DIR:-/root/paperclip}"
REPO_URL="${PAPERCLIP_REPO_URL:-https://github.com/paperclipai/paperclip.git}"
DEFAULT_HOME="${PAPERCLIP_HOME_DIR:-/root/paperclip-data}"
ENV_FILE="${PAPERCLIP_ENV_FILE:-$TARGET_DIR/.env.local}"

mkdir -p "$(dirname "$TARGET_DIR")"
if [ ! -d "$TARGET_DIR/.git" ]; then
  echo "[INFO] cloning Paperclip into $TARGET_DIR"
  git clone --depth=1 "$REPO_URL" "$TARGET_DIR"
else
  echo "[INFO] updating Paperclip in $TARGET_DIR"
  git -C "$TARGET_DIR" fetch --depth=1 origin --prune
  DEFAULT_BRANCH="$(git -C "$TARGET_DIR" symbolic-ref refs/remotes/origin/HEAD --short | sed 's#^origin/##')"
  if [ -z "$DEFAULT_BRANCH" ]; then
    DEFAULT_BRANCH=master
  fi
  git -C "$TARGET_DIR" reset --hard "origin/$DEFAULT_BRANCH"
fi

cd "$TARGET_DIR"
echo "[INFO] installing dependencies via corepack pnpm"
if ! corepack pnpm install --frozen-lockfile; then
  echo "[WARN] frozen lockfile install failed, retrying with --no-frozen-lockfile"
  corepack pnpm install --no-frozen-lockfile
fi

mkdir -p "$DEFAULT_HOME"
if [ ! -f "$ENV_FILE" ]; then
  BETTER_AUTH_SECRET="$(python3 - <<'PY'
import secrets
print(secrets.token_hex(32))
PY
)"
  cat > "$ENV_FILE" <<EOF
HOST=127.0.0.1
PORT=3100
PAPERCLIP_HOME=$DEFAULT_HOME
PAPERCLIP_PUBLIC_URL=http://127.0.0.1:3100
PAPERCLIP_DEPLOYMENT_MODE=local_trusted
PAPERCLIP_DEPLOYMENT_EXPOSURE=private
BETTER_AUTH_SECRET=$BETTER_AUTH_SECRET
EOF
  echo "[INFO] generated $ENV_FILE"
else
  echo "[INFO] keeping existing env file: $ENV_FILE"
fi

cat <<EOF
[OK] Paperclip bootstrap complete.
- repo: $TARGET_DIR
- env:  $ENV_FILE
- run:  cd $TARGET_DIR && set -a && source $ENV_FILE && set +a && corepack pnpm dev:once
EOF
