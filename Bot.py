import os
import re
import sqlite3
from threading import Thread

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
from flask import Flask

# Lit le fichier .env (en local). Sur un hébergeur, les variables viennent de ses réglages.
load_dotenv()

intents = discord.Intents.default()
intents.message_content = True  # nécessaire pour lire le texte des messages

bot = commands.Bot(command_prefix="!", intents=intents)

# --- 1. BASE DE DONNÉES ---
# Si le dossier /data existe (sur Render), on stocke la BDD dedans, sinon en local
DB_NAME = "/data/database.db" if os.path.exists("/data") else "database.db"


def init_db():
    """Crée le fichier et la table s'ils n'existent pas encore"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS guil_config (
            guild_id INTEGER PRIMARY KEY,
            salon_id INTEGER,
            role_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()


def save_salon(guild_id, salon_id):
    """Enregistre ou met à jour le salon de logs"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO guil_config (guild_id, salon_id) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET salon_id = excluded.salon_id
    ''', (guild_id, salon_id))
    conn.commit()
    conn.close()


def save_role(guild_id, role_id):
    """Enregistre ou met à jour le rôle vendeur"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO guil_config (guild_id, role_id) VALUES (?, ?)
        ON CONFLICT(guild_id) DO UPDATE SET role_id = excluded.role_id
    ''', (guild_id, role_id))
    conn.commit()
    conn.close()


def get_config(guild_id):
    """Récupère le salon et le rôle d'un serveur"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT salon_id, role_id FROM guil_config WHERE guild_id = ?", (guild_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"salon_id": row[0], "role_id": row[1]}
    return {"salon_id": None, "role_id": None}


init_db()


# --- 2. DÉTECTION DE PHISHING ET D'ARNAQUES ---
FISHFISH_URL = "https://api.fishfish.gg/v1/domains?category=phishing"

# Domaines connus et fiables : on ne les signale jamais (ajoute les tiens si besoin)
DOMAINES_SURS = {"discord.com", "discord.gg", "discordapp.com", "youtube.com", "google.com", "github.com"}

SCAM_KEYWORDS = ["gratuit", "free nitro", "steam-gift", "crypto air-drop", "gagner de l'argent"]

# Repère tout ce qui ressemble à un nom de domaine (avec ou sans https://)
DOMAIN_REGEX = re.compile(r"(?:[a-z0-9-]+\.)+[a-z]{2,}")

phishing_domains = set()


async def charger_liste_phishing():
    """Télécharge la liste des domaines de phishing (sans jamais envoyer les messages des membres)"""
    global phishing_domains
    timeout = aiohttp.ClientTimeout(total=30)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(FISHFISH_URL) as response:
                if response.status != 200:
                    print(f"⚠️ FishFish a répondu avec le code {response.status}")
                    return
                data = await response.json(content_type=None)
        phishing_domains = {domaine.lower() for domaine in data}
        print(f"🛡️ Liste de phishing chargée : {len(phishing_domains)} domaines")
    except Exception as e:
        print(f"⚠️ Impossible de charger la liste de phishing : {e}")


@tasks.loop(hours=6)
async def rafraichir_liste():
    """Met la liste à jour toutes les 6 heures"""
    await charger_liste_phishing()


def trouver_domaine_dangereux(texte):
    """Renvoie le domaine dangereux trouvé dans le texte, ou None"""
    for domaine in DOMAIN_REGEX.findall(texte.lower()):
        parties = domaine.split(".")
        # On teste le domaine complet, puis ses parents (a.b.com -> a.b.com, b.com)
        for i in range(len(parties) - 1):
            candidat = ".".join(parties[i:])
            if candidat in DOMAINES_SURS:
                break
            if candidat in phishing_domains:
                return candidat
    return None


def tronquer(texte, limite=1000):
    """Coupe un texte trop long (limite Discord : 1024 caractères par champ)"""
    return texte if len(texte) <= limite else texte[:limite] + "…"


async def envoyer_log(guild, embed):
    """Envoie une alerte dans le salon de logs du serveur, s'il est configuré"""
    salon_id = get_config(guild.id)["salon_id"]
    salon = guild.get_channel(salon_id) if salon_id else None
    if salon is None:
        return
    try:
        await salon.send(embed=embed)
    except discord.HTTPException as e:
        print(f"⚠️ Impossible d'envoyer l'alerte dans le salon de logs : {e}")


