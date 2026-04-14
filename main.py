"""
Point d'entrée principal — lance le bot Discord et le serveur web en parallèle.
Le bot et Flask partagent la même instance de base de données.
"""
import threading
import os
from dotenv import load_dotenv

load_dotenv()

# Définit le chemin absolu de la BDD une seule fois pour tout le projet
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "heraut.db")
os.environ["DB_PATH"] = DB_PATH

# Importe la BDD et crée une instance unique partagée
from database import Database
shared_db = Database()

# Injecte cette instance dans bot et web avant leur démarrage
import bot as bot_module
import web as web_module

bot_module.db = shared_db
web_module.db = shared_db


def run_web():
    port = int(os.getenv("PORT", 8080))
    web_module.app.run(host="0.0.0.0", port=port, use_reloader=False)


def run_bot():
    bot_module.bot.run(os.getenv("DISCORD_TOKEN"))


if __name__ == "__main__":
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()
    run_bot()
