#!/usr/bin/env python3
# ============================================================
# TEST CALIBRAZIONE: carica immagine_test1.png e la manda alla Vision
# ============================================================
# Verifica cosa legge il modello vision: carte, pot, giocatori, coordinate.
# Output: JSON strutturato + confronto visivo.
# ============================================================

import sys
import os
import json
import cv2
import numpy as np

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from see import SeeModule
from config import HERO_NAME

# --- Config ---
IMG_PATH = os.path.join(
    _parent,
    "..", "modalità-web-9max-4colori", "immagine_test1.png"
)

def main():
    # 1. Carica immagine
    print("=" * 60)
    print("TEST CALIBRAZIONE VISION — immagine_test1.png")
    print("=" * 60)

    if not os.path.exists(IMG_PATH):
        print(f"ERRORE: immagine non trovata: {IMG_PATH}")
        sys.exit(1)

    # Carica con OpenCV (BGR) e converti in RGB (come si aspetta parse_state_vision)
    img_bgr = cv2.imread(IMG_PATH)
    if img_bgr is None:
        print("ERRORE: impossibile leggere l'immagine")
        sys.exit(1)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    print(f"Immagine caricata: {w}x{h} px")

    # 2. Crea modulo Vision
    see = SeeModule(roi_mode="web", table_format="9max")

    # 3. Chiama Vision (modello su LM Studio)
    print("\nInvio immagine al modello Vision su LM Studio...")
    print("(il modello deve essere caricato — verifica se LM Studio è attivo)")
    print()

    raw_response = see.parse_state_vision(img_rgb)

    print("=" * 60)
    print("RISPOSTA RAW DAL MODELLO VISION:")
    print("=" * 60)
    print(raw_response)

    # 4. Prova a parsare come JSON
    print("\n" + "=" * 60)
    print("TENTATIVO PARSING JSON:")
    print("=" * 60)

    # Pulisci eventuale testo prima/dopo il JSON
    text = raw_response.strip()
    # Cerca il primo { e l'ultimo }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            parsed = json.loads(json_str)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))

            # 5. Risultati sintetici
            print("\n" + "=" * 60)
            print("RIEPILOGO CALIBRAZIONE:")
            print("=" * 60)
            print(f"  Carte Hero:    {parsed.get('hole_cards', [])}")
            print(f"  Board:         {parsed.get('board', [])}")
            print(f"  Pot:           {parsed.get('pot', 'N/A')}")
            print(f"  Timer:         {parsed.get('timer', 'N/A')} sec")
            print(f"  Hero Seat:     {parsed.get('hero_seat', 'N/A')}")
            players = parsed.get("players", [])
            print(f"  Giocatori:     {len(players)}")
            for p in players:
                hero_mark = " ★ HERO" if p.get("name", "").lower() == HERO_NAME.lower() else ""
                print(f"    Seat {p.get('seat','?')}: {p.get('name','?')} "
                      f"stack={p.get('stack','?')} bet={p.get('bet','?')} "
                      f"action={p.get('action','?')}{hero_mark}")
        except json.JSONDecodeError as e:
            print(f"ERRORE JSON parsing: {e}")
            print(f"Testo JSON estratto:\n{json_str}")
    else:
        print("Nessun JSON trovato nella risposta.")
        print("Risposta grezza potrebbe contenere errori del modello.")

if __name__ == "__main__":
    main()
