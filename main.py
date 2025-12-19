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
    if len(parts) < 2: return await message.answer("Пример: `/add_match 258076`")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"📡 Анализ текста страницы #{m_id}...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        full_text = r.text
        soup = BeautifulSoup(full_text, 'html.parser')
        
        winners, losers = [], []
        # Проверяем наличие ваших ников просто в сыром тексте страницы
        for name, nick in PLAYERS.items():
            if nick.lower() in full_text.lower():
                # Если ник найден, пытаемся понять, в какой он команде
                # Ищем ближайшее упоминание Winner/Loser
                player_element = soup.find(string=lambda t: nick.lower() in t.lower())
                if player_element:
                    parent_table = player_element.find_parent('table')
                    if parent_table:
                        is_win = "winner" in parent_table.get_text().lower()
                        if is_win: winners.append(name)
                        else: losers.append(name)

        winners, losers = list(set(winners)), list(set(losers))
        
        if winners and losers:
            pts_win, pts_lose = len(losers), len(winners)
            for w in winners: MANUAL_ADJUSTMENTS[w] += pts_win
            for l in losers: MANUAL_ADJUSTMENTS[l] -= pts_lose
            save_bonuses(MANUAL_ADJUSTMENTS)
            await status_msg.edit_text(f"✅ Матч #{m_id} засчитан!\n🏆 Победили: {winners}\n💀 Проиграли: {losers}")
        else:
            # Если не нашли, присылаем отладочный файл
            with open("debug.html", "w", encoding="utf-8") as f:
                f.write(full_text)
            
            from telegram import InputFile
            await message.answer_document(types.FSInputFile("debug.html"), caption="❌ Игроки не найдены. Посмотри этот файл, виден ли там твой ник?")
            await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"💥 Ошибка: {e}")
