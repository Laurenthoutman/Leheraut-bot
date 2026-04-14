"""
Point d'entrée principal — lance le bot Discord et le serveur web en parallèle.
"""
import threading
import os
from dotenv import load_dotenv

load_dotenv()


def run_web():
    from web import app
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, use_reloader=False)


def run_bot():
    import bot  # Lance bot.run() à l'intérieur


if __name__ == "__main__":
    # Lance le serveur web dans un thread séparé
    web_thread = threading.Thread(target=run_web, daemon=True)
    web_thread.start()

    # Lance le bot dans le thread principal
    run_bot()
