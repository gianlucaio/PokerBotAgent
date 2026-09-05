#!/usr/bin/env bash
# ============================================================
#  PokerBotAgent — Script di avvio
#  Doppio click per aprire la GUI di configurazione
#  Crea automaticamente il venv e installa le dipendenze
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR" || exit 1

VENV_DIR=".venv"
PYTHON_SYSTEM=""
VENV_PYTHON="$VENV_DIR/bin/python3"

# --- Trova Python3 di sistema ---
if command -v python3 &>/dev/null; then
    PYTHON_SYSTEM="python3"
elif command -v python &>/dev/null; then
    PYTHON_SYSTEM="python"
else
    echo "========================================="
    echo "  ERRORE: Python 3 non trovato"
    echo "========================================="
    echo ""
    echo "Installa Python 3.8+ con:"
    echo "  sudo apt install python3 python3-venv python3-tk"
    echo ""
    read -p "Premi Invio per uscire..."
    exit 1
fi

# --- Verifica python3-venv ---
$PYTHON_SYSTEM -c "import venv" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "========================================="
    echo "  ERRORE: python3-venv non installato"
    echo "========================================="
    echo ""
    echo "Installalo con:"
    echo "  sudo apt install python3-venv"
    echo ""
    read -p "Premi Invio per uscire..."
    exit 1
fi

# --- Crea venv se non esiste ---
if [ ! -d "$VENV_DIR" ]; then
    echo "========================================="
    echo "  Primo avvio: creo l'ambiente virtuale"
    echo "========================================="
    echo ""
    $PYTHON_SYSTEM -m venv "$VENV_DIR"
    if [ $? -ne 0 ]; then
        echo "ERRORE: impossibile creare il venv."
        echo "Verifica di avere i permessi di scrittura."
        read -p "Premi Invio per uscire..."
        exit 1
    fi
    echo "✓ Ambiente virtuale creato"
    echo ""
    echo "Installo le dipendenze (può volerci un minuto)..."
    echo ""
    "$VENV_PYTHON" -m pip install --upgrade pip --quiet 2>/dev/null
    if command -v uv &>/dev/null; then
        uv pip install --python "$VENV_PYTHON" -r requirements.txt --quiet
    else
        "$VENV_PYTHON" -m pip install -r requirements.txt --quiet
    fi
    if [ $? -ne 0 ]; then
        echo ""
        echo "========================================="
        echo "  ERRORE installazione dipendenze"
        echo "========================================="
        echo "Prova manualmente:"
        echo "  $VENV_PYTHON -m pip install -r requirements.txt"
        read -p "Premi Invio per uscire..."
        exit 1
    fi
    echo "✓ Dipendenze installate"
    echo ""
    echo "========================================="
    echo "  Installazione completata!"
    echo "========================================="
    echo ""
    sleep 1
fi

# --- Verifica file/cartelle critici ---
echo "Verifica file di sistema..."
CRITICO=""
[ -f "main.py" ] || CRITICO="$CRITICO main.py"
[ -f "gui.py" ] || CRITICO="$CRITICO gui.py"
[ -f "config.py" ] || CRITICO="$CRITICO config.py"
[ -f "see.py" ] || CRITICO="$CRITICO see.py"
[ -f "eval_engine.py" ] || CRITICO="$CRITICO eval_engine.py"
[ -f "act.py" ] || CRITICO="$CRITICO act.py"
[ -f "voice.py" ] || CRITICO="$CRITICO voice.py"
[ -f "db.py" ] || CRITICO="$CRITICO db.py"
[ -d "layouts" ] || CRITICO="$CRITICO layouts/"
[ -d "assets/deck_labels" ] || CRITICO="$CRITICO assets/deck_labels/"
[ -d "test" ] || CRITICO="$CRITICO test/"
[ -f "requirements.txt" ] || CRITICO="$CRITICO requirements.txt"

if [ -n "$CRITICO" ]; then
    echo ""
    echo "========================================="
    echo "  ERRORE: File/cartelle mancanti:"
    echo "========================================="
    echo "$CRITICO"
    echo ""
    echo "Riesegui lo zip da GitHub o verifica"
    echo "di aver estratto tutti i file."
    echo ""
    read -p "Premi Invio per uscire..."
    exit 1
fi
echo "✓ Tutti i file di sistema presenti"
echo ""

# --- Verifica dipendenze critiche e ripristina se mancanti ---
MISSING=""
"$VENV_PYTHON" -c "import cv2" 2>/dev/null || MISSING="$MISSING opencv-python"
"$VENV_PYTHON" -c "import tkinter" 2>/dev/null || MISSING="$MISSING python3-tk"
"$VENV_PYTHON" -c "import requests" 2>/dev/null || MISSING="$MISSING requests"

if [ -n "$MISSING" ]; then
    echo "AVVISO: Dipendenze mancanti:$MISSING"
    echo "Tento di installarle da requirements.txt..."
    echo ""
    if command -v uv &>/dev/null; then
        uv pip install --python "$VENV_PYTHON" -r requirements.txt --quiet
    else
        "$VENV_PYTHON" -m pip install -r requirements.txt --quiet
    fi
    if [ $? -eq 0 ]; then
        echo "✓ Dipendenze ripristinate"
        echo ""
    else
        echo "ERRORE: impossibile installare le dipendenze."
        echo "Ripristina il venv con:"
        echo "  rm -rf .venv && ./avvio.sh"
        echo ""
        sleep 2
    fi
fi

# --- Avvia la GUI ---
echo "Avvio PokerBotAgent..."
"$VENV_PYTHON" gui.py

# --- Se la GUI si chiude con errore ---
if [ $? -ne 0 ]; then
    echo ""
    echo "========================================="
    echo "  La GUI si è chiusa con un errore"
    echo "========================================="
    read -p "Premi Invio per uscire..."
fi
