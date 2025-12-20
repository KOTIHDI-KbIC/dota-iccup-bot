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
TOKEN = "В8061584127:AAHTy23uzphGgg8wWHVMcWOSfALy9phxnPE"
ADMIN_ID = 830148833 # Вставь свой ID

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
vs_stats = load_data(STATS_FILE, {name: {other: 0 for other in PLAYERS if other != name} for name in PLAYERS})
streaks = load_data(STREAKS_FILE, {name: 0 for name in PLAYERS})

for name in PLAYERS:
    if name not in MANUAL_ADJUSTMENTS: MANUAL_ADJUSTMENTS[name] = 0
    if name not in streaks: streaks[name] = 0

def get_current_king():
    if not streaks: return None, 0
    max_val = max(streaks.values())
    leaders = [n for n, v in streaks.items() if v == max_val]
    if max_val >= 2 and len(leaders) == 1:
        return leaders[0], max_val
    return None, 0

async def process_match(m_id):
    if str(m_id) in processed_matches: return False
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        t1_win_elem = soup.find('div', class_='details-team-one')
        if not t1_win_elem: return False
        t1_win = "win" in t1_win_elem.get_text().lower()
        
        def get_names(block_class):
            block = soup.find('div', class_=block_class)
            found = []
            if not block: return found
            for link in block.find_all('a', href=True):
                nick = link['href'].split('/')[-1].replace('.html', '').lower()
                for name, p_nick in PLAYERS.items():
                    if p_nick.lower() == nick: found.append(name)
            return list(set(found))

        p1, p2 = get_names('team-one'), get_names('team-two')
        winners, losers = (p1, p2) if t1_win else (p2, p1)

        if winners and losers:
            old_king, _ = get_current_king()
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
            
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
            save_data(HISTORY_FILE, processed_matches)
            save_data(STATS_FILE, vs_stats)
            save_data(STREAKS_FILE, streaks)

            msg = f"🎯 **Матч #{m_id} обработан!**\n\n"
            msg += f"🏆 Победили (+{pts_win}): {', '.join(winners)}\n"
            msg += f"💀 Проиграли (-{pts_lose}): {', '.join(losers)}\n"
            msg += "⎯"*15 + "\n"

            if old_king and old_king in losers:
                msg += f"☠️ **КОРОЛЬ ПОВЕРЖЕН!**\n{old_king} потерял корону. Трон пустует...\n"
            elif new_king and new_king != old_king:
                msg += f"📣 **НОВЫЙ КОРОЛЬ АРЕНЫ!**\n👑 **{new_king}** захватил трон (серия: {new_val})\n"
            elif old_king and not new_king:
                msg += f"⚔️ **БОРЬБА ЗА ВЛАСТЬ!**\nСерии сравнялись. Корона временно снята.\n"

            await bot.send_message(ADMIN_ID, msg)
            return True
        return False
    except Exception as e:
        print(f"Error parsing match {m_id}: {e}")
        return False

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    data = {n: MANUAL_ADJUSTMENTS.get(n, 0) for n in PLAYERS}
    sorted_s = sorted(data.items(), key=lambda x: x[1], reverse=True)
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
    found = False
    for p, rivals in vs_stats.items():
        wins = [f"{r}: {c}" for r, c in rivals.items() if c > 0]
        if wins:
            found = True
            text += f"👤 **{p}** побеждал: {', '.join(wins)}\n"
    await message.answer(text if found else "Истории встреч пока нет.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer(f"⛔️ Отказ. Твой ID: `{message.from_user.id}`")
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ Инструкция: `/stats Кана -6`.")
        return
    name_input, val_raw = parts[1], parts[2]
    try:
        val = int(val_raw)
        target = next((n for n in PLAYERS if n.lower() == name_input.lower()), None)
        if target:
            MANUAL_ADJUSTMENTS[target] += val
            if val > 0: streaks[target] += 1
            elif val < 0: streaks[target] = 0
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
            save_data(STREAKS_FILE, streaks)
            await message.answer(f"✅ **{target}**: {val:+}\n📊 В рейтинге: `{MANUAL_ADJUSTMENTS[target]}`\n🔥 Серия: `{streaks[target]}`")
        else:
            await message.answer(f"👤 Игрок '{name_input}' не найден.")
    except:
        await message.answer("❌ Ошибка: введите число.")

async def check_all():
    for name, nick in PLAYERS.items():
        try:
            r = requests.get(f"https://iccup.com/dota/gamingprofile/{nick}.html", timeout=10)
            ids = re.findall(r'/dota/details/(\d+)\.html', r.text)
            if ids and ids[0] not in processed_matches: await process_match(ids[0])
            await asyncio.sleep(5)
        except: continue

async def main():
    app = web.Application()
    app.router.add_get('/', lambda r: web.Response(text="Bot Alive"))
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all, 'interval', minutes=15)
    scheduler.start()
    print("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
