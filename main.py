import asyncio
import requests
import time
import json
import os
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiohttp import web

# ================= НАСТРОЙКИ =================
TOKEN = "8061584127:AAHEw85svEYaASKwuUfT0XoQzUo5y4HTB4c" 
ADMIN_ID = 830148833 # Твой ID

PLAYERS = {
    "Батр": "Ebu_O4karikov",
    "Дос": "KILL_YOU_NOOB",
    "Даур": "DAUR3N",
    "Кана": "KOTIHDI_KbIC",
    "Аба": "amandoser",
    "Райм": "N4GIBATEL"
}

BONUS_FILE = "bonuses.txt"
# =============================================

def load_bonuses():
    if os.path.exists(BONUS_FILE):
        try:
            with open(BONUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {name: 0 for name in PLAYERS}
    return {name: 0 for name in PLAYERS}

def save_bonuses(bonuses):
    with open(BONUS_FILE, 'w', encoding='utf-8') as f:
        json.dump(bonuses, f, ensure_ascii=False)

MANUAL_ADJUSTMENTS = load_bonuses()
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot status: Online")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЛОГИКА ПАРСИНГА МАТЧА ---
@dp.message(Command("add_match"))
async def cmd_add_match(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Использование: `/add_match ID` (например, /add_match 258076)")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"🔍 Парсинг матча #{m_id} через профили...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return await status_msg.edit_text(f"❌ iCCup вернул ошибку {r.status_code}")

        soup = BeautifulSoup(r.text, 'html.parser')
        winners, losers = [], []
        
        # Ищем все ссылки на профили игроков
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href'].lower()
            if '/dota/gamingprofile/' in href:
                # Извлекаем ник из ссылки: /dota/gamingprofile/NICK.html -> NICK
                found_nick = href.split('/')[-1].replace('.html', '').strip()
                
                # Ищем, в какой таблице находится эта ссылка
                parent_table = link.find_parent('table')
                if parent_table:
                    # Проверяем, есть ли в этой таблице или её заголовке слово Winner
                    table_text = parent_
