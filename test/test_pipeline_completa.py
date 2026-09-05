#!/usr/bin/env python3
# ============================================================
# TEST PIPELINE COMPLETA — Vision → Poker 1B → Mouse (click reale)
# ============================================================
# Verifica l'integrazione end-to-end:
#   1. Cattura schermo LIVE (posizione default, 899x742 ancorata 0,0)
#   2. Vision (qwen3-vl-8b) legge board, hole cards, pot, timer, hero_seat
#   3. texasholdem-llama-3.2-1b decide un'azione (FOLD/CHECK/CALL/RAISE)
#   4. Mouse si POSIZIONA sul pulsante dell'azione decisa
#   5. CLICK REALE sul pulsante (verificabile)
#   6. Ritorno mouse nell'angolo (0,0) per sicurezza
#
# Lancia dal TUO terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent/test
#   DISPLAY=:0 python3 test_pipeline_completa.py
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
pyautogui.FAILSAFE = True

from see import SeeModule
from eval_engine import EvalEngine
from main import _parse_vision_output


# ------------------------------------------------------------
# Mapping azione modello -> pulsante (coordinate dal layout)
# Si riusa il layout reale per i centri dei pulsanti.
# ------------------------------------------------------------
def load_button_centers():
    """Carica i centri dei pulsanti dal layout attivo."""
    layout_path = os.path.join(_parent,
                               "layouts", "layout_web_9max.json")
    with open(layout_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    buttons = layout["sub_roi"]["buttons"]
    centers = {}
    for name, coords in buttons.items():
        cx = coords["x"] + coords["width"] // 2
        cy = coords["y"] + coords["height"] // 2
        centers[name] = (cx, cy)
    return centers


BUTTON_CENTERS = load_button_centers()

# mapping azione (output eval) -> chiave pulsante nel layout
ACTION_TO_BUTTON = {
    "FOLD": "fold",
    "CHECK": "check",
    "CALL": "call",
    "RAISE": "raise",
}


def run_test():
    """Esegue la pipeline completa. Solo chiamata come script."""
    print("=" * 64)
    print("TEST PIPELINE COMPLETA — Vision → Poker 1B → Mouse")
    print("=" * 64)
    print("⚠️  Farà un CLICK REALE sul pulsante dell'azione decisa dal")
    print("    modello poker (basa la decisione su board + dati Vision).")
    print("    PER ANNULLARE: sposta violentemente il mouse nell'angolo")
    print("    in alto a sinistra (0,0) entro il countdown.")
    print()

    # Countdown di sicurezza (5s)
    for i in range(5, 0, -1):
        print(f"  Avvio tra {i}... (tavolo visibile in posizione default)")
        time.sleep(1)

    # ------------------------------------------------------------
    # 1. Cattura schermo LIVE
    # ------------------------------------------------------------
    print("\n[1/6] Cattura schermo LIVE...")
    see = SeeModule(roi_mode="web", table_format="9max")
    img = see.capture_screen()
    print(f"   ✓ Frame catturato: {img.shape}")

    # ------------------------------------------------------------
    # 2. Vision legge il tavolo
    # ------------------------------------------------------------
    print("\n[2/6] Vision (qwen3-vl-8b) legge il tavolo...")
    vision_raw = see.parse_state_vision(img)
    print(f"   [VISION RAW] {vision_raw[:400]}{'...' if len(vision_raw) > 400 else ''}")

    if vision_raw.startswith("ERRORE VISION"):
        print(f"   ✗ ERRORE: {vision_raw}")
        sys.exit(1)

    # ------------------------------------------------------------
    # 3. Parsing output Vision -> stato strutturato
    # ------------------------------------------------------------
    print("\n[3/6] Parsing output Vision in stato strutturato...")
    state = _parse_vision_output(vision_raw, see)
    print(f"   ✓ Hole cards: {state.get('hole_cards')}")
    print(f"   ✓ Board:      {state.get('board')}")
    print(f"   ✓ Pot:        {state.get('pot')}")
    print(f"   ✓ Timer:      {state.get('move_timer_seconds_remaining')}")
    print(f"   ✓ Hero seat:  {see.hero_seat}")
    print(f"   ✓ Players:    {len(state.get('players', []))}")

    if len(state.get("hole_cards", [])) >= 2 and (state.get("pot") or 0) > 0:
        print("   ✓ Stato actionabile (Hero ha carte + pot > 0)")
    else:
        print("   ⚠ Stato NON pienamente actionabile (posso comunque chiedere decisione)")

    # ------------------------------------------------------------
    # 4. Decisione modello poker (texasholdem 1B)
    # ------------------------------------------------------------
    print("\n[4/6] Decisione modello poker (texasholdem-1b)...")
    print("   (Chiamata a LM Studio — il modello 1B è già caricato in VRAM)")
    eval_engine = EvalEngine()
    decision = eval_engine.evaluate(state)

    if not decision or "error" in decision:
        print(f"   ✗ ERRORE decisione: {decision}")
        sys.exit(1)

    azione = decision.get("azione", "FOLD")
    sizing = decision.get("sizing", 0)
    motivazione = decision.get("motivazione", "")
    print(f"   ✓ AZIONE DECISA: {azione}")
    print(f"   ✓ Sizing:        {sizing}")
    print(f"   ✓ Motivazione:   {motivazione}")

    # ------------------------------------------------------------
    # 5. Mapping azione -> pulsante
    # ------------------------------------------------------------
    print("\n[5/6] Mapping azione -> pulsante...")
    if azione not in ACTION_TO_BUTTON:
        # Se fallback o azione non nota, logga e blocca (no click)
        print(f"   ✗ Azione non mappabile su pulsante: '{azione}' — CLICK BLOCCATO")
        sys.exit(2)

    btn_key = ACTION_TO_BUTTON[azione]
    target = BUTTON_CENTERS[btn_key]
    print(f"   ✓ Azione {azione} -> pulsante '{btn_key}' al centro {target}")

    # ------------------------------------------------------------
    # 6. Mouse: posizionamento + CLICK REALE
    # ------------------------------------------------------------
    print("\n[6/6] Mouse su pulsante + CLICK REALE...")
    print(f"   Movimento verso {target}...")
    pyautogui.moveTo(target[0], target[1], duration=0.6)
    time.sleep(0.4)
    print(f"   ✓ Freccia su {btn_key} ({target[0]}, {target[1]})")
    print(f"   → CLICK REALE su {btn_key}...")
    pyautogui.click(target[0], target[1])
    time.sleep(0.5)
    print(f"   ✓ Click eseguito su '{btn_key}' (azione {azione})")

    # ------------------------------------------------------------
    # 7. Ritorno sicuro
    # ------------------------------------------------------------
    print("\n[SEC] Ritorno mouse nell'angolo (0,0)...")
    pyautogui.moveTo(5, 5, duration=0.4)
    time.sleep(0.2)

    print("\n" + "=" * 64)
    print("TEST COMPLETATO")
    print("=" * 64)
    print(f"Vision letta:  hole={state.get('hole_cards')} board={state.get('board')} pot={state.get('pot')}")
    print(f"Decisione:     {azione} (sizing={sizing})")
    print(f"Pulsante:      {btn_key} @ {target}")
    print(f"Click:         Eseguito REALE")
    print("=" * 64)
    print("Verifica visiva: il click è arrivato sul pulsante corretto?")


if __name__ == "__main__":
    run_test()
