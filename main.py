@dp.message(Command("add_match"))
async def cmd_add_match(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    parts = message.text.split()
    if len(parts) < 2: return await message.answer("Пример: `/add_match 258076`")
    
    m_id = "".join(filter(str.isdigit, parts[1]))
    status_msg = await message.answer(f"📡 Проверяю матч #{m_id}...")
    
    url = f"https://iccup.com/dota/details/{m_id}.html"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/119.0.0.0 Safari/537.36'}
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        
        winners, losers = [], []
        all_players_in_match = [] # Список для диагностики
        
        tables = soup.find_all('table')
        for table in tables:
            is_winning_team = "winner" in table.text.lower() or "победитель" in table.text.lower()
            rows = table.find_all('tr')
            for row in rows:
                # Ищем все ссылки на профили, обычно там лежат ники
                links = row.find_all('a')
                for link in links:
                    if '/dota/gamingprofile/' in str(link.get('href')):
                        found_nick = link.text.strip()
                        all_players_in_match.append(found_nick)
                        
                        # Проверяем, есть ли этот ник в нашем списке PLAYERS
                        for name, nick in PLAYERS.items():
                            if nick.lower() == found_nick.lower():
                                if is_winning_team: winners.append(name)
                                else: losers.append(name)

        winners, losers = list(set(winners)), list(set(losers))
        
        if winners and losers:
            for w in winners: MANUAL_ADJUSTMENTS[w] += len(losers)
            for l in losers: MANUAL_ADJUSTMENTS[l] -= len(winners)
            save_bonuses(MANUAL_ADJUSTMENTS)
            await status_msg.edit_text(f"✅ Матч #{m_id} засчитан!\n🏆 Победили: {winners}\n💀 Проиграли: {losers}")
        else:
            # ДИАГНОСТИКА: выводим всех, кого бот вообще увидел
            debug_list = ", ".join(all_players_in_match[:10]) # первые 10 ников
            await status_msg.edit_text(
                f"❌ Свои не найдены.\n\n"
                f"**Я увидел в матче ники:**\n`{debug_list}`\n\n"
                f"**Сравни со своим списком:**\n`{[n for n in PLAYERS.values()]}`"
            )
    except Exception as e:
        await status_msg.edit_text(f"💥 Ошибка: {e}")
