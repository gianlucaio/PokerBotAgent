# ============================================================
# HoldEm Agent — Modulo SEE (Percezione Visiva)
# ============================================================
# v0.3.0 — Ristrutturato: SEE carica il layout esterno da PokerTableScope.
# Le coordinate (seats, pulsanti, ROI) sono nel layout_<preset>.json
# generato da PokerTableScope. OCR mantenuto solo come fallback se Vision
# non restituisce dati utili.
# Contratto SEE→EVAL v2.2: SEE normalizza le carte in formato Treys ("As").
# ============================================================

import mss
import cv2
import numpy as np
import json
import os
import time

# Tesseract è importato solo dentro i metodi fallback (lazy), così se
# non è installato il modulo principale funziona comunque.
from config import (
    LAYOUTS_DIR, DEFAULT_WEB_WIDTH, DEFAULT_WEB_HEIGHT,
    POLL_INTERVAL_MS, TESSERACT_CMD, HERO_NAME, VISION_MODEL, VISION_MAX_TOKENS
)


class SeeModule:
    """Gestisce cattura schermo, riconoscimento (Vision + fallback OCR)."""

    # Mappa conversione formato esteso → Treys compatto
    RANK_MAP = {
        "2": "2", "3": "3", "4": "4", "5": "5", "6": "6", "7": "7",
        "8": "8", "9": "9", "10": "T", "T": "T",
        "JACK": "J", "J": "J", "QUEEN": "Q", "Q": "Q",
        "KING": "K", "K": "K", "ACE": "A", "A": "A"
    }
    SUIT_MAP = {
        "HEARTS": "h", "H": "h", "SPADES": "s", "S": "s",
        "DIAMONDS": "d", "D": "d", "CLUBS": "c", "C": "c"
    }

    def __init__(self, layout_file=None):
        """layout_file: nome del layout PokerTableScope (es. 'layout_peoples-web-9max-4colori.json').
        Se omesso, carica il primo layout trovato in LAYOUTS_DIR.
        """
        self.sct = mss.mss()
        self.hero_seat = None
        self.width = DEFAULT_WEB_WIDTH
        self.height = DEFAULT_WEB_HEIGHT
        self.layout = self._load_layout(layout_file)

    def _load_layout(self, layout_file=None):
        """Carica il layout JSON generato da PokerTableScope."""
        if layout_file:
            path = os.path.join(LAYOUTS_DIR, layout_file)
            if os.path.exists(path):
                return self._apply_layout(path)
        # Altrimenti cerca il primo layout disponibile
        if os.path.isdir(LAYOUTS_DIR):
            for f in sorted(os.listdir(LAYOUTS_DIR)):
                if f.startswith("layout_") and f.endswith(".json"):
                    return self._apply_layout(os.path.join(LAYOUTS_DIR, f))
        return {}

    def _apply_layout(self, path):
        """Applica un layout: legge res, seats, act_targets, override_rois."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                layout = json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
        # Risoluzione
        res = layout.get("resolution")
        if res and "x" in res:
            try:
                w, h = res.split("x")
                self.width, self.height = int(w), int(h)
            except (ValueError, AttributeError):
                pass
        elif isinstance(res, dict):
            self.width = res.get("width", self.width)
            self.height = res.get("height", self.height)
        self.layout = layout
        print(f"[SEE] Layout caricato: {os.path.basename(path)} ({self.width}x{self.height})")
        return layout

    # ------------------------------------------------------------------
    # Cattura schermo
    # ------------------------------------------------------------------
    def _get_table_window_origin(self):
        """Trova la posizione (left, top) della finestra del tavolo reale.
        Fallback su (0,0) se non trova la finestra."""
        import subprocess
        try:
            out = subprocess.run(["wmctrl", "-l"], capture_output=True, text=True, timeout=5).stdout
            wid = None
            for line in out.splitlines():
                if "no limit hold'em" in line.lower():
                    wid = line.split()[0]
                    break
            if not wid:
                return 0, 0
            geo = subprocess.run(["xwininfo", "-id", wid], capture_output=True, text=True, timeout=5).stdout
            def _get(key):
                for ln in geo.splitlines():
                    if key in ln and ":" in ln:
                        try:
                            return int(ln.split(":")[1].strip().split()[0])
                        except (ValueError, IndexError):
                            return None
                return None
            left = _get("Absolute upper-left X")
            top = _get("Absolute upper-left Y")
            if left is None or top is None:
                return 0, 0
            return left, top
        except Exception:
            return 0, 0

    def _load_test_screenshot(self, path=None):
        """Carica uno screenshot da file per test (opzionale)."""
        import cv2
        if path is None:
            # Cerca un file di test in shots/
            base_dir = os.path.dirname(os.path.abspath(__file__))
            shots_dir = os.path.join(base_dir, "shots")
            if os.path.isdir(shots_dir):
                for f in os.listdir(shots_dir):
                    if f.endswith(".png") and "test" in f.lower():
                        path = os.path.join(shots_dir, f)
                        break
        if path and os.path.exists(path):
            img = cv2.imread(path)
            if img is not None:
                return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        return None

    def capture_screen(self):
        """Cattura la finestra del tavolo. Ritorna numpy array RGB.
        1. Prima prova screenshot di test (se presente in shots/)
        2. Altrimenti cattura live
        """
        # 1. Prova screenshot di test
        img = self._load_test_screenshot()
        if img is not None:
            return img
        # 2. Altrimenti cattura live
        left, top = self._get_table_window_origin()
        monitor = {"top": top, "left": left, "width": self.width, "height": self.height}
        screenshot = self.sct.grab(monitor)
        img = np.array(screenshot)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)

    def capture_double(self):
        """Doppia cattura ravvicinata per consistenza frame."""
        img1 = self.capture_screen()
        time.sleep(0.12)
        img2 = self.capture_screen()
        return img1, img2

    def save_and_view(self, img=None, name="shot"):
        """Salva uno screenshot in shots/ per visualizzazione manuale."""
        if img is None:
            img = self.capture_screen()
        base_dir = os.path.dirname(os.path.abspath(__file__))
        shots_dir = os.path.join(base_dir, "shots")
        os.makedirs(shots_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        path = os.path.join(shots_dir, f"{name}_{ts}.png")
        cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
        print(f"[VIEW] Screenshot salvato: {path}")
        return path

    # ------------------------------------------------------------------
    # Normalizzazione carte (Treys)
    # ------------------------------------------------------------------
    def normalize_card(self, card_str: str) -> str:
        """Converte formato esteso (es. 'Ace of SPADES') in Treys ('As')."""
        card_str = card_str.strip().upper()
        if " OF " in card_str:
            rank_part, suit_part = card_str.split(" OF ")
            rank = self.RANK_MAP.get(rank_part.strip(), rank_part.strip()[0])
            suit = self.SUIT_MAP.get(suit_part.strip(), suit_part.strip()[0].lower())
        else:
            if len(card_str) >= 2:
                rank = self.RANK_MAP.get(card_str[0], card_str[0])
                suit = self.SUIT_MAP.get(card_str[1], card_str[1].lower())
            else:
                raise ValueError(f"Formato carta non riconosciuto: {card_str}")
        return rank + suit

    def normalize_cards(self, cards: list) -> list:
        """Normalizza una lista di carte."""
        return [self.normalize_card(c) for c in cards
                if c and c.lower() not in ("none", "not visible", "")]

    # ------------------------------------------------------------------
    # Fallback OCR (usato solo se Vision non restituisce dati)
    # ------------------------------------------------------------------
    def preprocess(self, img, roi_box):
        """Ritaglia Sub-ROI e applica preprocessing OCR."""
        x, y, w, h = roi_box
        roi = img[y:y+h, x:x+w]
        roi_resized = cv2.resize(roi, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
        gray = cv2.cvtColor(roi_resized, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    def ocr_text(self, binary_img):
        """OCR su immagine binaria (import lazy di pytesseract)."""
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        text = pytesseract.image_to_string(binary_img, lang="eng")
        return text.strip()

    def _parse_cards_from_text(self, text: str) -> list:
        """Estrae carte da testo OCR."""
        import re
        pattern = r"(A|K|Q|J|10|\d)\s*(?:of\s+)?(HEARTS|SPADES|DIAMONDS|CLUBS|H|S|D|C)"
        matches = re.findall(pattern, text, re.IGNORECASE)
        return [f"{rank} of {suit}" for rank, suit in matches]

    def _parse_numeric(self, text: str):
        """Estrae valore numerico da testo OCR."""
        import re
        cleaned = re.sub(r"[^\d.,]", "", text)
        if not cleaned:
            return None
        cleaned = cleaned.replace(".", "").replace(",", "")
        try:
            return int(cleaned)
        except ValueError:
            return None

    # ------------------------------------------------------------------
    # Parsing stato (fallback OCR su layout)
    # ------------------------------------------------------------------
    def parse_state(self, screenshot):
        """Genera JSON payload per EVAL usando OCR (fallback)."""
        import datetime
        state = {
            "timestamp": datetime.datetime.now().isoformat(),
            "hole_cards": [],
            "board": [],
            "pot": None,
            "move_timer_seconds_remaining": None,
            "players": []
        }
        seats = self.layout.get("seats", {}) if isinstance(self.layout, dict) else {}
        for seat_key in seats:
            seat = seats[seat_key]
            state["players"].append({
                "seat": seat_key, "stack": None, "action": None,
                "is_hero": False, "bet_amount": 0
            })
        return state

    # ------------------------------------------------------------------
    # Consistent check (doppia cattura)
    # ------------------------------------------------------------------
    def check_frame_consistency(self, img1, img2, state1, state2):
        """Confronta due frame sui valori critici."""
        critical_keys = ["hole_cards", "board", "pot", "move_timer_seconds_remaining"]
        for key in critical_keys:
            if state1.get(key) != state2.get(key):
                return False, f"Inconsistenza su {key}: {state1.get(key)} vs {state2.get(key)}"
        return True, "OK"

    # ------------------------------------------------------------------
    # Vision parsing (percorso principale)
    # ------------------------------------------------------------------
    def parse_state_vision(self, screenshot):
        """Usa qwen3-vl-8b-instruct per leggere lo stato live via Vision."""
        import requests
        import base64

        _, buffer = cv2.imencode('.png', cv2.cvtColor(screenshot, cv2.COLOR_RGB2BGR))
        img_base64 = base64.b64encode(buffer).decode('utf-8')

        user_prompt = f"""Analizza questo screenshot di un tavolo Texas Hold'em e restituisci SOLO un JSON valido con questa struttura esatta:
{{
  "hole_cards": ["As", "Kh"],
  "board": ["7h", "9h", "As", "6d"],
  "pot": 5110,
  "timer": 15,
  "hero_seat": 3,
  "players": [
    {{"seat": 1, "name": "player1", "stack": 10000, "bet": 0, "action": null, "active": true}},
    {{"seat": 3, "name": "{HERO_NAME}", "stack": 15000, "bet": 100, "action": "call", "active": true}}
  ],
  "tournament": {{
    "blind": "20/40",
    "ante": "0",
    "players_remaining": "526/577",
    "paid_positions": "25"
  }}
}}
Regole:
- Carte formato Treys compatto. Semi: h=hearts, d=diamonds, s=spades, c=clubs
- Seme dal COLORE: VERDE=Fiori(c), NERO=Picche(s), ROSSO=Cuori(h), BLU=Denari(d)
- Hero è SEMPRE "{HERO_NAME}"
- "active" true se avatar pieno/nitido, false se attenuato/grigiato (fold/sit-out)
- Se una carta è coperta, omettila
- NESSUN testo fuori dal JSON."""

        payload = {
            "model": VISION_MODEL,
            "messages": [
                {"role": "user", "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_base64}"}}
                ]}
            ],
            "max_tokens": VISION_MAX_TOKENS,
            "stream": False,
        }

        try:
            response = requests.post("http://localhost:1234/v1/chat/completions", json=payload, timeout=60)
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]
            if not content or not content.strip():
                print("[VISION DEBUG] Risposta vuota!")
            return content
        except Exception as e:
            return f"ERRORE VISION: {str(e)}"
