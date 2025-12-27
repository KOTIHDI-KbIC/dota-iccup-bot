import asyncio
import requests
import os
import json
import re
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeChat
from aiohttp import web
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# ================= НАСТРОЙКИ =================
TOKEN = "8061584127:AAEbh0BKI9DndQkXy_V7CIpBoS8xxtRw-FU"
ADMIN_ID = 830148833  # Ваш ID (цифрами)

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
DAILY_FILE = "daily_stats.json" # Новый файл для сессий

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="Markdown"))
dp = Dispatcher()

# --- ЗАГРУЗКА ДАННЫХ ---
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
user_ids = load_data(USERS_FILE, {})
daily_points = load_data(DAILY_FILE, {name: 0 for name in PLAYERS}) # Очки сессии

def get_current_king():
    if not streaks: return None, 0
    vals = list(streaks.values())
    if not vals: return None, 0
    max_val = max(vals)
    leaders = [n for n, v in streaks.items() if v == max_val]
    if max_val >= 2 and len(leaders) == 1:
        return leaders[0], max_val
    return None, 0

async def notify_players(winners, losers, m_id, pts_win, pts_lose):
    active_players = winners + losers
    msg_active = (f"🎯 **МАТЧ #{m_id} ЗАСЧИТАН!**\n\n"
                  f"🏆 Победители (+{pts_win}): {', '.join(winners)}\n"
                  f"💀 Проигравшие (-{pts_lose}): {', '.join(losers)}")
    msg_idle = (f"👀 **ТАМ ЗАМЕС БЕЗ ТЕБЯ!**\n\n"
                f"🎮 В катке #{m_id} рубились: {', '.join(active_players)}\n"
                f"А ты где потерялся? 🚀")

    for name, chat_id in user_ids.items():
        try:
            if name in active_players: await bot.send_message(chat_id, msg_active)
            else: await bot.send_message(chat_id, msg_idle)
        except: pass

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

        # Обновляем ОБЩИЙ рейтинг и ДНЕВНУЮ сессию
        for w in winners:
            MANUAL_ADJUSTMENTS[w] += pts_win
            daily_points[w] = daily_points.get(w, 0) + pts_win
            streaks[w] = streaks.get(w, 0) + 1
            for l in losers: vs_stats[w][l] = vs_stats[w].get(l, 0) + 1
        for l in losers:
            MANUAL_ADJUSTMENTS[l] -= pts_lose
            daily_points[l] = daily_points.get(l, 0) - pts_lose
            streaks[l] = 0

        processed_matches.append(m_id_str)
        save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
        save_data(HISTORY_FILE, processed_matches)
        save_data(STREAKS_FILE, streaks)
        save_data(STATS_FILE, vs_stats)
        save_data(DAILY_FILE, daily_points)

        await notify_players(winners, losers, m_id, pts_win, pts_lose)
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
        await bot.send_message(ADMIN_ID, "✅ Проверка завершена.")
    elif not quiet:
        await bot.send_message(ADMIN_ID, "ℹ️ Новых игр нет.")

# --- КОМАНДЫ ---
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("🏆 Напиши: `/start Имя` (например: `/start Батр`)")
        return
    name = args[1].capitalize()
    if name not in PLAYERS:
        await message.answer("❌ Тебя нет в списке участников.")
        return
    if name not in user_ids and len(user_ids) >= 6:
        await message.answer("🚫 Лимит 6 человек исчерпан.")
        return
    user_ids[name] = message.from_user.id
    save_data(USERS_FILE, user_ids)
    await message.answer(f"✅ {name}, ты в системе! Ожидай уведомлений.")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    king, val = get_current_king()
    text = "🏆 **ОБЩИЙ РЕЙТИНГ:**\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} {n}: `{s}`\n"
    if king:
        if val >= 10: status = "🏆 ЛЕГЕНДА!"
        elif val >= 5: status = "💎 Неудержимый!"
        elif val >= 3: status = "⚡️ В ударе!"
        else: status = "🔥 Хорош!"
        text += f"\n👑 **{king}** ({status})"
    await message.answer(text)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    args = message.text.split()
    name = args[1].capitalize() if len(args) > 1 else ""
    if name not in PLAYERS: return await message.answer("Пример: `/stats Батр`")
    await message.answer(f"📊 **СТАТИСТИКА: {name}**\n💰 Очки: `{MANUAL_ADJUSTMENTS.get(name,0)}`\n🔥 Серия: `{streaks.get(name,0)}`")

