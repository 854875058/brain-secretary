import hashlib
import logging
from bot.task_db import add_task, update_task, get_project, get_all_projects
from bot.openclaw_client import OpenClawError

logger = logging.getLogger(__name__)


def _make_project_session_id(user_qq: int, project_name: str, project_path: str) -> str:
    raw = f"{user_qq}|{project_name}|{project_path}"
    short_hash = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"qq-{user_qq}-proj-{short_hash}"


def _build_project_prompt(project_name: str, project_path: str, prompt: str) -> str:
    return (
        "你正在处理一个【项目任务】。\n"
        f"项目名: {project_name}\n"
        f"项目路径: {project_path}\n\n"
        f"用户指令:\n{prompt}\n\n"
        "输出要求：\n"
        "1) 先给结论，再给关键步骤\n"
        "2) 如有改动，列出改动的文件路径\n"
        "3) 如需要执行命令，给出可复制的命令\n"
    ).strip()


async def dispatch_task(project_name: str, prompt: str, user_qq: int, qq_sender, reply_func, openclaw_client):
    """分发任务到指定项目的 Agent"""
    project = await get_project(project_name)
    if not project:
        projects = await get_all_projects()
        names = ", ".join(p["name"] for p in projects) if projects else "暂无项目"
        await reply_func(f"项目 [{project_name}] 不存在\n可用项目: {names}")
        return

    task_id = await add_task(project_name, prompt, user_qq)
    await update_task(task_id, "running")
    await reply_func(f"任务 #{task_id} 已创建，正在执行...\n项目: {project_name}\n指令: {prompt[:100]}")

    # 走 OpenClaw（默认具备会话/记忆能力）
    project_path = project["path"]
    session_id = _make_project_session_id(user_qq, project_name, project_path)
    full_prompt = _build_project_prompt(project_name, project_path, prompt)

    try:
        logger.info(f"[任务#{task_id}] OpenClaw 开始执行: {project_name} session={session_id}")
        result = await openclaw_client.agent_turn(session_id, full_prompt)
        status = "done"
    except OpenClawError as e:
        logger.error(f"[任务#{task_id}] OpenClaw 执行失败: {e}")
        result = str(e)
        status = "failed"
    except Exception as e:
        logger.error(f"[任务#{task_id}] 执行失败: {e}", exc_info=True)
        result = f"执行失败: {str(e)}"
        status = "failed"

    await update_task(task_id, status, result)

    # 结果可能很长，截断发送
    if len(result) > 1500:
        result = result[:1500] + "\n...(结果过长已截断)"

    await reply_func(f"任务 #{task_id} 完成\n\n{result}")
