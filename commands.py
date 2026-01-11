import discord
from discord import app_commands
import json
import os

tiers = ['S', 'A+', 'A-', 'B+', 'B-', 'C+', 'C-', 'D+', 'D-', 'F']

tier_emojis = {
    'S': '🟣',
    'A+': '🟡',
    'A-': '🟠',
    'B+': '🔴',
    'B-': '⚪',
    'C+': '🔵',
    'C-': '🟢',
    'D+': '⭕',
    'D-': '⚫',
    'F': '🟤'
}

def load_json(file):
    with open(file, 'r') as f:
        return json.load(f)

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f, indent=4)

def find_player(input_val, players):
    return next((p for p in players if str(p['id']) == input_val or p['name'] == input_val or p['discord_id'] == input_val), None)

def find_character(input_val, characters):
    return next((c for c in characters if c['name'].lower() == input_val.lower()), None)

def tiers_touching(t1, t2):
    i1 = tiers.index(t1)
    i2 = tiers.index(t2)
    return abs(i1 - i2) == 1

class SmashBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()

bot = SmashBot()

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} 🤖')

# /addPlayer
@app_commands.command(name="addplayer", description="Add a player to the system 👤")
@app_commands.describe(name="Player name", discord_id="Discord ID")
async def add_player(interaction: discord.Interaction, name: str, discord_id: str):
    # Restrict player management commands from smash-commands channel
    if interaction.channel.name == "smash-commands":
        await interaction.response.send_message("❌ Player management commands are not allowed in this channel! Please use an admin channel.", ephemeral=True)
        return

    players = load_json('players.json')
    if any(p['discord_id'] == discord_id for p in players):
        await interaction.response.send_message("❌ Player with this Discord ID already exists!")
        return
    new_id = max([p['id'] for p in players], default=0) + 1
    player = {"id": new_id, "name": name, "discord_id": discord_id, "current_tier": "F"}
    players.append(player)
    save_json('players.json', players)

    # Assign F role to the new player
    guild = interaction.guild
    member = guild.get_member(int(discord_id))
    if member:
        f_role = discord.utils.get(guild.roles, name="F")
        if f_role:
            await member.add_roles(f_role)

    await interaction.response.send_message(f"✅ Player {name} added with tier {tier_emojis['F']} F!")

bot.tree.add_command(add_player)

# /removePlayer
@app_commands.command(name="removeplayer", description="Remove a player 🗑️")
@app_commands.describe(discord_id="Discord ID")
async def remove_player(interaction: discord.Interaction, discord_id: str):
    # Restrict player management commands from smash-commands channel
    if interaction.channel.name == "smash-commands":
        await interaction.response.send_message("❌ Player management commands are not allowed in this channel! Please use an admin channel.", ephemeral=True)
        return

    players = load_json('players.json')
    player = next((p for p in players if p['discord_id'] == discord_id), None)
    if not player:
        await interaction.response.send_message("❌ Player not found!")
        return
    players.remove(player)
    save_json('players.json', players)
    await interaction.response.send_message(f"✅ Player {player['name']} removed!")

bot.tree.add_command(remove_player)

