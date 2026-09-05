#!/usr/bin/env python3
# ============================================================
# TEST RICONOSCIMENTO HERO: verifica che la Vision identifichi
# correttamente il giocatore umano (Hero) nello screenshot
# ============================================================
# Prende uno screenshot, invia alla Vision e verifica:
# 1. Il nome Hero (HERO_NAME) è presente nei players
# 2. Le carte di Hero sono nel formato Treys corretto
# 3. Il seat di Hero è valido
# 4. Hero ha lo stato active=true (è in gioco)
# ============================================================

import sys
import os
import json
import cv2

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from see import SeeModule
from config import HERO_NAME


def main():
    print("=" * 60)
    print("TEST RICONOSCIMENTO HERO")
    print("=" * 60)
    print(f"Hero configurato: {HERO_NAME}")

    # Prendi screenshot da argomento o usa il primo disponibile
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        img_path = sys.argv[1]
    else:
        # Cerca uno screenshot nella cartella test
        shots_dir = os.path.join(_parent, "..", "modalità-web-6max-4colori")
        if not os.path.exists(shots_dir):
            print("ERRORE: specifica uno screenshot come argomento")
            print(f"Uso: python3 {sys.argv[0]} /path/to/screenshot.png")
            sys.exit(1)
        import glob
        pngs = glob.glob(os.path.join(shots_dir, "*.png"))
        if not pngs:
            print("ERRORE: nessun screenshot trovato")
            sys.exit(1)
        pngs.sort(key=os.path.getmtime, reverse=True)
        img_path = pngs[0]

    print(f"Screenshot: {os.path.basename(img_path)}")

    img_bgr = cv2.imread(img_path)
    if img_bgr is None:
        print("ERRORE: impossibile leggere l'immagine")
        sys.exit(1)

    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    print(f"Dimensioni: {w}x{h} px")

    # Rileva formato (6max o 9max) dalle dimensioni
    table_format = "6max" if w <= 920 else "9max"
    print(f"Formato rilevato: {table_format}")

    see = SeeModule(roi_mode="web", table_format=table_format)

    print("\nInvio alla Vision...")
    raw_response = see.parse_state_vision(img_rgb)

    # Parsing JSON
    text = raw_response.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        print("ERRORE: nessun JSON nella risposta Vision")
        print(f"Risposta: {raw_response[:500]}")
        sys.exit(1)

    try:
        parsed = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        print(f"ERRORE JSON: {e}")
        sys.exit(1)

    # === VERIFICHE ===
    print("\n" + "=" * 60)
    print("VERIFICHE RICONOSCIMENTO HERO")
    print("=" * 60)

    players = parsed.get("players", [])
    errors = []
    warnings = []

    # 1. Hero presente?
    hero = None
    for p in players:
        name = (p.get("name") or "").lower().strip()
        if name == HERO_NAME.lower():
            hero = p
            break

    if hero:
        print(f"✅ Hero trovato: seat {hero.get('seat', '?')}, nome '{hero.get('name')}'")
    else:
        errors.append(f"Hero '{HERO_NAME}' non trovato nei players")
        print(f"❌ Hero '{HERO_NAME}' NON trovato nei players")
        print(f"   Players trovati: {[p.get('name') for p in players]}")

    # 2. Hero ha le carte?
    if hero:
        cards = hero.get("cards", hero.get("hole_cards", []))
        if cards and len(cards) >= 2:
            print(f"✅ Carte Hero: {cards}")
            # Verifica formato Treys
            valid_ranks = "23456789TJQKA"
            valid_suits = "hdsc"
            for card in cards:
                if len(card) == 2 and card[0] in valid_ranks and card[1] in valid_suits:
                    pass  # OK
                else:
                    warnings.append(f"Carta '{card}' potrebbe non essere in formato Treys")
                    print(f"⚠️  Carta '{card}' non in formato Treys standard")
        else:
            warnings.append("Carte Hero non visibili o assenti")
            print("⚠️  Carte Hero non visibili (potrebbe essere normale se non è il turno)")

    # 3. Hero è attivo?
    if hero:
        active = hero.get("active", None)
        if active is True:
            print("✅ Hero è ATTIVO (in gioco)")
        elif active is False:
            print("⚠️  Hero è INATTIVO (foldato o sit-out)")
            warnings.append("Hero inattivo — potrebbe essere normale")
        else:
            warnings.append("Stato active di Hero non determinato")
            print("⚠️  Stato active di Hero non determinato")

    # 4. Seat valido?
    if hero:
        seat = hero.get("seat")
        max_seats = 6 if table_format == "6max" else 9
        if seat and 1 <= seat <= max_seats:
            print(f"✅ Seat Hero valido: {seat}/{max_seats}")
        else:
            errors.append(f"Seat Hero non valido: {seat}")
            print(f"❌ Seat Hero non valido: {seat} (max: {max_seats})")

    # 5. Numero player coerente?
    expected_min = 2  # almeno Hero + 1 avversario
    if len(players) >= expected_min:
        print(f"✅ Numero players: {len(players)} (minimo {expected_min})")
    else:
        warnings.append(f"Pochi players: {len(players)}")
        print(f"⚠️  Pochi players: {len(players)}")

    # RIEPILOGO
    print("\n" + "=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    if not errors:
        print("✅ RICONOSCIMENTO HERO: OK")
    else:
        print("❌ RICONOSCIMENTO HERO: PROBLEMI")
        for e in errors:
            print(f"   - {e}")
    if warnings:
        print("⚠️  Avvisi:")
        for w in warnings:
            print(f"   - {w}")

    print("\n" + json.dumps(parsed, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
