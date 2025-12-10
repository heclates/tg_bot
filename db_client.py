import asyncio
from supabase import create_client, Client
from config import config
from datetime import datetime, timezone
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Database:
    """
    Класс-обертка для работы с Supabase (PostgreSQL).
    Инкапсулирует всю логику запросов к БД.
    Все методы асинхронные для совместимости с aiogram.
    """

    def __init__(self):
        # Инициализация клиента Supabase
        self.supabase: Client = create_client(
            str(config.SUPABASE_URL), config.SUPABASE_KEY
        )

    # --- Пользователи и Активность ---
    async def upsert_user(
        self, user_id: int, username: str | None, full_name: str | None
    ):
        """Обновляет дату последней активности или создает пользователя."""
        data = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name or f"User_{user_id}",
            "last_active": datetime.now(timezone.utc).isoformat(),
        }

        try:
            # Используем upsert для обновления last_active или создания нового пользователя
            await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .upsert(data, on_conflict="user_id")
                .execute()
            )
        except Exception as e:
            logging.error(f"DB Error (upsert_user {user_id}): {e}")

    # --- Модерация (Предупреждения) ---
    async def _get_warning_count(self, user_id: int) -> int:
        """Внутренний метод для получения текущего количества предупреждений."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .select("warning_count")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0].get("warning_count", 0) or 0
            return 0
        except Exception as e:
            logging.error(f"DB Error (get_warning_count {user_id}): {e}")
            return 0

    async def add_warning(self, user_id: int) -> int:
        """Добавляет предупреждение и возвращает текущее количество."""
        current_count = await self._get_warning_count(user_id)
        new_count = current_count + 1

        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .upsert(
                    {"user_id": user_id, "warning_count": new_count},
                    on_conflict="user_id",
                )
                .execute()
            )
            return new_count
        except Exception as e:
            logging.error(f"DB Error (add_warning {user_id}): {e}")
            return current_count

    async def remove_warning(self, user_id: int) -> int:
        """Снимает одно предупреждение с пользователя, не давая счетчику уйти в минус."""
        current_count = await self._get_warning_count(user_id)
        new_count = max(0, current_count - 1)

        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .update({"warning_count": new_count})
                .eq("user_id", user_id)
                .execute()
            )
            return new_count
        except Exception as e:
            logging.error(f"DB Error (remove_warning {user_id}): {e}")
            return current_count

    async def reset_warnings(self, user_id: int) -> None:
        """Сбрасывает все предупреждения пользователя."""
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .update({"warning_count": 0})
                .eq("user_id", user_id)
                .execute()
            )
        except Exception as e:
            logging.error(f"DB Error (reset_warnings {user_id}): {e}")

    # --- Запрещенные слова ---
    async def get_bad_words(self) -> list[str]:
        """Получает список запрещенных слов из БД."""
        try:
            res = await asyncio.to_thread(
                lambda: self.supabase.table("bad_words").select("word").execute()
            )
            return [item["word"].lower() for item in res.data]
        except Exception as e:
            logging.error(f"DB Error (get_bad_words): {e}")
            return []

    async def add_bad_word(self, word: str) -> bool:
        """Добавляет запрещенное слово в БД."""
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("bad_words")
                .insert({"word": word.lower()})
                .execute()
            )
            return True
        except Exception as e:
            logging.error(f"DB Error (add_bad_word): {e}")
            return False

    async def remove_bad_word(self, word: str) -> bool:
        """Удаляет запрещенное слово из БД."""
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("bad_words")
                .delete()
                .eq("word", word.lower())
                .execute()
            )
            return True
        except Exception as e:
            logging.error(f"DB Error (remove_bad_word): {e}")
            return False

    # --- События (Events) ---
    async def create_event(
        self, title: str, created_by: int, event_date: datetime | None = None
    ) -> int | None:
        """Создает новое событие и возвращает его ID."""
        try:
            data = {"title": title, "created_by": created_by, "is_active": True}
            if event_date:
                data["event_date"] = event_date.isoformat()

            result = await asyncio.to_thread(
                lambda: self.supabase.table("events").insert(data).execute()
            )

            if result.data:
                return result.data[0]["id"]
            return None
        except Exception as e:
            logging.error(f"DB Error (create_event): {e}")
            return None

    async def add_event_participant(
        self, event_id: int, user_id: int, status: str = "joined"
    ) -> bool:
        """Добавляет участника к событию."""
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("event_participants")
                .upsert(
                    {"event_id": event_id, "user_id": user_id, "status": status},
                    on_conflict="event_id,user_id",
                )
                .execute()
            )
            return True
        except Exception as e:
            logging.error(f"DB Error (add_event_participant): {e}")
            return False

    async def get_event_participants(self, event_id: int) -> list[dict]:
        """Получает список участников события."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("event_participants")
                .select("user_id, status")
                .eq("event_id", event_id)
                .execute()
            )
            return result.data
        except Exception as e:
            logging.error(f"DB Error (get_event_participants): {e}")
            return []

    async def get_active_events(self) -> list[dict]:
        """Получает список активных событий."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("events")
                .select("*")
                .eq("is_active", True)
                .execute()
            )
            return result.data
        except Exception as e:
            logging.error(f"DB Error (get_active_events): {e}")
            return []

    async def close_event(self, event_id: int) -> bool:
        """Закрывает событие (делает неактивным)."""
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("events")
                .update({"is_active": False})
                .eq("id", event_id)
                .execute()
            )
            return True
        except Exception as e:
            logging.error(f"DB Error (close_event): {e}")
            return False

    # --- Статистика ---
    async def get_user_stats(self, user_id: int) -> dict | None:
        """Получает статистику пользователя."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .select("*")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )

            if result.data:
                return result.data[0]
            return None
        except Exception as e:
            logging.error(f"DB Error (get_user_stats): {e}")
            return None

    async def get_top_warned_users(self, limit: int = 10) -> list[dict]:
        """Получает топ пользователей по количеству предупреждений."""
        try:
            result = await asyncio.to_thread(
                lambda: self.supabase.table("users")
                .select("user_id, username, full_name, warning_count")
                .gt("warning_count", 0)
                .order("warning_count", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data
        except Exception as e:
            logging.error(f"DB Error (get_top_warned_users): {e}")
            return []


db = Database()
