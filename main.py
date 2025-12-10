import asyncio
import logging
import re
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.exceptions import TelegramBadRequest
from asyncio import Lock

# Импорты ваших модулей
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
    """Thread-safe кэш для запрещенных слов."""

    def __init__(self):
        self._words: list[str] = []
        self._lock = Lock()

    async def reload(self) -> int:
        """Загрузка списка запрещенных слов из БД."""
        async with self._lock:
            self._words = await db.get_bad_words()
            count = len(self._words)
            logging.info(f"Словарь обновлен. Загружено слов: {count}")
            return count

    def contains(self, text: str) -> bool:
        """Проверяет, содержит ли текст запрещенные слова."""
        text_lower = text.lower()
        return any(word in text_lower for word in self._words)

    def get_count(self) -> int:
        """Возвращает количество загруженных слов."""
        return len(self._words)


bad_words_cache = BadWordsCache()


# --- 1. АДМИНСКИЕ КОМАНДЫ ---


@dp.message(Command("reload"), IsProtectedAdmin())
async def cmd_reload(message: types.Message):
    """Обновляет список запрещенных слов (защищенная команда)."""
    count = await bad_words_cache.reload()
    await message.answer(f"✅ Список запрещенных слов обновлен! Всего: {count}")


@dp.message(Command("addword"), IsProtectedAdmin())
async def cmd_add_word(message: types.Message):
    """Добавляет запрещенное слово."""
    word = message.text.replace("/addword", "").strip().lower()
    if not word:
        await message.answer("Укажите слово. Пример: /addword спам")
        return

    if await db.add_bad_word(word):
        await bad_words_cache.reload()
        await message.answer(f"✅ Слово '{word}' добавлено в список запрещенных.")
    else:
        await message.answer(f"❌ Не удалось добавить слово. Возможно, оно уже есть.")


@dp.message(Command("removeword"), IsProtectedAdmin())
async def cmd_remove_word(message: types.Message):
    """Удаляет запрещенное слово."""
    word = message.text.replace("/removeword", "").strip().lower()
    if not word:
        await message.answer("Укажите слово. Пример: /removeword спам")
        return

    if await db.remove_bad_word(word):
        await bad_words_cache.reload()
        await message.answer(f"✅ Слово '{word}' удалено из списка запрещенных.")
    else:
        await message.answer(f"❌ Не удалось удалить слово.")


@dp.message(Command("stats"), IsProtectedAdmin())
async def cmd_stats(message: types.Message):
    """Показывает статистику модерации."""
    top_users = await db.get_top_warned_users(limit=5)

    if not top_users:
        await message.answer("📊 Нет пользователей с предупреждениями.")
        return

    text = "📊 **Топ пользователей по предупреждениям:**\n\n"
    for i, user in enumerate(top_users, 1):
        name = (
            user.get("full_name") or user.get("username") or f"User_{user['user_id']}"
        )
        warns = user.get("warning_count", 0)
        text += f"{i}. {name} - {warns} ⚠️\n"

    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("event"), IsAdmin(), IsGroupChat())
async def cmd_create_event(message: types.Message):
    """Создает событие и опрос для участия."""
    event_text = message.text.replace("/event", "").strip()
    if not event_text:
        await message.answer("Укажите название события. Пример: /event Поход в кино")
        return

    # Создаем событие в БД
    event_id = await db.create_event(title=event_text, created_by=message.from_user.id)

    if not event_id:
        await message.answer("❌ Не удалось создать событие.")
        return

    try:
        poll = await message.answer_poll(
            question=f"📅 {event_text}. Кто идет?",
            options=["Я иду! ✅", "Думаю 🤔", "Не иду ❌"],
            is_anonymous=False,
        )

        # Можно сохранить poll.poll.id для связи с event_id
        logging.info(f"Создано событие #{event_id}: {event_text}")

    except TelegramBadRequest as e:
        logging.error(f"Не удалось создать опрос: {e}")
        await message.answer("⚠️ Не удалось создать опрос. Проверьте права бота.")


@dp.message(Command("events"), IsGroupChat())
async def cmd_list_events(message: types.Message):
    """Показывает список активных событий."""
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


@dp.message(Command("unwarn"), IsAdmin(), IsGroupChat())
async def cmd_unwarn(message: types.Message):
    """Снимает одно предупреждение с пользователя (по ответу на сообщение)."""
    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user

    if not target_user:
        return await message.answer(
            "⚠️ Команду `/unwarn` нужно использовать **в ответ** на сообщение пользователя.",
            parse_mode="Markdown",
        )

    # Проверка на администратора
    if target_user.id in config.ADMIN_IDS:
        return await message.answer(
            "❌ Нельзя снимать предупреждения с администраторов."
        )

    # Проверка, что это не бот
    if target_user.is_bot:
        return await message.answer("❌ Нельзя применять команды к ботам.")

    new_count = await db.remove_warning(target_user.id)

    await message.answer(
        f"✅ С пользователя **{target_user.full_name}** снято одно предупреждение.\n"
        f"Текущее количество: **{new_count}**.",
        parse_mode="Markdown",
    )


