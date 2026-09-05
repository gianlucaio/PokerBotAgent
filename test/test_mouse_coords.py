#!/usr/bin/env python3
# ============================================================
# TEST MOUSE — coordinate REALI pulsanti (da calibrazione utente)
# ============================================================
# Muove la freccia su PASSA → CALL/CHECK → RILANCIA/ALLIN,
# 2 secondi ciascuno, usando le coordinate misurate dall'utente
# sull'immagine_test1.png (nel desktop, ancorata a 0,0).
#
# NOTA (dall'utente): alcuni pulsanti condividono le coordinate
# perché visibili in momenti diversi:
#   - CALL e CHECK  → stessa posizione
#   - RILANCIA e ALLIN → stessa posizione
#
# Lancia TU dal terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_mouse_coords.py
# ============================================================

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyautogui

pyautogui.FAILSAFE = True

# Coordinate reali misurate dall'utente (bordo in alto a sx + size)
BUTTONS = {
    # nome: (x, y, width, height)
    "PASSA":       (456, 686, 143, 42),
    "CALL/CHECK":  (606, 686, 143, 42),
    "RILANCIA/ALLIN": (750, 685, 143, 42),
}
# Nota: il "box inserimento puntata numerica" è a (823, 653, 67, 18)
# ma non lo testiamo nel movement (è un campo di input, non un pulsante).

# Durata fermo su ogni pulsante
HOLD_SECONDS = 2.0


def get_center(coords):
    x, y, w, h = coords
    return x + w // 2, y + h // 2


def main():
    print("=" * 60)
    print("TEST MOUSE — coordinate reali pulsanti (2s ciascuno)")
    print("=" * 60)
    print("⚠️  Solo HOVER (nessun click).")
    print("   Per fermare: sposta il mouse nell'angolo in alto a sinistra.")
    print()

    # Mostra i centri calcolati
    print("Coordinate pulsanti (centro):")
    centers = {}
    for name, coords in BUTTONS.items():
        cx, cy = get_center(coords)
        centers[name] = (cx, cy)
        print(f"  {name:16s}: centro ({cx}, {cy})  box={coords}")
    print()

    # Countdown
    print(f"Conteggio alla rovescia 3s prima di muovere il mouse...")
    for i in range(3, 0, -1):
        print(f"  {i}...")
        time.sleep(1)

    # Muovi il mouse su ciascun pulsante, 2 secondi ciascuno
    print(f"\nMuovo la freccia (ferma {HOLD_SECONDS}s su ciascuno):")
    try:
        for name, (cx, cy) in centers.items():
            print(f"\n  → {name} a ({cx}, {cy})  [tengo {HOLD_SECONDS} secondi]")
            pyautogui.moveTo(cx, cy, duration=0.7)
            time.sleep(HOLD_SECONDS)
            print(f"    ✓ {HOLD_SECONDS}s trascorse su {name}")

    except pyautogui.FailSafeException:
        print("\n⚠ FAILSAFE: mouse spostato in angolo, interrotto.")
        sys.exit(0)
    except Exception as e:
        print(f"\nERRORE mouse: {e}")
        sys.exit(1)

    # Ritorna al centro
    print("\nRitorno mouse al centro immagine...")
    pyautogui.moveTo(450, 371, duration=0.5)

    print("\n" + "=" * 60)
    print("TEST COMPLETATO")
    print("=" * 60)
    print("\nConfronta dove si è fermata la freccia con i pulsanti")
    print("nell'immagine del desktop. Sono sopra PASSA/CALL/RILANCIA?")
    print("Se no, dimmi dove sbaglia e correggiamo.")


if __name__ == "__main__":
    main()