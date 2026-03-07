# QQ 接入层

> 目录: qq-bridge/
> 状态: 已有可用实现（qq-bot 目录）

---

## 技术栈

- **NapCat** - QQ 协议桥接，将 QQ 消息转为 OneBot 11 标准事件
- **路径**: D:\NapCat\
- **协议版本**: OneBot 11

---

## 当前状态

父目录中已有 `qq-bot/` 项目，已实现“QQ Bridge → OpenClaw”链路：
- 接收 NapCat OneBot11 事件（`/qq/message`）
- 生成稳定 `session-id`，调用 `openclaw agent --session-id ... --json`
- 把回复通过 NapCat API 发回 QQ
- 支持私聊对话、群聊 @bot、基础管理指令

---

## 待完成

- [ ] 统一“QQ 接入层”与“Brain/Agents”目录结构（逐步替换旧版实现）
- [ ] 在 OpenClaw 中创建隔离 agent（workspace 指向测试文件夹/本仓库）
- [ ] 扩展白名单/权限控制（目前默认仅管理员可用）

---

## 常见问题

见 [../docs/napcat-setup.md](../docs/napcat-setup.md)
