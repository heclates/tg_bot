from supabase import create_client, Client
from config import config
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


class Database:
    """
    Класс-обертка для работы с Supabase (PostgreSQL).
    Инкапсулирует всю логику запросов к БД.
    """

    def __init__(self):
        # Инициализация клиента Supabase
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
        # Улучшенная обработка None для имени
        if not full_name:
            data["full_name"] = f"User_{user_id}"

        try:
            self.supabase.table("users").upsert(data).execute()
        except Exception as e:
            logging.error(f"DB Error (upsert_user {user_id}): {e}")

    # --- Модерация (Предупреждения) ---
    def _get_warning_count(self, user_id: int) -> int:
        """Внутренний метод для получения текущего количества предупреждений."""
        try:
            # Используем .limit(1) вместо .single(), чтобы избежать исключения, если запись не найдена
            result = (
                self.supabase.table("users")
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

    def add_warning(self, user_id: int):
        """Добавляет предупреждение и возвращает текущее количество."""
        current_count = self._get_warning_count(user_id)
        new_count = current_count + 1

        try:
            # Обновляем или вставляем (если не существует)
            self.supabase.table("users").upsert(
                {"user_id": user_id, "warning_count": new_count}
            ).execute()
            return new_count
        except Exception as e:
            logging.error(f"DB Error (add_warning {user_id}): {e}")
            return current_count  # Возвращаем старое значение при ошибке

    def remove_warning(self, user_id: int):
        """Снимает одно предупреждение с пользователя, не давая счетчику уйти в минус."""
        current_count = self._get_warning_count(user_id)

        # Уменьшаем (минимум 0)
        new_count = max(0, current_count - 1)

        try:
            # Обновляем БД
            self.supabase.table("users").update({"warning_count": new_count}).eq(
                "user_id", user_id
            ).execute()
            return new_count
        except Exception as e:
            logging.error(f"DB Error (remove_warning {user_id}): {e}")
            return current_count  # Возвращаем старое значение при ошибке

    # --- Запрещенные слова ---
    def get_bad_words(self) -> list[str]:
        """Получает список запрещенных слов из БД."""
        try:
            res = self.supabase.table("bad_words").select("word").execute()
            return [item["word"] for item in res.data]
        except Exception as e:
            logging.error(f"DB Error (get_bad_words): {e}")
            return []


db = Database()