@dp.message(Command("userinfo"), IsAdmin(), IsGroupChat())
async def cmd_userinfo(message: types.Message):
    """Показывает информацию о пользователе (по ответу)."""
    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user

    if not target_user:
        return await message.answer(
            "⚠️ Используйте команду в ответ на сообщение пользователя."
        )

    stats = await db.get_user_stats(target_user.id)

    if not stats:
        await message.answer("❌ Пользователь не найден в базе данных.")
        return

    text = f"👤 **Информация о пользователе**\n\n"
    text += f"**Имя:** {stats.get('full_name')}\n"
    text += f"**Username:** @{stats.get('username') or 'не указан'}\n"
    text += f"**ID:** `{stats.get('user_id')}`\n"
    text += (
        f"**Предупреждения:** {stats.get('warning_count', 0)}/{config.MAX_WARNINGS}\n"
    )
    text += f"**Последняя активность:** {stats.get('last_active', 'Неизвестно')}\n"
    text += f"**Присоединился:** {stats.get('joined_at', 'Неизвестно')}\n"

    await message.answer(text, parse_mode="Markdown")


# --- 2. МОДЕРАЦИЯ И САНКЦИИ ---


async def apply_sanction(message: types.Message, reason: str):
    """Централизованная функция для удаления, предупреждения и бана."""
    user = message.from_user

    # Игнорируем администраторов
    if user.id in config.ADMIN_IDS:
        return

    try:
        # Удаляем сообщение
        await message.delete()
    except TelegramBadRequest as e:
        logging.warning(f"Не удалось удалить сообщение от {user.id}: {e}")

    try:
        warn_count = await db.add_warning(user.id)

        # Логирование действия модерации
        logging.info(
            f"Модерация: user_id={user.id}, username={user.username}, "
            f"reason={reason}, warns={warn_count}/{config.MAX_WARNINGS}"
        )

        if warn_count >= config.MAX_WARNINGS:
            # БАН
            try:
                await bot.ban_chat_member(message.chat.id, user.id)
                await message.answer(
                    f"🚫 Пользователь {user.full_name} был забанен.\n"
                    f"Причина: {reason} ({warn_count}/{config.MAX_WARNINGS})."
                )
                # Сбрасываем счетчик после бана
                await db.reset_warnings(user.id)
            except TelegramBadRequest as e:
                logging.error(f"Не удалось забанить пользователя {user.id}: {e}")
                await message.answer(
                    f"⚠️ Не удалось забанить пользователя {user.full_name}. "
                    "Проверьте права бота."
                )
        else:
            # ПРЕДУПРЕЖДЕНИЕ
            await message.answer(
                f"⚠️ {user.full_name}, нарушение!\n"
                f"Причина: {reason}\n"
                f"Предупреждение {warn_count}/{config.MAX_WARNINGS}."
            )
    except Exception as e:
        logging.error(
            f"Не удалось применить санкции к {user.full_name} ({user.id}): {e}"
        )


@dp.message(F.text, IsGroupChat(), ~IsAdmin())
async def moderation_handler(message: types.Message):
    """Обработчик модерации: проверяет текст на ссылки и стоп-слова."""
    if not message.text:
        return

    text = message.text.lower()

    # 1. Анти-Реклама (улучшенный regex)
    url_regex = r"(?:https?://|t\.me/|@|www\.|[a-zA-Z0-9-]+\.[a-z]{2,})[^\s]*"
    if re.search(url_regex, text):
        await apply_sanction(message, "Реклама и ссылки запрещены")
        return

    # 2. Стоп-слова
    if bad_words_cache.contains(text):
        await apply_sanction(message, "Использование запрещенной лексики/агрессия")
        return


# --- 3. РЕАКЦИИ НА СОБЫТИЯ (Приветствие) ---


@dp.message(F.new_chat_members)
async def on_new_chat_members(message: types.Message):
    """Автоматическое приветствие новых участников."""

    # Удаляем системное сообщение о вступлении
    try:
        await message.delete()
    except TelegramBadRequest as e:
        logging.warning(f"Не удалось удалить системное сообщение: {e}")

    for user in message.new_chat_members:
        # Игнорируем самого себя и других ботов
        if user.id == bot.id or user.is_bot:
            continue

        welcome_message = (
            f"🎉 **Добро пожаловать, {user.full_name}!**\n\n"
            f"Обязательно изучи **Правила сообщества** перед началом общения.\n\n"
            f"❗️ Ознакомиться с Правилами: [Нажми сюда](https://t.me/your_rules_link)\n\n"
            f"Приятного общения!"
        )

        try:
            await message.answer(welcome_message, parse_mode="Markdown")
        except TelegramBadRequest as e:
            logging.error(f"Не удалось отправить приветствие: {e}")


# --- 4. ОБРАБОТЧИК ОШИБОК ---


@dp.errors()
async def error_handler(event, exception):
    """Глобальный обработчик ошибок."""
    logging.error(f"Необработанная ошибка: {exception}", exc_info=True)
    return True


# --- 5. ЗАПУСК ---


async def main():
    """Точка входа, инициализация и запуск polling."""

    # КРИТИЧЕСКИ ВАЖНО: загружаем кэш перед стартом
    try:
        count = await bad_words_cache.reload()
        if count == 0:
            logging.warning("⚠️ Список запрещенных слов пуст!")
    except Exception as e:
        logging.error(f"Не удалось загрузить кэш запрещенных слов: {e}")
        return

    # Отбрасываем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("🚀 Бот запущен и готов к работе!")
    logging.info(f"👮 Администраторы: {config.ADMIN_IDS}")
    logging.info(f"⚠️ Максимум предупреждений: {config.MAX_WARNINGS}")

    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logging.info("Получен сигнал остановки...")
    finally:
        await bot.session.close()
        logging.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Бот остановлен пользователем")
