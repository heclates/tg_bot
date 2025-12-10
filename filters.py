from aiogram.filters import BaseFilter
from aiogram.types import Message
from config import get_admins


class IsAdmin(BaseFilter):
    """Проверяет, является ли пользователь администратором бота (по ID)."""

    async def __call__(self, message: Message) -> bool:
        if not message.from_user:
            return False
        return message.from_user.id in get_admins()


class IsGroupChat(BaseFilter):
    """Проверяет, что сообщение пришло из группы или супергруппы."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in ["group", "supergroup"]


class IsPrivateChat(BaseFilter):
    """Проверяет, что сообщение пришло из личных сообщений бота."""

    async def __call__(self, message: Message) -> bool:
        return message.chat.type == "private"


class IsProtectedAdmin(BaseFilter):
    """
    ЗАЩИТА ОТ ВЗЛОМА: Комбинация для команд, которые должны быть доступны
    ТОЛЬКО администраторам И ТОЛЬКО в личном чате с ботом.
    Это предотвращает случайный вызов важных команд в публичных группах.
    """

    async def __call__(self, message: Message) -> bool:
        return message.from_user.id in get_admins() and message.chat.type == "private"
