from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Класс для загрузки конфигурации из переменных окружения.
    """

    BOT_TOKEN: str
    SUPABASE_URL: str
    SUPABASE_KEY: str
    ADMIN_IDS: str  # ID администраторов через запятую

    class Config:
        env_file = ".env"


config = Settings()


def get_admins() -> list[int]:
    """Возвращает список ID администраторов в формате int."""
    try:
        return [int(x.strip()) for x in config.ADMIN_IDS.split(",") if x.strip()]
    except ValueError:
        raise ValueError(
            "ADMIN_IDS должен содержать только числа, разделенные запятыми."
        )
