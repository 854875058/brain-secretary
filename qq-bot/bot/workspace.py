import aiosqlite
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = "data/tasks.db"


async def init_workspace_db():
    """初始化共享工作区表"""
    async with aiosqlite.connect(DB_PATH) as db:
        # 公告板：Agent 之间的消息
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bulletin (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                target TEXT DEFAULT 'all',
                content TEXT NOT NULL,
                msg_type TEXT DEFAULT 'info',
                created_at TEXT,
                read_flag INTEGER DEFAULT 0
            )
        """)
        # 知识库：共享文档和笔记
        await db.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                project TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        # Agent 状态：记录各 Agent 的运行状态
        await db.execute("""
            CREATE TABLE IF NOT EXISTS agent_status (
                agent_id TEXT PRIMARY KEY,
                project TEXT,
                status TEXT DEFAULT 'idle',
                current_task TEXT,
                last_heartbeat TEXT,
                pid INTEGER
            )
        """)
        await db.commit()
    logger.info("共享工作区初始化完成")


# ===== 公告板 =====

async def post_bulletin(source: str, content: str, target: str = "all", msg_type: str = "info"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO bulletin (source, target, content, msg_type, created_at) VALUES (?, ?, ?, ?, ?)",
            (source, target, content, msg_type, datetime.now().isoformat())
        )
        await db.commit()


async def get_unread_bulletins(target: str = "all", limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM bulletin WHERE (target=? OR target='all') AND read_flag=0 ORDER BY id DESC LIMIT ?",
            (target, limit)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def mark_bulletins_read(target: str = "all"):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE bulletin SET read_flag=1 WHERE target=? OR target='all'",
            (target,)
        )
        await db.commit()


# ===== 知识库 =====

async def add_knowledge(title: str, content: str, tags: str = "", project: str = "", created_by: str = "user"):
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        await db.execute(
            "INSERT INTO knowledge (title, content, tags, project, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, content, tags, project, created_by, now, now)
        )
        await db.commit()


async def search_knowledge(keyword: str) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM knowledge WHERE title LIKE ? OR content LIKE ? OR tags LIKE ? ORDER BY updated_at DESC LIMIT 20",
            (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%")
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def list_knowledge(limit: int = 20) -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT id, title, tags, project, created_by, updated_at FROM knowledge ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_knowledge(doc_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM knowledge WHERE id=?", (doc_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ===== Agent 状态 =====

async def update_agent_status(agent_id: str, project: str = "", status: str = "idle",
                               current_task: str = "", pid: int = 0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO agent_status (agent_id, project, status, current_task, last_heartbeat, pid) VALUES (?, ?, ?, ?, ?, ?)",
            (agent_id, project, status, current_task, datetime.now().isoformat(), pid)
        )
        await db.commit()


async def get_all_agent_status() -> list:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM agent_status ORDER BY last_heartbeat DESC")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
