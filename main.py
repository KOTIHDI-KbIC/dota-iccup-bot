import asyncio
import requests
import os
import json
import re
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= НАСТРОЙКИ =================
TOKEN = "В8061584127:AAHEw85svEYaASKwuUfT0XoQzUo5y4HTB4c"
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
HISTORY_FILE = "history.json" # Храним ID всех обработанных матчей
# =============================================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

def load_data(file, default):
    if os.path.exists(file):
        with open(file, 'r', encoding='utf-8') as f: return json.load(f)
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)

MANUAL_ADJUSTMENTS = load_data(BONUS_FILE, {name: 0 for name in PLAYERS})
processed_matches = load_data(HISTORY_FILE, [])

async def process_match(m_id, is_auto=False):
    if m_id in processed_matches: return False
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        t1_block = soup.find('div', class_='team-one')
        t2_block = soup.find('div', class_='team-two')
        t1_status_div = soup.find('div', class_='details-team-one')
        
        t1_win = False
        if t1_status_div:
            mark = t1_status_div.find('div', class_='meta-mark')
            if mark and 'win' in mark.get_text().lower(): t1_win = True

        def get_players_from_block(block):
            found = []
            if not block: return found
            links = block.find_all('a', href=True)
            for link in links:
                href_nick = link['href'].split('/')[-1].replace('.html', '').lower()
                for name, nick in PLAYERS.items():
                    if nick.lower() == href_nick: found.append(name)
            return list(set(found))

        p1, p2 = get_players_from_block(t1_block), get_players_from_block(t2_block)
        winners, losers = (p1, p2) if t1_win else (p2, p1)

        if winners and losers:
            pts_win, pts_lose = len(losers), len(winners)
            for w in winners: MANUAL_ADJUSTMENTS[w] += pts_win
            for l in losers: MANUAL_ADJUSTMENTS[l] -= pts_lose
            
            processed_matches.append(m_id)
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
            save_data(HISTORY_FILE, processed_matches)
            
            text = f"🎯 **Обнаружен новый матч #{m_id}!**\n\n"
            text += f"🏆 Победили (+{pts_win}): {', '.join(winners)}\n"
            text += f"💀 Проиграли (-{pts_lose}): {', '.join(losers)}"
            await bot.send_message(ADMIN_ID, text)
            return True
        return False
    except Exception as e:
        print(f"Ошибка парсинга матча {m_id}: {e}")
        return False

async def check_all_players():
    # Проверяем историю каждого игрока по очереди
    for display_name, nick in PLAYERS.items():
        url = f"https://iccup.com/dota/gamingprofile/{nick}.html"
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            # Ищем ссылки вида /dota/details/12345.html
            match_ids = re.findall(r'/dota/details/(\d+)\.html', r.text)
            if match_ids:
                # Берем только самый свежий матч игрока
                latest = match_ids[0]
                if latest not in processed_matches:
                    await process_match(latest, is_auto=True)
            await asyncio.sleep(2) # Пауза 2 сек, чтобы iCCup не забанил за спам
        except: continue

# --- КОМАНДЫ ---
@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 **ТЕКУЩИЙ РЕЙТИНГ:**\n" + "⎯"*15 + "\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        text += f"{i}. **{n}**: `{s}`\n"
    await message.answer(text)

@dp.message(Command("add_match"))
async def cmd_manual(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    m_id = "".join(filter(str.isdigit, message.text))
    if m_id:
        if await process_match(m_id):
            await message.answer(f"✅ Матч {m_id} добавлен вручную.")
        else:
            await message.answer("❌ Матч уже есть в базе или там нет 'замеса'.")

# --- ЗАПУСК ---
async def main():
    # Фейк сервер для Render
    app = web.Application(); app.router.add_get('/', lambda r: web.Response(text="OK"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()
    
    # Проверка раз в 15 минут
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all_players, 'interval', minutes=15)
    scheduler.start()
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
