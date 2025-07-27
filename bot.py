import configparser
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from datetime import datetime
from rate_limit import RateLimitMiddleware
from collections import defaultdict
from typing import DefaultDict


# Загрузка токена из config.ini
config = configparser.ConfigParser()
config.read('config_my.ini')
TOKEN = config['bot']['token']
ADMIN_CHAT_ID = int(config['bot']['admin_id'])
SPAM_WARNING_LIMIT = int(config['bot'].get('spam_warning_limit', 20))
SPAM_BLOCK_LIMIT = int(config['bot'].get('spam_block_limit', 200))
SPAM_INTERVAL_SECONDS = int(config['bot'].get('SPAM_INTERVAL_SECONDS', 3))

bot = Bot(token=TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(RateLimitMiddleware(
    interval_seconds=SPAM_INTERVAL_SECONDS,
    warning_limit=SPAM_WARNING_LIMIT,
    block_limit=SPAM_BLOCK_LIMIT,
    admin_chat_id=ADMIN_CHAT_ID
))


class JobSearchStates(StatesGroup):
    waiting_for_vacancy_link = State()
    waiting_for_resume = State()

class SupportStates(StatesGroup):
    collecting_messages = State()

keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
keyboard.add(
    KeyboardButton("🔹 Хочу получить рекомендацию"),
    KeyboardButton("🔹 Хочу рекомендовать кандидатов")
)
keyboard.add(
    KeyboardButton("🛠 Поддержка"),
    KeyboardButton("🔙 Вернуться в начало")
)

support_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
support_keyboard.add(KeyboardButton("✅ Отправить сообщение"))
support_keyboard.add(KeyboardButton("🔙 Вернуться в начало"))

user_daily_counts: DefaultDict[int, dict[str, object]] = defaultdict(
    lambda: {"count": 0, "last_seen": datetime.now()}
)
blocked_users = set()

# Приветственное сообщение
WELCOME_MESSAGE = (
    "👋 Привет! Это tap2work — платформа, где люди помогают друг другу быстрее трудоустраиваться через внутренние рекомендации.\n"
    "Хочешь попасть в компанию мечты? Отправь вакансию — и тебе помогут.\n"
    "Готов порекомендовать классного кандидата в свою компанию? Получай бонусы!\n\n"
    "📌 Мы **не собираем персональные данные**. Пожалуйста, **не указывай ФИО, email, номер телефона и другие личные данные**.\n"
    "Только информация о вакансии и твоём профессиональном опыте — этого достаточно.\n\n"
    "⚠️ Если бот работает некорректно, попробуй перезапустить его (выйди и снова нажми /start). "
    "Если не помогло — обратись в поддержку через кнопку ниже.\n\n"
    "👇 Выбери, с чего начнём:"
)

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.reply(WELCOME_MESSAGE, reply_markup=keyboard, parse_mode="Markdown")

@dp.message_handler(lambda message: message.text == "🔙 Вернуться в начало", state="*")
async def return_to_start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.reply(WELCOME_MESSAGE, reply_markup=keyboard)

@dp.message_handler(lambda message: message.text == "🛠 Поддержка")
async def start_support(message: types.Message, state: FSMContext):
    await state.set_state(SupportStates.collecting_messages)
    await state.update_data(messages=[])
    await message.reply(
        "Напиши, что не так или прикрепи файл. Можешь отправить несколько сообщений.\n\n"
        "Когда всё готово — нажми кнопку *Отправить сообщение* ниже 👇",
        reply_markup=support_keyboard,
        parse_mode="Markdown"
    )

@dp.message_handler(state=SupportStates.collecting_messages, content_types=types.ContentTypes.ANY)
async def collect_support_message(message: types.Message, state: FSMContext):
    if message.text and message.text.strip().lower() in {"отправить", "✅ отправить сообщение"}:
        data = await state.get_data()
        messages = data.get("messages", [])
        username = message.from_user.username or message.from_user.full_name

        await bot.send_message(ADMIN_CHAT_ID, f"📩 Обращение в поддержку от @{username}:")
        for msg in messages:
            if msg.text:
                await bot.send_message(ADMIN_CHAT_ID, f"📝 {msg.text}")
            elif msg.document:
                await bot.send_document(ADMIN_CHAT_ID, msg.document.file_id, caption=msg.caption or "")
            elif msg.photo:
                await bot.send_photo(ADMIN_CHAT_ID, msg.photo[-1].file_id, caption=msg.caption or "")

        await message.reply("✅ Запрос отправлен в поддержку. Спасибо!", reply_markup=keyboard)
        await prompt_to_continue(message)
        await state.finish()
    else:
        data = await state.get_data()
        messages = data.get("messages", [])
        messages.append(message)
        await state.update_data(messages=messages)

@dp.message_handler(lambda message: message.text == "🔹 Хочу получить рекомендацию")
async def handle_recommendation_request(message: types.Message):
    await message.reply(
    "Отлично! Пришли вакансию, которая тебя интересует — это может быть ссылка, профессия, описание или просто направление. "
    "Главное, чтобы было понятно, куда ты хочешь попасть 🙂"
    )
    await JobSearchStates.waiting_for_vacancy_link.set()

@dp.message_handler(state=JobSearchStates.waiting_for_vacancy_link, content_types=types.ContentType.TEXT)
async def collect_vacancy_description(message: types.Message, state: FSMContext):
    vacancy_info = message.text.strip()
    await state.update_data(vacancy_url=vacancy_info)

    await message.reply(
        "Теперь пришли короткое *обезличенное мини-резюме*.\n"
        "📌 Укажи свой опыт, ключевые навыки, стек, достижения — но **без ФИО и контактов**.\n\n"
        "❗️Это будет отправлено тем, кто сможет дать тебе рекомендацию.",
        parse_mode="Markdown"
    )
    await JobSearchStates.waiting_for_resume.set()

@dp.message_handler(lambda message: message.text == "🔹 Хочу рекомендовать кандидатов")
async def handle_candidate_offer(message: types.Message):
    username = message.from_user.username or message.from_user.full_name

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"👤 @{username} хочет рекомендовать кандидатов."
    )

    await message.reply("Спасибо! Мы свяжемся с тобой в течение 24 часов для помощи подбора кандидатов 🙌")
    await prompt_to_continue(message)

