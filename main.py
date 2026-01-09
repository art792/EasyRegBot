import asyncio
import aiohttp
import random
import string
import logging
import os
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web

# --- НАСТРОЙКИ ---
API_TOKEN = os.getenv("BOT_TOKEN")
API_URL = "https://api.mail.tm"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_sessions = {}

# --- СЕРВЕР ДЛЯ ОБМАНА RENDER (чтобы не было Timed out) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЛОГИКА ПОЧТЫ ---
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
            logging.error(f"Mail error: {e}")
    return None, None

async def fetch_messages(token):
    headers = {"Authorization": f"Bearer {token}"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(f"{API_URL}/messages", headers=headers) as r:
                if r.status == 200:
                    data = await r.json()
                    return data.get('hydra:member', [])
        except: pass
    return []

def main_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Создать почту", callback_data="new")
    builder.button(text="📥 Проверить входящие", callback_data="wait")
    builder.adjust(1)
    return builder.as_markup()

@dp.message(Command("start"))
async def start(msg: types.Message):
    await msg.answer("✨ **EasyReg: Готов к работе!**", reply_markup=main_kb(), parse_mode="Markdown")

@dp.callback_query(F.data == "new")
async def handle_new(call: types.CallbackQuery):
    email, token = await get_mail_address()
    if email:
        user_sessions[call.from_user.id] = token
        await call.message.edit_text(f"📧 **Ваш адрес:**\n`{email}`", parse_mode="Markdown", reply_markup=main_kb())
    else:
        await call.answer("❌ Ошибка сервиса")

@dp.callback_query(F.data == "wait")
async def handle_wait(call: types.CallbackQuery):
    token = user_sessions.get(call.from_user.id)
    if not token: return await call.answer("❌ Создайте почту!")
    
    await call.answer("📩 Проверяю...")
    msgs = await fetch_messages(token)
    if msgs:
        m = msgs[0]
        await call.message.answer(f"✉️ **От:** `{m['from']['address']}`\n📝 **Тема:** {m['subject']}\n📥 `{m['intro']}`", parse_mode="Markdown")
    else:
        await call.answer("📭 Писем нет", show_alert=True)

async def main():
    await start_web_server()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
