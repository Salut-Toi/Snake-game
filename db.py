# db.py
import re
import sqlite3
from pathlib import Path
from contextlib import closing

DB_PATH = Path(__file__).with_name("snake.db")

ALLOWED_USERNAME_RE = re.compile(r"^[A-Za-z0-9 _-]{3,20}$")  # 3..20, alphanum + espace/_/-

def get_conn():
    # isolation_level=None (autocommit) non nécessaire ici, on utilise "with conn:"
    return sqlite3.connect(DB_PATH)

# ---------- Helpers internes ----------

def _executescript(conn, sql: str) -> None:
    if not sql.strip():
        return
    conn.executescript(sql)

def _column_exists(conn, table: str, column: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())

# ---------- Schéma + contraintes + triggers + vues ----------

def init_db():
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON;")

        # -- Tables de base
        _executescript(conn, """
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

        # -- Tables avancées
        _executescript(conn, """
        CREATE TABLE IF NOT EXISTS achievements(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          code TEXT NOT NULL UNIQUE,
          name TEXT NOT NULL,
          description TEXT,
          threshold_score INTEGER,
          threshold_runs  INTEGER,
          created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS player_achievements(
          player_id INTEGER NOT NULL,
          achievement_id INTEGER NOT NULL,
          unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY (player_id, achievement_id),
          FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
          FOREIGN KEY (achievement_id) REFERENCES achievements(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS seasons(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL UNIQUE,
          start_date DATE NOT NULL,
          end_date   DATE
        );
        """)

        # -- Colonne season_id (si absente)
        if not _column_exists(conn, "runs", "season_id"):
            try:
                c.execute("ALTER TABLE runs ADD COLUMN season_id INTEGER REFERENCES seasons(id)")
            except sqlite3.DatabaseError:
                pass  # si déjà ajoutée par une autre exécution, on ignore

        # -- Index performance complémentaires
        _executescript(conn, """
        CREATE INDEX IF NOT EXISTS idx_runs_created_at ON runs(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_runs_player_created ON runs(player_id, created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_best_scores_score ON best_scores(best_score DESC);
        """)

        # -- Triggers de validation (contraintes via triggers, non destructifs)

        # Vérification username conforme (INSERT)
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_players_validate_bi
        BEFORE INSERT ON players
        FOR EACH ROW
        WHEN NEW.username IS NULL
             OR length(trim(NEW.username)) < 3
             OR length(trim(NEW.username)) > 20
             OR trim(NEW.username) GLOB '*[^A-Za-z0-9 _-]*'
        BEGIN
          SELECT RAISE(ABORT, 'Invalid username');
        END;
        """)

        # Vérification username conforme (UPDATE)
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_players_validate_bu
        BEFORE UPDATE ON players
        FOR EACH ROW
        WHEN NEW.username IS NULL
             OR length(trim(NEW.username)) < 3
             OR length(trim(NEW.username)) > 20
             OR trim(NEW.username) GLOB '*[^A-Za-z0-9 _-]*'
        BEGIN
          SELECT RAISE(ABORT, 'Invalid username');
        END;
        """)

        # Runs: valeurs non négatives (INSERT)
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_runs_validate_bi
        BEFORE INSERT ON runs
        FOR EACH ROW
        WHEN NEW.score < 0
          OR (NEW.duration_seconds IS NOT NULL AND NEW.duration_seconds < 0)
          OR (NEW.steps IS NOT NULL AND NEW.steps < 0)
        BEGIN
          SELECT RAISE(ABORT, 'Invalid run values');
        END;
        """)

        # Runs: valeurs non négatives (UPDATE)
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_runs_validate_bu
        BEFORE UPDATE ON runs
        FOR EACH ROW
        WHEN NEW.score < 0
          OR (NEW.duration_seconds IS NOT NULL AND NEW.duration_seconds < 0)
          OR (NEW.steps IS NOT NULL AND NEW.steps < 0)
        BEGIN
          SELECT RAISE(ABORT, 'Invalid run values');
        END;
        """)

        # best_scores: recalcul après DELETE d'une run
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_runs_ad_recompute_best
        AFTER DELETE ON runs
        FOR EACH ROW
        BEGIN
          UPDATE best_scores
             SET best_score = COALESCE((SELECT MAX(score) FROM runs WHERE player_id = OLD.player_id), 0),
                 updated_at = CURRENT_TIMESTAMP
           WHERE player_id = OLD.player_id;

          DELETE FROM best_scores
           WHERE player_id = OLD.player_id
             AND NOT EXISTS (SELECT 1 FROM runs WHERE player_id = OLD.player_id);
        END;
        """)

        # settings.updated_at : mise à jour auto (sans boucle infinie)
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_settings_touch_au
        AFTER UPDATE ON settings
        FOR EACH ROW
        WHEN NEW.updated_at = OLD.updated_at
        BEGIN
          UPDATE settings SET updated_at = CURRENT_TIMESTAMP WHERE key = NEW.key;
        END;
        """)

        # Saisons : si season_id NULL, affecter la saison courante depuis settings
        _executescript(conn, """
        INSERT OR IGNORE INTO settings(key, value) VALUES ('current_season_id', NULL);

        CREATE TRIGGER IF NOT EXISTS trg_runs_ai_set_season
        AFTER INSERT ON runs
        FOR EACH ROW
        WHEN NEW.season_id IS NULL
        BEGIN
          UPDATE runs
             SET season_id = (SELECT CAST(value AS INTEGER) FROM settings WHERE key='current_season_id')
           WHERE id = NEW.id;
        END;
        """)

        # Succès : déblocage auto score et volume de parties
        _executescript(conn, """
        CREATE TRIGGER IF NOT EXISTS trg_runs_ai_unlock_achievements
        AFTER INSERT ON runs
        FOR EACH ROW
        BEGIN
          -- Par score
          INSERT INTO player_achievements(player_id, achievement_id)
          SELECT NEW.player_id, a.id
          FROM achievements a
          WHERE NEW.player_id IS NOT NULL
            AND a.threshold_score IS NOT NULL
            AND NEW.score >= a.threshold_score
            AND NOT EXISTS (
              SELECT 1 FROM player_achievements pa
              WHERE pa.player_id = NEW.player_id AND pa.achievement_id = a.id
            );

          -- Par nombre total de runs
          INSERT INTO player_achievements(player_id, achievement_id)
          SELECT NEW.player_id, a.id
          FROM achievements a
          WHERE NEW.player_id IS NOT NULL
            AND a.threshold_runs IS NOT NULL
            AND (SELECT COUNT(*) FROM runs r WHERE r.player_id = NEW.player_id) >= a.threshold_runs
            AND NOT EXISTS (
              SELECT 1 FROM player_achievements pa
              WHERE pa.player_id = NEW.player_id AND pa.achievement_id = a.id
            );
        END;
        """)

        # Vues : stats joueur + leaderboards périodiques
        _executescript(conn, """
        CREATE VIEW IF NOT EXISTS v_player_stats AS
        SELECT
          p.id AS player_id,
          p.username,
          COUNT(r.id)              AS runs_count,
          COALESCE(MAX(r.score),0) AS best_score,
          ROUND(AVG(r.score),2)    AS avg_score,
          COALESCE(SUM(r.duration_seconds),0) AS total_seconds,
          MAX(r.created_at)        AS last_played
        FROM players p
        LEFT JOIN runs r ON r.player_id = p.id
        GROUP BY p.id, p.username;

        CREATE VIEW IF NOT EXISTS v_leaderboard_daily AS
        SELECT r.score, COALESCE(p.username,'Invité') AS username, r.created_at
        FROM runs r LEFT JOIN players p ON p.id = r.player_id
        WHERE date(r.created_at) = date('now','localtime')
        ORDER BY r.score DESC, r.created_at ASC
        LIMIT 10;

        CREATE VIEW IF NOT EXISTS v_leaderboard_weekly AS
        SELECT r.score, COALESCE(p.username,'Invité') AS username, r.created_at
        FROM runs r LEFT JOIN players p ON p.id = r.player_id
        WHERE strftime('%W', r.created_at) = strftime('%W','now','localtime')
          AND strftime('%Y', r.created_at) = strftime('%Y','now','localtime')
        ORDER BY r.score DESC, r.created_at ASC
        LIMIT 10;

        CREATE VIEW IF NOT EXISTS v_leaderboard_monthly AS
        SELECT r.score, COALESCE(p.username,'Invité') AS username, r.created_at
        FROM runs r LEFT JOIN players p ON p.id = r.player_id
        WHERE strftime('%Y-%m', r.created_at) = strftime('%Y-%m','now','localtime')
        ORDER BY r.score DESC, r.created_at ASC
        LIMIT 10;
        """)

# ---------- API de lecture/écriture ----------

def get_or_create_player(username: str) -> int | None:
    """Crée ou renvoie un joueur en normalisant le pseudo (trim + lower).
       Déclenchera une erreur si le pseudo ne respecte pas le pattern."""
    username = (username or "").strip().lower()
    if not username:
        return None
    if not ALLOWED_USERNAME_RE.fullmatch(username):
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
               season_id: int | None = None):
    """Enregistre une partie. best_scores & achievements se mettent à jour via triggers.
       season_id est optionnel : si None, la saison courante (settings.current_season_id) sera affectée par trigger."""
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO runs(player_id, score, duration_seconds, steps, season_id) VALUES (?, ?, ?, ?, ?)",
            (player_id, score, duration_seconds, steps, season_id),
        )
        if player_id is not None:
            # upsert best_scores (géré aussi en delete par trigger)
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

def leaderboard(period: str = "all", limit: int = 10):
    """period: 'all' | 'daily' | 'weekly' | 'monthly' (utilise les vues)"""
    if period == "daily":
        view = "v_leaderboard_daily"
    elif period == "weekly":
        view = "v_leaderboard_weekly"
    elif period == "monthly":
        view = "v_leaderboard_monthly"
    else:
        # fallback sur top_scores global
        return top_scores(limit)
    with closing(get_conn()) as conn:
        c = conn.cursor()
        c.execute(f"SELECT * FROM {view}")
        rows = c.fetchall()
        return rows[:limit]

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

def seed_achievements_if_empty():
    """Optionnel : appeler une fois pour préremplir des succès."""
    with closing(get_conn()) as conn, conn:
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM achievements")
        if c.fetchone()[0] == 0:
            c.executemany(
                "INSERT INTO achievements(code, name, threshold_score) VALUES (?, ?, ?)",
                [
                    ('SCORE_10',  'Premier palier',    10),
                    ('SCORE_50',  'Serpent confirmé',  50),
                    ('SCORE_100', 'Maître du serpent', 100),
                ]
            )
            c.executemany(
                "INSERT INTO achievements(code, name, threshold_runs) VALUES (?, ?, ?)",
                [
                    ('RUNS_10',  'Assidu',   10),
                    ('RUNS_50',  'Endurant', 50),
                ]
            )
