# db.py
import sqlite3
from pathlib import Path
from contextlib import closing

DB_PATH = Path(__file__).with_name("snake.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def _column_exists(c, table: str, column: str) -> bool:
    c.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in c.fetchall())

def init_db():
    """Initialise/upgrade le schéma SANS effacer les données."""
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON")

        # 1) Tables (si elles n'existent pas)
        c.executescript("""
        CREATE TABLE IF NOT EXISTS players (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          username TEXT NOT NULL UNIQUE,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          player_id INTEGER,
          score INTEGER NOT NULL,
          duration_seconds INTEGER,
          steps INTEGER,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS settings (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS best_scores (
          player_id INTEGER PRIMARY KEY,
          best_score INTEGER NOT NULL,
          updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
        );
        """)

        # 2) Upgrades de colonnes (ajout si manquantes)
        if not _column_exists(c, "runs", "speed_mode"):
            c.execute("ALTER TABLE runs ADD COLUMN speed_mode TEXT DEFAULT 'normal'")
        if not _column_exists(c, "runs", "wrap_walls"):
            c.execute("ALTER TABLE runs ADD COLUMN wrap_walls INTEGER DEFAULT 0")

        # 3) Index (après que les colonnes existent)
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_runs_score ON runs(score DESC)")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_runs_player ON runs(player_id)")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_runs_speed ON runs(speed_mode)")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_runs_wrap ON runs(wrap_walls)")
        except sqlite3.OperationalError:
            pass


def get_or_create_player(username: str) -> int | None:
    username = (username or "").strip()
    if not username:
        return None
    if not (3 <= len(username) <= 20):
        raise ValueError("Username must be 3..20 chars: letters, digits, space, _ or -")

    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("SELECT id FROM players WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            return row[0]
        c.execute("INSERT INTO players(username) VALUES (?)", (username,))
        return c.lastrowid


def record_run(score: int, player_id: int | None = None,
               duration_seconds: int | None = None, steps: int | None = None,
               speed_mode: str | None = None, wrap_walls: int | None = None):
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO runs(player_id, score, duration_seconds, steps, speed_mode, wrap_walls)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (player_id, score, duration_seconds, steps, speed_mode or "normal", wrap_walls or 0))

        if player_id is not None:
            c.execute("""
                INSERT INTO best_scores(player_id, best_score)
                VALUES (?, ?)
                ON CONFLICT(player_id) DO UPDATE SET
                    best_score = MAX(best_score, excluded.best_score),
                    updated_at = CURRENT_TIMESTAMP
            """, (player_id, score))


def top_scores(limit: int = 10):
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT runs.score,
                   COALESCE(players.username, 'Invité') AS username,
                   runs.created_at
            FROM runs
            LEFT JOIN players ON players.id = runs.player_id
            ORDER BY runs.score DESC, runs.created_at ASC
            LIMIT ?
        """, (limit,))
        return c.fetchall()


def leaderboard(period: str = "daily", limit: int = 10,
                speed_mode: str | None = None, wrap_walls: bool | None = None):
    with closing(get_conn()) as conn:
        c = conn.cursor()

        if period == "daily":
            date_cond = "DATE(runs.created_at) = DATE('now','localtime')"
        elif period == "weekly":
            date_cond = "strftime('%W', runs.created_at) = strftime('%W', 'now','localtime')"
        elif period == "monthly":
            date_cond = "strftime('%Y-%m', runs.created_at) = strftime('%Y-%m', 'now','localtime')"
        else:
            date_cond = "1=1"

        filters = [date_cond]
        params = []
        if speed_mode is not None:
            filters.append("runs.speed_mode = ?")
            params.append(speed_mode)
        if wrap_walls is not None:
            filters.append("runs.wrap_walls = ?")
            params.append(1 if wrap_walls else 0)

        where_clause = " AND ".join(filters)
        query = f"""
            SELECT runs.score,
                   COALESCE(players.username, 'Invité') AS username,
                   runs.created_at
            FROM runs
            LEFT JOIN players ON players.id = runs.player_id
            WHERE {where_clause}
            ORDER BY runs.score DESC, runs.created_at ASC
            LIMIT ?
        """
        params.append(limit)
        c.execute(query, params)
        return c.fetchall()


def player_best(player_id: int) -> int | None:
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT best_score FROM best_scores WHERE player_id = ?", (player_id,))
        row = c.fetchone()
        return row[0] if row else None


def set_setting(key: str, value: str):
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO settings(key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))


def get_setting(key: str, default: str | None = None) -> str | None:
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = c.fetchone()
        return row[0] if row else default
