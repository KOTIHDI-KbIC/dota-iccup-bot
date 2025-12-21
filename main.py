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
TOKEN = "8061584127:AAGHprsUOdUCXBE9yBEmWEjGmTKOlJGJh1s"
ADMIN_ID = 830148833 # ТВОЙ_ID_ТУТ

PLAYERS = {
    "Батр": "Ebu_O4karikov",
    "Дос": "KILL_YOU_NOOB",
    "Даур": "DAUR3N",
    "Кана": "KOTIHDI_KbIC",
    "Аба": "amandoser",
    "Райм": "N4GIBATEL"
}

BONUS_FILE = "bonuses.json"
HISTORY_FILE = "history.json"
STATS_FILE = "vs_stats.json"
STREAKS_FILE = "streaks.json"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# --- ФУНКЦИИ РАБОТЫ С ДАННЫМИ ---
def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: 
        json.dump(data, f, ensure_ascii=False, indent=4)

MANUAL_ADJUSTMENTS = load_data(BONUS_FILE, {name: 0 for name in PLAYERS})
processed_matches = load_data(HISTORY_FILE, [])
vs_stats = load_data(STATS_FILE, {name: {other: 0 for other in PLAYERS if other != name} for name in PLAYERS})
streaks = load_data(STREAKS_FILE, {name: 0 for name in PLAYERS})

def get_current_king():
    if not streaks: return None, 0
    vals = list(streaks.values())
    if not vals: return None, 0
    max_val = max(vals)
    leaders = [n for n, v in streaks.items() if v == max_val]
    if max_val >= 2 and len(leaders) == 1:
        return leaders[0], max_val
    return None, 0

async def process_match(m_id):
    m_id_str = str(m_id)
    if m_id_str in processed_matches: return False
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        t1_block = soup.find('div', class_='details-team-one')
        if not t1_block: return False
        t1_win = "win" in t1_block.get_text().lower()
        def get_names(block_class):
            block = soup.find('div', class_=block_class)
            found = []
            if not block: return found
            for link in block.find_all('a', href=True):
                if '/gamingprofile/' in link['href']:
                    nick = link['href'].split('/')[-1].replace('.html', '').lower()
                    for name, p_nick in PLAYERS.items():
                        if p_nick.lower() == nick: found.append(name)
            return list(set(found))
        p1, p2 = get_names('team-one'), get_names('team-two')
        if not p1 or not p2:
            processed_matches.append(m_id_str)
            save_data(HISTORY_FILE, processed_matches)
            return False
        winners, losers = (p1, p2) if t1_win else (p2, p1)
        pts_win, pts_lose = len(losers), len(winners)
        for w in winners:
            MANUAL_ADJUSTMENTS[w] = MANUAL_ADJUSTMENTS.get(w, 0) + pts_win
            streaks[w] = streaks.get(w, 0) + 1
            for l in losers:
                vs_stats[w][l] = vs_stats[w].get(l, 0) + 1
        for l in losers:
            MANUAL_ADJUSTMENTS[l] = MANUAL_ADJUSTMENTS.get(l, 0) - pts_lose
            streaks[l] = 0
        processed_matches.append(m_id_str)
        save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
        save_data(HISTORY_FILE, processed_matches)
        save_data(STREAKS_FILE, streaks)
        msg = f"🎯 **МАТЧ #{m_id} ЗАСЧИТАН!**\n🏆 Победители (+{pts_win}): {', '.join(winners)}\n💀 Проигравшие (-{pts_lose}): {', '.join(losers)}"
        await bot.send_message(ADMIN_ID, msg)
        return True
    except: return False

async def check_all(quiet=True):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0'}
    all_ids = []
    for name, nick in PLAYERS.items():
        try:
            r = requests.get(f"https://iccup.com/dota/gamingprofile/{nick}.html", headers=headers, timeout=15)
            ids = re.findall(r'details/(\d+)\.html', r.text)
            for m_id in ids:
                if m_id not in processed_matches and m_id not in all_ids: all_ids.append(m_id)
        except: continue
    if all_ids:
        all_ids = sorted([int(x) for x in all_ids])
        for m_id in all_ids:
            await process_match(m_id)
            await asyncio.sleep(1)
        if not quiet: await bot.send_message(ADMIN_ID, "✅ Проверка завершена.")
    elif not quiet: await bot.send_message(ADMIN_ID, "ℹ️ Новых игр не найдено. Проверка завершена.")

@dp.message(Command("start", "help"))
async def cmd_help(message: types.Message):
    await message.answer("🏆 `/rating` — Таблица\n📊 `/stats Имя` — Профиль\n🔍 `/check` — Поиск игр")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    king, val = get_current_king()
    text = "🏆 **РЕЙТИНГ:**\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} {n}: `{s}`\n"
    if king: text += f"\n👑 Король: {king} (🔥 {val} победы подряд)"
    await message.answer(text)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return await message.answer("Пример: `/stats Батр`")
    name = args[1].capitalize()
    if name not in PLAYERS: return await message.answer("Игрок не найден.")
    await message.answer(f"📊 **СТАТИСТИКА: {name}**\n\n💰 Очки: `{MANUAL_ADJUSTMENTS.get(name,0)}`\n🔥 Серия: `{streaks.get(name,0)}`")

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3: return
    name, amount = args[1].capitalize(), int(args[2])
    if name in PLAYERS:
        MANUAL_ADJUSTMENTS[name] += amount
        save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
        await message.answer(f"✅ {name}: `{MANUAL_ADJUSTMENTS[name]}`")

@dp.message(Command("check"))
async def cmd_manual_check(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🛰 Запускаю сканирование...")
    await check_all(quiet=False)

@dp.message(Command("reset_all"))
async def cmd_reset(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global processed_matches, MANUAL_ADJUSTMENTS, streaks
    processed_matches, streaks = [], {n: 0 for n in PLAYERS}
    MANUAL_ADJUSTMENTS = {n: 0 for n in PLAYERS}
    for f in [HISTORY_FILE, BONUS_FILE, STREAKS_FILE, STATS_FILE]:
        if os.path.exists(f): os.remove(f)
    await message.answer("🧹 База очищена.")

async def handle_ping(request): return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all, 'interval', minutes=15)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
