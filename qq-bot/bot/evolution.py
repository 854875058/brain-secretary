from __future__ import annotations

DEFAULT_EVOLUTION_TRIGGERS = [
    "自助进化",
    "自我进化",
    "进化一下",
    "进化出来这些功能",
    "自己去安排agent进化",
    "自己去安排进化",
    "更新你的规则",
    "写进规则",
    "把这件事记住",
    "记住这个",
    "吸取这个教训",
    "别再犯",
    "别再这样",
    "以后遇到这种情况",
    "这8项技能都给我整好",
    "把这8项技能都整好",
    "你可以发图片",
    "让你能发图片",
    "以后直接发图",
    "具备发图能力",
    "让你具备",
    "给你加一个功能",
    "让你学会",
    "以后你自己去做",
    "以后你自己处理",
    "自己完成",
    "自动完成",
    "形成闭环",
    "做这个闭环",
    "完成一件告诉我一件",
]


def should_trigger_evolution(message: str, extra_keywords: list[str] | None = None) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    if text.startswith("/"):
        return False
    keywords = list(DEFAULT_EVOLUTION_TRIGGERS)
    if extra_keywords:
        keywords.extend(item for item in extra_keywords if item)
    return any(keyword in text for keyword in keywords)


def build_evolution_prompt(user_message: str) -> str:
    return (
        "这是一次【自助进化 / 自我修正】请求。\n"
        "你的目标不是只口头答应，而是尽量通过修改本地文件把改进真正固化下来，并形成可追踪的闭环。\n\n"
        "请按这个顺序判断并执行：\n"
        "1. 先判断这是记忆固化、规则更新、工程实现还是跨仓协同；不要跳过拆解\n"
        "2. 需要改主仓工程时，优先委派 `brain-secretary-dev`；需要次仓参考/迁移时，再委派 `agent-hub-dev`\n"
        "3. 如果是长期记忆 / 用户偏好 / 经验教训 → 更新 MEMORY.md 或 memory/YYYY-MM-DD.md\n"
        "4. 如果是行为规范 / 路由 / 验收方式 / 协调规则 → 更新 AGENTS.md、SOUL.md、BRAIN.md、SUBAGENTS.md、TOOLS.md、EVOLUTION.md 等\n"
        "5. 如果是可复用流程 / 固定操作模式 → 在 workspace/skills 下创建或更新本地 skill\n"
        "6. 如果涉及主项目部署、路径、端口、agent 结构 → 同步更新 /root/brain-secretary 下相关文档\n\n"
        "闭环要求：\n"
        "- 能改文件就改文件，不要只说‘以后我会注意’\n"
        "- 修改尽量最小但要真正落地，并做最必要的验证\n"
        "- 如果不能一轮做完，先给当前 QQ 一句简短确认；之后每完成一个子任务，都用 `[[reply_to_current]]` 回推一次进展，做到‘完成一件回一件’\n"
        "- 最终汇总必须用中文说明：改了哪些文件、委派了哪些 agent、做了哪些验证、现在还差什么\n\n"
        f"用户原话：{user_message}"
    )


def build_remember_prompt(user_message: str) -> str:
    return (
        "这是一次【记忆固化】请求。\n"
        "请把用户要你记住的信息写入合适的记忆文件：长期的写 MEMORY.md，当日临时上下文写 memory/YYYY-MM-DD.md。\n"
        "完成后只用中文简要说明：记到了哪里、以后会怎么用。\n\n"
        f"用户原话：{user_message}"
    )
