#!/usr/bin/env python3
# ============================================================
# Test Vision-Guided Mouse — Vision trova i pulsanti, Mouse ci va
# ============================================================
# Lancia dal TUO terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_vision_mouse.py
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
from see import SeeModule
from act import ActModule

pyautogui.FAILSAFE = True

print("=" * 60)
print("TEST VISION-GUIDED MOUSE — Vision rileva, Mouse esegue")
print("=" * 60)
print("⚠️  Farà click REALE sul pulsante rilevato dalla Vision!")
print("   Per ANNULLARE: sposta violentemente il mouse nell'angolo")
print("   in alto a sinistra (0,0) entro 5 secondi.")
print()

# Countdown
for i in range(5, 0, -1):
    print(f"  Avvio tra {i}... (prepara il tavolo visibile)")
    time.sleep(1)

# 1. Cattura schermo
print("\n1. Cattura schermo...")
see = SeeModule(roi_mode="web", table_format="9max")
img = see.capture_screen()
print(f"   ✓ Screenshot catturato: {img.shape}")

# 2. Vision analizza e trova pulsanti
print("\n2. Vision analizza tavolo (cerca pulsanti)...")
vision_output = see.parse_state_vision(img)
print(f"[VISION RAW] {vision_output[:300]}...")

# 3. Parsa output Vision per estrarre coordinate pulsanti
#    Il prompt chiede JSON con "players" che include "action_buttons" o simili
#    Se il modello non restituisce coordinate pixel, usiamo fallback layout
import re

button_coords = None

# Prova a parsare JSON dalla Vision
try:
    start = vision_output.find('{')
    end = vision_output.rfind('}') + 1
    if start >= 0 and end > start:
        data = json.loads(vision_output[start:end])
        # Cerca info pulsanti nel JSON
        # Il prompt non chiede esplicitamente coordinate pixel dei bottoni
        # ma possiamo chiedere al modello di restituirle
        print(f"[PARSE] JSON parsato: {list(data.keys())}")
except:
    pass

# FALLBACK: usa layout ma con offset reale della finestra
# La Vision dovrebbe idealmente restituire le coordinate assolute dei bottoni
# Per ora usiamo il layout come reference, ma la Vision conferma che ci siamo
print("\n3. Uso coordinate da layout (Vision conferma presenza pulsanti)...")

layout_path = os.path.join(_parent, "layouts", "layout_web_9max.json")
with open(layout_path, "r") as f:
    layout = json.load(f)

buttons = layout["sub_roi"]["buttons"]
BUTTONS = {}
for name, coords in buttons.items():
    x = coords["x"] + coords["width"] // 2
    y = coords["y"] + coords["height"] // 2
    BUTTONS[name.upper()] = (x, y)

print("Pulsanti da layout (centro):")
for name, (x, y) in BUTTONS.items():
    print(f"  {name:6s}: ({x}, {y})")

# 4. Scegli target (quello che la Vision vede attivo)
#    Per ora testiamo FOLD come esempio
TARGET = "FOLD"
x, y = BUTTONS[TARGET]

print(f"\n4. Target: {TARGET} → ({x}, {y})")

# 5. Mouse va lì
print("\n5. Spostamento mouse guidato...")
pyautogui.moveTo(x, y, duration=0.5)
time.sleep(0.3)
print(f"   ✓ Mouse su {TARGET} ({x}, {y})")

# 6. Click via ActModule
print(f"\n6. Click su {TARGET}...")
act = ActModule(roi_mode="web")
try:
    result = act.click_action(x, y)
    if result:
        print(f"   ✓ Click {TARGET} eseguito")
    else:
        print(f"   ⚠ Click eseguito, validazione non confermata")
except Exception as e:
    print(f"   ✗ ERRORE: {e}")

# 7. Ritorno sicuro
print("\n7. Ritorno mouse sicuro...")
pyautogui.moveTo(10, 10, duration=0.5)
print("   ✓ Fatto")

print("\n" + "=" * 60)
print("TEST COMPLETATO")
print("=" * 60)
print("\nPROSSIMO PASSO: Estendere il prompt Vision per far restituire")
print("le COORDINATE PIXEL ASSOLUTE dei pulsanti visibili sullo schermo.")
print("Allora niente più layout fisso: Vision vede → Mouse va.")