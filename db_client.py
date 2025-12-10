from supabase import create_client, Client
from config import config
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)


class Database:
    """
    Класс-обертка для работы с Supabase (PostgreSQL).
    Инкапсулирует всю логику запросов к БД.
    """

    def __init__(self):
        self.supabase: Client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    # --- Пользователи и Активность ---
    def upsert_user(self, user_id: int, username: str | None, full_name: str | None):
        """Обновляет дату последней активности или создает пользователя."""
        data = {
            "user_id": user_id,
            "username": username,
            "full_name": full_name,
            "last_active": datetime.now().isoformat(),
        }
        self.supabase.table("users").upsert(data).execute()

    # --- Модерация (Предупреждения) ---
    def add_warning(self, user_id: int):
        """Добавляет предупреждение и возвращает текущее количество."""
        # Используем RPC или Single-call для атомарности в проде, но для примера:
        user = (
            self.supabase.table("users")
            .select("warning_count")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        new_count = (user.data.get("warning_count", 0) or 0) + 1
        self.supabase.table("users").update({"warning_count": new_count}).eq(
            "user_id", user_id
        ).execute()
        return new_count

    def remove_warning(self, user_id: int):
        """Снимает одно предупреждение с пользователя, не давая счетчику уйти в минус."""
        user_response = (
            self.supabase.table("users")
            .select("warning_count")
            .eq("user_id", user_id)
            .single()
            .execute()
        )
        current_count = user_response.data.get("warning_count", 0) or 0
        new_count = max(0, current_count - 1)
        self.supabase.table("users").update({"warning_count": new_count}).eq(
            "user_id", user_id
        ).execute()
        return new_count

    # --- Запрещенные слова ---
    def get_bad_words(self) -> list[str]:
        """Получает список запрещенных слов из БД."""
        res = self.supabase.table("bad_words").select("word").execute()
        return [item["word"] for item in res.data]


db = Database()
