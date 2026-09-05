# ============================================================
# HoldEm Agent — Database SQLite
# ============================================================

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "holdem.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def init_db():
    """Crea tutte le tabelle se non esistono."""
    conn = get_connection()
    cur = conn.cursor()

    # Profilazione avversari
    cur.execute("""
        CREATE TABLE IF NOT EXISTS opponent_stats (
            player_id TEXT PRIMARY KEY,
            hands_observed INTEGER DEFAULT 0,
            vpip REAL DEFAULT 0,
            pfr REAL DEFAULT 0,
            af REAL DEFAULT 0,
            fold_to_cbet REAL DEFAULT 0,
            last_updated TIMESTAMP
        )
    """)

    # Correzioni vocali (Sotto-Flusso B)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS voice_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP,
            hand_id TEXT,
            action_proposed TEXT,
            action_user TEXT,
            motivation TEXT
        )
    """)

    # Configurazione torneo
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tournament_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Correzioni percettive (Sotto-Flusso D)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS perception_corrections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP,
            environment TEXT,
            table_format TEXT,
            data_type TEXT,
            value_wrong TEXT,
            value_correct TEXT
        )
    """)

    # Storico mani
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hand_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP,
            hand_id TEXT,
            hero_cards TEXT,
            board TEXT,
            pot INTEGER,
            action_taken TEXT,
            action_eval TEXT,
            outcome TEXT,
            fallback_used INTEGER DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def save_tournament_config(key, value):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO tournament_config (key, value) VALUES (?, ?)",
        (key, value)
    )
    conn.commit()
    conn.close()


def get_tournament_config(key):
    conn = get_connection()
    row = conn.execute("SELECT value FROM tournament_config WHERE key = ?", (key,)).fetchone()
    conn.close()
    return row[0] if row else None


# ------------------------------------------------------------------
# Opponent Stats (Step 12)
# ------------------------------------------------------------------

def get_opponent_stats(player_id):
    """Ritorna stats di un avversario o None."""
    conn = get_connection()
    row = conn.execute(
        "SELECT player_id, hands_observed, vpip, pfr, af, fold_to_cbet, last_updated "
        "FROM opponent_stats WHERE player_id = ?",
        (player_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return {
        "player_id": row[0], "hands_observed": row[1],
        "vpip": row[2], "pfr": row[3], "af": row[4],
        "fold_to_cbet": row[5], "last_updated": row[6]
    }


def update_opponent_stats(player_id, stats):
    """Inserisce o aggiorna le statistiche di un avversario."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO opponent_stats "
        "(player_id, hands_observed, vpip, pfr, af, fold_to_cbet, last_updated) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(player_id) DO UPDATE SET "
        "hands_observed = excluded.hands_observed, "
        "vpip = excluded.vpip, "
        "pfr = excluded.pfr, "
        "af = excluded.af, "
        "fold_to_cbet = excluded.fold_to_cbet, "
        "last_updated = excluded.last_updated",
        (player_id, stats["hands_observed"], stats["vpip"],
         stats["pfr"], stats["af"], stats["fold_to_cbet"],
         datetime.now().isoformat())
    )
    conn.commit()
    conn.close()


def get_all_opponent_stats():
    """Ritorna tutti i profili avversari, ordinati per mani osservate."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT player_id, hands_observed, vpip, pfr, af, fold_to_cbet "
        "FROM opponent_stats ORDER BY hands_observed DESC"
    ).fetchall()
    conn.close()
    return [
        {"player_id": r[0], "hands_observed": r[1], "vpip": r[2],
         "pfr": r[3], "af": r[4], "fold_to_cbet": r[5]}
        for r in rows
    ]


# ------------------------------------------------------------------
# Hand History (Step 12)
# ------------------------------------------------------------------

def save_hand_history(hand_id, hero_cards, board, pot, action_taken,
                      action_eval, outcome, fallback_used):
    """Salva una mano nello storico."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO hand_history "
        "(timestamp, hand_id, hero_cards, board, pot, action_taken, "
        "action_eval, outcome, fallback_used) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (datetime.now().isoformat(), hand_id, hero_cards, board, pot,
         action_taken, action_eval, outcome, fallback_used)
    )
    conn.commit()
    conn.close()


def get_recent_hands(limit=20):
    """Ritorna le ultime N mani dallo storico."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT hand_id, hero_cards, board, pot, action_taken, "
        "outcome, fallback_used, timestamp "
        "FROM hand_history ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    return [
        {"hand_id": r[0], "hero_cards": r[1], "board": r[2],
         "pot": r[3], "action_taken": r[4], "outcome": r[5],
         "fallback_used": r[6], "timestamp": r[7]}
        for r in rows
    ]
