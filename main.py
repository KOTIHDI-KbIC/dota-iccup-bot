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
TOKEN = "8061584127:AAEU6ngT1FFD4D2eBpyhI1CSLZaqEI1wgOg"
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
HISTORY_FILE = "history.json"
STATS_FILE = "vs_stats.json"
STREAKS_FILE = "streaks.json"
# =============================================

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

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
vs_stats = load_data(STATS_FILE, {})
streaks = load_data(STREAKS_FILE, {name: 0 for name in PLAYERS})

# Инициализация структур
for name in PLAYERS.keys():
    if name not in vs_stats: vs_stats[name] = {other: 0 for other in PLAYERS if other != name}
    if name not in streaks: streaks[name] = 0

def get_current_king():
    max_val = max(streaks.values())
    count = list(streaks.values()).count(max_val)
    if max_val >= 2 and count == 1:
        return next(n for n, v in streaks.items() if v == max_val), max_val
    return None, 0

async def process_match(m_id, is_auto=False):
    if str(m_id) in processed_matches: return False
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        t1_block = soup.find('div', class_='team-one')
        t2_block = soup.find('div', class_='team-two')
        t1_win = "win" in soup.find('div', class_='details-team-one').get_text().lower()

        def get_players(block):
            found = []
            if not block: return found
            for link in block.find_all('a', href=True):
                nick = link['href'].split('/')[-1].replace('.html', '').lower()
                for name, p_nick in PLAYERS.items():
                    if p_nick.lower() == nick: found.append(name)
            return list(set(found))

        p1, p2 = get_players(t1_block), get_players(t2_block)
        winners, losers = (p1, p2) if t1_win else (p2, p1)

        if winners and losers:
            old_king, _ = get_current_king() # Запоминаем, кто был королем
            
            pts_win, pts_lose = len(losers), len(winners)
            for w in winners: 
                MANUAL_ADJUSTMENTS[w] += pts_win
                streaks[w] += 1
                for l in losers: vs_stats[w][l] = vs_stats[w].get(l, 0) + 1
            
            for l in losers: 
                MANUAL_ADJUSTMENTS[l] -= pts_lose
                streaks[l] = 0
            
            new_king, new_val = get_current_king()
            
            processed_matches.append(str(m_id))
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS); save_data(HISTORY_FILE, processed_matches)
            save_data(STATS_FILE, vs_stats); save_data(STREAKS_FILE, streaks)
            
            # Формируем отчет
            text = f"🎯 **Матч #{m_id} обработан!**\n\n"
            text += f"🏆 Победили (+{pts_win}): {', '.join(winners)}\n"
            text += f"💀 Проиграли (-{pts_lose}): {', '.join(losers)}\n"
            text += "⎯"*15 + "\n"
            
            # Логика уведомлений о короне
            if old_king and old_king in losers:
                text += f"☠️ **КОРОЛЬ ПОВЕРЖЕН!**\n{old_king} потерял корону. Трон пустует...\n"
            elif new_king and new_king != old_king:
                text += f"📣 **НОВЫЙ КОРОЛЬ АРЕНЫ!**\n👑 **{new_king}** захватил трон (серия: {new_val})\n"
            elif old_king and not new_king and any(streaks[w] == streaks.get(old_king, 0) for w in winners if w != old_king):
                text += f"⚔️ **БОРЬБА ЗА ВЛАСТЬ!**\nЛидеры сравнялись. Корона временно снята.\n"

            await bot.send_message(ADMIN_ID, text)
            return True
        return False
    except: return False

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    king, val = get_current_king()
    
    text = "🏆 **ТЕКУЩИЙ РЕЙТИНГ:**\n" + "⎯"*15 + "\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} **{n}**: `{s}`\n"
    
    text += "⎯"*15 + "\n"
    text += f"👑 **Король арены: {king}** ({val} побед подряд!)\n" if king else "⚔️ **Претендентов на корону пока нет**\n"
    await message.answer(text)

@dp.message(Command("versus"))
async def cmd_versus(message: types.Message):
    text = "⚔️ **ЛИЧНЫЕ ВСТРЕЧИ:**\n" + "⎯"*15 + "\n"
    for player, rivals in vs_stats.items():
        wins = [f"{r}: {c}" for r, c in rivals.items() if c > 0]
        if wins: text += f"👤 **{player}** побеждал: {', '.join(wins)}\n"
    await message.answer(text if "👤" in text else "Истории встреч нет.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        _, n_in, v = message.text.split()
        target = next((n for n in PLAYERS if n.lower() == n_in.lower()), None)
        if target:
            MANUAL_ADJUSTMENTS[target] += int(v)
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
            await message.answer(f"✅ **{target}**: {v}. Итого: `{MANUAL_ADJUSTMENTS[target]}`")
    except: pass

async def check_all_players():
    for name, nick in PLAYERS.items():
        try:
            r = requests.get(f"https://iccup.com/dota/gamingprofile/{nick}.html", timeout=10)
            ids = re.findall(r'/dota/details/(\d+)\.html', r.text)
            if ids and ids[0] not in processed_matches: await process_match(ids[0], True)
            await asyncio.sleep(3)
        except: continue

async def main():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot Active"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all_players, 'interval', minutes=15)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