async def prompt_to_continue(message: types.Message):
    await message.reply(
        "📌 Ты можешь в любое удобное время вернуться и выбрать, чем хочешь помочь или в чём нуждаешься 👇",
        reply_markup=keyboard
    )

@dp.message_handler(state=JobSearchStates.waiting_for_resume, content_types=types.ContentType.TEXT)
async def handle_text_resume(message: types.Message, state: FSMContext):
    data = await state.get_data()
    vacancy_url = data.get("vacancy_url")
    resume_text = message.text.strip()
    username = message.from_user.username or message.from_user.full_name

    admin_message = (
        f"📩 Заявка на рекомендацию от @{username}:\n\n"
        f"📋 Вакансия: {vacancy_url}\n\n"
        f"📄 Мини-резюме:\n{resume_text}"
    )

    await bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_message)

    await message.reply("Спасибо! Мы передали твоё мини-резюме. С тобой свяжутся в течении 24 часов, чтобы дать рекомендацию.")
    await prompt_to_continue(message)
    await state.finish()

@dp.message_handler(content_types=types.ContentTypes.ANY)
async def fallback_handler(message: types.Message):
    await process_message(message)


async def process_message(message: types.Message):
    # Сюда можно вставить прежнюю логику из handle_unexpected_message
    username = message.from_user.username or message.from_user.full_name

    if message.text:
        await bot.send_message(ADMIN_CHAT_ID, f"📥 Сообщение от @{username}:\n\n{message.text}")
    elif message.document:
        await bot.send_document(ADMIN_CHAT_ID, message.document.file_id, caption=f"📥 Документ от @{username}")
    elif message.photo:
        await bot.send_photo(ADMIN_CHAT_ID, message.photo[-1].file_id, caption=f"📥 Фото от @{username}")
    else:
        await bot.send_message(ADMIN_CHAT_ID, f"📥 Неподдерживаемый тип сообщения от @{username}")

    await message.reply("Спасибо за сообщение! Если у тебя есть вопрос — мы его обязательно рассмотрим 👌")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
