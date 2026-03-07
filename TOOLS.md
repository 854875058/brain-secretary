# TOOLS.md

## 常用路径

- 统一运维脚本：`scripts/ops_manager.py`
- 运维清单：`ops/deployment_manifest.json`
- QQ Bridge 配置：`qq-bot/config.yaml`
- QQ Bridge 入口：`qq-bot/main.py`
- OpenClaw 配置文档：`docs/openclaw-setup.md`
- systemd 运维文档：`docs/systemd-ops.md`

## 常用命令

```bash
python3 scripts/ops_manager.py info
python3 scripts/ops_manager.py status all
python3 scripts/ops_manager.py restart backend
python3 scripts/ops_manager.py logs bridge -n 80
```

## 当前线上链路

`QQ -> NapCat -> qq-bot -> OpenClaw(qq-main)`

## 当前关键端口

- OpenClaw：`80`
- QQ Bridge：`8000`
- NapCat HTTP API：`3000`
- NapCat WebUI：`6099`
