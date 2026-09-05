#!/usr/bin/env python3
# ============================================================
# TEST RICONOSCIMENTO CARTE — cosa vede la Vision
# ============================================================
# Carica immagine_test1.png (quella che vedi nel desktop) e chiede
# al modello Vision di dire QUALE carte vede: VALORE + SEME.
# NIENTE coordinate: solo le carte.
#
# Lancia TU dal terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   python3 test_carte_desktop.py
# ============================================================

import sys
import os
import json
import base64
import cv2
import requests

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)
from vision_prompt import VISION_SYSTEM_PROMPT, VISION_MODEL
from config import HERO_NAME

# La tua immagine (quella aperta nel desktop, 899x742)
IMG_PATH = os.path.join(
    _parent,
    "..", "modalità-web-9max-4colori", "immagine_test1.png"
)

LM_URL = "http://localhost:1234/v1/chat/completions"

# Nomi italiani per stampare le carte leggibili
RANK_IT = {"A": "Asso", "K": "Re", "Q": "Donna", "J": "Jack", "T": "10",
           "10": "10", "9": "9", "8": "8", "7": "7", "6": "6",
           "5": "5", "4": "4", "3": "3", "2": "2"}
SUIT_IT = {"h": "Cuori", "d": "Denari", "s": "Picche", "c": "Fiori"}
COLOR_IT = {"h": "ROSSO", "d": "BLU", "s": "NERO", "c": "VERDE"}

def card_to_italian(card):
    """As → 'Asso di Picche (NERO)'"""
    if not card or len(card) < 2:
        return card
    r = card[0].upper()
    s = card[1].lower()
    if r == "1" and len(card) > 2 and card[1].upper() == "0":
        r, s = "10", card[2].lower()
    rank = RANK_IT.get(r, r)
    suit = SUIT_IT.get(s, s)
    color = COLOR_IT.get(s, "?")
    return f"{rank} di {suit} ({color})"


def main():
    print("=" * 60)
    print("TEST RICONOSCIMENTO CARTE — immagine_test1")
    print("=" * 60)

    if not os.path.exists(IMG_PATH):
        print(f"ERRORE: immagine non trovata:\n  {IMG_PATH}")
        sys.exit(1)

    img_bgr = cv2.imread(IMG_PATH)
    if img_bgr is None:
        print("ERRORE: impossibile leggere l'immagine")
        sys.exit(1)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    h, w = img_rgb.shape[:2]
    print(f"\nImmagine caricata: {w}x{h} px")
    print("Invio al modello Vision (qwen3-vl-8b-instruct)...")
    print("Attendere: può richiedere fino a 120s se il modello è lento.\n")

    # --- Base64 dell'immagine ---
    _, buffer = cv2.imencode(".png", img_bgr)
    img_base64 = base64.b64encode(buffer).decode("utf-8")

    # --- Prompt utente: MINIMALE, la mappatura colori è SOLO nel prompt dell'utente ---
    user_prompt = f"""Analizza questo screenshot di un tavolo Texas Hold'em.
Applica esattamente le istruzioni del system prompt per identificare i semi dai colori.
Descrivi le carte che vedi (hole cards di {HERO_NAME}, board e carte degli altri giocatori se visibili), il pot e il timer.
Rispondi in formato chiaro. Nessuna invenzione: se qualcosa non è leggibile, dillo esplicitamente."""

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {"role": "system", "content": VISION_SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": user_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
            ]}
        ],
        "max_tokens": 800,
        "stream": False,
        "temperature": 0.1
    }

    try:
        response = requests.post(LM_URL, json=payload, timeout=120)
        res_json = response.json()
        content = res_json["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"ERRORE VISION: {e}")
        print()
        print("Il modello Vision non risponde. Verifica che su LM Studio")
        print("sia CARICATO 'qwen3-vl-8b-instruct' (non il 35B).")
        sys.exit(1)

    # --- Stampa risposta grezza ---
    print("-" * 60)
    print("RISPOSTA RAW DEL MODELLO:")
    print("-" * 60)
    print(content)
    print()

    # --- Prova a parsare JSON ---
    text = content.strip()
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        print("Nessun JSON valido nella risposta.")
        sys.exit(1)

    try:
        data = json.loads(text[start:end])
    except json.JSONDecodeError as e:
        print(f"ERRORE parsing JSON: {e}")
        sys.exit(1)

    # --- Output chiaro: LE CARTE CHE VEDE ---
    print("=" * 60)
    print("🎴 CARTE CHE VEDE IL MODELLO")
    print("=" * 60)

    hole = data.get("hole_cards") or []
    board = data.get("board") or []
    print(f"\n  CARTE HERO ({HERO_NAME}):")
    if hole:
        for c in hole:
            print(f"    • {card_to_italian(c)}")
    else:
        print("    (nessuna carta visibile / non letta)")

    print(f"\n  CARTE SUL TAVOLO (board):")
    if board:
        for c in board:
            print(f"    • {card_to_italian(c)}")
    else:
        print("    (nessuna carta visibile / non letta)")

    print(f"\n  Pot:   {data.get('pot', 'N/A')}")
    print(f"  Timer: {data.get('timer', 'N/A')} sec")
    print(f"  Hero seat: {data.get('hero_seat', 'N/A')}")

    print("\n" + "=" * 60)
    print("Confronta con quello che vedi nell'immagine del desktop.")
    print("Se una carta è sbagliata, dimmi quale: correggiamo il prompt o la Vision.")
    print("=" * 60)


if __name__ == "__main__":
    main()