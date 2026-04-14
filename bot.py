import discord
from discord.ext import commands, tasks
import asyncio
import os
from dotenv import load_dotenv
from database import Database
from datetime import datetime, timedelta
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GUILD_ID = int(os.getenv("GUILD_ID", "671313137550753830"))
BATTLE_CHANNEL_ID = int(os.getenv("BATTLE_CHANNEL_ID", "890677502169735179"))
VOTE_EMOJI = "✅"

intents = discord.Intents.default()
intents.message_content = True
intents.reactions = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)
db = Database()


# ─────────────────────────────────────────────
# EVENTS
# ─────────────────────────────────────────────

@bot.event
async def on_ready():
    logger.info(f"✅ Le Héraut est en ligne : {bot.user}")
    await bot.tree.sync()
    check_battle_end.start()


@bot.event
async def on_message(message):
    """Détecte les soumissions de logos dans les threads de bataille."""
    if message.author.bot:
        return

    # Vérifie si le message est dans un thread du salon bataille
    if not isinstance(message.channel, discord.Thread):
        return
    if message.channel.parent_id != BATTLE_CHANNEL_ID:
        return

    # Vérifie s'il y a une image jointe
    has_image = any(
        att.content_type and att.content_type.startswith("image/")
        for att in message.attachments
    )
    if not has_image:
        return

    # Récupère la bataille active liée à ce thread
    battle = db.get_battle_by_thread(message.channel.id)
    if not battle:
        return

    battle_id = battle["id"]
    user_id = str(message.author.id)
    username = message.author.display_name

    # Enregistre la participation
    already = db.add_participation(battle_id, user_id, username, message.id)
    if not already:
        logger.info(f"📝 Participation enregistrée : {username} dans bataille #{battle['number']}")

    await bot.process_commands(message)


# ─────────────────────────────────────────────
# SLASH COMMANDS
# ─────────────────────────────────────────────

async def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


@bot.tree.command(name="nouvelle-bataille", description="[ADMIN] Démarre une nouvelle bataille de logos")
@discord.app_commands.check(is_admin)
async def nouvelle_bataille(interaction: discord.Interaction, numero: int, theme: str, thread_id: str):
    """
    Crée une nouvelle bataille en base de données.
    numero : numéro de la bataille (ex: 219)
    theme : thème de la bataille (ex: Espace)
    thread_id : ID du thread créé pour cette bataille
    """
    tid = int(thread_id)
    battle_id = db.create_battle(numero, theme, tid)
    await interaction.response.send_message(
        f"⚔️ **Bataille #{numero}** — *{theme}* enregistrée ! Le thread est surveillé.",
        ephemeral=True
    )
    logger.info(f"Nouvelle bataille créée : #{numero} - {theme}")


