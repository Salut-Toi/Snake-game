# db.py
import sqlite3
from pathlib import Path
from contextlib import closing

DB_PATH = Path(__file__).with_name("snake.db")

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.executescript("""
        PRAGMA foreign_keys = ON;

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

        CREATE INDEX IF NOT EXISTS idx_runs_score ON runs(score DESC);
        CREATE INDEX IF NOT EXISTS idx_runs_player ON runs(player_id);
        """)

def get_or_create_player(username: str) -> int | None:
    username = (username or "").strip()
    if not username:
        return None
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("SELECT id FROM players WHERE username = ?", (username,))
        row = c.fetchone()
        if row:
            return row[0]
        c.execute("INSERT INTO players(username) VALUES (?)", (username,))
        return c.lastrowid

def record_run(score: int, player_id: int | None = None,
               duration_seconds: int | None = None, steps: int | None = None):
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO runs(player_id, score, duration_seconds, steps) VALUES (?, ?, ?, ?)",
            (player_id, score, duration_seconds, steps),
        )
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
