from aiogram import BaseMiddleware
from aiogram.types import Message
from db_client import db


class ActivityMiddleware(BaseMiddleware):
    """
    Middleware, который обновляет время последней активности пользователя в БД
    при каждом входящем текстовом сообщении.
    """

    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.from_user:
            user = event.from_user
            db.upsert_user(
                user_id=user.id, username=user.username, full_name=user.full_name
            )

        return await handler(event, data)
