import asyncio
import aiohttp
import random
import string
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- НАСТРОЙКИ ---
API_TOKEN = '8302811214:AAHmCSI0gTJYf0qV-WNgaPQHwLFAJVSSJrE'
API_URL = "https://api.mail.tm"

# Включаем логирование, чтобы видеть ошибки в панели сервера
logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Хранилище сессий (в оперативной памяти сервера)
user_sessions = {}

async def get_mail_address():
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_URL}/domains") as r:
                res = await r.json()
                domain = random.choice(res['hydra:member'])['domain']
            
            user = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
            email = f"{user}@{domain}"
            password = "Pass" + user
            
            async with session.post(f"{API_URL}/accounts", json={"address": email, "password": password}) as r:
                if r.status == 201:
                    async with session.post(f"{API_URL}/token", json={"address": email, "password": password}) as tr:
                        token_data = await tr.json()
                        return email, token_data['token']
        except Exception as e:
            logging.error(f"Ошибка создания почты: {e}")
            return None, None
    return None, None

async def fetch_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_URL}/messages", headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('hydra:member', [])
        except Exception as e:
            logging.error(f"Ошибка проверки писем: {e}")
    return []

# --- ДИЗАЙН КЛАВИАТУРЫ ---
def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать почту", callback_data="new")
    builder.button(text="📥 Проверить входящие", callback_data="wait")
    builder.adjust(1)
    return builder.as_markup()

# --- ОБРАБОТЧИКИ ---

@dp.message(Command("start"))
async def start(msg: types.Message):
    welcome = (
        "✨ **EasyReg: Сервис временных почт**\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "🛡 *Безопасная регистрация в один клик.*\n\n"
        "• Нажмите на адрес, чтобы скопировать.\n"
        "• Коды приходят автоматически.\n\n"
        "👇 *Выберите действие:* "
    )
    await msg.answer(welcome, reply_markup=main_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "new")
async def handle_new(call: types.CallbackQuery):
    await call.answer("🔎 Ищу чистый домен...")
    email, token = await get_mail_address()
    
    if email:
        user_sessions[call.from_user.id] = token
        ready = (
            "📧 **Ваш адрес готов:**\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"`{email}`\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "👆 *Нажми, чтобы скопировать.*\n\n"
            "💬 *Вставь его на сайте и нажми кнопку ниже.*"
        )
        await call.message.edit_text(ready, parse_mode="Markdown", reply_markup=main_kb())
    else:
        await call.answer("❌ Ошибка. Попробуйте еще раз.", show_alert=True)

@dp.callback_query(F.data == "wait")
async def handle_wait(call: types.CallbackQuery):
    token = user_sessions.get(call.from_user.id)
    if not token:
        return await call.answer("❌ Сначала создайте почту!", show_alert=True)
    
    await call.answer("📩 Проверяю ящик...")
    status_msg = await call.message.answer("⏳ **Ожидание сообщения...**")
    
    for _ in range(15):
        msgs = await fetch_messages(token)
        if msgs:
            m = msgs[0]
            letter = (
                "✉️ **Новое письмо!**\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"👤 **От:** `{m['from']['address']}`\n"
                f"📝 **Тема:** *{m['subject']}*\n"
                "━━━━━━━━━━━━━━━━━━\n"
                f"📥 **Текст:**\n\n`{m['intro']}`\n"
                "━━━━━━━━━━━━━━━━━━"
            )
            await status_msg.edit_text(letter, parse_mode="Markdown", reply_markup=main_kb())
            return
        await asyncio.sleep(4)
    
    await status_msg.edit_text("📭 **Писем пока нет.** Попробуйте снова через 30 секунд.", reply_markup=main_kb())

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())