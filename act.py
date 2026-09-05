# ============================================================
# HoldEm Agent — Modulo ACT (Esecuzione Motoria)
# ============================================================
# v0.3.0 — Carica coordinate pulsanti dal layout PokerTableScope.
# Non più hardcoded. Il layout contiene: table_roi, act_targets (fold/check/call/raise/allin/bet).
# ============================================================

import pyautogui
import time
import json
import os
from config import LAYOUTS_DIR, DEBUG_MODE


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
        """Click su coordinate validate rispetto alla ROI tavolo."""
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

    def click_by_action(self, azione):
        """Mappa un'azione alle coordinate del pulsante nel layout.
        Supporta: FOLD, CHECK, CALL, RAISE, ALL-IN, BET (6 pulsanti PokerTableScope).
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
        return self.click_action(x, y)

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
        Placeholder: la vera implementazione richiede micro-cattura mirata.
        """
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