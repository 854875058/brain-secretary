#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="openclaw-project-auto-evolve.service"
SRC_UNIT="$ROOT/ops/systemd/$UNIT_NAME"
DST_DIR="$HOME/.config/systemd/user"
DST_UNIT="$DST_DIR/$UNIT_NAME"

python3 "$ROOT/scripts/reconcile_auto_evolve_agent.py" --json
openclaw config validate
python3 "$ROOT/scripts/ops_manager.py" restart gateway

mkdir -p "$DST_DIR"
install -m 0644 "$SRC_UNIT" "$DST_UNIT"

systemctl --user daemon-reload
systemctl --user enable "$UNIT_NAME"
systemctl --user restart "$UNIT_NAME"
systemctl --user status "$UNIT_NAME" --no-pager -n 40 || true
