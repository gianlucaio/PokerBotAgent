#!/usr/bin/env python3
# ============================================================
# Test Calibrazione Mouse — Posiziona su CHECK button
# ============================================================
# Lancia dal TUO terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_calibrate_check.py
# ============================================================

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pyautogui

pyautogui.FAILSAFE = True

# Coordinate CHECK button dal layout (centro)
# layout_web_9max.json → buttons.check: x=320, y=620, w=60, h=30
# Centro = (320+30, 620+15) = (350, 635)
CHECK_X = 350
CHECK_Y = 635

print("=" * 60)
print("TEST CALIBRAZIONE — Mouse su PULSANTE CHECK")
print("=" * 60)
print(f"Coordinate target: ({CHECK_X}, {CHECK_Y})")
print()
print("⚠️  Sposterà il mouse su CHECK tra 3 secondi!")
print("   Per ANNULLARE: sposta violentemente il mouse nell'angolo")
print("   in alto a sinistra (0,0) entro 3 secondi.")
print()

for i in range(3, 0, -1):
    print(f"  Avvio tra {i}...")
    time.sleep(1)

print(f"\n>>> Spostamento su CHECK ({CHECK_X}, {CHECK_Y})...")
pyautogui.moveTo(CHECK_X, CHECK_Y, duration=0.5)
time.sleep(0.3)

# Verifica posizione
current = pyautogui.position()
print(f">>> Mouse ora a: {current}")
print(f">>> Differenza: ({abs(current.x - CHECK_X)}, {abs(current.y - CHECK_Y)}) px")

if abs(current.x - CHECK_X) <= 2 and abs(current.y - CHECK_Y) <= 2:
    print(">>> ✓ CALIBRAZIONE OK: Mouse perfettamente su CHECK")
else:
    print(">>> ⚠ Mouse NON allineato — possibile offset finestra")

print("\nMouse rimane su CHECK per 5 secondi (verifica visiva)...")
time.sleep(5)

print("\n>>> Ritorno mouse sicuro (10, 10)...")
pyautogui.moveTo(10, 10, duration=0.5)
print(">>> Fatto")