# --- КОМАНДЫ СЕССИИ ---
@dp.message(Command("session_start"))
async def cmd_sess_start(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global daily_points
    daily_points = {name: 0 for name in PLAYERS}
    save_data(DAILY_FILE, daily_points)
    await message.answer("🚀 **Игровой вечер начался!**\nДневной рейтинг сброшен. Погнали! 🔥")

@dp.message(Command("session_stats"))
async def cmd_sess_stats(message: types.Message):
    sorted_d = sorted(daily_points.items(), key=lambda x: x[1], reverse=True)
    text = "📅 **РЕЗУЛЬТАТЫ ЗА СЕГОДНЯ:**\n\n"
    for i, (n, s) in enumerate(sorted_d, 1):
        smile = "🔥" if s > 0 else "📉" if s < 0 else "⏳"
        text += f"{i}. {n}: `{s}` {smile}\n"
    await message.answer(text)

# --- АДМИН КОМАНДЫ ---
@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    if not user_ids: return await message.answer("Список пуст.")
    text = "👥 **ЗАРЕГИСТРИРОВАНЫ:**\n"
    for n, i in user_ids.items(): text += f"• {n} (ID: `{i}`)\n"
    await message.answer(text)

@dp.message(Command("add"))
async def cmd_add(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) < 3: return await message.answer("Пример: `/add Батр 10`")
    name, amount = args[1].capitalize(), int(args[2])
    if name in PLAYERS:
        MANUAL_ADJUSTMENTS[name] += amount
        save_data(BONUS_FILE, MANUAL_ADJUSTMENTS)
        await message.answer(f"✅ {name}: `{MANUAL_ADJUSTMENTS[name]}`")

@dp.message(Command("check"))
async def cmd_manual_check(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("🛰 Сканирую...")
        await check_all(quiet=False)

@dp.message(Command("reset_all"))
async def cmd_reset(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    global processed_matches, MANUAL_ADJUSTMENTS, streaks, user_ids, daily_points
    processed_matches, user_ids = [], {}
    MANUAL_ADJUSTMENTS = {n: 0 for n in PLAYERS}
    streaks = {n: 0 for n in PLAYERS}
    daily_points = {n: 0 for n in PLAYERS}
    for f in [HISTORY_FILE, BONUS_FILE, STREAKS_FILE, STATS_FILE, USERS_FILE, DAILY_FILE]:
        if os.path.exists(f): os.remove(f)
    await message.answer("☢️ **ВСЯ БАЗА ОБНУЛЕНА!**")

# --- УПРАВЛЕНИЕ МЕНЮ ---
async def set_main_menu(bot: Bot):
    # Для всех
    user_commands = [
        BotCommand(command="rating", description="🏆 Общий рейтинг"),
        BotCommand(command="session_stats", description="📅 Результаты за сегодня"),
        BotCommand(command="stats", description="📊 Моя статистика"),
        BotCommand(command="start", description="🔑 Регистрация")
    ]
    await bot.set_my_commands(user_commands)
    # Для тебя
    admin_commands = user_commands + [
        BotCommand(command="session_start", description="🆕 Начать новую сессию"),
        BotCommand(command="users", description="👥 Кто зарегистрирован"),
        BotCommand(command="check", description="🔍 Поиск новых игр"),
        BotCommand(command="add", description="💰 Изменить очки"),
        BotCommand(command="reset_all", description="☢️ СБРОСИТЬ ВСЁ")
    ]
    try: await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
    except: pass

async def handle_ping(request): return web.Response(text="OK")

async def main():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()
    
    await set_main_menu(bot)
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_all, 'interval', minutes=1)
    scheduler.start()
    
    try: await bot.send_message(ADMIN_ID, f"🚀 Бот запущен!\n👥 В базе: {len(user_ids)}/6")
    except: pass
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