@bot.tree.command(name="cloturer-vote", description="[ADMIN] Clôture le vote et désigne le gagnant")
@discord.app_commands.check(is_admin)
async def cloturer_vote(interaction: discord.Interaction):
    """Compte les checkmarks et désigne le vainqueur de la bataille active."""
    await interaction.response.defer(ephemeral=True)

    battle = db.get_active_battle()
    if not battle:
        await interaction.followup.send("❌ Aucune bataille active trouvée.", ephemeral=True)
        return

    thread = bot.get_channel(battle["thread_id"])
    if not thread:
        await interaction.followup.send("❌ Thread introuvable.", ephemeral=True)
        return

    participations = db.get_participations(battle["id"])
    if not participations:
        await interaction.followup.send("❌ Aucune participation enregistrée.", ephemeral=True)
        return

    # Compte les réactions ✅ sur chaque logo
    results = []
    for p in participations:
        try:
            msg = await thread.fetch_message(p["message_id"])
            votes = 0
            for reaction in msg.reactions:
                if str(reaction.emoji) == VOTE_EMOJI:
                    votes = reaction.count - 1  # -1 pour le bot lui-même
                    break
            results.append({
                "user_id": p["user_id"],
                "username": p["username"],
                "votes": votes,
                "message_id": p["message_id"]
            })
        except Exception as e:
            logger.warning(f"Impossible de fetch le message {p['message_id']}: {e}")

    if not results:
        await interaction.followup.send("❌ Impossible de compter les votes.", ephemeral=True)
        return

    # Désigne le gagnant
    winner = max(results, key=lambda x: x["votes"])
    db.close_battle(battle["id"], winner["user_id"], winner["username"], winner["votes"])

    # Met à jour les rôles
    guild = interaction.guild
    await update_roles(guild, winner["user_id"])

    embed = discord.Embed(
        title=f"🏆 Résultats — Bataille #{battle['number']}",
        description=f"**Thème : {battle['theme']}**",
        color=discord.Color.gold()
    )
    embed.add_field(
        name="👑 Vainqueur",
        value=f"<@{winner['user_id']}> avec **{winner['votes']} votes**",
        inline=False
    )

    # Affiche le classement complet du vote
    results.sort(key=lambda x: x["votes"], reverse=True)
    podium = "\n".join([
        f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}.'} {r['username']} — {r['votes']} votes"
        for i, r in enumerate(results[:10])
    ])
    embed.add_field(name="📊 Classement du vote", value=podium, inline=False)

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="classement", description="Affiche le classement de la bataille de logos")
async def classement(interaction: discord.Interaction):
    stats = db.get_leaderboard(limit=10)
    if not stats:
        await interaction.response.send_message("Aucune donnée disponible.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🏆 Classement — Bataille de Logos",
        color=discord.Color.gold()
    )

    lines = []
    medals = ["🥇", "🥈", "🥉"]
    for i, s in enumerate(stats):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        streak = f" 🔥×{s['current_streak']}" if s["current_streak"] >= 2 else ""
        lines.append(
            f"{medal} **{s['username']}** — {s['victories']}V / {s['participations']}P{streak}"
        )

    embed.description = "\n".join(lines)
    embed.set_footer(text="V = Victoires · P = Participations · 🔥 = Streak actif")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="monstats", description="Affiche tes statistiques personnelles")
