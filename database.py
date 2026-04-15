import sqlite3
import os
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
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                number          INTEGER UNIQUE NOT NULL,
                theme           TEXT NOT NULL,
                thread_id       INTEGER UNIQUE NOT NULL,
                closed          INTEGER DEFAULT 0,
                winner_id       TEXT DEFAULT NULL,
                winner_name     TEXT DEFAULT NULL,
                created_at      TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS participations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                battle_id   INTEGER NOT NULL,
                user_id     TEXT NOT NULL,
                username    TEXT NOT NULL,
                message_id  INTEGER NOT NULL,
                votes       INTEGER DEFAULT 0,
                UNIQUE(battle_id, user_id),
                FOREIGN KEY (battle_id) REFERENCES battles(id)
            );

            CREATE TABLE IF NOT EXISTS user_stats (
                user_id         TEXT PRIMARY KEY,
                username        TEXT NOT NULL,
                participations  INTEGER DEFAULT 0,
                victories       INTEGER DEFAULT 0,
                current_streak  INTEGER DEFAULT 0,
                best_streak     INTEGER DEFAULT 0
            );
        """)
        self.conn.commit()

    # ── BATTLES ──────────────────────────────────────────────────────────

    def create_battle(self, number: int, theme: str, thread_id: int) -> int:
        try:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO battles (number, theme, thread_id) VALUES (?, ?, ?)",
                (number, theme, thread_id)
            )
            self.conn.commit()
            if cur.lastrowid:
                return cur.lastrowid
            row = self.conn.execute("SELECT id FROM battles WHERE number=?", (number,)).fetchone()
            return row["id"]
        except Exception as e:
            print(f"[DB] create_battle error: {e}")
            return -1

    def get_battle_by_number(self, number: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM battles WHERE number=?", (number,)).fetchone()
        return dict(row) if row else None

    def get_battle_by_thread(self, thread_id: int) -> Optional[dict]:
        row = self.conn.execute("SELECT * FROM battles WHERE thread_id=?", (thread_id,)).fetchone()
        return dict(row) if row else None

    def get_active_battle(self) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM battles WHERE closed=0 ORDER BY number DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def set_winner(self, battle_id: int, winner_id: str, winner_name: str):
        """Définit le gagnant d'une bataille et reconstruit les stats."""
        self.conn.execute(
            "UPDATE battles SET closed=1, winner_id=?, winner_name=? WHERE id=?",
            (winner_id, winner_name, battle_id)
        )
        self.conn.commit()
        self.rebuild_user_stats()

    # ── PARTICIPATIONS ────────────────────────────────────────────────────

    def add_participation(self, battle_id: int, user_id: str, username: str, message_id: int) -> bool:
        """Retourne True si la participation existait déjà."""
        existing = self.conn.execute(
            "SELECT id FROM participations WHERE battle_id=? AND user_id=?",
            (battle_id, user_id)
        ).fetchone()
        if existing:
            # Met à jour le username au passage (corrige le mode streamer)
            self.conn.execute(
                "UPDATE participations SET username=? WHERE battle_id=? AND user_id=?",
                (username, battle_id, user_id)
            )
            self.conn.commit()
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

    def add_participation_if_missing(self, battle_id: int, user_id: str, username: str):
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

    # ── STATS ─────────────────────────────────────────────────────────────

    def rebuild_user_stats(self):
        """Reconstruit entièrement user_stats depuis les participations et batailles."""
        self.conn.execute("DELETE FROM user_stats")
        self.conn.commit()

        battles = self.conn.execute(
            "SELECT * FROM battles ORDER BY number ASC"
        ).fetchall()

        user_data = {}

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
                d["username"] = uname  # Toujours le nom le plus récent
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

        for uid, d in user_data.items():
            self.conn.execute(
                """INSERT INTO user_stats
                   (user_id, username, participations, victories, current_streak, best_streak)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (uid, d["username"], d["participations"], d["victories"],
                 d["current_streak"], d["best_streak"])
            )
        self.conn.commit()

    def get_user_stats(self, user_id: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM user_stats WHERE user_id=?", (user_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_user_stats_by_username(self, username: str) -> Optional[dict]:
        row = self.conn.execute(
            "SELECT * FROM user_stats WHERE LOWER(username)=LOWER(?)", (username,)
        ).fetchone()
        return dict(row) if row else None

    def get_user_rank(self, user_id: str) -> int:
        row = self.conn.execute("""
            SELECT COUNT(*) + 1 as rank FROM user_stats
            WHERE victories > (SELECT COALESCE(victories, 0) FROM user_stats WHERE user_id=?)
               OR (victories = (SELECT COALESCE(victories, 0) FROM user_stats WHERE user_id=?)
                   AND participations > (SELECT COALESCE(participations, 0) FROM user_stats WHERE user_id=?))
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
        rows = self.conn.execute("""
            SELECT
                user_id, username, participations, victories,
                current_streak, best_streak
            FROM user_stats
            ORDER BY victories DESC, participations DESC, current_streak DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def get_total_battles(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM battles WHERE closed=1").fetchone()
        return row["c"] if row else 0

    def get_recent_battles(self, limit: int = 10) -> list:
        rows = self.conn.execute("""
            SELECT * FROM battles WHERE closed=1
            ORDER BY number DESC LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
