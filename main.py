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
TOKEN = "8061584127:AAFVhwpbP4kKwg1tAMY7ChE8KxeSUoxA6z4"
ADMIN_ID = 830148833  # Твой ID

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
    max_val = max(streaks.values())
    leaders = [n for n, v in streaks.items() if v == max_val]
    if max_val >= 2 and len(leaders) == 1:
        return leaders[0], max_val
    return None, 0

async def process_match(m_id):
    m_id_str = str(m_id)
    if m_id_str in processed_matches: return False
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
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
                MANUAL_ADJUSTMENTS[w] = MANUAL_ADJUSTMENTS.get(w, 0) + pts_win
                streaks[w] = streaks.get(w, 0) + 1
                for l in losers: vs_stats[w][l] = vs_stats[w].get(l, 0) + 1
            for l in losers:
                MANUAL_ADJUSTMENTS[l] = MANUAL_ADJUSTMENTS.get(l, 0) - pts_lose
                streaks[l] = 0
            
            new_king, new_val = get_current_king()
            processed_matches.append(m_id_str)
            
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
            save_data(HISTORY_FILE, processed_matches)
            save_data(STATS_FILE, vs_stats)
            save_data(STREAKS_FILE, streaks)

            msg = f"🎯 **Матч #{m_id} обработан!**\n\n"
            msg += f"🏆 Победили (+{pts_win}): {', '.join(winners)}\n"
            msg += f"💀 Проиграли (-{pts_lose}): {', '.join(losers)}\n"
            if old_king and old_king in losers: msg += f"\n☠️ **КОРОЛЬ ПОВЕРЖЕН!**\n{old_king} потерял корону.\n"
            elif new_king and new_king != old_king: msg += f"\n👑 **НОВЫЙ КОРОЛЬ: {new_king}** (серия: {new_val})\n"
            
            await bot.send_message(ADMIN_ID, msg)
            return True
    except: return False

async def check_all():
    print(">>> [LOG] Сканирование iCCup (3 последние игры)...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }
    
    for name, nick in PLAYERS.items():
        try:
            url = f"https://iccup.com/dota/gamingprofile/{nick}.html"
            # Принудительный запрос к внешнему адресу
            response = requests.get(url, headers=headers, timeout=20)
            
            if response.status_code != 200:
                print(f"    [ERR] Статус {response.status_code} для {name}")
                continue

            ids = re.findall(r'/dota/details/(\d+)\.html', response.text)
            if ids:
                unique_ids = []
                for mid in ids:
                    if mid not in unique_ids: unique_ids.append(mid)
                
                for m_id in unique_ids[:3]:
                    if m_id not in processed_matches:
                        print(f"    [NEW] Найдена игра {m_id} у {name}")
                        await process_match(m_id)
                        await asyncio.sleep(2)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"    [ERR] Ошибка у {name}: {e}")
            continue
    print(">>> [LOG] Сканирование завершено.")

# --- КОМАНДЫ ---
@dp.message(Command("start", "help"))
async def cmd_help(message: types.Message):
    text = "📖 **СПРАВКА:**\n" + "⎯"*15 + "\n"
    text += "📊 `/rating` — Таблица\n"
    text += "⚔️ `/versus` — Встречи\n"
    if message.from_user.id == ADMIN_ID:
        text += "\n🛠 **АДМИН:**\n"
        text += "🔍 `/check` — Начать поиск игр\n"
        text += "📝 `/stats Имя Очки` — Правка\n"
    await message.answer(text)

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
    text += f"👑 **Король: {king}** ({val} побед подряд!)\n" if king else "⚔️ Трон пустует\n"
    await message.answer(text)

@dp.message(Command("versus"))
async def cmd_versus(message: types.Message):
    text = "⚔️ **ЛИЧНЫЕ ВСТРЕЧИ:**\n" + "⎯"*15 + "\n"
    found = False
    for p, rivals in vs_stats.items():
        wins = [f"{r}: {c}" for r, c in rivals.items() if c > 0]
        if wins:
            found = True; text += f"👤 **{p}** обыграл: {', '.join(wins)}\n"
    await message.answer(text if found else "Истории встреч нет.")

@dp.message(Command("check"))
async def cmd_check(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("🔍 Запускаю поиск новых игр...")
    await check_all()
    await message.answer("✅ Проверка окончена.")

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 3: return
    name_in, val_raw = parts[1], parts[2]
    try:
        val = int(val_raw)
        target = next((n for n in PLAYERS if n.lower() == name_in.lower()), None)
        if target:
            MANUAL_ADJUSTMENTS[target] += val
            if val > 0: streaks[target] += 1
            elif val < 0: streaks[target] = 0
            save_data(BONUS_FILE, MANUAL_ADJUSTMENTS); save_data(STREAKS_FILE, streaks)
            await message.answer(f"✅ {target}: {val:+}. Итого: `{MANUAL_ADJUSTMENTS[target]}`")
    except: pass

async def handle_ping(request):
    return web.Response(text="Bot is Alive")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all, 'interval', minutes=15)
    scheduler.start()

    print(f"--- Бот запущен (Порт: {port}) ---")
    
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())