async def monstats(interaction: discord.Interaction):
    user_id = str(interaction.user.id)
    stats = db.get_user_stats(user_id)

    if not stats:
        await interaction.response.send_message(
            "Tu n'as pas encore participé à une bataille !", ephemeral=True
        )
        return

    win_rate = round((stats["victories"] / stats["participations"]) * 100) if stats["participations"] > 0 else 0
    rank = db.get_user_rank(user_id)

    embed = discord.Embed(
        title=f"📊 Stats de {interaction.user.display_name}",
        color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(name="🏅 Rang", value=f"#{rank}", inline=True)
    embed.add_field(name="🏆 Victoires", value=stats["victories"], inline=True)
    embed.add_field(name="🎨 Participations", value=stats["participations"], inline=True)
    embed.add_field(name="📈 Taux de victoire", value=f"{win_rate}%", inline=True)
    embed.add_field(name="🔥 Streak actuel", value=f"{stats['current_streak']} semaines", inline=True)
    embed.add_field(name="⚡ Meilleur streak", value=f"{stats['best_streak']} semaines", inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="reset-bdd", description="[ADMIN] Remet la base de données à zéro (irréversible !)")
@discord.app_commands.check(is_admin)
async def reset_bdd(interaction: discord.Interaction):
    """Efface toutes les données et repart de zéro."""
    db.reset_all()
    await interaction.response.send_message(
        "🗑️ Base de données remise à zéro. Lance `/scanner-historique` pour réimporter.",
        ephemeral=True
    )
    logger.info("Base de données réinitialisée.")


@bot.tree.command(name="attribuer-victoire", description="[ADMIN] Attribue manuellement la victoire d'une bataille à un joueur")
@discord.app_commands.check(is_admin)
async def attribuer_victoire(interaction: discord.Interaction, numero: int, username: str):
    """
    Corrige ou attribue manuellement le gagnant d'une bataille passée.
    numero   : numéro de la bataille (ex: 217)
    username : pseudo exact du joueur tel qu'il apparaît dans le classement
    """
    await interaction.response.defer(ephemeral=True)

    battle = db.get_battle_by_number(numero)
    if not battle:
        await interaction.followup.send(f"❌ Bataille #{numero} introuvable en base.", ephemeral=True)
        return

    # Cherche le joueur par username dans les participations de cette bataille
    participations = db.get_participations(battle["id"])
    match = None
    for p in participations:
        if p["username"].lower() == username.lower():
            match = p
            break

    # Si pas trouvé dans les participations, cherche dans user_stats
    if not match:
        stats = db.get_user_stats_by_username(username)
        if stats:
            match = {"user_id": stats["user_id"], "username": stats["username"]}

    if not match:
        names = [p["username"] for p in participations]
        await interaction.followup.send(
            f"❌ Joueur **{username}** introuvable dans la bataille #{numero}.\n"
            f"Participants connus : {', '.join(names[:20])}",
            ephemeral=True
        )
        return

    # Applique la victoire
    old_winner = battle.get("winner_name", "aucun")
    db.force_winner(battle["id"], match["user_id"], match["username"])
    db.rebuild_user_stats()

    await interaction.followup.send(
        f"✅ Victoire de la bataille **#{numero}** attribuée à **{match['username']}**.\n"
        f"_(ancien gagnant enregistré : {old_winner})_\n"
        f"Les stats et streaks ont été recalculés.",
        ephemeral=True
    )
    logger.info(f"Victoire #{numero} attribuée manuellement à {match['username']}")


@bot.tree.command(name="whois", description="[ADMIN] Identifie un membre Discord depuis son ID")
@discord.app_commands.check(is_admin)
async def whois(interaction: discord.Interaction, user_id: str):
    """Résout le vrai pseudo d'un membre depuis son ID, même en mode streamer."""
    await interaction.response.defer(ephemeral=True)

    try:
        member = interaction.guild.get_member(int(user_id))
        if not member:
            member = await interaction.guild.fetch_member(int(user_id))
    except discord.NotFound:
        await interaction.followup.send(f"❌ Aucun membre trouvé avec l'ID `{user_id}`.", ephemeral=True)
        return
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        return

    streamer_mode = member.display_name != member.name and len(member.display_name) <= 4

    embed = discord.Embed(title="🔍 Whois", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🪪 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="👤 Username global", value=member.name, inline=True)
    embed.add_field(name="📛 Pseudo sur le serveur", value=member.display_name, inline=True)
    embed.add_field(name="🎭 Mode streamer", value="⚠️ Probablement actif" if streamer_mode else "Non détecté", inline=True)

    stats = db.get_user_stats(str(member.id))
    if stats:
        embed.add_field(
            name="📊 Stats BALO",
            value=f"Enregistré sous : **{stats['username']}**\n"
                  f"Victoires : {stats['victories']} · Participations : {stats['participations']}",
            inline=False
        )
    else:
        embed.add_field(name="📊 Stats BALO", value="Aucune donnée en base", inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)



@discord.app_commands.check(is_admin)
async def debug_joueur(interaction: discord.Interaction, user_id: str):
    """Affiche tout ce que la base contient pour un user_id donné."""
    await interaction.response.defer(ephemeral=True)

    stats = db.get_user_stats(user_id)
    participations = db.get_all_participations_for_user(user_id)
    battles_won = db.get_battles_won_by(user_id)

    embed = discord.Embed(title=f"🔍 Debug — {user_id}", color=discord.Color.blurple())

    if stats:
        embed.add_field(
            name="📊 user_stats",
            value=f"Username: **{stats['username']}**\n"
                  f"Participations: {stats['participations']}\n"
                  f"Victoires: {stats['victories']}\n"
                  f"Streak actuel: {stats['current_streak']}\n"
                  f"Meilleur streak: {stats['best_streak']}",
            inline=False
        )
    else:
        embed.add_field(name="📊 user_stats", value="❌ Aucune entrée trouvée", inline=False)

    if participations:
        lines = [f"Bataille #{p['battle_number']} — msg {p['message_id']} — {p['votes']} votes" for p in participations[:10]]
        embed.add_field(name=f"🎨 Participations ({len(participations)})", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="🎨 Participations", value="❌ Aucune participation trouvée", inline=False)

    if battles_won:
        lines = [f"Bataille #{b['number']} — {b['theme']}" for b in battles_won]
        embed.add_field(name=f"🏆 Victoires en base ({len(battles_won)})", value="\n".join(lines), inline=False)
    else:
        embed.add_field(name="🏆 Victoires en base", value="❌ Aucune victoire enregistrée", inline=False)

    await interaction.followup.send(embed=embed, ephemeral=True)



@discord.app_commands.check(is_admin)
async def scanner_historique(interaction: discord.Interaction, limite: int = 50, bataille_min: int = 205):
    """
    Scanne les threads existants pour importer les participations passées.
    bataille_min : numéro minimum de bataille à importer (défaut: 205)
    """
    await interaction.response.defer(ephemeral=True)

    channel = bot.get_channel(BATTLE_CHANNEL_ID)
    if not channel:
        await interaction.followup.send("❌ Salon introuvable.", ephemeral=True)
        return

    threads = list(channel.threads)
    archived = [t async for t in channel.archived_threads(limit=limite)]
    all_threads = threads + archived

    imported = 0
    battles_found = 0

    for thread in all_threads:
        # Détecte le numéro de bataille dans le nom du thread
        name = thread.name
        battle_number = None
        for word in name.replace("#", " ").split():
            if word.isdigit():
                battle_number = int(word)
                break

        if battle_number is None or battle_number < bataille_min:
            continue

        battles_found += 1

        # Crée la bataille si elle n'existe pas
        battle = db.get_battle_by_number(battle_number)
        if not battle:
            battle_id = db.create_battle(battle_number, name, thread.id, closed=True)
        else:
            battle_id = battle["id"]

        # Parcourt les messages du thread
        participations_thread = {}
        async for message in thread.history(limit=200):
            if message.author.bot:
                continue
            has_image = any(
                att.content_type and att.content_type.startswith("image/")
                for att in message.attachments
            )
            if not has_image:
                continue

            uid = str(message.author.id)
            uname = message.author.display_name

            already = db.add_participation(battle_id, uid, uname, message.id)
            if not already:
                imported += 1

            # Compte les votes si disponibles
            votes = 0
            for reaction in message.reactions:
                if str(reaction.emoji) == VOTE_EMOJI:
                    votes = max(0, reaction.count - 1)
            if votes > 0:
                db.update_votes(battle_id, uid, votes)

            participations_thread[uid] = votes

        # Reconstruit les user_stats pour cette bataille
        if participations_thread:
            winner_id = max(participations_thread, key=lambda u: participations_thread[u])
            winner_votes = participations_thread[winner_id]
            b = db.get_battle_by_number(battle_number)
            # Ne touche pas aux batailles avec victoire attribuée manuellement
            if b and b.get("manual_override"):
                logger.info(f"Bataille #{battle_number} protégée (manual_override), gagnant conservé.")
            elif b and not b.get("winner_id"):
                db.close_battle_silent(battle_id, winner_id, winner_votes)

    # Reconstruit tous les user_stats depuis les participations importées
    db.rebuild_user_stats()

    await interaction.followup.send(
        f"✅ Scan terminé !\n"
        f"• **{battles_found}** batailles trouvées (≥ #{bataille_min})\n"
        f"• **{imported}** nouvelles participations importées\n"
        f"• Classement reconstruit ✓",
        ephemeral=True
    )


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message(
            "❌ Cette commande est réservée aux administrateurs.", ephemeral=True
        )
    else:
        logger.error(f"Erreur commande : {error}")




@tasks.loop(hours=1)
async def check_battle_end():
    """Vérifie toutes les heures si une bataille doit être clôturée."""
    pass  # Clôture manuelle via /cloturer-vote pour l'instant


# ─────────────────────────────────────────────
# RÔLES AUTOMATIQUES
# ─────────────────────────────────────────────

ROLE_THRESHOLDS = [
    {"name": "🎨 Participant",    "participations": 1,  "victories": 0},
    {"name": "🖌️ Compétiteur",   "participations": 5,  "victories": 0},
    {"name": "⭐ Finaliste",      "participations": 0,  "victories": 1},
    {"name": "🏆 Champion",       "participations": 0,  "victories": 3},
    {"name": "👑 Légende BALO",   "participations": 0,  "victories": 5},
]


async def update_roles(guild: discord.Guild, user_id: str):
    """Attribue les rôles en fonction des stats du joueur."""
    member = guild.get_member(int(user_id))
    if not member:
        return

    stats = db.get_user_stats(user_id)
    if not stats:
        return

    for threshold in ROLE_THRESHOLDS:
        role = discord.utils.get(guild.roles, name=threshold["name"])
        if not role:
            continue

        qualifies = (
            stats["participations"] >= threshold["participations"] and
            stats["victories"] >= threshold["victories"]
        )

        if qualifies and role not in member.roles:
            try:
                await member.add_roles(role)
                logger.info(f"Rôle '{role.name}' attribué à {member.display_name}")
            except discord.Forbidden:
                logger.warning(f"Impossible d'attribuer le rôle '{role.name}'")


# ─────────────────────────────────────────────
# LANCEMENT
# ─────────────────────────────────────────────

# Le bot est lancé depuis main.py
