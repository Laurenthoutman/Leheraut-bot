import discord
from discord.ext import commands, tasks
import os
from dotenv import load_dotenv
from database import Database
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


# ── HELPER ────────────────────────────────────────────────────────────────

async def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator


# ── EVENTS ────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    logger.info(f"✅ Le Héraut est en ligne : {bot.user}")
    await bot.tree.sync()


@bot.event
async def on_message(message):
    """Détecte automatiquement les soumissions de logos dans les threads actifs."""
    if message.author.bot:
        return
    if not isinstance(message.channel, discord.Thread):
        return
    if message.channel.parent_id != BATTLE_CHANNEL_ID:
        return

    has_image = any(
        att.content_type and att.content_type.startswith("image/")
        for att in message.attachments
    )
    if not has_image:
        return

    battle = db.get_battle_by_thread(message.channel.id)
    if not battle:
        return

    already = db.add_participation(
        battle["id"],
        str(message.author.id),
        message.author.display_name,
        message.id
    )
    if not already:
        logger.info(f"📝 Participation : {message.author.display_name} → bataille #{battle['number']}")

    await bot.process_commands(message)


# ── COMMANDES PUBLIQUES ────────────────────────────────────────────────────

@bot.tree.command(name="classement", description="Affiche le top 10 de la bataille de logos")
async def classement(interaction: discord.Interaction):
    stats = db.get_leaderboard(limit=10)
    if not stats:
        await interaction.response.send_message("Aucune donnée disponible.", ephemeral=True)
        return

    embed = discord.Embed(title="🏆 Classement — Bataille de Logos", color=discord.Color.gold())
    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, s in enumerate(stats):
        medal = medals[i] if i < 3 else f"`{i+1}.`"
        streak = f" 🔥×{s['current_streak']}" if s["current_streak"] >= 2 else ""
        lines.append(f"{medal} **{s['username']}** — {s['victories']}V / {s['participations']}P{streak}")

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


# ── COMMANDES ADMIN ────────────────────────────────────────────────────────

@bot.tree.command(name="nouvelle-bataille", description="[ADMIN] Enregistre une nouvelle bataille et surveille le thread")
@discord.app_commands.check(is_admin)
async def nouvelle_bataille(interaction: discord.Interaction, numero: int, theme: str, thread_id: str):
    tid = int(thread_id)
    db.create_battle(numero, theme, tid)
    await interaction.response.send_message(
        f"⚔️ **Bataille #{numero}** — *{theme}* enregistrée ! Le thread `{tid}` est surveillé.",
        ephemeral=True
    )
    logger.info(f"Nouvelle bataille : #{numero} - {theme}")


@bot.tree.command(name="attribuer-victoire", description="[ADMIN] Désigne manuellement le gagnant d'une bataille")
@discord.app_commands.check(is_admin)
async def attribuer_victoire(
    interaction: discord.Interaction,
    numero: int,
    username: str,
    user_id: str = None
):
    await interaction.response.defer(ephemeral=True)

    battle = db.get_battle_by_number(numero)
    if not battle:
        await interaction.followup.send(f"❌ Bataille #{numero} introuvable.", ephemeral=True)
        return

    # Résolution du joueur : priorité à user_id si fourni
    if user_id:
        uid = user_id.strip()
        try:
            member = interaction.guild.get_member(int(uid)) or await interaction.guild.fetch_member(int(uid))
            uname = member.display_name
        except Exception:
            uname = username
        db.add_participation_if_missing(battle["id"], uid, uname)
        match = {"user_id": uid, "username": uname}
    else:
        # Cherche par username dans les participations puis dans les stats
        participations = db.get_participations(battle["id"])
        match = next((p for p in participations if p["username"].lower() == username.lower()), None)
        if not match:
            stats = db.get_user_stats_by_username(username)
            if stats:
                match = {"user_id": stats["user_id"], "username": stats["username"]}
        if not match:
            names = [p["username"] for p in participations]
            await interaction.followup.send(
                f"❌ **{username}** introuvable dans la bataille #{numero}.\n"
                f"💡 Si la personne est en mode streamer, ajoute le paramètre `user_id`.\n"
                f"Participants : {', '.join(names[:20])}",
                ephemeral=True
            )
            return

    old = battle.get("winner_name") or "aucun"
    db.set_winner(battle["id"], match["user_id"], match["username"])

    await interaction.followup.send(
        f"✅ Victoire **#{numero}** attribuée à **{match['username']}**.\n"
        f"_(ancien gagnant : {old})_ — Stats recalculées.",
        ephemeral=True
    )
    logger.info(f"Victoire #{numero} → {match['username']}")


