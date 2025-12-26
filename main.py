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
TOKEN = "8061584127:AAEbh0BKI9DndQkXy_V7CIpBoS8xxtRw-FU"
ADMIN_ID = 830148833  # ВАШ TELEGRAM ID (цифрами)

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
USERS_FILE = "users.json"

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def load_data(file, default):
    if os.path.exists(file):
        try:
            with open(file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return default
    return default

def save_data(file, data):
    with open(file, 'w', encoding='utf-8') as f: 
        json.dump(data, f, ensure_ascii=False, indent=4)

# Загрузка данных
MANUAL_ADJUSTMENTS = load_data(BONUS_FILE, {name: 0 for name in PLAYERS})
processed_matches = load_data(HISTORY_FILE, [])
vs_stats = load_data(STATS_FILE, {name: {other: 0 for other in PLAYERS if other != name} for name in PLAYERS})
streaks = load_data(STREAKS_FILE, {name: 0 for name in PLAYERS})
user_ids = load_data(USERS_FILE, {}) # {Имя: ID_телеграм}

def get_current_king():
    if not streaks: return None, 0
    vals = list(streaks.values())
    max_val = max(vals) if vals else 0
    leaders = [n for n, v in streaks.items() if v == max_val]
    if max_val >= 2 and len(leaders) == 1:
        return leaders[0], max_val
    return None, 0

async def notify_players(winners, losers, m_id, pts_win, pts_lose):
    """Рассылка всем 6 игрокам: участникам — результат, остальным — подкол"""
    active_players = winners + losers
    
    msg_active = (f"🎯 **МАТЧ #{m_id} ЗАСЧИТАН!**\n\n"
                  f"🏆 Победители (+{pts_win}): {', '.join(winners)}\n"
                  f"💀 Проигравшие (-{pts_lose}): {', '.join(losers)}")
    
    msg_idle = (f"👀 **ТАМ ЗАМЕС БЕЗ ТЕБЯ!**\n\n"
                f"🎮 В катке #{m_id} рубились: {', '.join(active_players)}\n"
                f"А ты где потерялся? Залетай в следующую! 🚀")

    for name, chat_id in user_ids.items():
        try:
            if name in active_players:
                await bot.send_message(chat_id, msg_active)
            else:
                await bot.send_message(chat_id, msg_idle)
        except:
            pass # Если пользователь не нажал старт или заблочил бота

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
            MANUAL_ADJUSTMENTS[l] = MANUAL_ADJUSTMENTS.get(l, 0) - pts_lose
            streaks[l] = 0

        processed_matches.append(m_id_str)
        save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
        save_data(HISTORY_FILE, processed_matches)
        save_data(STREAKS_FILE, streaks)

        await notify_players(winners, losers, m_id, pts_win, pts_lose)
        return True
    except:
        return False

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
        await bot.send_message(ADMIN_ID, "✅ Проверка новых игр завершена.")
    elif not quiet:
        await bot.send_message(ADMIN_ID, "ℹ️ Новых игр не найдено.")

# --- КОМАНДЫ ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🏆 Привет! Чтобы получать уведомления в личку, напиши: `/start Имя` (например: `/start Батр`)")
        return

    name = args[1].capitalize()
    if name not in PLAYERS:
        await message.answer("❌ Тебя нет в списке участников (PLAYERS).")
        return

    if name not in user_ids and len(user_ids) >= 6:
        await message.answer("🚫 Лимит регистраций (6 человек) уже исчерпан.")
        return

    user_ids[name] = message.from_user.id
    save_data(USERS_FILE, user_ids)
    await message.answer(f"✅ {name}, ты в системе! Теперь я буду присылать тебе отчеты и уведомления о замесах.")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    king, val = get_current_king()
    text = "🏆 **РЕЙТИНГ:**\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} {n}: `{s}`\n"
    if king:
        text += f"\n👑 **{king}** (Серия побед: {val})"
    await message.answer(text)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    args = message.text.split()
    name = args[1].capitalize() if len(args) > 1 else ""
    if name not in PLAYERS: return await message.answer("Пример: `/stats Батр`")
    await message.answer(f"📊 **СТАТИСТИКА: {name}**\n💰 Очки: `{MANUAL_ADJUSTMENTS.get(name,0)}`\n🔥 Серия: `{streaks.get(name,0)}`")

@dp.message(Command("check"))
async def cmd_manual_check(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛰 Запускаю сканирование...")
        await check_all(quiet=False)

@dp.message(Command("clear_users"))
async def cmd_clear_users(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global user_ids
    user_ids = {}
    if os.path.exists(USERS_FILE): os.remove(USERS_FILE)
    await message.answer("🗑 Список регистраций полностью очищен.")

# --- ЗАПУСК ---
async def handle_ping(request): return web.Response(text="OK")

async def main():
    # Настройка веб-сервера для поддержки активности (Ping)
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app); await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    await web.TCPSite(runner, '0.0.0.0', port).start()

    # Планировщик проверки игр (раз в 1 минуту)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all, 'interval', minutes=1)
    scheduler.start()

    # Уведомление администратора о запуске
    try:
        count = len(user_ids)
        await bot.send_message(
            ADMIN_ID, 
            f"🚀 **Бот успешно запущен!**\n\n"
            f"📂 Данные загружены.\n"
            f"👥 Регистраций: `{count}/6`"
        )
    except: pass

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
