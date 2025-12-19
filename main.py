import asyncio
import requests
import time
import json
import os
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

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

@dp.message(Command("add_match"))
async def cmd_add_match(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2: return await message.answer("Пример: `/add_match 258076`")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"📡 Соединяюсь с iCCup (Матч #{m_id})...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0 Safari/537.36'}
    
    try:
        # Прямой запрос БЕЗ прокси
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return await status_msg.edit_text(f"❌ Ошибка {r.status_code}. iCCup не пускает.")

        soup = BeautifulSoup(r.text, 'html.parser')
        winners, losers = [], []
        tables = soup.find_all('table')
        
        for table in tables:
            is_winning_team = "winner" in table.text.lower() or "победитель" in table.text.lower()
            rows = table.find_all('tr')
            for row in rows:
                row_text = row.text.lower()
                for name, nick in PLAYERS.items():
                    if nick.lower() in row_text:
                        if is_winning_team: winners.append(name)
                        else: losers.append(name)

        winners, losers = list(set(winners)), list(set(losers))
        if winners and losers:
            for w in winners: MANUAL_ADJUSTMENTS[w] += len(losers)
            for l in losers: MANUAL_ADJUSTMENTS[l] -= len(winners)
            save_bonuses(MANUAL_ADJUSTMENTS)
            await status_msg.edit_text(f"✅ Матч #{m_id} засчитан!\n🏆 Победили: {winners}\n💀 Проиграли: {losers}")
        else:
            await status_msg.edit_text("❌ В этом матче не было 'замеса' своих.")
    except Exception as e:
        await status_msg.edit_text(f"💥 Ошибка: {e}")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 **ТЕКУЩИЙ РЕЙТИНГ:**\n" + "⎯" * 15 + "\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} **{n}**: `{s}`\n"
    text += "⎯" * 15 + "\n`/add_match ID`"
    await message.answer(text)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())