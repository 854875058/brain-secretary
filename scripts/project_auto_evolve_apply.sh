#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_NAME="openclaw-project-auto-evolve.service"
SRC_UNIT="$ROOT/ops/systemd/$UNIT_NAME"
DST_DIR="$HOME/.config/systemd/user"
DST_UNIT="$DST_DIR/$UNIT_NAME"

mkdir -p "$DST_DIR"
install -m 0644 "$SRC_UNIT" "$DST_UNIT"

systemctl --user daemon-reload
systemctl --user enable --now "$UNIT_NAME"
systemctl --user status "$UNIT_NAME" --no-pager -n 40 || true
