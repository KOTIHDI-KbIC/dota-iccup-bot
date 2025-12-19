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

# ================= НАСТРОЙКИ =================
TOKEN = "8061584127:AAHEw85svEYaASKwuUfT0XoQzUo5y4HTB4c" 
ADMIN_ID = 830148833 # Твой ID (узнай в @userinfobot)

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

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER (ЧТОБЫ НЕ ЗАСЫПАЛ) ---
async def handle(request):
    return web.Response(text="Bot is running!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

# --- ЛОГИКА ПАРСИНГА ---
@dp.message(Command("add_match"))
async def cmd_add_match(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    
    parts = message.text.split()
    if len(parts) < 2:
        return await message.answer("Использование: `/add_match ID` (например, /add_match 258076)")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"📡 Глубокий поиск в матче #{m_id}...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        html_content = r.text
        soup = BeautifulSoup(html_content, 'html.parser')
        
        winners, losers = [], []
        
        # Перебираем все таблицы на странице
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text().lower()
            # Проверяем, является ли эта таблица списком победителей
            is_winner_team = any(word in table_text for word in ["winner", "победитель", "win"])
            
            # Ищем ники из нашего списка внутри этой таблицы
            for name, nick in PLAYERS.items():
                # Ищем ник как отдельное слово в тексте таблицы
                if nick.lower() in table_text:
                    if is_winner_team:
                        winners.append(name)
                    else:
                        losers.append(name)

        # Очистка списков
        winners = list(set(winners))
        losers = list(set(losers))
        # Если игрок попал в оба списка (ошибка разметки), оставляем в победителях
        for w in winners:
            if w in losers: losers.remove(w)

        if winners and losers:
            pts_win, pts_lose = len(losers), len(winners)
            for w in winners: MANUAL_ADJUSTMENTS[w] += pts_win
            for l in losers: MANUAL_ADJUSTMENTS[l] -= pts_lose
            
            save_bonuses(MANUAL_ADJUSTMENTS)
            await status_msg.edit_text(
                f"✅ **Матч #{m_id} засчитан!**\n\n"
                f"🥇 Победили (+{pts_win}): {', '.join(winners)}\n"
                f"💀 Проиграли (-{pts_lose}): {', '.join(losers)}"
            )
        else:
            # Если не нашли, создаем файл отладки
            debug_path = "debug_page.html"
            with open(debug_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            
            await message.answer_document(
                types.FSInputFile(debug_path), 
                caption=f"❌ Свои не найдены в матче #{m_id}. Отправляю файл страницы для проверки."
            )
            await status_msg.delete()

    except Exception as e:
        await status_msg.edit_text(f"💥 Ошибка: {str(e)}")

@dp.message(Command("rating"))
async def cmd_rating(message: types.Message):
    sorted_s = sorted(MANUAL_ADJUSTMENTS.items(), key=lambda x: x[1], reverse=True)
    text = "🏆 **ТЕКУЩИЙ РЕЙТИНГ:**\n" + "⎯"*15 + "\n"
    for i, (n, s) in enumerate(sorted_s, 1):
        m = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else "🔹"
        text += f"{m} **{n}**: `{s}`\n"
    text += "⎯"*15 + "\nДобавить матч: `/add_match ID`"
    await message.answer(text)

@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    try:
        args = message.text.split()
        name, val = args[1], int(args[2])
        if name in MANUAL_ADJUSTMENTS:
            MANUAL_ADJUSTMENTS[name] += val
            save_bonuses(MANUAL_ADJUSTMENTS)
            await message.answer(f"✅ Обновлено: {name} {val}")
    except:
        await message.answer("Пример: `/stats Даур 5` или `/stats Даур -5`")

async def main():
    await asyncio.gather(start_web_server(), dp.start_polling(bot))

if __name__ == "__main__":
    asyncio.run(main())
