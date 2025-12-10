import asyncio
import logging
import re
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from config import config, get_admins
from db_client import db
from middlewares import ActivityMiddleware
from filters import IsAdmin, IsGroupChat, IsProtectedAdmin

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Подключение Middleware
dp.message.middleware(ActivityMiddleware())

# --- ГЛОБАЛЬНЫЙ КЭШ ---
BAD_WORDS_CACHE = []


async def reload_bad_words_cache():
    """Загрузка списка запрещенных слов из БД в оперативную память."""
    global BAD_WORDS_CACHE
    try:
        words = db.get_bad_words()
        BAD_WORDS_CACHE = words
        logging.info(f"Словарь обновлен. Загружено слов: {len(words)}")
    except Exception as e:
        logging.error(f"Ошибка обновления кэша: {e}")


# --- 1. АДМИНСКИЕ КОМАНДЫ ---


# Команда только для админов и только в ЛС с ботом
@dp.message(Command("reload"), IsProtectedAdmin())
async def cmd_reload(message: types.Message):
    """Обновляет список запрещенных слов (защищенная команда)."""
    await reload_bad_words_cache()
    await message.answer(
        f"✅ Список запрещенных слов обновлен! Всего: {len(BAD_WORDS_CACHE)}"
    )


# Команда для админов в группе (для создания мероприятий)
@dp.message(Command("event"), IsAdmin(), IsGroupChat())
async def cmd_create_event(message: types.Message):
    """Создает неанонимный опрос для организации мероприятия."""
    event_text = message.text.replace("/event", "").strip()
    if not event_text:
        await message.answer("Укажите название события. Пример: /event Кино")
        return

    await message.answer_poll(
        question=f"📅 {event_text}. Кто идет?",
        options=["Я иду! ✅", "Думаю 🤔", "Не иду ❌"],
        is_anonymous=False,
    )


@dp.message(Command("unwarn"), IsAdmin(), IsGroupChat())
async def cmd_unwarn(message: types.Message):
    """Снимает одно предупреждение с пользователя (по ответу на сообщение)."""
    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user

    if not target_user:
        return await message.answer(
            "⚠️ Команду `/unwarn` нужно использовать **в ответ** на сообщение пользователя."
        )

    if target_user.id in get_admins():
        return await message.answer(
            "❌ Нельзя снимать предупреждения с администраторов."
        )

    new_count = db.remove_warning(target_user.id)

    await message.answer(
        f"✅ С пользователя **{target_user.full_name}** снято одно предупреждение.\n"
        f"Текущее количество: **{new_count}**."
    )


# --- 2. МОДЕРАЦИЯ И САНКЦИИ ---


async def apply_sanction(message: types.Message, reason: str):
    """Централизованная функция для удаления, предупреждения и бана."""
    try:
        await message.delete()
        warn_count = db.add_warning(message.from_user.id)

        if warn_count >= 3:
            # БАН (Правило: 3 предупреждения = бан)
            await bot.ban_chat_member(message.chat.id, message.from_user.id)
            await message.answer(
                f"🚫 Пользователь {message.from_user.full_name} был забанен.\n"
                f"Причина: {reason} (3/3)."
            )
        else:
            # ПРЕДУПРЕЖДЕНИЕ
            await message.answer(
                f"⚠️ {message.from_user.full_name}, нарушение!\n"
                f"Причина: {reason}\n"
                f"Предупреждение {warn_count}/3."
            )
    except Exception as e:
        logging.error(f"Не удалось применить санкции: {e}")


@dp.message(F.text, IsGroupChat(), ~IsAdmin())
async def moderation_handler(message: types.Message):
    """Обработчик модерации: проверяет текст на ссылки и стоп-слова."""
    text = message.text.lower()

    # 1. Анти-Реклама (Правило 2.1)
    url_regex = r"(https?://|t\.me/|@)[^\s]+"
    if re.search(url_regex, text):
        await apply_sanction(message, "Реклама и ссылки запрещены.")
        return

    # 2. Стоп-слова (Правило 1.x)
    if any(word in text for word in BAD_WORDS_CACHE):
        await apply_sanction(message, "Использование запрещенной лексики/агрессия.")
        return


# --- 3. РЕАКЦИИ НА СОБЫТИЯ ---


@dp.message(F.new_chat_members)
async def on_new_chat_members(message: types.Message):
    """Автоматическое приветствие новых участников."""
    # Удаляем системное сообщение о вступлении
    try:
        await message.delete()
    except Exception:
        pass

    for user in message.new_chat_members:
        if user.id == bot.id:
            continue

        welcome_message = (
            f"🎉 **Добро пожаловать, {user.full_name}!**\n\n"
            f"Обязательно изучи **Правила сообщества** перед началом общения.\n\n"
            f"❗️ Ознакомиться с Правилами: [**Ваша ссылка на правила**]\n\n"
        )
        await message.answer(welcome_message, parse_mode="Markdown")


# --- 4. ЗАПУСК ---


async def main():
    """Точка входа, инициализация и запуск polling."""
    # Загружаем кэш перед стартом
    await reload_bad_words_cache()

    # Отбрасываем старые апдейты
    await bot.delete_webhook(drop_pending_updates=True)

    logging.info("🚀 Бот запущен и готов к работе!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
