# ============================================================
# HoldEm Agent — Modulo ACT (Esecuzione Motoria)
# ============================================================
# v0.4.0 — Integrazione PokerBotStealther per anti-ban.
# Carica coordinate pulsanti dal layout PokerTableScope.
# Ogni click passa per: PathBuilder (curva) → Clicker (offset) → Timing (delay) → Drift
# Fallback a pyautogui diretto se PokerBotStealther non è disponibile.
# ============================================================

import pyautogui
import time
import json
import os
import sys
from config import LAYOUTS_DIR, DEBUG_MODE

# --- Integrazione PokerBotStealther ---
_stealther_available = False
try:
    # Aggiungi il percorso di PokerBotStealther al sys.path
    _stealther_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "PokerBotStealther")
    if os.path.isdir(_stealther_path) and _stealther_path not in sys.path:
        sys.path.insert(0, _stealther_path)
    from bezier import BezierPath
    from clicker import Clicker
    from drift import DriftManager
    from profiler import Profiler
    from path import PathBuilder
    from timing import TimingManager
    from keyboard import KeyboardManager
    _stealther_available = True
    print("[ACT] PokerBotStealther caricato con successo")
except ImportError:
    print("[ACT] PokerBotStealther non disponibile — fallback pyautogui diretto")


class ActModule:
    """Gestisce click e input sulla finestra del tavolo usando coordinate dal layout."""

    def __init__(self, layout=None):
        """
        layout: dict caricato da layout_<preset>.json (già parsato da SeeModule o
        passato direttamente). Contiene: table_roi, act_targets, seats.
        """
        pyautogui.FAILSAFE = True
        self.layout = layout or {}
        self.table_roi = self.layout.get("table_roi", {"x": 0, "y": 0, "w": 899, "h": 742})
        self.act_targets = self.layout.get("act_targets", {})
        self.seats = self.layout.get("seats", {})
        self.bounding_box = self._get_bounding_box()

        # --- Inizializza componenti PokerBotStealther ---
        self._profiler = Profiler() if _stealther_available else None
        self._path_builder = None
        self._clicker = None
        self._timing = None
        self._drift = None
        self._keyboard = None
        self._init_stealther()

    def _init_stealther(self):
        """Inizializza i componenti PokerBotStealther con i livelli del profilo."""
        if not _stealther_available:
            return
        if self._profiler:
            self._path_builder = PathBuilder(speed_level=self._profiler.speed_level)
            self._clicker = Clicker(click_latency=self._profiler.click_latency)
            self._timing = TimingManager(click_latency=self._profiler.click_latency)
            self._drift = DriftManager(speed_level=self._profiler.speed_level)
            self._keyboard = KeyboardManager(typing_level=self._profiler.typing_level)
            print(f"[ACT] Stealther inizializzato: {self._profiler.profile.name} "
                  f"(speed={self._profiler.speed_level} click={self._profiler.click_latency} "
                  f"typing={self._profiler.typing_level})")

    def _get_bounding_box(self):
        """Bounding box della ROI tavolo (usata per validazione click)."""
        tr = self.table_roi
        return {
            "x": tr.get("x", 0),
            "y": tr.get("y", 0),
            "width": tr.get("w", tr.get("width", 899)),
            "height": tr.get("h", tr.get("height", 742))
        }

    def _validate_coordinates(self, x, y):
        """Verifica che le coordinate siano dentro la bounding box."""
        bb = self.bounding_box
        if x < bb["x"] or x > bb["x"] + bb["width"]:
            return False
        if y < bb["y"] or y > bb["y"] + bb["height"]:
            return False
        return True

    def click_action(self, x, y):
        """
        Click su coordinate validate rispetto alla ROI tavolo.
        Se PokerBotStealther è disponibile, usa: PathBuilder → Clicker → Timing → Drift
        Altrimenti: pyautogui diretto.
        """
        if not self._validate_coordinates(x, y):
            print(f"[ACT] ANOMALY: coordinates ({x},{y}) out of bounding box!")
            return False

        if _stealther_available and self._path_builder:
            return self._click_with_stealther(x, y)
        else:
            return self._click_direct(x, y)

    def _click_with_stealther(self, x, y):
        """Click completo con PokerBotStealther: movimento → click → delay → drift.
        Se il click è stato eseguito ma post-azioni falliscono, NON rifare il click.
        """
        clicked = False  # flag: il click è stato fisicamente eseguito
        try:
            # 1. Riflessione pre-azione
            if self._timing:
                reflection = self._timing.reflection_delay("click")
                time.sleep(reflection)

            # 2. Movimento mouse con curva Bezier
            if self._path_builder:
                current = pyautogui.position()
                self._path_builder._old_x, self._path_builder._old_y = current.x, current.y
                self._path_builder._initialized = True
                self._path_builder.move_to((x, y))

            # 3. Click con offset gaussiano
            if self._clicker:
                self._clicker.click(x, y)
            else:
                pyautogui.click(x, y)
            clicked = True

            # 4. Delay post-azione
            if self._timing:
                post_delay = self._timing.post_action_delay()
                time.sleep(post_delay)
            else:
                time.sleep(0.05)

            # 5. Drift fuori finestra
            if self._drift:
                current = pyautogui.position()
                self._drift.drift_outside_window(
                    table_roi=self.table_roi,
                    current_pos=(current.x, current.y))

            # 6. Verifica stato
            changed = self._verify_state_change()
            if not changed:
                print("[ACT] No state change detected, retrying click...")
                time.sleep(0.3)
                if self._clicker:
                    self._clicker.click(x, y)
                else:
                    pyautogui.click(x, y)
                time.sleep(0.05)
                if self._drift:
                    current = pyautogui.position()
                    self._drift.drift_outside_window(
                        table_roi=self.table_roi,
                        current_pos=(current.x, current.y))
                changed = self._verify_state_change()

            return changed

        except Exception as e:
            if clicked:
                # Il click è stato eseguito — NON rifare, logga solo
                print(f"[ACT] Post-click error (click già eseguito): {e}")
                return True
            print(f"[ACT] Pre-click error: {e} — fallback diretto")
            return self._click_direct(x, y)

    def _click_direct(self, x, y):
        """Click diretto con pyautogui (fallback)."""
        if not self._validate_coordinates(x, y):
            print(f"[ACT] ANOMALY: coordinates ({x},{y}) out of bounding box!")
            return False

        pyautogui.click(x, y)
        time.sleep(0.05)

        changed = self._verify_state_change()
        if not changed:
            print("[ACT] No state change detected, retrying click...")
            time.sleep(0.3)
            pyautogui.click(x, y)
            time.sleep(0.05)
            changed = self._verify_state_change()

        return changed

    def click_by_action(self, azione, sizing=None):
        """
        Mappa un'azione alle coordinate del pulsante nel layout.
        Supporta: FOLD, CHECK, CALL, RAISE, ALL-IN, BET (6 pulsanti PokerTableScope).
        Se sizing è fornito e l'azione è BET/RAISE, usa la tastiera per inserire l'importo.
        """
        # Normalizza l'azione
        key = str(azione).strip().upper()

        # Alias mappati ai nomi canonici del layout (act_targets keys)
        alias_map = {
            "FOLD": "fold", "PASSA": "fold",
            "CHECK": "check",
            "CALL": "call",
            "RAISE": "raise", "RILANCIA": "raise",
            "ALL-IN": "allin", "ALLIN": "allin", "TUTTO": "allin",
            "BET": "bet",
        }
        canonical = alias_map.get(key, key.lower())
        target = self.act_targets.get(canonical)

        if not target or not isinstance(target, dict):
            print(f"[ACT] Azione non calibrata nel layout: {key} (canonical={canonical})")
            # Fallback safety: fold
            if "fold" in self.act_targets:
                target = self.act_targets["fold"]
                print("[ACT] Fallback su FOLD")
            else:
                return False

        x = target.get("x")
        y = target.get("y")
        if x is None or y is None:
            print(f"[ACT] Coordinate mancanti per {canonical}")
            return False

        print(f"[ACT] click_by_action: {key} -> ({x},{y})")

        # Se sizing è fornito e l'azione è BET/RAISE, usa la tastiera
        if sizing and canonical in ("bet", "raise"):
            return self._type_and_click(x, y, str(sizing))

        return self.click_action(x, y)

    def _type_and_click(self, x, y, amount):
        """Click sull'input field e digita il bet sizing."""
        if not _stealther_available or not self._keyboard:
            if not self._validate_coordinates(x, y):
                print(f"[ACT] ANOMALY: coordinates ({x},{y}) out of bounding box!")
                return False
            pyautogui.click(x, y)
            pyautogui.typewrite(str(amount), interval=0.05)
            pyautogui.press("enter")
            return True

        submitted = False  # flag: l'importo è stato inviato
        try:
            # Riflessione
            if self._timing:
                reflection = self._timing.reflection_delay("raise")
                time.sleep(reflection)

            # Movimento verso l'input field
            if self._path_builder:
                current = pyautogui.position()
                self._path_builder._old_x, self._path_builder._old_y = current.x, current.y
                self._path_builder._initialized = True
                self._path_builder.move_to((x, y))

            # Digitazione bet sizing
            self._keyboard.type_and_submit(x, y, amount)
            submitted = True

            # Delay post
            if self._timing:
                time.sleep(self._timing.post_action_delay())

            # Drift
            if self._drift:
                current = pyautogui.position()
                self._drift.drift_outside_window(
                    table_roi=self.table_roi,
                    current_pos=(current.x, current.y))

            return True

        except Exception as e:
            if submitted:
                # L'importo è già stato inviato — NON rifare
                print(f"[ACT] Post-submit error (importo già inviato): {e}")
                return True
            print(f"[ACT] Errore tastiera: {e} — fallback diretto")
            if not self._validate_coordinates(x, y):
                print(f"[ACT] ANOMALY: coordinates ({x},{y}) out of bounding box!")
                return False
            pyautogui.click(x, y)
            pyautogui.typewrite(str(amount), interval=0.05)
            pyautogui.press("enter")
            return True

    def click_by_seat(self, seat):
        """Click su un seat specifico (per select, sit-out recovery, ecc.)."""
        seat_key = str(seat)
        seat_data = self.seats.get(seat_key)
        if not seat_data:
            print(f"[ACT] Seat {seat} non trovato nel layout")
            return False
        x = seat_data.get("x")
        y = seat_data.get("y")
        if x is None or y is None:
            return False
        return self.click_action(x, y)

    def _verify_state_change(self):
        """Verifica se lo stato del tavolo è cambiato dopo il click.
        Placeholder: la vera implementazione richiede micro-cattura mirata."""
        return True

    def sit_out_recovery(self):
        """Rileva e clicca pulsante 'Torna in Gioco'.
        Da implementare con detection specifica."""
        pass

    def set_layout(self, layout):
        """Aggiorna il layout in runtime (per cambio tavolo)."""
        self.layout = layout
        self.table_roi = layout.get("table_roi", self.table_roi)
        self.act_targets = layout.get("act_targets", self.act_targets)
        self.seats = layout.get("seats", self.seats)
        self.bounding_box = self._get_bounding_box()
        # Reinizializza stealther con nuovo layout
        self._init_stealther()

    def set_budget(self, seconds):
        """Imposta budget per l'azione corrente."""
        if self._profiler:
            self._profiler.set_budget(seconds)

    def get_stealther_status(self):
        """Restituisce lo stato dell'integrazione PokerBotStealther."""
        return {
            "available": _stealther_available,
            "profile": self._profiler.profile.name if self._profiler else None,
            "speed_level": self._profiler.speed_level if self._profiler else None,
            "click_latency": self._profiler.click_latency if self._profiler else None,
            "typing_level": self._profiler.typing_level if self._profiler else None,
        }
