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
TOKEN = "8061584127:AAHTy23uzphGgg8wWHVMcWOSfALy9phxnPE"
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

# Инициализация БД
MANUAL_ADJUSTMENTS = load_data(BONUS_FILE, {name: 0 for name in PLAYERS})
processed_matches = load_data(HISTORY_FILE, [])
vs_stats = load_data(STATS_FILE, {name: {other: 0 for other in PLAYERS if other != name} for name in PLAYERS})
streaks = load_data(STREAKS_FILE, {name: 0 for name in PLAYERS})

# Гарантируем, что все игроки есть в структурах
for name in PLAYERS:
    if name not in MANUAL_ADJUSTMENTS: MANUAL_ADJUSTMENTS[name] = 0
    if name not in streaks: streaks[name] = 0

def get_current_king():
    """Определяет единоличного Короля арены по серии побед"""
    if not streaks: return None, 0
    max_val = max(streaks.values())
    leaders = [n for n, v in streaks.items() if v == max_val]
    # Король только один и серия от 2 побед
    if max_val >= 2 and len(leaders) == 1:
        return leaders[0], max_val
    return None, 0

# --- ЛОГИКА ОБРАБОТКИ МАТЧЕЙ ---
async def process_match(m_id):
    if str(m_id) in processed_matches: return False
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        t1_win = "win" in soup.find('div', class_='details-team-one').get_text().lower()
        
        def get_names(block_class):
            block = soup.find
