# 👑 Le Héraut — Bot de classement BALO

Bot Discord de gamification pour la **Bataille de Logos** du serveur BALO.  
Il track les participations, les victoires, les streaks et génère une page web de classement.

---

## 📁 Structure du projet

```
le-heraut/
├── main.py          ← Point d'entrée (lance bot + page web)
├── bot.py           ← Bot Discord (commandes, détection des logos)
├── database.py      ← Base de données SQLite
├── web.py           ← Page web de classement (Flask)
├── requirements.txt
├── railway.toml
├── .env.example     ← Modèle de configuration
└── .gitignore
```

---

## 🚀 Installation locale

### 1. Copier et configurer le `.env`
```bash
cp .env.example .env
```
Ouvre `.env` et remplace `METS_TON_TOKEN_ICI` par le token de ton bot.

### 2. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 3. Lancer le bot
```bash
python main.py
```

---

## ☁️ Déploiement sur Railway

1. Crée un nouveau projet sur [railway.app](https://railway.app)
2. Connecte ton dépôt GitHub contenant ce dossier
3. Dans les **Variables** du projet, ajoute :
   - `DISCORD_TOKEN` = ton token
   - `GUILD_ID` = `671313137550753830`
   - `BATTLE_CHANNEL_ID` = `890677502169735179`
4. Railway détecte automatiquement `railway.toml` et lance `python main.py`
5. Dans **Settings → Networking**, génère un domaine public pour accéder à la page web

---

## 🎮 Commandes Discord

| Commande | Description | Réservée admin |
|---|---|---|
| `/nouvelle-bataille` | Enregistre une nouvelle bataille | ✅ |
| `/cloturer-vote` | Compte les ✅ et désigne le vainqueur | ✅ |
| `/scanner-historique` | Importe les 218 batailles existantes | ✅ |
| `/classement` | Affiche le top 10 | ❌ |
| `/monstats` | Affiche ses propres statistiques | ❌ |

---

## 🏅 Rôles automatiques

Crée ces rôles manuellement dans Discord (exact spelling) :

| Rôle | Condition |
|---|---|
| 🎨 Participant | 1ère soumission |
| 🖌️ Compétiteur | 5 participations |
| ⭐ Finaliste | 1ère victoire |
| 🏆 Champion | 3 victoires |
| 👑 Légende BALO | 5 victoires |

---

## 🔄 Workflow hebdomadaire

**Lundi** — Tu crées le thread → lance `/nouvelle-bataille numero:219 theme:Typographie thread_id:ID_DU_THREAD`  
**Dans la semaine** — Le bot détecte automatiquement les images soumises  
**Samedi** — Ton bot existant place les ✅ sur les logos  
**Dimanche soir** — Tu lances `/cloturer-vote` → le bot compte, annonce le gagnant, attribue les rôles  

---

## 📱 API JSON (pour une future app mobile)

```
GET https://ton-domaine.railway.app/api/leaderboard
```

Retourne tous les joueurs + batailles récentes en JSON.

---

## 🗄️ Première utilisation — importer l'historique

Lance `/scanner-historique limite:250` pour que le bot parcoure les 218 threads existants.  
Il importera toutes les participations visibles et les votes encore disponibles.
