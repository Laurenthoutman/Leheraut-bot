import sqlite3
import os
from datetime import datetime
from typing import Optional

DB_PATH = os.getenv("DB_PATH", "heraut.db")


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS battles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                number      INTEGER UNIQUE NOT NULL,
                theme       TEXT NOT NULL,
                thread_id   INTEGER UNIQUE NOT NULL,
                closed      INTEGER DEFAULT 0,
                winner_id   TEXT,
                winner_name TEXT,
                winner_votes INTEGER DEFAULT 0,
                manual_override INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS participations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                battle_id   INTEGER NOT NULL,
                user_id     TEXT NOT NULL,
                username    TEXT NOT NULL,
                message_id  INTEGER NOT NULL,
                votes       INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(battle_id, user_id),
                FOREIGN KEY (battle_id) REFERENCES battles(id)
            );

            CREATE TABLE IF NOT EXISTS user_stats (
                user_id         TEXT PRIMARY KEY,
                username        TEXT NOT NULL,
                participations  INTEGER DEFAULT 0,
                victories       INTEGER DEFAULT 0,
                current_streak  INTEGER DEFAULT 0,
                best_streak     INTEGER DEFAULT 0,
                last_battle_id  INTEGER DEFAULT NULL,
                updated_at      TEXT DEFAULT (datetime('now'))
            );
        """)
        # Migration : ajoute manual_override si absent (base existante)
        try:
            self.conn.execute("ALTER TABLE battles ADD COLUMN manual_override INTEGER DEFAULT 0")
            self.conn.commit()
        except Exception:
            pass  # Colonne déjà présente

    # ─── BATTLES ───────────────────────────────────────

    def create_battle(self, number: int, theme: str, thread_id: int, closed: bool = False) -> int:
        try:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO battles (number, theme, thread_id, closed) VALUES (?, ?, ?, ?)",
                (number, theme, thread_id, int(closed))
            )
            self.conn.commit()
            if cur.lastrowid:
                return cur.lastrowid
            row = self.conn.execute("SELECT id FROM battles WHERE number=?", (number,)).fetchone()
            return row["id"]
        except Exception as e:
            print(f"[DB] create_battle error: {e}")
            return -1

    def get_active_battle(self) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM battles WHERE closed=0 ORDER BY number DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def get_battle_by_thread(self, thread_id: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM battles WHERE thread_id=?", (thread_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_battle_by_number(self, number: int) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM battles WHERE number=?", (number,)
        ).fetchone()
        return dict(row) if row else None

    def close_battle(self, battle_id: int, winner_id: str, winner_name: str, winner_votes: int):
        self.conn.execute(
            """UPDATE battles SET closed=1, winner_id=?, winner_name=?, winner_votes=?
               WHERE id=?""",
            (winner_id, winner_name, winner_votes, battle_id)
        )
        self.conn.commit()
        self._update_user_stats_after_battle(battle_id, winner_id)

    def _update_user_stats_after_battle(self, battle_id: int, winner_id: str):
        """Met à jour les stats et streaks après clôture d'une bataille."""
        participations = self.get_participations(battle_id)

        for p in participations:
            uid = p["user_id"]
            uname = p["username"]
            is_winner = uid == winner_id

            # Récupère ou crée les stats
            row = self.conn.execute(
                "SELECT * FROM user_stats WHERE user_id=?", (uid,)
            ).fetchone()

            if row:
                stats = dict(row)
                new_participations = stats["participations"] + 1
                new_victories = stats["victories"] + (1 if is_winner else 0)

                # Calcul du streak
                last_battle = self.conn.execute(
                    "SELECT id FROM battles WHERE id < ? AND closed=1 ORDER BY id DESC LIMIT 1",
                    (battle_id,)
                ).fetchone()

                participated_last = False
                if last_battle:
                    prev = self.conn.execute(
                        "SELECT id FROM participations WHERE battle_id=? AND user_id=?",
                        (last_battle["id"], uid)
                    ).fetchone()
                    participated_last = prev is not None

                if participated_last:
                    new_streak = stats["current_streak"] + 1
                else:
                    new_streak = 1

                new_best = max(stats["best_streak"], new_streak)

                self.conn.execute(
                    """UPDATE user_stats SET
                        username=?, participations=?, victories=?,
                        current_streak=?, best_streak=?, last_battle_id=?, updated_at=datetime('now')
                       WHERE user_id=?""",
                    (uname, new_participations, new_victories, new_streak, new_best, battle_id, uid)
                )
            else:
                self.conn.execute(
                    """INSERT INTO user_stats
                        (user_id, username, participations, victories, current_streak, best_streak, last_battle_id)
                       VALUES (?, ?, 1, ?, 1, 1, ?)""",
                    (uid, uname, 1 if is_winner else 0, battle_id)
                )

        self.conn.commit()

    # ─── PARTICIPATIONS ────────────────────────────────

    def add_participation(self, battle_id: int, user_id: str, username: str, message_id: int) -> bool:
        """Retourne True si la participation existait déjà."""
        existing = self.conn.execute(
            "SELECT id FROM participations WHERE battle_id=? AND user_id=?",
            (battle_id, user_id)
        ).fetchone()
        if existing:
            return True

        self.conn.execute(
            "INSERT INTO participations (battle_id, user_id, username, message_id) VALUES (?, ?, ?, ?)",
            (battle_id, user_id, username, message_id)
        )
        self.conn.commit()
        return False

    def get_participations(self, battle_id: int) -> list:
        rows = self.conn.execute(
            "SELECT * FROM participations WHERE battle_id=?", (battle_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def update_votes(self, battle_id: int, user_id: str, votes: int):
        self.conn.execute(
            "UPDATE participations SET votes=? WHERE battle_id=? AND user_id=?",
            (votes, battle_id, user_id)
        )
        self.conn.commit()

    # ─── STATS & CLASSEMENT ────────────────────────────

    def get_user_stats(self, user_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM user_stats WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_user_rank(self, user_id: str) -> int:
        row = self.conn.execute("""
            SELECT COUNT(*) + 1 as rank FROM user_stats
            WHERE victories > (SELECT victories FROM user_stats WHERE user_id=?)
               OR (victories = (SELECT victories FROM user_stats WHERE user_id=?)
                   AND participations > (SELECT participations FROM user_stats WHERE user_id=?))
        """, (user_id, user_id, user_id)).fetchone()
        return row["rank"] if row else 1

    def get_leaderboard(self, limit: int = 10) -> list:
        rows = self.conn.execute("""
            SELECT * FROM user_stats
            ORDER BY victories DESC, participations DESC, current_streak DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_all_stats(self) -> list:
        """Pour la page web — retourne tous les joueurs classés."""
        rows = self.conn.execute("""
            SELECT
                user_id, username, participations, victories,
                current_streak, best_streak,
                CASE WHEN participations > 0
                     THEN ROUND(victories * 100.0 / participations, 1)
                     ELSE 0 END as win_rate
            FROM user_stats
            ORDER BY victories DESC, participations DESC, current_streak DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def update_username_if_changed(self, user_id: str, real_name: str) -> str:
        """
        Met à jour le username en base si nécessaire.
        Retourne 'updated', 'merged' ou 'ok'.
        """
        # Cherche une entrée avec cet ID
        row = self.conn.execute(
            "SELECT * FROM user_stats WHERE user_id=?", (user_id,)
        ).fetchone()

        if row:
            if dict(row)["username"] != real_name:
                self.conn.execute(
                    "UPDATE user_stats SET username=? WHERE user_id=?",
                    (real_name, user_id)
                )
                # Met aussi à jour les participations
                self.conn.execute(
                    "UPDATE participations SET username=? WHERE user_id=?",
                    (real_name, user_id)
                )
                self.conn.commit()
                return "updated"
            return "ok"

        # Cherche un doublon par nom similaire (cas mode streamer)
        # Si une entrée existe avec un nom tronqué (ex: "P...") pour un ID différent
        # mais qu'on retrouve le même message_id dans les participations, on fusionne
        dupe = self.conn.execute("""
            SELECT DISTINCT p.user_id FROM participations p
            JOIN participations p2 ON p2.message_id = p.message_id AND p2.user_id = ?
            WHERE p.user_id != ?
            LIMIT 1
        """, (user_id, user_id)).fetchone()

        if dupe:
            old_id = dupe["user_id"]
            # Fusionne : réattribue toutes les participations et victoires à l'ID réel
            self.conn.execute(
                "UPDATE participations SET user_id=?, username=? WHERE user_id=?",
                (user_id, real_name, old_id)
            )
            self.conn.execute(
                "UPDATE battles SET winner_id=?, winner_name=? WHERE winner_id=?",
                (user_id, real_name, old_id)
            )
            self.conn.execute("DELETE FROM user_stats WHERE user_id=?", (old_id,))
            self.conn.commit()
            return "merged"

        return "ok"

    def add_participation_if_missing(self, battle_id: int, user_id: str, username: str):
        """Ajoute une participation avec message_id=0 si elle n'existe pas encore."""
        existing = self.conn.execute(
            "SELECT id FROM participations WHERE battle_id=? AND user_id=?",
            (battle_id, user_id)
        ).fetchone()
        if not existing:
            self.conn.execute(
                "INSERT INTO participations (battle_id, user_id, username, message_id) VALUES (?, ?, ?, 0)",
                (battle_id, user_id, username)
            )
            self.conn.commit()

    def get_all_participations_for_user(self, user_id: str) -> list:
        rows = self.conn.execute("""
            SELECT p.*, b.number as battle_number
            FROM participations p
            JOIN battles b ON b.id = p.battle_id
            WHERE p.user_id = ?
            ORDER BY b.number ASC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_battles_won_by(self, user_id: str) -> list:
        rows = self.conn.execute("""
            SELECT * FROM battles
            WHERE winner_id = ? AND closed = 1
            ORDER BY number ASC
        """, (user_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_user_stats_by_username(self, username: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM user_stats WHERE LOWER(username)=LOWER(?)", (username,)
        ).fetchone()
        return dict(row) if row else None

    def force_winner(self, battle_id: int, winner_id: str, winner_name: str):
        """Écrase le gagnant d'une bataille et la verrouille contre le scanner."""
        self.conn.execute(
            """UPDATE battles
               SET closed=1, winner_id=?, winner_name=?, manual_override=1
               WHERE id=?""",
            (winner_id, winner_name, battle_id)
        )
        self.conn.commit()

    def reset_all(self):
        """Remet toutes les tables à zéro."""
        self.conn.executescript("""
            DELETE FROM participations;
            DELETE FROM battles;
            DELETE FROM user_stats;
        """)
        self.conn.commit()

    def close_battle_silent(self, battle_id: int, winner_id: str, winner_votes: int):
        """Met à jour le gagnant sans recalculer les stats (utilisé pendant le scan)."""
        self.conn.execute(
            "UPDATE battles SET closed=1, winner_id=?, winner_votes=? WHERE id=?",
            (winner_id, winner_votes, battle_id)
        )
        self.conn.commit()

    def rebuild_user_stats(self):
        """Reconstruit entièrement user_stats depuis les participations et batailles."""
        self.conn.execute("DELETE FROM user_stats")
        self.conn.commit()

        # Récupère toutes les batailles fermées triées par numéro
        battles = self.conn.execute(
            "SELECT * FROM battles WHERE closed=1 ORDER BY number ASC"
        ).fetchall()

        # Pour chaque utilisateur, reconstruit les stats en ordre chronologique
        user_data = {}  # user_id -> {participations, victories, current_streak, best_streak, last_battle_number}

        for battle in battles:
            bid = battle["id"]
            bnum = battle["number"]
            winner_id = battle["winner_id"]

            parts = self.conn.execute(
                "SELECT * FROM participations WHERE battle_id=?", (bid,)
            ).fetchall()

            for p in parts:
                uid = p["user_id"]
                uname = p["username"]

                if uid not in user_data:
                    user_data[uid] = {
                        "username": uname,
                        "participations": 0,
                        "victories": 0,
                        "current_streak": 0,
                        "best_streak": 0,
                        "last_battle_number": None,
                    }

                d = user_data[uid]
                d["participations"] += 1
                if uid == winner_id:
                    d["victories"] += 1

                # Calcul du streak
                if d["last_battle_number"] is not None and bnum == d["last_battle_number"] + 1:
                    d["current_streak"] += 1
                else:
                    d["current_streak"] = 1

                d["best_streak"] = max(d["best_streak"], d["current_streak"])
                d["last_battle_number"] = bnum

        # Insère les stats reconstruites
        for uid, d in user_data.items():
            self.conn.execute(
                """INSERT INTO user_stats
                   (user_id, username, participations, victories, current_streak, best_streak)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (uid, d["username"], d["participations"], d["victories"],
                 d["current_streak"], d["best_streak"])
            )
        self.conn.commit()

    def get_recent_battles(self, limit: int = 10) -> list:
        rows = self.conn.execute("""
            SELECT * FROM battles WHERE closed=1
            ORDER BY number DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def get_total_battles(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM battles WHERE closed=1").fetchone()
        return row["c"] if row else 0
