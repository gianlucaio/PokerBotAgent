#!/usr/bin/env python3
# ============================================================
# Test Mouse Rapido — Movimento + Click (NON interattivo)
# ============================================================
# Lancia dal TUO terminale con:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_mouse_quick.py
# ============================================================

import sys
import os
import time

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

import pyautogui
from act import ActModule

# SICUREZZA: PyAutoGUI FAILSAFE attivo (sposta mouse in angolo 0,0 per annullare)
pyautogui.FAILSAFE = True

print("=" * 60)
print("TEST MOUSE RAPIDO — Movimento + Click centro bounding box")
print("=" * 60)
print("⚠️  Sposterà il mouse e farà 1 click reale tra 3 secondi!")
print("   Per ANNULLARE: sposta violentemente il mouse nell'angolo")
print("   in alto a sinistra (0,0) entro 3 secondi.")
print()
print("Coordinate click: centro bounding box web (400, 371)")
print()

# Countdown
for i in range(3, 0, -1):
    print(f"  Avvio tra {i}...")
    time.sleep(1)

# Init ActModule
act = ActModule(roi_mode="web")
bb = act.bounding_box
center_x = bb["x"] + bb["width"] // 2
center_y = bb["y"] + bb["height"] // 2

print(f"\n[ACT] Bounding box: {bb}")
print(f"[ACT] Click a: ({center_x}, {center_y})")

# Test movimento
print("\n1. Spostamento mouse...")
pyautogui.moveTo(center_x, center_y, duration=0.5)
time.sleep(0.3)
print("   ✓ Mouse posizionato")

# Test click via ActModule (con validazione coordinate)
print("\n2. Click via ActModule.click_action()...")
try:
    result = act.click_action(center_x, center_y)
    if result:
        print("   ✓ Click eseguito e validato")
    else:
        print("   ⚠ Click eseguito ma validazione stato non confermata")
except Exception as e:
    print(f"   ✗ ERRORE: {e}")

# Torna mouse in posizione sicura
print("\n3. Ritorno mouse in angolo sicuro (10, 10)...")
pyautogui.moveTo(bb["x"] + 10, bb["y"] + 10, duration=0.5)
print("   ✓ Fatto")

print("\n" + "=" * 60)
print("TEST COMPLETATO — Se hai visto il mouse muoversi e clickare: OK!")
print("=" * 60)