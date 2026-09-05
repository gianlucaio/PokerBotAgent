# ============================================================
# HoldEm Agent — Configuration
# ============================================================
# v0.3.0 — Ristrutturato: PokerBotAgent non calibra più.
# Tutte le coordinate vengono dai profili PokerTableScope.

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- Layout PokerTableScope ---
# Il bot carica il layout da qui (output di PokerTableScope).
# Formato: layout_<preset>.json (generato da canonical.py:profile_to_see_config)
LAYOUTS_DIR = os.path.join(BASE_DIR, "layouts")
LAYOUT_FILE = "layout_peoples-web-9max-4colori.json"  # default, sovrascritto da GUI

# --- Dimensioni default (usate SOLO se il layout non le fornisce) ---
# Le dimensioni reali vengono dal campo "resolution" del layout.
DEFAULT_WEB_WIDTH = 899
DEFAULT_WEB_HEIGHT = 742

# --- LM Studio ---
LM_STUDIO_URL = "http://localhost:1234/v1/chat/completions"

# --- Tesseract (fallback se Vision fallisce) ---
TESSERACT_CMD = "/usr/bin/tesseract"

# --- Polling ---
POLL_INTERVAL_MS = 1000

# --- Fallback ---
FALLBACK_MAX_RETRIES = 1
SELF_HEAL_THRESHOLD = 3   # mani consecutive prima di notifica vocale

# --- Timer critico ---
MOVE_TIMER_CRITICAL_THRESHOLD = 5  # secondi: sotto questa soglia -> fallback

# --- Event-Driven Loop ---
VISION_POLL_INTERVAL = 2.0        # secondi tra cicli Vision
EVAL_TRIGGER_TIMER_THRESHOLD = 15 # secondi: se timer < questo -> trigger EVAL

# --- Profili tattici ---
DEFAULT_PLAYSTYLE = "normal"  # tight | normal | aggressive | auto_adaptant

# --- GTO Preflop Tables ---
USE_GTO_PREFLOP = False
GTO_TABLE_FILE = "gto_pusht_fold_9max.json"

# --- Debug ---
DEBUG_MODE = False
DEBUG_DIR = "/tmp/holdem_debug"

# --- Garbage Collection ---
GC_ENABLED = True
GC_TTL_SECONDS = 600
GC_MAX_MEMORY_MB = 200
GC_INTERVAL_CYCLES = 50

# --- Modello Poker ---
POKER_MODEL = "texasholdem-llama-3.2-1b-instruct"

# --- Modello Vision ---
VISION_MODEL = "qwen3-vl-8b-instruct"
VISION_MAX_TOKENS = 1000

# --- Giocatore Hero ---
HERO_NAME = "hero"
