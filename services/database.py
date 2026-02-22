"""
Сервіс бази даних - SQLite для тимчасових даних
"""
import asyncio
import logging
import sqlite3
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = "bot_data.db"):
        self.db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = asyncio.Lock()

    async def init(self):
        """Ініціалізація бази даних"""
        async with self._lock:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            await asyncio.get_event_loop().run_in_executor(None, self._create_tables)
            logger.info(f"БД ініціалізовано: {self.db_path}")

    def _create_tables(self):
        cursor = self._conn.cursor()
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS questions (
                request_id TEXT PRIMARY KEY,
                -- user_id зберігається тимчасово для доставки відповіді
                user_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                answered_at TIMESTAMP,
                delivered_at TIMESTAMP,
                rating INTEGER
            );

            CREATE TABLE IF NOT EXISTS rate_limits (
                user_id INTEGER PRIMARY KEY,
                last_request TIMESTAMP NOT NULL
            );

            CREATE TABLE IF NOT EXISTS admin_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE DEFAULT (DATE('now')),
                total_questions INTEGER DEFAULT 0,
                total_answers INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_status ON questions(status);
            CREATE INDEX IF NOT EXISTS idx_created ON questions(created_at);
        """)
        self._conn.commit()

    async def _execute(self, query: str, params=()) -> sqlite3.Cursor:
        async with self._lock:
            return await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._conn.execute(query, params)
            )

    async def _commit(self):
        async with self._lock:
            await asyncio.get_event_loop().run_in_executor(None, self._conn.commit)

    # ---- Rate Limiting ----

    async def check_rate_limit(self, user_id: int, limit_seconds: int) -> Optional[int]:
        """Перевірка ліміту. Повертає секунди до наступного дозволу або None якщо OK"""
        cursor = await self._execute(
            "SELECT last_request FROM rate_limits WHERE user_id = ?", (user_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        last_request = datetime.fromisoformat(row["last_request"])
        elapsed = (datetime.now() - last_request).total_seconds()
        if elapsed < limit_seconds:
            return int(limit_seconds - elapsed)
        return None

    async def update_rate_limit(self, user_id: int):
        """Оновлення часу останнього запиту"""
        await self._execute(
            """INSERT INTO rate_limits (user_id, last_request) VALUES (?, ?)
               ON CONFLICT(user_id) DO UPDATE SET last_request = excluded.last_request""",
            (user_id, datetime.now().isoformat())
        )
        await self._commit()

    # ---- Questions ----

    async def create_question(self, user_id: int, question: str) -> str:
        """Створення нового питання. Повертає request_id"""
        request_id = str(uuid.uuid4())[:8].upper()
        await self._execute(
            """INSERT INTO questions (request_id, user_id, question, status)
               VALUES (?, ?, ?, 'pending')""",
            (request_id, user_id, question)
        )
        await self._commit()
        await self.update_rate_limit(user_id)
        return request_id

    async def get_question(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Отримання питання за ID"""
        cursor = await self._execute(
            "SELECT * FROM questions WHERE request_id = ?", (request_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

    async def get_pending_questions(self) -> list:
        """Список питань без відповіді"""
        cursor = await self._execute(
            "SELECT * FROM questions WHERE status = 'pending' ORDER BY created_at"
        )
        return [dict(row) for row in cursor.fetchall()]

    async def save_answer(self, request_id: str, answer: str) -> Optional[int]:
        """Збереження відповіді. Повертає user_id для доставки"""
        cursor = await self._execute(
            "SELECT user_id FROM questions WHERE request_id = ? AND status = 'pending'",
            (request_id,)
        )
        row = cursor.fetchone()
        if not row:
            return None

        user_id = row["user_id"]
        await self._execute(
            """UPDATE questions SET answer = ?, status = 'answered',
               answered_at = CURRENT_TIMESTAMP WHERE request_id = ?""",
            (answer, request_id)
        )
        await self._commit()
        return user_id

    async def mark_delivered(self, request_id: str):
        """Позначення відповіді як доставленої та видалення user_id"""
        await self._execute(
            """UPDATE questions SET status = 'delivered',
               delivered_at = CURRENT_TIMESTAMP,
               user_id = -1
               WHERE request_id = ?""",
            (request_id,)
        )
        await self._commit()
        logger.info(f"[АНОНІМНІСТЬ] user_id видалено для запиту {request_id}")

    async def save_rating(self, request_id: str, rating: int):
        """Збереження рейтингу відповіді"""
        await self._execute(
            "UPDATE questions SET rating = ? WHERE request_id = ?",
            (rating, request_id)
        )
        await self._commit()

    # ---- Статистика ----

    async def get_stats(self) -> Dict[str, Any]:
        """Статистика для адміна"""
        cursor = await self._execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status IN ('answered', 'delivered') THEN 1 ELSE 0 END) as answered,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                AVG(CASE
                    WHEN answered_at IS NOT NULL
                    THEN CAST((julianday(answered_at) - julianday(created_at)) * 86400 AS INTEGER)
                    ELSE NULL
                END) as avg_seconds,
                MAX(created_at) as last_question
            FROM questions
        """)
        row = cursor.fetchone()
        stats = dict(row) if row else {}

        avg = stats.get("avg_seconds")
        if avg:
            mins = int(avg // 60)
            stats["avg_time"] = f"{mins} хв" if mins < 60 else f"{mins // 60} год {mins % 60} хв"
        else:
            stats["avg_time"] = "—"

        last = stats.get("last_question")
        if last:
            try:
                dt = datetime.fromisoformat(last)
                stats["last_question"] = dt.strftime("%d.%m.%Y %H:%M")
            except Exception:
                pass

        return stats

    async def cleanup_old_data(self, days: int = 7):
        """Очищення старих доставлених даних"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        await self._execute(
            "DELETE FROM questions WHERE status = 'delivered' AND delivered_at < ?",
            (cutoff,)
        )
        await self._execute(
            "DELETE FROM rate_limits WHERE last_request < ?",
            (cutoff,)
        )
        await self._commit()
        logger.info(f"Очищено старі дані старше {days} днів")

    async def close(self):
        if self._conn:
            self._conn.close()
            logger.info("З'єднання з БД закрито")


db = Database()