# /addGame
@app_commands.command(name="addgame", description="Add a new game 🎮")
@app_commands.describe(
    player1="Player 1 (name or Discord ID)",
    player2="Player 2 (name or Discord ID)",
    character1="Character 1",
    character2="Character 2",
    ranked="Is this a ranked game?",
    winner="Who won? (ID, name, or Discord ID)",
    stocks="How many stocks did the winner have?",
    percentage="What percentage did the winner have?"
)
@app_commands.choices(ranked=[
    app_commands.Choice(name="Ranked", value="ranked"),
    app_commands.Choice(name="Unranked", value="unranked")
])
async def add_game(
    interaction: discord.Interaction,
    player1: str,
    player2: str,
    character1: str,
    character2: str,
    ranked: str,
    winner: str,
    stocks: int,
    percentage: float
):
    # Restrict game commands to smash-commands channel only
    if interaction.channel.name != "smash-commands":
        await interaction.response.send_message("🎮 Game commands are only allowed in #smash-commands!", ephemeral=True)
        return
    players = load_json('players.json')
    characters = load_json('characters.json')

    # Find players
    p1 = find_player(player1, players)
    p2 = find_player(player2, players)
    if not p1 or not p2:
        await interaction.response.send_message("❌ Invalid player(s)!", ephemeral=True)
        return

    # Find characters
    c1 = find_character(character1, characters)
    c2 = find_character(character2, characters)
    if not c1 or not c2:
        await interaction.response.send_message("❌ Invalid character(s)!", ephemeral=True)
        return

    # Check ranked validity
    ranked_bool = ranked == "ranked"
    if ranked_bool:
        t1 = p1['current_tier']
        t2 = p2['current_tier']
        if not tiers_touching(t1, t2):
            await interaction.response.send_message("❌ Players' tiers are not touching for ranked game!", ephemeral=True)
            return

    # Find winner
    w = find_player(winner, players)
    if not w or w['id'] not in [p1['id'], p2['id']]:
        await interaction.response.send_message("❌ Invalid winner!", ephemeral=True)
        return

    # Add game
    games = load_json('games.json')
    new_id = max([g['id'] for g in games], default=0) + 1
    game = {
        'id': new_id,
        'contenders': [
            {'player_id': p1['id'], 'character_id': c1['id']},
            {'player_id': p2['id'], 'character_id': c2['id']}
        ],
        'ranked': ranked_bool,
        'results': {
            'winner_id': w['id'],
            'stocks': stocks,
            'percentage': percentage
        }
    }
    games.append(game)
    save_json('games.json', games)

    # Handle tier swap
    tier_changed = False
    if ranked_bool:
        higher = p1 if tiers.index(p1['current_tier']) < tiers.index(p2['current_tier']) else p2
        lower = p1 if higher == p2 else p2
        if w['id'] == lower['id']:
            temp = higher['current_tier']
            higher['current_tier'] = lower['current_tier']
            lower['current_tier'] = temp
            save_json('players.json', players)
            tier_changed = True
            # Update roles
            guild = interaction.guild
            higher_member = guild.get_member(int(higher['discord_id']))
            lower_member = guild.get_member(int(lower['discord_id']))
            if higher_member and lower_member:
                old_higher_role = discord.utils.get(guild.roles, name=temp)
                old_lower_role = discord.utils.get(guild.roles, name=higher['current_tier'])
                new_higher_role = discord.utils.get(guild.roles, name=higher['current_tier'])
                new_lower_role = discord.utils.get(guild.roles, name=temp)
                if old_higher_role:
                    await higher_member.remove_roles(old_higher_role)
                if new_higher_role:
                    await higher_member.add_roles(new_higher_role)
                if old_lower_role:
                    await lower_member.remove_roles(old_lower_role)
                if new_lower_role:
                    await lower_member.add_roles(new_lower_role)

    # Post to channel
    channel = discord.utils.get(interaction.guild.channels, name="game-logs")
    if channel:
        # Check if bot has permission to send messages in the channel
        if not channel.permissions_for(interaction.guild.me).send_messages:
            await interaction.followup.send("⚠️ Warning: Game logged successfully, but I don't have permission to post in #game-logs. Please check my channel permissions!", ephemeral=True)
        else:
            p1_name = p1['name']
            p2_name = p2['name']
            c1_name = c1['name']
            c2_name = c2['name']
            c1_emoji = c1['emoji']
            c2_emoji = c2['emoji']
            winner_name = w['name']
            ranked_str = "Ranked" if ranked_bool else "Unranked"
            message = f"**Game {new_id} | {ranked_str}**\n**------------------**\n**Players: {p1_name} as {c1_emoji} {c1_name} versus {p2_name} as {c2_emoji} {c2_name}**\n**Result: {winner_name} won with {stocks} stocks and {percentage}%**\n"
            if ranked_bool:
                if tier_changed:
                    message += f"**{lower['name']} overtook {higher['name']} and is now {tier_emojis[lower['current_tier']]} {lower['current_tier']} tier!**"
                else:
                    message += "**No tier updates**"
            # For unranked games, no tier update message
            try:
                msg = await channel.send(message)
                game['message_id'] = msg.id
                save_json('games.json', games)
            except discord.Forbidden:
                await interaction.followup.send("⚠️ Warning: Game logged successfully, but I don't have permission to post in #game-logs. Please check my channel permissions!", ephemeral=True)
    else:
        await interaction.followup.send("⚠️ Warning: Game logged successfully, but #game-logs channel not found. Please create it!", ephemeral=True)

    await interaction.response.send_message("✅ Game added!", ephemeral=True)

@add_game.autocomplete('player1')
@add_game.autocomplete('player2')
@add_game.autocomplete('winner')
async def player_autocomplete(interaction: discord.Interaction, current: str):
    players = load_json('players.json')
    return [
        app_commands.Choice(name=p['name'], value=str(p['id']))
        for p in players
        if current.lower() in p['name'].lower() or current in str(p['id']) or current in p['discord_id']
    ][:25]  # Discord limits to 25 choices

