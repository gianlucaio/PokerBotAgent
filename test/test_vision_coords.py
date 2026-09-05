#!/usr/bin/env python3
# ============================================================
# TEST MOUSE GUIDATO DALLA VISION — immagine_test1.png
# ============================================================
# Carica immagine_test1.png (899x742, quella aperta nel desktop),
# chiede alla Vision le coordinate ASSOLUTE dei 3 pulsanti
# (passa/call/rilancia) e muove la freccia su ciascuno
# per 2 secondi (SENZA click, solo hover).
#
# Lancia TU dal terminale:
#   source /home/hack/.hermes/hermes-agent/venv/bin/activate
#   cd /home/hack/Documenti/progetto_pokerbot/holdem-agent
#   DISPLAY=:0 python3 test_vision_coords.py
# ============================================================

import sys
import os
import json
import time
import base64
import cv2
import requests

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)
from vision_prompt import VISION_SYSTEM_PROMPT, VISION_MODEL

IMG_PATH = os.path.join(
    _parent,
    "..", "modalità-web-9max-4colori", "immagine_test1.png"
)
LM_URL = "http://localhost:1234/v1/chat/completions"

# Nomi pulsanti in italiano → chiave
BUTTON_NAMES = {"passa": "PASSA", "call": "CALL", "rilancia": "RILANCIA"}


def ask_vision_coords(img_bgr):
    """Chiede alla Vision le coordinate pixel dei 3 pulsanti."""
    _, buffer = cv2.imencode(".png", img_bgr)
    img_base64 = base64.b64encode(buffer).decode("utf-8")

    user_prompt = """Analizza questo screenshot di un tavolo poker (899x742 pixel).
Individua i 3 pulsanti di azione nella parte bassa dell'immagine:
1. PASSA (check)
2. CALL (chiama)
3. RILANCIA (raise)

Per ognuno restituisci le coordinate pixel ESATTE della bounding box che lo contiene.
ATTENZIONE: le coordinate devono essere quelle dell'IMMAGINE (pixel da 0 a 899 in x, da 0 a 742 in y), NON dello schermo.

Rispondi SOLO con un JSON valido, senza altro testo:
{
  "passa": {"x": 400, "y": 640, "width": 60, "height": 30},
  "call": {"x": 480, "y": 640, "width": 60, "height": 30},
  "rilancia": {"x": 560, "y": 640, "width": 60, "height": 30}
}

Regole:
- "x","y" = angolo in alto a sinistra della bounding box del pulsante
- "width","height" = dimensioni del pulsante in pixel
- Se un pulsante non è visibile, metti null per quel pulsante
- Nessun testo fuori dal JSON"""

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
        content = response.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"ERRORE VISION: {e}")
        return None

    print("RISPOSTA RAW VISION (coordinate):")
    print(content)
    print()

    # Parsa JSON
    text = content.strip()
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        print("Nessun JSON valido nella risposta.")
        return None
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError as e:
        print(f"ERRORE parsing JSON: {e}")
        return None


def get_center(bbox):
    """Centro della bounding box."""
    return bbox["x"] + bbox["width"] // 2, bbox["y"] + bbox["height"] // 2


def main():
    print("=" * 60)
    print("TEST MOUSE GUIDATO DALLA VISION — 3 pulsanti, 2s ciascuno")
    print("=" * 60)
    print("⚠️  Solo HOVER (nessun click).")
    print("   Per fermare: sposta il mouse nell'angolo in alto a sinistra.")
    print()

    if not os.path.exists(IMG_PATH):
        print(f"ERRORE: immagine non trovata:\n  {IMG_PATH}")
        sys.exit(1)

    img_bgr = cv2.imread(IMG_PATH)
    if img_bgr is None:
        print("ERRORE: impossibile leggere l'immagine")
        sys.exit(1)
    h, w = img_bgr.shape[:2]
    print(f"Immagine: {w}x{h} px (ancorata a 0,0 nel desktop)")
    print()

    # 1. Chiedi alla Vision le coordinate dei pulsanti
    print("[1] Vision individua i 3 pulsanti (passa/call/rilancia)...")
    coords = ask_vision_coords(img_bgr)
    if not coords:
        print("FALLITO: la Vision non ha restituito coordinate valide.")
        sys.exit(1)

    # 2. Calcola i centri e verifica
    targets = []
    for italian, key in BUTTON_NAMES.items():
        bbox = coords.get(key.lower())
        if bbox and bbox.get("x") is not None:
            # Il modello scrive "passa"/"call"/"rilancia" come chiave
            pass
        bbox = coords.get(key) or coords.get(key.lower()) or coords.get(italian)
        if bbox and bbox.get("x") is not None:
            cx, cy = get_center(bbox)
            if 0 <= cx <= w and 0 <= cy <= h:
                targets.append((key, cx, cy, bbox))
                print(f"  ✓ {key}: centro ({cx}, {cy})  box={bbox}")
            else:
                print(f"  ⚠ {key}: coordinate fuori immagine ({cx},{cy}), ignorato")
        else:
            print(f"  ⚠ {key}: non rilevato dalla Vision (null)")

    if not targets:
        print("NESSUN pulsante rilevato. Verifica l'immagine / modello.")
        sys.exit(1)

    # 3. Countdown prima di muovere il mouse
    print("\n[2] Conteggio alla rovescia 3s prima di muovere il mouse...")
    for i in range(3, 0, -1):
        print(f"    {i}...")
        time.sleep(1)

    # 4. Muovi il mouse su ogni pulsante per 2 secondi
    print("\n[3] Muovo la freccia su ogni pulsante (2s ciascuno):")
    try:
        import pyautogui
        pyautogui.FAILSAFE = True

        for name, cx, cy, bbox in targets:
            print(f"\n  → {name} a ({cx}, {cy})  [tengo 2 secondi]")
            pyautogui.moveTo(cx, cy, duration=0.8)
            time.sleep(2.0)  # fermo 2 secondi
            print(f"    ✓ 2s trascorse su {name}")

    except Exception as e:
        print(f"\nERRORE mouse: {e}")
        print("(pyautogui potrebbe non avere accesso al display)")
        sys.exit(1)

    # 5. Ritorna al centro
    print("\n[4] Ritorno mouse al centro schermo...")
    try:
        import pyautogui
        pyautogui.moveTo(w // 2, h // 2, duration=0.5)
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("TEST COMPLETATO")
    print("=" * 60)
    print("\nConfronta dove si è fermata la freccia con i pulsanti")
    print("nell'immagine del desktop. Sono sopra passa/call/rilancia?")
    print("Se no, dimmi dove sbaglia e correggiamo la Vision.")


if __name__ == "__main__":
    main()