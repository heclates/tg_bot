import asyncio
import logging
import re
from datetime import datetime
from typing import Optional, List

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from asyncio import Lock

# Импорты модулей
from config import config
from db_client import db
from middlewares import ActivityMiddleware
from filters import IsAdmin, IsGroupChat, IsProtectedAdmin

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# Инициализация
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Подключение Middleware
dp.message.middleware(ActivityMiddleware())


# --- КЭШИРОВАНИЕ ЗАПРЕЩЕННЫХ СЛОВ ---
class BadWordsCache:
    """Класс для кэширования запрещенных слов (Single Responsibility)."""

    def __init__(self):
        self._words: List[str] = []
        self._lock = Lock()

    async def reload(self) -> int:
        """Загрузка списка запрещенных слов из БД."""
        async with self._lock:
            self._words = await db.get_bad_words()
            count = len(self._words)
            logging.info(f"Словарь обновлен. Загружено слов: {count}")
            return count

    def contains(self, text: str) -> bool:
        """Проверяет, содержит ли текст запрещенные слова (whole word match)."""
        text_lower = text.lower()
        return any(
            re.search(r"\b" + re.escape(word) + r"\b", text_lower)
            for word in self._words
        )

    def get_count(self) -> int:
        """Возвращает количество загруженных слов."""
        return len(self._words)


bad_words_cache = BadWordsCache()


# --- СЕРВИСНЫЕ КЛАССЫ (Dependency Inversion, Interface Segregation) ---


class CommandHandler:
    """Базовый класс для обработки команд (Open-Closed Principle)."""

    async def handle(self, message: types.Message) -> None:
        raise NotImplementedError


class ReloadCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        try:
            count = await bad_words_cache.reload()
            await message.answer(f"✅ Список запрещенных слов обновлен! Всего: {count}")
        except Exception as e:
            logging.error(f"Ошибка при перезагрузке списка слов: {e}")
            await message.answer("❌ Ошибка при обновлении списка слов.")


class AddWordCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        word = message.text.replace("/addword", "").strip().lower()
        if not word:
            await message.answer("Укажите слово. Пример: /addword спам")
            return

        try:
            if await db.add_bad_word(word):
                await bad_words_cache.reload()
                await message.answer(
                    f"✅ Слово '{word}' добавлено в список запрещенных."
                )
            else:
                await message.answer(
                    f"❌ Не удалось добавить слово. Возможно, оно уже есть."
                )
        except Exception as e:
            logging.error(f"Ошибка при добавлении слова: {e}")
            await message.answer("❌ Ошибка при добавлении слова.")


class RemoveWordCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        word = message.text.replace("/removeword", "").strip().lower()
        if not word:
            await message.answer("Укажите слово. Пример: /removeword спам")
            return

        try:
            if await db.remove_bad_word(word):
                await bad_words_cache.reload()
                await message.answer(
                    f"✅ Слово '{word}' удалено из списка запрещенных."
                )
            else:
                await message.answer(f"❌ Не удалось удалить слово.")
        except Exception as e:
            logging.error(f"Ошибка при удалении слова: {e}")
            await message.answer("❌ Ошибка при удалении слова.")


class StatsCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        try:
            top_users = await db.get_top_warned_users(limit=5)

            if not top_users:
                await message.answer("📊 Нет пользователей с предупреждениями.")
                return

            text = "📊 **Топ пользователей по предупреждениям:**\n\n"
            for i, user in enumerate(top_users, 1):
                name = (
                    user.get("full_name")
                    or user.get("username")
                    or f"User_{user['user_id']}"
                )
                warns = user.get("warning_count", 0)
                text += f"{i}. {name} - {warns} ⚠️\n"

            await message.answer(text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Ошибка при получении статистики: {e}")
            await message.answer("❌ Ошибка при получении статистики.")


class CreateEventCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        event_text = message.text.replace("/event", "").strip()
        if not event_text:
            await message.answer(
                "Укажите название события. Пример: /event Поход в кино"
            )
            return

        try:
            event_id = await db.create_event(
                title=event_text, created_by=message.from_user.id
            )

            if not event_id:
                await message.answer("❌ Не удалось создать событие.")
                return

            poll = await message.answer_poll(
                question=f"📅 {event_text}. Кто идет?",
                options=["Я иду! ✅", "Думаю 🤔", "Не иду ❌"],
                is_anonymous=False,
            )

            logging.info(f"Создано событие #{event_id}: {event_text}")
        except TelegramBadRequest as e:
            logging.error(f"Не удалось создать опрос: {e}")
            await message.answer("⚠️ Не удалось создать опрос. Проверьте права бота.")
        except Exception as e:
            logging.error(f"Ошибка при создании события: {e}")
            await message.answer("❌ Ошибка при создании события.")


class ListEventsCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        try:
            events = await db.get_active_events()

            if not events:
                await message.answer("📅 Нет активных событий.")
                return

            text = "📅 **Активные события:**\n\n"
            for event in events:
                title = event.get("title")
                event_id = event.get("id")
                participants = await db.get_event_participants(event_id)
                text += f"• {title} (ID: {event_id})\n"
                text += f"  Участников: {len(participants)}\n\n"

            await message.answer(text, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Ошибка при получении списка событий: {e}")
            await message.answer("❌ Ошибка при получении списка событий.")


class UnwarnCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        target_user: Optional[types.User] = None

        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user

        if not target_user:
            await message.answer(
                "⚠️ Команду `/unwarn` нужно использовать **в ответ** на сообщение пользователя.",
                parse_mode="Markdown",
            )
            return

        if target_user.id in config.ADMIN_IDS:
            await message.answer("❌ Нельзя снимать предупреждения с администраторов.")
            return

        if target_user.is_bot:
            await message.answer("❌ Нельзя применять команды к ботам.")
            return

        try:
            new_count = await db.remove_warning(target_user.id)
            new_count = new_count if new_count is not None else 0

            await message.answer(
                f"✅ С пользователя **{target_user.full_name}** снято одно предупреждение.\n"
                f"Текущее количество: **{new_count}**.",
                parse_mode="Markdown",
            )
        except Exception as e:
            logging.error(f"Ошибка при снятии предупреждения для {target_user.id}: {e}")
            await message.answer("❌ Ошибка при снятии предупреждения.")


class UserInfoCommandHandler(CommandHandler):
    async def handle(self, message: types.Message) -> None:
        target_user: Optional[types.User] = None

        if message.reply_to_message and message.reply_to_message.from_user:
            target_user = message.reply_to_message.from_user

        if not target_user:
            await message.answer(
                "⚠️ Используйте команду в ответ на сообщение пользователя."
            )
            return

        try:
            stats = await db.get_user_stats(target_user.id)

            if not stats:
                await message.answer("❌ Пользователь не найден в базе данных.")
                return

            last_active = stats.get("last_active", "Неизвестно")
            if isinstance(last_active, datetime):
                last_active = last_active.strftime("%Y-%m-%d %H:%M:%S")

            joined_at = stats.get("joined_at", "Неизвестно")
            if isinstance(joined_at, datetime):
                joined_at = joined_at.strftime("%Y-%m-%d %H:%M:%S")

            text = f"👤 **Информация о пользователе**\n\n"
            text += f"**Имя:** {stats.get('full_name')}\n"
            text += f"**Username:** @{stats.get('username') or 'не указан'}\n"
            text += f"**ID:** `{stats.get('user_id')}`\n"
            text += f"**Предупреждения:** {stats.get('warning_count', 0)}/{config.MAX_WARNINGS}\n"
            text += f"**Последняя активность:** {last_active}\n"
            text += f"**Присоединился:** {joined_at}\n"

            await message.answer(text, parse_mode="Markdown")
        except Exception as e:
            logging.error(
                f"Ошибка при получении информации о пользователе {target_user.id}: {e}"
            )
            await message.answer("❌ Ошибка при получении информации о пользователе.")


# --- РЕГИСТРАЦИЯ КОМАНД (DRY) ---


@dp.message(Command("reload"), IsProtectedAdmin())
async def cmd_reload(message: types.Message) -> None:
    await ReloadCommandHandler().handle(message)


@dp.message(Command("addword"), IsProtectedAdmin())
async def cmd_add_word(message: types.Message) -> None:
    await AddWordCommandHandler().handle(message)


@dp.message(Command("removeword"), IsProtectedAdmin())
async def cmd_remove_word(message: types.Message) -> None:
    await RemoveWordCommandHandler().handle(message)


@dp.message(Command("stats"), IsProtectedAdmin())
async def cmd_stats(message: types.Message) -> None:
    await StatsCommandHandler().handle(message)


@dp.message(Command("event"), IsAdmin(), IsGroupChat())
async def cmd_create_event(message: types.Message) -> None:
    await CreateEventCommandHandler().handle(message)


@dp.message(Command("events"), IsGroupChat())
async def cmd_list_events(message: types.Message) -> None:
    await ListEventsCommandHandler().handle(message)


@dp.message(Command("unwarn"), IsAdmin(), IsGroupChat())
async def cmd_unwarn(message: types.Message) -> None:
    await UnwarnCommandHandler().handle(message)


@dp.message(Command("userinfo"), IsAdmin(), IsGroupChat())
async def cmd_userinfo(message: types.Message) -> None:
    await UserInfoCommandHandler().handle(message)


# --- МОДЕРАЦИЯ И САНКЦИИ ---


class ModerationService:
    """Сервис для модерации (Single Responsibility)."""

    async def apply_sanction(self, message: types.Message, reason: str) -> None:
        user = message.from_user

        if user.id in config.ADMIN_IDS:
            return

        try:
            await message.delete()
        except TelegramBadRequest as e:
            logging.warning(f"Не удалось удалить сообщение от {user.id}: {e}")

        try:
            warn_count = await db.add_warning(user.id)

            logging.info(
                f"Модерация: user_id={user.id}, username={user.username}, "
                f"reason={reason}, warns={warn_count}/{config.MAX_WARNINGS}"
            )

            if warn_count >= config.MAX_WARNINGS:
                await bot.ban_chat_member(message.chat.id, user.id)
                await bot.send_message(
                    message.chat.id,
                    f"🚫 Пользователь {user.full_name} был забанен.\n"
                    f"Причина: {reason} ({warn_count}/{config.MAX_WARNINGS}).",
                )
                await db.reset_warnings(user.id)
            else:
                await bot.send_message(
                    message.chat.id,
                    f"⚠️ {user.full_name}, нарушение!\n"
                    f"Причина: {reason}\n"
                    f"Предупреждение {warn_count}/{config.MAX_WARNINGS}.",
                )
        except TelegramBadRequest as e:
            logging.error(f"Не удалось применить санкции (Telegram ошибка): {e}")
            await bot.send_message(
                message.chat.id,
                f"⚠️ Не удалось применить санкции к {user.full_name}. Проверьте права бота.",
            )
        except Exception as e:
            logging.error(
                f"Не удалось применить санкции к {user.full_name} ({user.id}): {e}"
            )
            await bot.send_message(
                message.chat.id, f"❌ Ошибка при применении санкций к {user.full_name}."
            )

    async def check_moderation(self, message: types.Message) -> None:
        if not message.text:
            return

        text = message.text.lower()

        url_regex = r"(?:https?://|t\.me/|@|www\.|[a-zA-Z0-9-]+\.[a-z]{2,})[^\s]*"
        if re.search(url_regex, text):
            await self.apply_sanction(message, "Реклама и ссылки запрещены")
            return

        if bad_words_cache.contains(text):
            await self.apply_sanction(
                message, "Использование запрещенной лексики/агрессия"
            )
            return


moderation_service = ModerationService()


@dp.message(F.text, IsGroupChat(), ~IsAdmin())
async def moderation_handler(message: types.Message) -> None:
    await moderation_service.check_moderation(message)


# --- ПРИВЕТСТВИЕ НОВЫХ УЧАСТНИКОВ ---


class WelcomeService:
    """Сервис для приветствия новых участников (KISS, Single Responsibility)."""

    async def welcome_new_members(self, message: types.Message) -> None:
        try:
            await message.delete()
        except TelegramBadRequest as e:
            logging.warning(f"Не удалось удалить системное сообщение о вступлении: {e}")

        bot_info = await bot.get_me()
        for user in message.new_chat_members:
            if user.id == bot_info.id or user.is_bot:
                continue

            welcome_message = (
                f"🎉 **Добро пожаловать, {user.full_name}!**\n\n"
                f"Обязательно изучи **Правила сообщества** перед началом общения.\n\n"
                f"❗️ Ознакомиться с Правилами: [Нажми сюда](https://t.me/your_rules_link)\n\n"
                f"Приятного общения!"
            )

            try:
                await bot.send_message(
                    message.chat.id, welcome_message, parse_mode="Markdown"
                )
            except TelegramBadRequest as e:
                logging.error(f"Не удалось отправить приветствие для {user.id}: {e}")


welcome_service = WelcomeService()


@dp.message(F.new_chat_members)
async def on_new_chat_members(message: types.Message) -> None:
    await welcome_service.welcome_new_members(message)


# --- ОБРАБОТЧИК ОШИБОК ---


@dp.errors()
async def error_handler(event, exception) -> bool:
    logging.error(f"Необработанная ошибка: {exception}", exc_info=True)
    return True


# --- ЗАПУСК ---


async def main() -> None:
    try:
        count = await bad_words_cache.reload()
        if count == 0:
            logging.warning("⚠️ Список запрещенных слов пуст!")
    except Exception as e:
        logging.error(f"Не удалось загрузить кэш запрещенных слов: {e}")
        return

    commands = [
        types.BotCommand("reload", "Обновить список запрещенных слов"),
        types.BotCommand("addword", "Добавить запрещенное слово"),
        types.BotCommand("removeword", "Удалить запрещенное слово"),
        types.BotCommand("stats", "Статистика модерации"),
        types.BotCommand("event", "Создать событие"),
        types.BotCommand("events", "Список событий"),
        types.BotCommand("unwarn", "Снять предупреждение с пользователя"),
        types.BotCommand("userinfo", "Информация о пользователе"),
    ]
    try:
        await bot.set_my_commands(commands)
        logging.info("✅ Команды бота установлены для подсказок.")
    except Exception as e:
        logging.error(f"Не удалось установить команды бота: {e}")

    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("🚀 Бот запущен и готов к работе!")
    logging.info(f"👮 Администраторы: {config.ADMIN_IDS}")
    logging.info(f"⚠️ Максимум предупреждений: {config.MAX_WARNINGS}")

    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Получен сигнал остановки...")
    except Exception as e:
        logging.error(f"Ошибка в polling: {e}")
    finally:
        await bot.session.close()
        logging.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
    except Exception as e:
        logging.error(f"Критическая ошибка при запуске: {e}")
