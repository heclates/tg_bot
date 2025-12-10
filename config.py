from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Класс для загрузки конфигурации из переменных окружения.
    """

    BOT_TOKEN: str
    SUPABASE_URL: HttpUrl
    SUPABASE_KEY: str
    ADMIN_IDS: list[int] = Field(default_factory=list)
    MAX_WARNINGS: int = Field(default=3)

    @field_validator("BOT_TOKEN")
    @classmethod
    def validate_bot_token(cls, v: str) -> str:
        if not v or len(v) < 20:
            raise ValueError("BOT_TOKEN должен быть валидным токеном Telegram бота")
        return v

    @field_validator("ADMIN_IDS", mode="before")
    @classmethod
    def parse_admin_ids(cls, v):
        if isinstance(v, str):
            try:
                ids = [int(x.strip()) for x in v.split(",") if x.strip()]
                if not ids:
                    raise ValueError("ADMIN_IDS не может быть пустым")
                return ids
            except ValueError as e:
                raise ValueError(f"Ошибка парсинга ADMIN_IDS: {e}")
        return v

    @field_validator("MAX_WARNINGS")
    @classmethod
    def validate_max_warnings(cls, v: int) -> int:
        if v < 1:
            raise ValueError("MAX_WARNINGS должен быть больше 0")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Singleton instance
config = Settings()