@add_game.autocomplete('character1')
@add_game.autocomplete('character2')
async def character_autocomplete(interaction: discord.Interaction, current: str):
    characters = load_json('characters.json')
    return [
        app_commands.Choice(name=char['name'], value=char['name'])
        for char in characters
        if current.lower() in char['name'].lower()
    ][:25]  # Discord limits to 25 choices

bot.tree.add_command(add_game)

# /removeGame
@app_commands.command(name="removegame", description="Remove a game 🗑️")
@app_commands.describe(id="Game ID")
async def remove_game(interaction: discord.Interaction, id: int):
    # Restrict game commands to smash-commands channel only
    if interaction.channel.name != "smash-commands":
        await interaction.response.send_message("🎮 Game commands are only allowed in #smash-commands!", ephemeral=True)
        return

    games = load_json('games.json')
    game = next((g for g in games if g['id'] == id), None)
    if not game:
        await interaction.response.send_message("❌ Game not found!")
        return
    games.remove(game)
    save_json('games.json', games)
    # remove from channel
    if 'message_id' in game:
        channel = discord.utils.get(interaction.guild.channels, name="game-logs")
        if channel:
            try:
                message = await channel.fetch_message(game['message_id'])
                await message.delete()
            except:
                pass
    await interaction.response.send_message(f"✅ Game {id} removed!")

bot.tree.add_command(remove_game)

# /tierlist
@app_commands.command(name="tierlist", description="Show current tier list 📊")
async def tierlist(interaction: discord.Interaction):
    # Restrict stats/info commands to smash-commands channel only
    if interaction.channel.name != "smash-commands":
        await interaction.response.send_message("📊 Statistics commands are only allowed in #smash-commands!", ephemeral=True)
        return

    players = load_json('players.json')
    tier_dict = {}
    for p in players:
        tier = p['current_tier']
        if tier not in tier_dict:
            tier_dict[tier] = []
        tier_dict[tier].append(p['name'])
    response = "**Current Tier List:**\n-------------------\n"
    for tier in tiers:
        if tier in tier_dict:
            names = ', '.join(tier_dict[tier])
            response += f"**{tier_emojis[tier]} {tier}: {names}**\n"
    await interaction.response.send_message(response)

bot.tree.add_command(tierlist)

