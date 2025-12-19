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

# ================= НАСТРОЙКИ (ПРОВЕРЬ ИХ!) =================
TOKEN = "8061584127:AAHEw85svEYaASKwuUfT0XoQzUo5y4HTB4c" 
ADMIN_ID = 830148833 # Твой ID из телеграма

PLAYERS = {
    "Батр": "Ebu_O4karikov",
    "Дос": "KILL_YOU_NOOB",
    "Даур": "DAUR3N",
    "Кана": "KOTIHDI_KbIC",
    "Аба": "amandoser",
    "Райм": "N4GIBATEL"
}

BONUS_FILE = "bonuses.txt"
# ==========================================================

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

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (ЧТОБЫ НЕ ВЫКЛЮЧАЛСЯ) ---
async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЛОГИКА ОБРАБОТКИ МАТЧА ---
@dp.message(Command("add_match"))
async def cmd_add_match(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2: 
        return await message.answer("Пример: `/add_match 258076`")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"📡 Сканирую матч #{m_id}...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0 Safari/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return await status_msg.edit_text(f"❌ Ошибка {r.status_code} на iCCup.")

        soup = BeautifulSoup(r.text, 'html.parser')
        winners, losers = [], []

        # Находим обе таблицы (Sentinel и Scourge)
        tables = soup.find_all('table')
        for table in tables:
            # Проверяем, победила ли эта команда
            table_text = table.text.lower()
            is_winner_table = "winner" in table_text or "победитель" in table_text
            
            # Ищем наших игроков в строках этой таблицы
            rows = table.find_all('tr')
            for row in rows:
                row_txt = row.text.lower()
                for name, nick in PLAYERS.items():
                    if nick.lower() in row_txt:
                        if is_winner_table: winners.append(name)
                        else: losers.append(name)

        # Чистим списки
        winners = list(set(winners))
        losers = list(set(losers))
        for w in winners:
            if w in losers: losers.remove(w)

        if winners and losers:
            pts_win, pts_lose = len(losers), len(winners)
            for w in winners: MANUAL_ADJUSTMENTS[w] += pts_win
            for l in losers: MANUAL_ADJUSTMENTS[l] -= pts_lose
            
            save_bonuses(MANUAL_ADJUSTMENTS)
            await status_msg.edit_text(
                f"✅ **Матч #{m_id} засчитан!**\n\n"
                f"🏆 Победили (+{pts_win}): {', '.join(winners)}\n"
                f"💀 Проиграли (-{pts_lose}): {', '.join(losers)}"
            )
        else:
            await status_msg.edit_text(f"❌ Игроки не найдены или в матче не было противостояния 'свои против своих'.")
            
    except Exception as e:
        await status_msg.edit_text(f"💥 Ошибка: {e}")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 **ТЕКУЩИЙ РЕЙТИНГ:**\n" + "⎯"*15 + "\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} **{n}**: `{s}`\n"
    text += "⎯"*15 + "\nЧтобы добавить: `/add_match ID`"
    await message.answer(text)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, name, val = message.text.split()
        if name in MANUAL_ADJUSTMENTS:
            MANUAL_ADJUSTMENTS[name] += int(val)
            save_bonuses(MANUAL_ADJUSTMENTS)
            await message.answer(f"✅ Для {name} внесено {val}")
    except: await message.answer("Пример: /stats Даур +5")

async def main():
    # Запускаем сервер для Render и бота
    await asyncio.gather(start_web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
