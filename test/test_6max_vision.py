#!/usr/bin/env python3
# ============================================================
# TEST SIMULAZIONE 6-MAX: Vision parsing su screenshot 6-max reali
# ============================================================
# Prende un file dalla cartella modalità-web-6max-4colori/,
# invia alla Vision (LM Studio) e verifica l'estrazione dei player,
# incluse le carte, Hero e lo stato 'active' (attivo vs semi-trasparente).
# ============================================================

import sys
import os
import json
import cv2
import numpy as np
import glob

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from see import SeeModule
from config import HERO_NAME

# Cartella screenshot 6-max
SHOTS_DIR = os.path.join(
    _parent,
    "..", "modalità-web-6max-4colori"
)

def main():
    print("=" * 60)
    print("TEST SIMULAZIONE STATICA 6-MAX (Vision + Stato Active)")
    print("=" * 60)

    if not os.path.exists(SHOTS_DIR):
        print(f"ERRORE: Cartella non trovata: {SHOTS_DIR}")
        sys.exit(1)

    # Trova tutti i PNG nella cartella
    pngs = glob.glob(os.path.join(SHOTS_DIR, "*.png"))
    if not pngs:
        print(f"Nessun file PNG trovato in {SHOTS_DIR}")
        sys.exit(1)

    # Prendi il primo o quello passato da argomento
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        img_path = sys.argv[1]
    else:
        # Ordina per data (più recente) o prendi il primo
        pngs.sort(key=os.path.getmtime, reverse=True)
        img_path = pngs[0]

    print(f"Analisi screenshot: {os.path.basename(img_path)}")
    print(f"Path completo: {img_path}")

    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        print("ERRORE: impossibile leggere l'immagine con OpenCV")
        sys.exit(1)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    print(f"Dimensioni immagine: {w}x{h} px")

    # Inizializza SeeModule con formato 6max
    see = SeeModule(roi_mode="web", table_format="6max")

    print("\nInvio immagine al modello Vision (LM Studio)...")
    raw_response = see.parse_state_vision(img_rgb)

    print("\n" + "=" * 60)
    print("RISPOSTA RAW DAL MODELLO VISION:")
    print("=" * 60)
    print(raw_response)

    # Parsing JSON robusto
    text = raw_response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        json_str = text[start:end]
        try:
            parsed = json.loads(json_str)
            print("\n" + "=" * 60)
            print("JSON PARSATO:")
            print("=" * 60)
            print(json.dumps(parsed, indent=2, ensure_ascii=False))

            print("\n" + "=" * 60)
            print("VERIFICA STATO GIOCATORI (ATTIVO vs FOLD/SITOUT):")
            print("=" * 60)
            players = parsed.get("players", [])
            for p in players:
                is_hero = " ★ HERO" if p.get("name", "").lower() == HERO_NAME.lower() else ""
                active_status = p.get("active", True)
                status_str = "🟢 ATTIVO" if active_status else "🔴 INATTIVO (FOLD/SITOUT)"
                print(f"  Seat {p.get('seat','?')}: {p.get('name','?')} "
                      f"| Stato: {status_str} "
                      f"| Carte: {p.get('cards','non visibili')} "
                      f"| Stack: {p.get('stack','N/A')}{is_hero}")
        except json.JSONDecodeError as e:
            print(f"ERRORE JSON parsing: {e}")
    else:
        print("Nessun blocco JSON trovato nella risposta della Vision.")

if __name__ == "__main__":
    main()
