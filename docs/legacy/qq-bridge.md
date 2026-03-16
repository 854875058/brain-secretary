# QQ 接入层

> 原位置：`qq-bridge/README.md`
> 更新：2026-03-16
> 状态：历史演进说明文档

---

## 当前结论

当前现网主 QQ 入口已经不是旧桥接链路，而是 OpenClaw 原生 `qqbot` 渠道：

```text
QQ Bot (qqbot/default) -> OpenClaw(qq-main) -> 子 agents
```

因此，这份文档更适合被理解为：

- 早期 QQ 接入方案说明
- 历史桥接层背景资料
- 辅助多 QQ 入口的概念入口

---

## 当前仍然相关的桥接能力

虽然现网主入口已切换，但桥接层没有完全失去价值。当前仍然用于：

- 多 QQ 号扫码联调
- Windows 本地 `QQ + NapCat`，服务器侧 `QQ Bridge + OpenClaw`
- 指定 agent 的辅助扫码入口

默认辅助映射：

- `brain` -> `qq-main`
- `tech` -> `brain-secretary-dev`
- `review` -> `brain-secretary-review`

相关脚本：

- `../../scripts/napcat_multi.py`
- `../../scripts/qq_bot_multi.py`
- `../../scripts/windows_local_qq_multi.ps1`
- `../../scripts/windows_local_qq_remote_apply.ps1`

---

## 现网与历史链路的区别

当前现网主链路：

- OpenClaw 原生 `qqbot`
- 主入口固定绑定 `qq-main`
- 子 agent 协作走 OpenClaw 内部委派

历史 / 辅助链路：

- `NapCat -> qq-bot(FastAPI Bridge) -> OpenClaw`
- 用于兼容、联调或 Windows 本地辅助入口

如果两边说法冲突，以现网主链路为准。