@bot.event
async def on_ready():
    print(f"✅ Bot connecté avec succès en tant que : {bot.user.name}")
    if not rafraichir_liste.is_running():
        rafraichir_liste.start()
    try:
        synced = await bot.tree.sync()
        print(f"🔄 {len(synced)} commande(s) Slash synchronisée(s) avec succès !")
    except Exception as e:
        print(f"❌ Erreur lors de la synchronisation : {e}")


@bot.event
async def on_message(message):
    if message.author.bot or not message.guild:
        return

    domaine = trouver_domaine_dangereux(message.content)
    if domaine:
        try:
            await message.delete()
            supprime = True
        except discord.HTTPException:
            supprime = False  # permission « Gérer les messages » manquante

        embed = discord.Embed(title="🛡️ Lien de Phishing Intercepté", color=discord.Color.red())
        embed.add_field(name="Membre", value=message.author.mention, inline=False)
        embed.add_field(name="Domaine détecté", value=f"`{domaine}`", inline=False)
        embed.add_field(name="Message supprimé", value="Oui" if supprime else "Non (permission manquante)", inline=False)
        await envoyer_log(message.guild, embed)
        return

    contenu_minuscule = message.content.lower()
    if any(keyword in contenu_minuscule for keyword in SCAM_KEYWORDS):
        embed = discord.Embed(title="👀 Mot-clé Sensible Détecté", color=discord.Color.orange())
        embed.add_field(name="Membre", value=message.author.mention, inline=True)
        embed.add_field(name="Message", value=f'"{tronquer(message.content)}"', inline=False)
        await envoyer_log(message.guild, embed)

    await bot.process_commands(message)


# --- 3. COMMANDES SLASH ---
@bot.tree.command(name="config_logs", description="Définit le salon privé pour les alertes d'arnaques (Admin uniquement).")
@app_commands.describe(salon="Le salon textuel secret pour la modération")
@app_commands.guild_only()
@app_commands.checks.has_permissions(administrator=True)
async def config_logs_slash(interaction: discord.Interaction, salon: discord.TextChannel):
    save_salon(interaction.guild.id, salon.id)
    await interaction.response.send_message(f"✅ Configuration réussie ! Les alertes seront envoyées dans {salon.mention}.", ephemeral=True)


@bot.tree.command(name="config_role", description="Définit le rôle qui possède le badge vendeur (Admin uniquement).")
@app_commands.describe(role="Le rôle Discord à attribuer aux vendeurs vérifiés")
@app_commands.guild_only()
@app_commands.checks.has_permissions(administrator=True)
async def config_role_slash(interaction: discord.Interaction, role: discord.Role):
    save_role(interaction.guild.id, role.id)
    await interaction.response.send_message(f"✅ Configuration réussie ! Le rôle vendeur est désormais : **{role.name}**.", ephemeral=True)


@bot.tree.command(name="vendeur", description="Vérifie si un membre possède le badge de vendeur vérifié.")
@app_commands.describe(membre="Le membre à vérifier")
@app_commands.guild_only()
async def check_seller_slash(interaction: discord.Interaction, membre: discord.Member = None):
    membre = membre or interaction.user

    config = get_config(interaction.guild.id)
    role_id = config["role_id"]
    has_role = discord.utils.get(membre.roles, id=role_id) if role_id else None

    if has_role is not None:
        await interaction.response.send_message(f"🔰 **{membre.display_name}** est un **Vendeur Vérifié** (Rôle : {has_role.name}).")
    else:
        await interaction.response.send_message(f"❌ **{membre.display_name}** n'a pas le statut de vendeur vérifié.")


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        texte = "❌ Cette commande est réservée aux administrateurs."
    else:
        print(f"⚠️ Erreur de commande : {error}")
        texte = "⚠️ Une erreur est survenue."
    if interaction.response.is_done():
        await interaction.followup.send(texte, ephemeral=True)
    else:
        await interaction.response.send_message(texte, ephemeral=True)


# --- 4. SERVEUR KEEPALIVE FLASK POUR RENDER ---
app = Flask('')


@app.route('/')
def home():
    return "Bot en ligne et fonctionnel !"


def run_http_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)


def keep_alive():
    t = Thread(target=run_http_server, daemon=True)
    t.start()


if __name__ == "__main__":
    TOKEN = os.environ.get("DISCORD_TOKEN")
    if not TOKEN:
        raise SystemExit("❌ DISCORD_TOKEN introuvable : vérifie ton fichier .env ou les variables de l'hébergeur.")
    keep_alive()
    bot.run(TOKEN)