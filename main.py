import asyncio
import requests
import time
import json
import os
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiohttp import web  # Добавили для "обмана" Render

# ================= НАСТРОЙКИ =================
TOKEN = "8061584127:AAHEw85svEYaASKwuUfT0XoQzUo5y4HTB4c" 
ADMIN_ID = 830148833 

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

# --- ФЕЙКОВЫЙ ВЕБ-СЕРВЕР ДЛЯ RENDER ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    # Render передает порт в переменной окружения PORT
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- ЛОГИКА БОТА ---
@dp.message(Command("add_match"))
async def cmd_add_match(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2: return await message.answer("Пример: `/add_match 258076`")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"📡 Анализирую матч #{m_id}...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0 Safari/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        winners, losers = [], []
        all_players = []
        
        tables = soup.find_all('table')
        for table in tables:
            is_win = "winner" in table.text.lower() or "победитель" in table.text.lower()
            links = table.find_all('a')
            for link in links:
                if '/dota/gamingprofile/' in str(link.get('href')):
                    p_nick = link.text.strip()
                    all_players.append(p_nick)
                    for name, nick in PLAYERS.items():
                        if nick.lower() == p_nick.lower():
                            if is_win: winners.append(name)
                            else: losers.append(name)

        winners, losers = list(set(winners)), list(set(losers))
        if winners and losers:
            pts_win, pts_lose = len(losers), len(winners)
            for w in winners: MANUAL_ADJUSTMENTS[w] += pts_win
            for l in losers: MANUAL_ADJUSTMENTS[l] -= pts_lose
            save_bonuses(MANUAL_ADJUSTMENTS)
            await status_msg.edit_text(f"✅ Матч #{m_id} засчитан!\n🏆 +{pts_win}: {winners}\n💀 -{pts_lose}: {losers}")
        else:
            p_list = ", ".join(all_players[:10])
            await status_msg.edit_text(f"❌ Свои не найдены.\nВижу ники: `{p_list}`")
    except Exception as e:
        await status_msg.edit_text(f"💥 Ошибка: {e}")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 **ТЕКУЩИЙ РЕЙТИНГ:**\n" + "⎯"*15 + "\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} **{n}**: `{s}`\n"
    await message.answer(text)

async def main():
    # Запускаем и сервер, и бота одновременно
    await asyncio.gather(start_web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
