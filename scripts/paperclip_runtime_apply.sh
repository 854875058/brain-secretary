#!/usr/bin/env bash
set -euo pipefail

PUBLIC_HOST="${PAPERCLIP_PUBLIC_HOST:-110.41.170.155}"
PUBLIC_PORT="${PAPERCLIP_PUBLIC_PORT:-3100}"
INTERNAL_HOST="${PAPERCLIP_INTERNAL_HOST:-127.0.0.1}"
INTERNAL_PORT="${PAPERCLIP_INTERNAL_PORT:-3110}"
RUNTIME_USER="${PAPERCLIP_RUNTIME_USER:-paperclip}"
RUNTIME_GROUP="${PAPERCLIP_RUNTIME_GROUP:-$RUNTIME_USER}"
RUNTIME_HOME="${PAPERCLIP_RUNTIME_HOME:-/home/$RUNTIME_USER}"
PAPERCLIP_DIR="${PAPERCLIP_DIR:-$RUNTIME_HOME/paperclip}"
PAPERCLIP_HOME_DIR="${PAPERCLIP_HOME_DIR:-$RUNTIME_HOME/paperclip-data}"
ENV_FILE="${PAPERCLIP_ENV_FILE:-$PAPERCLIP_DIR/.env.local}"
SYSTEMD_UNIT_PATH="${PAPERCLIP_SYSTEMD_UNIT_PATH:-/etc/systemd/system/paperclip.service}"
NGINX_CONF_PATH="${PAPERCLIP_NGINX_CONF_PATH:-/etc/nginx/sites-available/paperclip-public.conf}"
NGINX_ENABLED_PATH="${PAPERCLIP_NGINX_ENABLED_PATH:-/etc/nginx/sites-enabled/paperclip-public.conf}"
VIEWER_ENV_FILE="${PAPERCLIP_VIEWER_ENV_FILE:-/root/.config/brain-secretary/paperclip-viewer.env}"
HTPASSWD_PATH="${PAPERCLIP_HTPASSWD_PATH:-/etc/nginx/.paperclip_htpasswd}"
VIEWER_USER="${PAPERCLIP_VIEWER_USER:-paperclip}"
VIEWER_PASSWORD="${PAPERCLIP_VIEWER_PASSWORD:-}"
PAPERCLIP_PUBLIC_URL="${PAPERCLIP_PUBLIC_URL:-http://$PUBLIC_HOST:$PUBLIC_PORT}"

if ! id -u "$RUNTIME_USER" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$RUNTIME_USER"
fi

if [ -z "$VIEWER_PASSWORD" ]; then
  VIEWER_PASSWORD="$(python3 - <<'PY2'
import secrets
print(secrets.token_urlsafe(18))
PY2
)"
fi

mkdir -p "$(dirname "$VIEWER_ENV_FILE")"
install -d -o "$RUNTIME_USER" -g "$RUNTIME_GROUP" "$RUNTIME_HOME" "$PAPERCLIP_DIR" "$PAPERCLIP_HOME_DIR"

python3 - "$ENV_FILE" "$INTERNAL_HOST" "$INTERNAL_PORT" "$PAPERCLIP_PUBLIC_URL" "$PAPERCLIP_HOME_DIR" <<'PY2'
from pathlib import Path
import sys
path = Path(sys.argv[1])
internal_host = sys.argv[2]
internal_port = sys.argv[3]
public_url = sys.argv[4]
paperclip_home = sys.argv[5]
existing = {}
if path.exists():
    for line in path.read_text(encoding='utf-8').splitlines():
        raw = line.strip()
        if not raw or raw.startswith('#') or '=' not in raw:
            continue
        key, value = raw.split('=', 1)
        existing[key.strip()] = value.strip()
for key, value in {
    'HOST': internal_host,
    'PORT': internal_port,
    'PAPERCLIP_HOME': paperclip_home,
    'PAPERCLIP_PUBLIC_URL': public_url,
    'PAPERCLIP_DEPLOYMENT_MODE': 'local_trusted',
    'PAPERCLIP_DEPLOYMENT_EXPOSURE': 'private',
}.items():
    existing[key] = value
ordered = [
    'HOST', 'PORT', 'PAPERCLIP_HOME', 'PAPERCLIP_PUBLIC_URL',
    'PAPERCLIP_DEPLOYMENT_MODE', 'PAPERCLIP_DEPLOYMENT_EXPOSURE', 'BETTER_AUTH_SECRET'
]
lines = []
for key in ordered:
    value = existing.get(key)
    if value is not None and str(value).strip() != '':
        lines.append(f'{key}={value}')
for key in sorted(existing):
    if key in ordered:
        continue
    value = existing.get(key)
    if value is not None and str(value).strip() != '':
        lines.append(f'{key}={value}')
