from apscheduler.schedulers.asyncio import AsyncIOScheduler
import logging
from bot.monitor import get_status_report, refresh_agent_status
from bot.task_db import get_recent_tasks
from bot.async_notifier import deliver_async_internal_updates
from bot.task_sync import sync_local_checklist_milestones, sync_task_checklist_from_transcripts

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def setup_scheduled_tasks(qq_sender, target_qq: int, transcript_dir: str | None = None):
    """配置定时任务"""

    # 每天 9:00 推送日报
    @scheduler.scheduled_job("cron", hour=9, minute=0)
    async def daily_report():
        try:
            status = await get_status_report()
            tasks = await get_recent_tasks(5)
            report = f"📋 每日汇报\n\n{status}\n\n"
            if tasks:
                report += "最近任务:\n"
                for t in tasks:
                    icon = {"pending": "⏳", "running": "🔄", "done": "✅", "failed": "❌"}.get(t["status"], "?")
                    report += f"  #{t['id']} {icon} [{t['project']}] {t['prompt'][:30]}\n"
            await qq_sender.send_private_msg(target_qq, report.strip())
            logger.info(f"日报已推送到 {target_qq}")
        except Exception as e:
            logger.error(f"日报推送失败: {e}")

    # 每 30 分钟刷新 Agent 状态
    @scheduler.scheduled_job("interval", minutes=30)
    async def refresh_status():
        try:
            await refresh_agent_status()
            logger.info("Agent 状态已刷新")
        except Exception as e:
            logger.error(f"刷新状态失败: {e}")

    # 每 20 秒检查一次 qq-main 的异步完成回推
    @scheduler.scheduled_job("interval", seconds=20)
    async def deliver_async_updates():
        try:
            if not transcript_dir:
                return
            delivered = await deliver_async_internal_updates(qq_sender, transcript_dir, target_qq)
            if delivered:
                logger.info(f"异步完成回推已发送 {delivered} 条")
        except Exception as e:
            logger.error(f"异步完成回推失败: {e}", exc_info=True)

    # 每 30 秒把子 Agent 完成情况同步到任务清单
    @scheduler.scheduled_job("interval", seconds=30)
    async def sync_checklist_progress():
        try:
            if not transcript_dir:
                return
            updated = await sync_task_checklist_from_transcripts('logs/bot.log', transcript_dir, target_qq)
            local_updates = await sync_local_checklist_milestones(target_qq)
            if updated or local_updates:
                logger.info(f"任务清单已同步：transcript_updates={updated} local_updates={local_updates}")
        except Exception as e:
            logger.error(f"任务清单同步失败: {e}", exc_info=True)

    scheduler.start()
    logger.info("定时任务已启动")
