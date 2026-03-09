#!/usr/bin/env bash
set -euo pipefail

RUNTIME_USER="${PAPERCLIP_RUNTIME_USER:-paperclip}"
RUNTIME_GROUP="${PAPERCLIP_RUNTIME_GROUP:-$RUNTIME_USER}"
RUNTIME_HOME="${PAPERCLIP_RUNTIME_HOME:-/home/$RUNTIME_USER}"
TARGET_DIR="${PAPERCLIP_DIR:-$RUNTIME_HOME/paperclip}"
REPO_URL="${PAPERCLIP_REPO_URL:-https://github.com/paperclipai/paperclip.git}"
PAPERCLIP_HOME_DIR="${PAPERCLIP_HOME_DIR:-$RUNTIME_HOME/paperclip-data}"
ENV_FILE="${PAPERCLIP_ENV_FILE:-$TARGET_DIR/.env.local}"

if ! id -u "$RUNTIME_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$RUNTIME_USER"
fi

install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" "$RUNTIME_HOME"
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

mkdir -p "$PAPERCLIP_HOME_DIR"
if [ ! -f "$ENV_FILE" ]; then
  BETTER_AUTH_SECRET="$(python3 - <<'PY2'
import secrets
print(secrets.token_hex(32))
PY2
)"
  cat > "$ENV_FILE" <<EOF
HOST=127.0.0.1
PORT=3110
PAPERCLIP_HOME=$PAPERCLIP_HOME_DIR
PAPERCLIP_PUBLIC_URL=http://127.0.0.1:3110
PAPERCLIP_DEPLOYMENT_MODE=local_trusted
PAPERCLIP_DEPLOYMENT_EXPOSURE=private
BETTER_AUTH_SECRET=$BETTER_AUTH_SECRET
EOF
  echo "[INFO] generated $ENV_FILE"
else
  echo "[INFO] keeping existing env file: $ENV_FILE"
fi

chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$TARGET_DIR" "$PAPERCLIP_HOME_DIR"

cat <<EOF
[OK] Paperclip bootstrap complete.
- repo: $TARGET_DIR
- env:  $ENV_FILE
- home: $PAPERCLIP_HOME_DIR
- next: bash scripts/paperclip_runtime_apply.sh
- seed: python3 scripts/paperclip_seed.py --json
EOF