path.write_text('
'.join(lines) + '
', encoding='utf-8')
PY2

python3 - "$PAPERCLIP_DIR" "$RUNTIME_USER" "$RUNTIME_GROUP" <<'PY2'
from pathlib import Path
import io
import json
import os
import pwd
import grp
import shutil
import sys
import tarfile
import tempfile
import urllib.request

paperclip_dir = Path(sys.argv[1])
runtime_user = sys.argv[2]
runtime_group = sys.argv[3]
server_pkg = paperclip_dir / 'server' / 'package.json'
if not server_pkg.exists():
    raise SystemExit(f'missing server package.json: {server_pkg}')
version = json.loads(server_pkg.read_text(encoding='utf-8')).get('version') or '0.2.7'
url = f'https://registry.npmjs.org/@paperclipai/server/-/server-{version}.tgz'
req = urllib.request.Request(url, headers={'User-Agent': 'brain-secretary-paperclip/1.0'})
with urllib.request.urlopen(req, timeout=60) as resp:
    payload = resp.read()
with tempfile.TemporaryDirectory(prefix='paperclip-ui-dist-') as tmp:
    tmp_path = Path(tmp)
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:gz') as tar:
        tar.extractall(tmp_path)
    src = tmp_path / 'package' / 'ui-dist'
    if not (src / 'index.html').exists():
        raise SystemExit(f'ui-dist missing in tarball: {src}')
    dst = paperclip_dir / 'server' / 'ui-dist'
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)
    uid = pwd.getpwnam(runtime_user).pw_uid
    gid = grp.getgrnam(runtime_group).gr_gid
    for root, dirs, files in os.walk(dst):
        os.chown(root, uid, gid)
        for name in dirs:
            os.chown(os.path.join(root, name), uid, gid)
        for name in files:
            os.chown(os.path.join(root, name), uid, gid)
PY2

cat > "$VIEWER_ENV_FILE" <<EOF
PAPERCLIP_VIEWER_URL=$PAPERCLIP_PUBLIC_URL
PAPERCLIP_VIEWER_USER=$VIEWER_USER
PAPERCLIP_VIEWER_PASSWORD=$VIEWER_PASSWORD
PAPERCLIP_INTERNAL_URL=http://$INTERNAL_HOST:$INTERNAL_PORT
EOF
chmod 600 "$VIEWER_ENV_FILE"

HASHED_PASSWORD="$(printf %s "$VIEWER_PASSWORD" | openssl passwd -apr1 -stdin)"
printf '%s:%s
' "$VIEWER_USER" "$HASHED_PASSWORD" > "$HTPASSWD_PATH"
chgrp www-data "$HTPASSWD_PATH"
chmod 640 "$HTPASSWD_PATH"

cat > "$SYSTEMD_UNIT_PATH" <<EOF
[Unit]
Description=Paperclip Service
After=network.target

[Service]
Type=simple
User=$RUNTIME_USER
Group=$RUNTIME_GROUP
WorkingDirectory=$PAPERCLIP_DIR
Environment=HOME=$RUNTIME_HOME
Environment=PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/usr/bin/bash -lc 'set -a && source "$ENV_FILE" && set +a && exec node server/node_modules/tsx/dist/cli.mjs server/src/index.ts'
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > "$NGINX_CONF_PATH" <<EOF
server {
    listen $PUBLIC_PORT;
    listen [::]:$PUBLIC_PORT;
    server_name $PUBLIC_HOST _;

    client_max_body_size 20m;
    proxy_read_timeout 600s;
    proxy_send_timeout 600s;

    auth_basic "Paperclip Viewer";
    auth_basic_user_file $HTPASSWD_PATH;

    location / {
        proxy_pass http://$INTERNAL_HOST:$INTERNAL_PORT;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
EOF
ln -sf "$NGINX_CONF_PATH" "$NGINX_ENABLED_PATH"

systemctl --user disable --now paperclip.service >/dev/null 2>&1 || true
rm -f "$HOME/.config/systemd/user/paperclip.service"

chown -R "$RUNTIME_USER:$RUNTIME_GROUP" "$PAPERCLIP_DIR" "$PAPERCLIP_HOME_DIR"

systemctl daemon-reload
systemctl enable --now paperclip.service
nginx -t
systemctl reload nginx

sleep 2
curl -fsS "http://$INTERNAL_HOST:$INTERNAL_PORT/api/health" >/dev/null
curl -fsS -u "$VIEWER_USER:$VIEWER_PASSWORD" "http://127.0.0.1:$PUBLIC_PORT/api/health" >/dev/null

echo "[OK] Paperclip runtime applied"
echo "- runtime user: $RUNTIME_USER"
echo "- repo:    $PAPERCLIP_DIR"
echo "- home:    $PAPERCLIP_HOME_DIR"
echo "- internal: http://$INTERNAL_HOST:$INTERNAL_PORT"
echo "- public:   $PAPERCLIP_PUBLIC_URL"
echo "- viewer env: $VIEWER_ENV_FILE"
