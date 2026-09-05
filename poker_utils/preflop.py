# coding: utf-8
"""
preflop.py — Lookup table equity preflop (da deepmind-pokerbot).

Carica le tabelle JSON precalcolate (1326 combinazioni di 2 carte)
e fornisce lookup istantaneo senza Monte Carlo.

Tabelle disponibili:
  - preflop_equity.json:      tutti i range avversario
  - preflop_equity-50.json:   top 50% mani avversarie

Uso:
    from poker_utils.preflop import PreflopLookup
    pf = PreflopLookup()
    eq = pf.equity("As", "Kd")          # 0.657
    eq = pf.equity("As", "Kd", opponent_range=0.5)  # usa tabella -50
    eq = pf.equity_from_key("AKS")      # 0.657
"""

import json
import os
from typing import Optional

from poker_utils.card_map import to_preflop_key

# ============================================================
# Costanti
# ============================================================

_DIR = os.path.dirname(os.path.abspath(__file__))
_FULL_FILE = os.path.join(_DIR, "preflop_equity.json")
_HALF_FILE = os.path.join(_DIR, "preflop_equity-50.json")


# ============================================================
# Classe principale
# ============================================================

class PreflopLookup:
    """
    Lookup table per equity preflop.

    Carica le tabelle JSON alla prima chiamata (lazy loading).
    Per default usa la tabella full range; passa opponent_range=0.5
    per la tabella top 50%.
    """

    def __init__(self):
        self._full: Optional[dict] = None
        self._half: Optional[dict] = None

    def _load_full(self) -> dict:
        if self._full is None:
            with open(_FULL_FILE, "r", encoding="utf-8") as f:
                self._full = json.load(f)
        return self._full

    def _load_half(self) -> dict:
        if self._half is None:
            with open(_HALF_FILE, "r", encoding="utf-8") as f:
                self._half = json.load(f)
        return self._half

    def equity(self, card1: str, card2: str,
               opponent_range: float = 1.0) -> Optional[float]:
        """
        Restituisce l'equity preflop per due carte.

        Args:
            card1, card2: carte formato Treys ("As") o Deepmind ("AS")
            opponent_range: 1.0 = full range (default), 0.5 = top 50%

        Returns:
            float 0-1 se trovato, None se non trovato.
        """
        key = to_preflop_key(card1, card2)
        return self.equity_from_key(key, opponent_range)

    def equity_from_key(self, key: str,
                        opponent_range: float = 1.0) -> Optional[float]:
        """
        Restituisce l'equity preflop da una chiave deepmind.

        Args:
            key: chiave deepmind ("AKS", "AKO", "AA", ecc.)
            opponent_range: 1.0 = full range, 0.5 = top 50%

        Returns:
            float 0-1 se trovato, None se non trovato.
        """
        key = key.upper()
        if opponent_range <= 0.5:
            table = self._load_half()
        else:
            table = self._load_full()
        return table.get(key)

    def lookup(self, card1: str, card2: str,
               opponent_range: float = 1.0) -> dict:
        """
        Lookup completo con info aggiuntive.

        Returns:
            dict con: equity, key, hand_name, range_used
        """
        key = to_preflop_key(card1, card2)
        eq = self.equity_from_key(key, opponent_range)
        if eq is None:
            return {"equity": None, "key": key, "hand_name": None,
                    "range_used": opponent_range}
        # Nome mano leggibile
        name = self._hand_name(key)
        return {"equity": eq, "key": key, "hand_name": name,
                "range_used": opponent_range}

    @staticmethod
    def _hand_name(key: str) -> str:
        """Restituisce il nome leggibile della mano."""
        rank_names = {
            "A": "Ace", "K": "King", "Q": "Queen", "J": "Jack", "T": "Ten",
            "9": "Nine", "8": "Eight", "7": "Seven", "6": "Six", "5": "Five",
            "4": "Four", "3": "Three", "2": "Two",
        }
        if len(key) == 2:
            r = rank_names.get(key[0], key[0])
            return f"Pocket {r}s"
        r1 = rank_names.get(key[0], key[0])
        r2 = rank_names.get(key[1], key[1])
        suited = "suited" if key[2] == "S" else "offsuit"
        return f"{r1}-{r2} {suited}"

    @property
    def table_size(self) -> int:
        """Numero di combinazioni nella tabella."""
        return len(self._load_full())


# ============================================================
# Funzione di convenienza
# ============================================================

_default_lookup = None

def quick_equity(card1: str, card2: str,
                 opponent_range: float = 1.0) -> Optional[float]:
    """
    Funzione rapida per equity preflop.
    Usa una singleton PreflopLookup interna.

    >>> quick_equity("As", "Kd")
    0.657
    """
    global _default_lookup
    if _default_lookup is None:
        _default_lookup = PreflopLookup()
    return _default_lookup.equity(card1, card2, opponent_range)


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=== Test preflop.py ===")

    pf = PreflopLookup()
    print(f"✓ Tabella caricata: {pf.table_size} combinazioni")

    # Test lookup diretto
    eq = pf.equity("As", "Kd")
    assert eq is not None, "Equity AK offsuit non trovata"
    assert 0.0 < eq < 1.0
    print(f"✓ Equity As-Kd = {eq:.4f}")

    # Test suited
    eq_s = pf.equity("As", "Ks")
    assert eq_s is not None
    assert eq_s > eq, "Suited dovrebbe avere equity > offsuit"
    print(f"✓ Equity As-Ks = {eq_s:.4f} (> {eq:.4f} OK)")

    # Test pair
    eq_aa = pf.equity("As", "Ad")
    assert eq_aa is not None
    assert eq_aa > 0.8, f"AA dovrebbe avere equity alta, ha {eq_aa}"
    print(f"✓ Equity As-Ad = {eq_aa:.4f}")

    # Test tabella half range
    eq_h = pf.equity("As", "Kd", opponent_range=0.5)
    assert eq_h is not None
    print(f"✓ Equity AK off (50% range) = {eq_h:.4f}")

    # Test lookup con info
    info = pf.lookup("As", "Kd")
    assert info["equity"] is not None
    assert info["hand_name"] == "King-Ace offsuit"
    assert info["key"] == "KAO"
    print(f"✓ Lookup: {info}")

    # Test quick_equity
    eq_q = quick_equity("As", "Ad")
    assert eq_q == eq_aa
    print("✓ quick_equity OK")

    # Test tutte le mani (stress test)
    import time
    t0 = time.time()
    count = 0
    for card1 in pf._load_full():
        count += 1
    elapsed = time.time() - t0
    print(f"✓ Iterazione {count} chiavi in {elapsed*1000:.1f}ms")

    print("\n=== Tutti i test passati! ===")