@bot.tree.command(name="cloturer-vote", description="[ADMIN] Compte les ✅ et propose le gagnant")
@discord.app_commands.check(is_admin)
async def cloturer_vote(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    battle = db.get_active_battle()
    if not battle:
        await interaction.followup.send("❌ Aucune bataille active.", ephemeral=True)
        return

    thread = bot.get_channel(battle["thread_id"])
    if not thread:
        await interaction.followup.send("❌ Thread introuvable.", ephemeral=True)
        return

    participations = db.get_participations(battle["id"])
    if not participations:
        await interaction.followup.send("❌ Aucune participation enregistrée.", ephemeral=True)
        return

    results = []
    for p in participations:
        try:
            msg = await thread.fetch_message(p["message_id"])
            votes = 0
            for reaction in msg.reactions:
                if str(reaction.emoji) == VOTE_EMOJI:
                    votes = max(0, reaction.count - 1)
                    break
            results.append({"user_id": p["user_id"], "username": p["username"], "votes": votes})
            db.update_votes(battle["id"], p["user_id"], votes)
        except Exception as e:
            logger.warning(f"Message {p['message_id']} introuvable : {e}")

    if not results:
        await interaction.followup.send("❌ Impossible de compter les votes.", ephemeral=True)
        return

    results.sort(key=lambda x: x["votes"], reverse=True)
    winner = results[0]

    podium = "\n".join([
        f"{'🥇' if i==0 else '🥈' if i==1 else '🥉' if i==2 else f'{i+1}.'} "
        f"{r['username']} — {r['votes']} votes"
        for i, r in enumerate(results[:10])
    ])

    embed = discord.Embed(
        title=f"📊 Résultats du vote — Bataille #{battle['number']}",
        description=f"**Thème : {battle['theme']}**",
        color=discord.Color.gold()
    )
    embed.add_field(name="👑 Gagnant suggéré", value=f"**{winner['username']}** ({winner['votes']} votes)", inline=False)
    embed.add_field(name="Classement", value=podium, inline=False)
    embed.set_footer(text=f"Lance /attribuer-victoire numero:{battle['number']} username:{winner['username']} pour confirmer.")

    await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="scanner-historique", description="[ADMIN] Importe les participations des anciens threads (sans gagnants)")
@discord.app_commands.check(is_admin)
async def scanner_historique(interaction: discord.Interaction, limite: int = 30, bataille_min: int = 205):
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
        battle_number = None
        for word in thread.name.replace("#", " ").split():
            if word.isdigit():
                n = int(word)
                if n >= bataille_min:
                    battle_number = n
                    break

        if battle_number is None:
            continue

        battles_found += 1

        battle = db.get_battle_by_number(battle_number)
        if not battle:
            db.create_battle(battle_number, thread.name, thread.id)
            battle = db.get_battle_by_number(battle_number)

        async for message in thread.history(limit=200):
            if message.author.bot:
                continue
            has_image = any(
                att.content_type and att.content_type.startswith("image/")
                for att in message.attachments
            )
            if not has_image:
                continue

            already = db.add_participation(
                battle["id"],
                str(message.author.id),
                message.author.display_name,
                message.id
            )
            if not already:
                imported += 1

    # Reconstruit les stats (participations + streaks uniquement, pas de victoires)
    db.rebuild_user_stats()

    await interaction.followup.send(
        f"✅ Scan terminé !\n"
        f"• **{battles_found}** batailles trouvées (≥ #{bataille_min})\n"
        f"• **{imported}** nouvelles participations importées\n"
        f"• Streaks recalculés ✓\n\n"
        f"_Utilise `/attribuer-victoire` pour désigner les gagnants._",
        ephemeral=True
    )


@bot.tree.command(name="whois", description="[ADMIN] Identifie un membre Discord depuis son ID")
@discord.app_commands.check(is_admin)
async def whois(interaction: discord.Interaction, user_id: str):
    await interaction.response.defer(ephemeral=True)
    try:
        member = interaction.guild.get_member(int(user_id)) or await interaction.guild.fetch_member(int(user_id))
    except discord.NotFound:
        await interaction.followup.send(f"❌ Aucun membre trouvé avec l'ID `{user_id}`.", ephemeral=True)
        return
    except Exception as e:
        await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)
        return

    embed = discord.Embed(title="🔍 Whois", color=discord.Color.blurple())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="🪪 ID", value=f"`{member.id}`", inline=False)
    embed.add_field(name="👤 Username global", value=member.name, inline=True)
    embed.add_field(name="📛 Pseudo serveur", value=member.display_name, inline=True)

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


# ── GESTION DES ERREURS ────────────────────────────────────────────────────

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message(
            "❌ Cette commande est réservée aux administrateurs.", ephemeral=True
        )
    else:
        logger.error(f"Erreur commande : {error}")


# ── RÔLES AUTOMATIQUES ─────────────────────────────────────────────────────

ROLE_THRESHOLDS = [
    {"name": "🎨 Participant",  "participations": 1,  "victories": 0},
    {"name": "🖌️ Compétiteur", "participations": 5,  "victories": 0},
    {"name": "⭐ Finaliste",    "participations": 0,  "victories": 1},
    {"name": "🏆 Champion",     "participations": 0,  "victories": 3},
    {"name": "👑 Légende BALO", "participations": 0,  "victories": 5},
]


async def update_roles(guild: discord.Guild, user_id: str):
    member = guild.get_member(int(user_id))
    if not member:
        return
    stats = db.get_user_stats(user_id)
    if not stats:
        return
    for t in ROLE_THRESHOLDS:
        role = discord.utils.get(guild.roles, name=t["name"])
        if not role:
            continue
        qualifies = stats["participations"] >= t["participations"] and stats["victories"] >= t["victories"]
        if qualifies and role not in member.roles:
            try:
                await member.add_roles(role)
                logger.info(f"Rôle '{role.name}' → {member.display_name}")
            except discord.Forbidden:
                logger.warning(f"Impossible d'attribuer '{role.name}'")


# ── LANCEMENT (géré par main.py) ───────────────────────────────────────────
# Le bot est lancé depuis main.py