# /stats
@app_commands.command(name="stats", description="Show player stats 📈")
@app_commands.describe(player="Player ID, name, or Discord ID", param="Optional: character name or 'characters'")
async def stats(interaction: discord.Interaction, player: str, param: str = None):
    # Restrict stats/info commands to smash-commands channel only
    if interaction.channel.name != "smash-commands":
        await interaction.response.send_message("📊 Statistics commands are only allowed in #smash-commands!", ephemeral=True)
        return

    players = load_json('players.json')
    games = load_json('games.json')
    p = find_player(player, players)
    if not p:
        await interaction.response.send_message("❌ Player not found!")
        return
    if param is None:
        player_games = [g for g in games if any(c['player_id'] == p['id'] for c in g['contenders'])]
        total_games = len(player_games)
        wins = sum(1 for g in player_games if g['results']['winner_id'] == p['id'])
        ranked_games = sum(1 for g in player_games if g['ranked'])
        ranked_wins = sum(1 for g in player_games if g['ranked'] and g['results']['winner_id'] == p['id'])
        unranked_games = total_games - ranked_games
        unranked_wins = wins - ranked_wins
        winrate = wins / total_games * 100 if total_games > 0 else 0
        ranked_winrate = ranked_wins / ranked_games * 100 if ranked_games > 0 else 0
        unranked_winrate = unranked_wins / unranked_games * 100 if unranked_games > 0 else 0
        response = f"**{p['name']}'s Stats:**\n--------------------------\n🎯 **Overall Winrate: {winrate:.2f}%**\n🏅 **Ranked Winrate: {ranked_winrate:.2f}%**\n🎲 **Unranked Winrate: {unranked_winrate:.2f}%**\n🏆 **Current Tier: {tier_emojis[p['current_tier']]} {p['current_tier']}**"
    elif param.lower() == "characters":
        char_stats = {}
        for g in games:
            if any(c['player_id'] == p['id'] for c in g['contenders']):
                char_id = next(c['character_id'] for c in g['contenders'] if c['player_id'] == p['id'])
                if char_id not in char_stats:
                    char_stats[char_id] = {'games': 0, 'wins': 0}
                char_stats[char_id]['games'] += 1
                if g['results']['winner_id'] == p['id']:
                    char_stats[char_id]['wins'] += 1
        characters = load_json('characters.json')
        sorted_chars = sorted(char_stats.items(), key=lambda x: x[1]['wins']/x[1]['games'] if x[1]['games'] > 0 else 0, reverse=True)
        response = f"**{p['name']}'s Top Characters:**\n---------------------------------------\n"
        for char_id, stats in sorted_chars[:10]:
            char = next(c for c in characters if c['id'] == char_id)
            char_name = char['name']
            char_emoji = char['emoji']
            winrate = stats['wins'] / stats['games'] * 100
            response += f"**{char_emoji} {char_name}: {winrate:.2f}%**\n"
    else:
        characters = load_json('characters.json')
        char = find_character(param, characters)
        if not char:
            await interaction.response.send_message("❌ Character not found!")
            return
        player_games = [g for g in games if any(c['player_id'] == p['id'] and c['character_id'] == char['id'] for c in g['contenders'])]
        total_games = len(player_games)
        wins = sum(1 for g in player_games if g['results']['winner_id'] == p['id'])
        ranked_games = sum(1 for g in player_games if g['ranked'])
        ranked_wins = sum(1 for g in player_games if g['ranked'] and g['results']['winner_id'] == p['id'])
        unranked_games = total_games - ranked_games
        unranked_wins = wins - ranked_wins
        overall_winrate = wins / total_games * 100 if total_games > 0 else 0
        ranked_winrate = ranked_wins / ranked_games * 100 if ranked_games > 0 else 0
        unranked_winrate = unranked_wins / unranked_games * 100 if unranked_games > 0 else 0
        response = f"**{p['name']} as {char['emoji']} {char['name']}:**\n------------------------------------\n🎮 **Total Games Played: {total_games}**\n🎯 **Overall Winrate: {overall_winrate:.2f}%**\n🏅 **Ranked Games Played: {ranked_games}**\n🏅 **Ranked Winrate: {ranked_winrate:.2f}%**\n🎲 **Unranked Games Played: {unranked_games}**\n🎲 **Unranked Winrate: {unranked_winrate:.2f}%**"
    await interaction.response.send_message(response)

@stats.autocomplete('param')
async def stats_param_autocomplete(interaction: discord.Interaction, current: str):
    characters = load_json('characters.json')
    choices = []
    
    # Always include "characters" option if it matches
    if "characters".startswith(current.lower()):
        choices.append(app_commands.Choice(name="characters (show top characters)", value="characters"))
    
    # Add matching character names
    char_choices = [
        app_commands.Choice(name=f"{char['emoji']} {char['name']}", value=char['name'])
        for char in characters
        if current.lower() in char['name'].lower()
    ][:24]  # Leave room for "characters" option
    
    choices.extend(char_choices)
    return choices[:25]  # Discord limits to 25 choices

bot.tree.add_command(stats)

# /settier
@app_commands.command(name="settier", description="Set a player's tier manually ⚙️")
@app_commands.describe(player="Player ID, name, or Discord ID", tier="New tier (S, A+, A-, B+, B-, C+, C-, D+, D-, F)")
async def set_tier(interaction: discord.Interaction, player: str, tier: str):
    # Restrict player management commands from smash-commands channel
    if interaction.channel.name == "smash-commands":
        await interaction.response.send_message("Player management commands are not allowed in this channel! Please use an admin channel. ❌", ephemeral=True)
        return

    if tier not in tiers:
        await interaction.response.send_message(f"❌ Invalid tier! Valid tiers: {', '.join(tiers)}")
        return

    players = load_json('players.json')
    p = find_player(player, players)
    if not p:
        await interaction.response.send_message("❌ Player not found!")
        return

    old_tier = p['current_tier']
    p['current_tier'] = tier
    save_json('players.json', players)

    # Update Discord role
    guild = interaction.guild
    member = guild.get_member(int(p['discord_id']))
    if member:
        old_role = discord.utils.get(guild.roles, name=old_tier)
        new_role = discord.utils.get(guild.roles, name=tier)
        if old_role:
            await member.remove_roles(old_role)
        if new_role:
            await member.add_roles(new_role)

    await interaction.response.send_message(f"✅ Set {p['name']}'s tier from {tier_emojis[old_tier]} {old_tier} to {tier_emojis[tier]} {tier}!")

bot.tree.add_command(set_tier)

bot.run(os.getenv('DISCORD_TOKEN'))
