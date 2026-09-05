#!/usr/bin/env python3
# ============================================================
# Test Mouse sui PULSANTI REALI — Fold / Check / Call / Raise
# ============================================================
# Lancia dal TUO terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_mouse_buttons.py
# ============================================================

import sys
import os
import time
import json

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

import pyautogui
from act import ActModule

pyautogui.FAILSAFE = True

# Carica coordinate pulsanti dal layout
layout_path = os.path.join(_parent, "layouts", "layout_web_9max.json")
with open(layout_path, "r") as f:
    layout = json.load(f)

buttons = layout["sub_roi"]["buttons"]
# Calcola centri
BUTTONS = {}
for name, coords in buttons.items():
    x = coords["x"] + coords["width"] // 2
    y = coords["y"] + coords["height"] // 2
    BUTTONS[name.upper()] = (x, y)

print("=" * 60)
print("TEST MOUSE — PULSANTI POKER REALI (da layout)")
print("=" * 60)
print("Coordinate pulsanti (centro click):")
for name, (x, y) in BUTTONS.items():
    print(f"  {name:6s}: ({x}, {y})")
print()
print("⚠️  Farà 1 click REALE su un pulsante tra 3 secondi!")
print("   Per ANNULLARE: sposta violentemente il mouse nell'angolo")
print("   in alto a sinistra (0,0) entro 3 secondi.")
print()

# Countdown
for i in range(3, 0, -1):
    print(f"  Avvio tra {i}...")
    time.sleep(1)

# Init
act = ActModule(roi_mode="web")

# Scegli quale pulsante testare
# Opzioni: "FOLD", "CHECK", "CALL", "RAISE"
TARGET_BUTTON = "FOLD"  # CAMBIA QUI per testare un altro

print(f"\n[TARGET] Click su {TARGET_BUTTON} → {BUTTONS[TARGET_BUTTON]}")

x, y = BUTTONS[TARGET_BUTTON]

# 1. Spostamento
print("1. Spostamento mouse...")
pyautogui.moveTo(x, y, duration=0.5)
time.sleep(0.3)
print(f"   ✓ Mouse su {TARGET_BUTTON} ({x}, {y})")

# 2. Click via ActModule (con validazione)
print(f"\n2. Click su {TARGET_BUTTON} via ActModule...")
try:
    result = act.click_action(x, y)
    if result:
        print(f"   ✓ Click {TARGET_BUTTON} eseguito e validato")
    else:
        print(f"   ⚠ Click eseguito ma validazione stato non confermata")
        print(f"      (Normale se il tavolo non reagisce allo screenshot)")
except Exception as e:
    print(f"   ✗ ERRORE: {e}")

# 3. Ritorno sicuro
print("\n3. Ritorno mouse in posizione sicura...")
pyautogui.moveTo(10, 10, duration=0.5)
print("   ✓ Fatto")

print("\n" + "=" * 60)
print(f"TEST COMPLETATO — Click su {TARGET_BUTTON}")
print("=" * 60)
print("\nPer testare un altro pulsante, modifica TARGET_BUTTON nello script")
print("e rilancia. Oppure crea un loop per testarli in sequenza.")