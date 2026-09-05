# ============================================================
# HoldEm Agent — Step 5: Calibrazione ROI con Screenshot Reali
# ============================================================
# Segue Guida Master v2.2 Sezione 2/3.2 e Piano Operativo v2.2 Step 5.
#
# Per ciascuno screenshot in modalità-web-9max-*/:
#   1. Chiama qwen3-vl-8b-instruct col prompt vision (vision_prompt.py)
#   2. Estrae carte/stack/pot/timer/hero dal testo prodotto
#   3. Verifica che le coordinate in layouts/layout_web_9max.json
#      ricadano sulle aree corrette
#
# Criterio di uscita: >= 18/20 screenshot letti correttamente
# ============================================================

import sys
import os
import json
import glob
import base64
import requests
from datetime import datetime

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from vision_prompt import VISION_SYSTEM_PROMPT, VISION_MODEL, VISION_MAX_TOKENS
from config import LM_STUDIO_URL, HERO_NAME


def encode_image(image_path: str) -> str:
    """Codifica immagine in base64 per invio a LM Studio."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def call_vision_model(image_path: str) -> str:
    """Chiama il modello vision e ritorna il testo prodotto."""
    base64_image = encode_image(image_path)

    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": VISION_SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Analizza questo screenshot del tavolo da poker e rileva carte, giocatori, pot, stack e hero secondo le istruzioni."
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.0,
        "max_tokens": VISION_MAX_TOKENS
    }

    try:
        response = requests.post(LM_STUDIO_URL, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        return f"ERROR: {e}"


def parse_vision_output(text: str) -> dict:
    """Estrae dal testo del modello vision le informazioni strutturate."""
    result = {
        "board_cards": [],
        "players": [],
        "hero": None,
        "pot": None,
        "readable": True
    }

    lines = text.split("\n")
    current_section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue

        lower = line.lower()

        if "carte comuni" in lower or "board" in lower:
            current_section = "board"
            continue
        elif "giocatori rilevati" in lower or "giocatori:" in lower:
            current_section = "players"
            continue
        elif "hero:" in lower:
            current_section = "hero"
            # Estrai nome hero dalla stessa linea
            if ":" in line:
                hero_part = line.split(":", 1)[1].strip()
                if hero_part and "non identificato" not in hero_part.lower():
                    result["hero"] = hero_part
            continue
        elif "non leggibili" in lower or "non visibili" in lower:
            current_section = "unreadable"
            continue

        # Parsing carte (formato: "Asso di Cuori" o "K di Picche")
        if current_section == "board" and ("di " in line or " di " in line.lower()):
            import re
            match = re.search(r"([AKQJ10-9-2]+)\s*di\s*([A-Za-z]+)", line)
            if match:
                val = match.group(1).upper()
                suit_name = match.group(2).lower()
                suit_map = {"fiori": "c", "clubs": "c", "picche": "s", "spades": "s",
                           "cuori": "h", "hearts": "h", "denari": "d", "diamonds": "d"}
                suit = suit_map.get(suit_name, "?")
                result["board_cards"].append(f"{val}{suit}")

        # Parsing giocatori
        if current_section == "players" and "—" in line:
            name = line.split("—")[0].strip()
            result["players"].append(name)

        # Sezione hero multi-linea
        if current_section == "hero" and result["hero"] is None:
            if HERO_NAME.lower() in line.lower():
                result["hero"] = HERO_NAME

    # Verifica leggibilità
    if "non leggibile" in text.lower() or "error" in text.lower():
        result["readable"] = "non leggibile" not in text.lower()

    return result


def verify_layout_coordinates(layout: dict, vision_result: dict) -> dict:
    """
    Verifica che le coordinate nel layout ricadano sulle aree attese.
    Questo è un controllo incrociato: se il modello vede '{HERO_NAME}'
    ma il layout non ha coordinate per quel seat, c'è disallineamento.
    """
    issues = []

    sub_roi = layout.get("sub_roi", {})

    # Verifica hero seat
    if vision_result.get("hero") == HERO_NAME:
        if "hero_seat" not in sub_roi:
            issues.append("Hero rilevato ma nessuna coordinata hero_seat nel layout")

    # Verifica player_seats presenti
    if vision_result.get("players"):
        if "player_seats" not in sub_roi or len(sub_roi.get("player_seats", [])) == 0:
            issues.append("Giocatori rilevati ma nessun player_seat nel layout")

    # Verifica board cards area
    if vision_result.get("board_cards"):
        if "board_cards" not in sub_roi:
            issues.append("Board cards rilevate ma nessuna ROI board_cards nel layout")

    # Verifica pot area
    if "pot" not in sub_roi:
        issues.append("Nessuna ROI pot nel layout")

    # Verifica timer area
    if "timer" not in sub_roi:
        issues.append("Nessuna ROI timer nel layout")

    return {"issues": issues, "valid": len(issues) == 0}


def main():
    print("=" * 70)
    print("STEP 5 — Calibrazione ROI con Screenshot Reali (Web 9-max)")
    print("=" * 70)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    screenshots_dirs = [
        os.path.join(base_dir, "..", "modalità-web-9max-2colori"),
        os.path.join(base_dir, "..", "modalità-web-9max-4colori"),
    ]

    # Carica layout
    layout_path = os.path.join(base_dir, "layouts", "layout_web_9max.json")
    with open(layout_path, "r", encoding="utf-8") as f:
        layout = json.load(f)
    print(f"Layout caricato: {layout_path}")

    # Raccogli screenshot (primi 20 per il criterio di uscita)
    all_screenshots = []
    for d in screenshots_dirs:
        if os.path.exists(d):
            shots = glob.glob(os.path.join(d, "*.png"))
            all_screenshots.extend(shots)

    all_screenshots = all_screenshots[:20]  # Limite per criterio di uscita
    print(f"Screenshot trovati: {len(all_screenshots)}")

    if not all_screenshots:
        print("⚠️  Nessuno screenshot trovato. Verifica le cartelle sorgente.")
        return

    correct_count = 0
    results_log = []

    for i, shot in enumerate(all_screenshots):
        print(f"\n[{i+1}/{len(all_screenshots)}] {os.path.basename(shot)}")
        vision_text = call_vision_model(shot)
        vision_result = parse_vision_output(vision_text)
        coord_check = verify_layout_coordinates(layout, vision_result)

        shot_ok = vision_result["readable"] and coord_check["valid"]
        if shot_ok:
            correct_count += 1
            status = "✅"
        else:
            status = "❌"
            if not coord_check["valid"]:
                print(f"    Problemi layout: {coord_check['issues']}")

        results_log.append({
            "file": os.path.basename(shot),
            "readable": vision_result["readable"],
            "hero": vision_result.get("hero"),
            "board": vision_result.get("board_cards"),
            "players": vision_result.get("players"),
            "layout_valid": coord_check["valid"],
            "status": status
        })

        print(f"  {status} Hero: {vision_result.get('hero')} | "
              f"Board: {vision_result.get('board_cards')} | "
              f"Players: {len(vision_result.get('players', []))}")

    # Criterio di uscita
    total = len(all_screenshots)
    print("\n" + "=" * 70)
    print(f"RISULTATO CALIBRAZIONE: {correct_count}/{total} screenshot corretti")
    print(f"Criterio di uscita (>= 18/20): {'✅ SUPERATO' if correct_count >= 18 else '❌ NON SUPERATO'}")

    if correct_count < 18:
        print("\nProblemi rilevati (prime 5 discrepanze):")
        discrepancies = [r for r in results_log if r["status"] == "❌"]
        for d in discrepancies[:5]:
            print(f"  - {d['file']}: readable={d['readable']}, layout_valid={d['layout_valid']}")

    print("=" * 70)

    # Salva report
    report_path = os.path.join(base_dir, "calibration_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "correct": correct_count,
            "total": total,
            "criterion_passed": correct_count >= 18,
            "results": results_log
        }, f, indent=2, ensure_ascii=False)
    print(f"\nReport salvato: {report_path}")


if __name__ == "__main__":
    main()
