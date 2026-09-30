import discord
from discord.ext import commands, tasks
import sqlite3
import asyncio
import os

# ==========================================================
# CONFIG
# ==========================================================
TOKEN = os.getenv("TOKEN") or "TON_TOKEN_ICI"
DB_FILE = "stats.db"
OWNER_ID = 1554174661242265770

# ==========================================================
# BASE DE DONNEES
# ==========================================================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            guild_id INTEGER PRIMARY KEY,
            prefix TEXT DEFAULT ';',
            category_id INTEGER,
            emoji_membres TEXT DEFAULT '',
            emoji_online TEXT DEFAULT '',
            emoji_vocal TEXT DEFAULT '',
            emoji_mute TEXT DEFAULT '',
            title TEXT DEFAULT 'Statistique',
            color INTEGER DEFAULT 16711680
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS compteurs (
            guild_id INTEGER,
            channel_id INTEGER,
            type TEXT,
            nom TEXT,
            role_id INTEGER,
            PRIMARY KEY (guild_id, channel_id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS permissions (
            guild_id INTEGER,
            commande TEXT,
            target_id INTEGER,
            PRIMARY KEY (guild_id, commande, target_id)
        )
    """)
    conn.commit()
    conn.close()

def db_execute(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    conn.commit()
    conn.close()

def db_fetchone(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchone()
    conn.close()
    return result

def db_fetchall(query, params=()):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(query, params)
    result = c.fetchall()
    conn.close()
    return result

def get_config(guild_id):
    row = db_fetchone("SELECT prefix, category_id, emoji_membres, emoji_online, emoji_vocal, emoji_mute, title, color FROM config WHERE guild_id=?", (guild_id,))
    if row:
        return {
            "prefix": row[0],
            "category_id": row[1],
            "emoji_membres": row[2],
            "emoji_online": row[3],
            "emoji_vocal": row[4],
            "emoji_mute": row[5],
            "title": row[6],
            "color": row[7]
        }
    db_execute("INSERT OR IGNORE INTO config (guild_id) VALUES (?)", (guild_id,))
    return get_config(guild_id)

def has_perm(guild_id, user, commande):
    if user.id == OWNER_ID:
        return True
    if user.id == user.guild.owner_id:
        return True
    perms = db_fetchall("SELECT target_id FROM permissions WHERE guild_id=? AND commande=?", (guild_id, commande))
    for (target_id,) in perms:
        if user.id == target_id:
            return True
        role = user.guild.get_role(target_id)
        if role and role in user.roles:
            return True
    return False

def color_from_name(name):
    colors = {
        "rouge": 0xFF0000, "red": 0xFF0000,
        "bleu": 0x0000FF, "blue": 0x0000FF,
        "vert": 0x00FF00, "green": 0x00FF00,
        "jaune": 0xFFFF00, "yellow": 0xFFFF00,
        "orange": 0xFFA500,
        "violet": 0x800080, "purple": 0x800080,
        "rose": 0xFFC0CB, "pink": 0xFFC0CB,
        "noir": 0x000000, "black": 0x000000,
        "blanc": 0xFFFFFF, "white": 0xFFFFFF,
        "gris": 0x808080, "gray": 0x808080,
        "cyan": 0x00FFFF,
        "marron": 0x8B4513, "brown": 0x8B4513
    }
    return colors.get(name.lower())

# ==========================================================
# BOT
# ==========================================================
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.voice_states = True
intents.message_content = True

async def get_prefix(bot, message):
    if not message.guild:
        return ";"
    config = get_config(message.guild.id)
    return config["prefix"]

bot = commands.Bot(command_prefix=get_prefix, intents=intents, help_command=None)

# ==========================================================
# COMMANDE ;vc
# ==========================================================
@bot.command(name="vc")
async def vc(ctx):
    if not has_perm(ctx.guild.id, ctx.author, "vc"):
        return
    config = get_config(ctx.guild.id)
    guild = ctx.guild

    total = guild.member_count
    online = sum(1 for m in guild.members if m.status != discord.Status.offline)
    vocal = sum(1 for m in guild.members if m.voice and m.voice.channel)
    mute = sum(1 for m in guild.members if m.voice and m.voice.channel and m.voice.self_mute)

    embed = discord.Embed(
        title=f"{config['title']} # {guild.name}",
        color=discord.Color(config['color'])
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)

    embed.description = (
        f"{config['emoji_membres']} - Membres : {total}\n"
        f"{config['emoji_online']} - En ligne : {online}\n"
        f"{config['emoji_vocal']} - En vocal : {vocal}\n"
        f"{config['emoji_mute']} - Mute : {mute}"
    )
    await ctx.send(embed=embed)

# ==========================================================
# COMMANDE ;setv (configuration embed ;vc)
# ==========================================================
@bot.command(name="setv")
async def setv(ctx):
    if ctx.author.id != OWNER_ID:
        return

    async def build_embed():
        config = get_config(ctx.guild.id)
        embed = discord.Embed(
            title="Configuration de ;vc",
            color=discord.Color(config['color'])
        )
        embed.description = (
            f"Titre : {config['title']}\n"
            f"Couleur : {config['color']}\n"
            f"Emoji membres : {config['emoji_membres'] or '(aucun)'}\n"
            f"Emoji en ligne : {config['emoji_online'] or '(aucun)'}\n"
            f"Emoji en vocal : {config['emoji_vocal'] or '(aucun)'}\n"
            f"Emoji mute : {config['emoji_mute'] or '(aucun)'}"
        )
        return embed

    options = [
        discord.SelectOption(label="Titre", value="title"),
        discord.SelectOption(label="Couleur", value="color"),
        discord.SelectOption(label="Emoji membres", value="emoji_membres"),
        discord.SelectOption(label="Emoji en ligne", value="emoji_online"),
        discord.SelectOption(label="Emoji en vocal", value="emoji_vocal"),
        discord.SelectOption(label="Emoji mute", value="emoji_mute"),
    ]
    select = discord.ui.Select(placeholder="Choisir une option", options=options)

    async def callback(interaction):
        if interaction.user.id != ctx.author.id:
            return
        choix = interaction.data['values'][0]
        await interaction.response.send_message("Envoie la nouvelle valeur :", ephemeral=True)
        try:
            msg = await bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=30)
        except asyncio.TimeoutError:
            return

        valeur = msg.content

        if choix == "title":
            db_execute("UPDATE config SET title=? WHERE guild_id=?", (valeur, ctx.guild.id))
            confirmation = f"Le titre a été modifié en {valeur}"
        elif choix == "color":
            color = color_from_name(valeur)
            if color is None:
                await ctx.send("Couleur inconnue.")
                return
            db_execute("UPDATE config SET color=? WHERE guild_id=?", (color, ctx.guild.id))
            confirmation = f"La couleur a été modifiée en {valeur}"
        elif choix == "emoji_membres":
            db_execute("UPDATE config SET emoji_membres=? WHERE guild_id=?", (valeur, ctx.guild.id))
            confirmation = f"L'emoji membres a été modifié en {valeur}"
        elif choix == "emoji_online":
            db_execute("UPDATE config SET emoji_online=? WHERE guild_id=?", (valeur, ctx.guild.id))
            confirmation = f"L'emoji en ligne a été modifié en {valeur}"
        elif choix == "emoji_vocal":
            db_execute("UPDATE config SET emoji_vocal=? WHERE guild_id=?", (valeur, ctx.guild.id))
            confirmation = f"L'emoji en vocal a été modifié en {valeur}"
        elif choix == "emoji_mute":
            db_execute("UPDATE config SET emoji_mute=? WHERE guild_id=?", (valeur, ctx.guild.id))
            confirmation = f"L'emoji mute a été modifié en {valeur}"

        await ctx.send(confirmation)
        await ctx.send(embed=await build_embed())

    select.callback = callback
    view = discord.ui.View()
    view.add_item(select)

    await ctx.send(embed=await build_embed(), view=view)
  # ==========================================================
# COMMANDE ;setvc (configuration des salons vocaux)
# ==========================================================
@bot.command(name="setvc")
async def setvc(ctx):
    if not has_perm(ctx.guild.id, ctx.author, "setvc"):
        return
    config = get_config(ctx.guild.id)
    compteurs = db_fetchall("SELECT channel_id, type, nom, role_id FROM compteurs WHERE guild_id=?", (ctx.guild.id,))

    category = ctx.guild.get_channel(config['category_id']) if config['category_id'] else None

    embed = discord.Embed(
        title="Configuration des salons vocaux",
        color=discord.Color(config['color'])
    )
    desc = f"Catégorie : {category.name if category else 'Aucune'}\n"
    desc += f"Compteurs : {len(compteurs)}/5\n\n"
    for i, (ch_id, type_c, nom, role_id) in enumerate(compteurs, 1):
        ch = ctx.guild.get_channel(ch_id)
        desc += f"{i}. {ch.name if ch else nom} ({type_c})\n"
    embed.description = desc

    view = discord.ui.View()

    categories = [c for c in ctx.guild.categories]
    if categories:
        options = [discord.SelectOption(label=c.name[:100], value=str(c.id)) for c in categories[:25]]
        select_cat = discord.ui.Select(placeholder="Catégorie", options=options)

        async def cat_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return
            db_execute("UPDATE config SET category_id=? WHERE guild_id=?", (int(interaction.data['values'][0]), ctx.guild.id))
            await interaction.response.send_message("Catégorie mise à jour.", ephemeral=True)

        select_cat.callback = cat_callback
        view.add_item(select_cat)

    types = [
        ("membres", "Membres total"),
        ("online", "En ligne"),
        ("vocal", "En vocal"),
        ("role", "Avec un rôle particulier")
    ]
    options_add = [discord.SelectOption(label=label, value=value) for value, label in types]
    select_add = discord.ui.Select(placeholder="Ajouter", options=options_add)

    async def add_callback(interaction):
        if interaction.user.id != ctx.author.id:
            return
        type_choisi = interaction.data['values'][0]

        if type_choisi == "role":
            await interaction.response.send_message("Mentionne le rôle :", ephemeral=True)
            try:
                msg = await bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=30)
                if not msg.role_mentions:
                    await ctx.send("Aucun rôle mentionné.")
                    return
                role = msg.role_mentions[0]
                role_id = role.id
            except asyncio.TimeoutError:
                return
        else:
            role_id = None
            await interaction.response.send_message("Envoie le nom du salon :", ephemeral=True)

        try:
            msg = await bot.wait_for("message", check=lambda m: m.author.id == ctx.author.id and m.channel.id == ctx.channel.id, timeout=30)
            nom = msg.content
        except asyncio.TimeoutError:
            return

        config = get_config(ctx.guild.id)
        if not config['category_id']:
            await ctx.send("Définis d'abord une catégorie.")
            return

        category = ctx.guild.get_channel(config['category_id'])
        channel = await ctx.guild.create_voice_channel(name=f"{nom} : ...", category=category)

        db_execute("INSERT OR REPLACE INTO compteurs VALUES (?, ?, ?, ?, ?)", (ctx.guild.id, channel.id, type_choisi, nom, role_id))
        await ctx.send(f"Salon {channel.mention} créé.")

    select_add.callback = add_callback
    view.add_item(select_add)

    options_del = []
    for ch_id, type_c, nom, role_id in compteurs:
        ch = ctx.guild.get_channel(ch_id)
        if ch:
            options_del.append(discord.SelectOption(label=ch.name[:100], value=str(ch_id)))

    if options_del:
        select_del = discord.ui.Select(placeholder="Supprimer", options=options_del[:25])

        async def del_callback(interaction):
            if interaction.user.id != ctx.author.id:
                return
            ch_id = int(interaction.data['values'][0])
            chuild = ctx.guild.get_channel(ch_id)
            if ch:
                await ch.delete()
            db_execute("DELETE FROM compteurs WHERE guild_id=? AND channel_id=?", (ctx.g.id, ch_id))
            await interaction.response.send_message("Compteur supprimé.", ephemeral=True)

        select_del.callback = del_callback
        view.add_item(select_del)

    await ctx.send(embed=embed, view=view)

# ==========================================================
# COMMANDE ;setperm
# ==========================================================
@bot.command(name="setperm")
async def setperm(ctx, action: str = None, commande: str = None, target: discord.Role = None):
    if ctx.author.id != OWNER_ID:
        return

    if action == "list":
        perms = db_fetchall("SELECT commande, target_id FROM permissions WHERE guild_id=?", (ctx.guild.id,))
        if not perms:
            await ctx.send("Aucune permission configurée.")
            return
        desc = ""
        for cmd, tid in perms:
            role = ctx.guild.get_role(tid)
            member = ctx.guild.get_member(tid)
            name = role.mention if role else (member.mention if member else str(tid))
            desc += f"{cmd} -> {name}\n"
        await ctx.send(embed=discord.Embed(title="Permissions", description=desc, color=discord.Color.red()))
        return

    if action == "remove":
        if not commande or not target:
            await ctx.send("Usage : ;setperm remove {commande} @role")
            return
        db_execute("DELETE FROM permissions WHERE guild_id=? AND commande=? AND target_id=?", (ctx.guild.id, commande, target.id))
        await ctx.send(f"La permission {commande} a été retirée à {target.mention}")
        return

    if not action or not commande or not target:
        await ctx.send("Usage : ;setperm {commande} @role")
        return

    db_execute("INSERT OR IGNORE INTO permissions VALUES (?, ?, ?)", (ctx.guild.id, commande, target.id))
    await ctx.send(f"La permission {commande} a été ajoutée à {target.mention}")

# ==========================================================
# COMMANDE ;config
# ==========================================================
@bot.command(name="config")
async def config_cmd(ctx):
    if ctx.author.id != OWNER_ID:
        return
    config = get_config(ctx.guild.id)
    compteurs = db_fetchall("SELECT channel_id FROM compteurs WHERE guild_id=?", (ctx.guild.id,))
    perms = db_fetchall("SELECT commande, target_id FROM permissions WHERE guild_id=?", (ctx.guild.id,))
    category = ctx.guild.get_channel(config['category_id']) if config['category_id'] else None

    embed = discord.Embed(title="Configuration", color=discord.Color(config['color']))
    if ctx.guild.icon:
        embed.set_thumbnail(url=ctx.guild.icon.url)

    desc = f"Préfixe : {config['prefix']}\n"
    desc += f"Catégorie vocaux : {category.name if category else 'Aucune'}\n"
    desc += f"Compteurs : {len(compteurs)}/5\n\n"
    desc += "Permissions :\n"
    for cmd, tid in perms:
        role = ctx.guild.get_role(tid)
        name = role.mention if role else str(tid)
        desc += f"- {cmd} -> {name}\n"
    embed.description = desc
    await ctx.send(embed=embed)

# ==========================================================
# BOUCLE DE MISE A JOUR DES SALONS
# ==========================================================
@tasks.loop(minutes=5)
async def update_stats():
    for guild in bot.guilds:
        compteurs = db_fetchall("SELECT channel_id, type, nom, role_id FROM compteurs WHERE guild_id=?", (guild.id,))
        for ch_id, type_c, nom, role_id in compteurs:
            channel = guild.get_channel(ch_id)
            if not channel:
                continue

            if type_c == "membres":
                valeur = guild.member_count
            elif type_c == "online":
                valeur = sum(1 for m in guild.members if m.status != discord.Status.offline)
            elif type_c == "vocal":
                valeur = sum(1 for m in guild.members if m.voice and m.voice.channel)
            elif type_c == "role":
                role = guild.get_role(role_id)
                valeur = len(role.members) if role else 0
            else:
                continue

            try:
                await channel.edit(name=f"{nom} : {valeur}")
            except discord.HTTPException:
                pass
            await asyncio.sleep(2)

# ==========================================================
# LANCEMENT
# ==========================================================
@bot.event
async def on_ready():
    print(f"Connecté en tant que {bot.user}")
    if not update_stats.is_running():
        update_stats.start()

init_db()
bot.run(MTU1NDE4NDU3OTMzNjc2NTQ4MA.GRk16W.qdrseQoZJiQspMpywy2JfDM9E7u9d7ZVozegU)
