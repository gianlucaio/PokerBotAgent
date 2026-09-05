#!/usr/bin/env python3
# ============================================================
# Test Vision + Viewer collegati — cattura, apri pixel-perfect, mostra coordinate
# ============================================================
# Lancia dal TUO terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_view_and_see.py
#
# Cosa fa: cattura lo schermo → salva in shots/ → lo apre SUBITO in
# modalità pixel-perfect (dimensione reale, senza cornici, ancorato 0,0).
# Poi passa lo screenshot alla Vision e mostra cosa rileva.
# ============================================================

import sys
import os
import time
import json

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from see import SeeModule

print("=" * 60)
print("TEST VISION + VIEWER — Cattura → Apri → Analizza")
print("=" * 60)

# 1. Cattura + salva + apri subito in pixel-perfect
print("\n1. Catturo lo schermo e lo apro subito in modalità pixel-perfect...")
see = SeeModule(roi_mode="web", table_format="9max")
path = see.save_and_view(name="test")
print(f"   ✓ Aperto: {path}")
print("   → Guarda lo screenshot sul tuo schermo (NON clickare per 4s)")
print("   → Passa il mouse sui pulsanti per leggerne le coordinate in giallo")
time.sleep(4)

# 2. Leggi coordinate pulsanti dal layout per riferimento
print("\n2. Coordinate pulsanti dal layout (per confronto):")
layout_path = os.path.join(_parent, "layouts", "layout_web_9max.json")
with open(layout_path, "r") as f:
    layout = json.load(f)

buttons = layout["sub_roi"]["buttons"]
for name, coords in buttons.items():
    x = coords["x"] + coords["width"] // 2
    y = coords["y"] + coords["height"] // 2
    print(f"   {name.upper():6s}: ({x}, {y})  [metti il mouse qui nello screenshot ap]")

# 3. Vision analizza lo screenshot
print("\n3. Vision analizza lo screenshot (richiede modello qwen3-vl-8b-instruct)...")
img = see.capture_screen()
try:
    vision_out = see.parse_state_vision(img)
    print(f"   [VISION]\n{vision_out[:600]}")
except Exception as e:
    print(f"   ⚠ Vision non disponibile: {e}")
    print("   → Carica qwen3-vl-8b-instruct su LM Studio e riprova")

print("\n" + "=" * 60)
print("FATTO")
print("=" * 60)