# coding: utf-8
"""
sizing.py — Calcolo sizing bet in base all'equity.

Usa una curva potenza: bet = adj1 * (equity + adj2) ^ pw

Riscritto da curvefitting.py (deepmind-pokerbot) usando solo numpy,
senza lmfit/scipy come dipendenze aggiuntive.

Uso:
    from poker_utils.sizing import BetSizing
    bs = BetSizing(small_blind=0.02, big_blind=0.04, max_value=2.0,
                   min_equity=0.75, max_equity=0.9, power=16)
    bet = bs.get_bet(0.85)
"""

from typing import List, Optional


class BetSizing:
    """
    Calcola la dimensione della bet in base all'equity della mano.

    La curva potenza passa per 2 punti:
      - (min_equity, big_blind) → bet minima
      - (1.0, max_value)        → bet massima

    Il parametro pw (power) controlla la curvatura.
    """

    def __init__(self, small_blind: float, big_blind: float,
                 max_value: float, min_equity: float,
                 max_equity: float, power: int = 16):
        """
        Args:
            small_blind: valore small blind
            big_blind: valore big blind
            max_value: bet massima (es. 2.0 = 2x pot)
            min_equity: equity sotto cui si scommette poco
            max_equity: equity sopra cui si passa al check/trapping
            power: esponente della curva (più alto = più aggressivo)
        """
        self.small_blind = small_blind
        self.big_blind = big_blind
        self.max_value = max_value
        self.min_equity = min_equity
        self.max_equity = max_equity
        self.power = power

        # Risolvi per adj1 e adj2 usando i 2 punti noti
        # y = adj1 * (x + adj2) ^ pw
        # Punto 1: big_blind = adj1 * (min_equity + adj2) ^ pw
        # Punto 2: max_value = adj1 * (1.0 + adj2) ^ pw
        # Dividendo: max_value/big_blind = ((1+adj2)/(min_equity+adj2))^pw
        # Risolvi per adj2 con bisezione
        self._adj1, self._adj2 = self._solve_params()

    def _solve_params(self) -> tuple:
        """Risolve i parametri adj1, adj2 con bisezione."""
        # Risolvi: ((1+x)/(min_eq+x))^pw = max_val/bb
        ratio = self.max_value / self.big_blind
        pw = self.power
        min_eq = self.min_equity

        # Funzione obiettivo: f(x) = ((1+x)/(min_eq+x))^pw - ratio
        def f(x):
            return ((1 + x) / (min_eq + x)) ** pw - ratio

        # Bisezione su x in [0, 10]
        lo, hi = 0.0, 10.0
        for _ in range(100):
            mid = (lo + hi) / 2
            if f(mid) > 0:
                hi = mid
            else:
                lo = mid
        adj2 = (lo + hi) / 2
        adj1 = self.big_blind / ((min_eq + adj2) ** pw)
        return adj1, adj2

    def get_bet(self, equity: float) -> float:
        """
        Calcola la dimensione della bet per una data equity.

        Args:
            equity: valore 0-1

        Returns:
            Dimensione della bet (big_blind ≤ bet ≤ max_value)
        """
        if equity < self.min_equity:
            return self.big_blind
        if equity > self.max_equity:
            return 0.0

        bet = self._adj1 * ((equity + self._adj2) ** self.power)
        bet = max(self.big_blind, min(self.max_value, bet))
        return round(bet, 4)

    def get_bets(self, equities: List[float]):
        """
        Calcola le bet per un array di equities.

        Args:
            equities: lista di valori equity 0-1

        Returns:
            Array numpy con le bet corrispondenti
        """
        import numpy as np
        return np.array([self.get_bet(e) for e in equities])

    def get_curve(self, n_points: int = 50) -> tuple:
        """
        Restituisce x (equities) e y (bets) per plotting.

        Returns:
            (x_array, y_array) tuple di numpy arrays
        """
        import numpy as np
        x = np.linspace(0, 1, n_points)
        y = self.get_bets(x.tolist())
        return x, y


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=== Test sizing.py ===")

    bs = BetSizing(
        small_blind=0.02,
        big_blind=0.04,
        max_value=2.0,
        min_equity=0.75,
        max_equity=0.9,
        power=16,
    )

    # Test equity bassa → big blind
    bet_low = bs.get_bet(0.5)
    assert bet_low == 0.04, f"Equity 0.5 dovrebbe dare BB, ha {bet_low}"
    print(f"✓ Equity 0.5 → bet {bet_low} (BB)")

    # Test equity alta → 0 (fold, troppo forte per bet)
    bet_high = bs.get_bet(0.95)
    assert bet_high == 0.0, f"Equity 0.95 dovrebbe dare 0, ha {bet_high}"
    print(f"✓ Equity 0.95 → bet {bet_high} (fold)")

    # Test equity media → bet intermedia
    bet_mid = bs.get_bet(0.82)
    assert 0.04 < bet_mid < 2.0, f"Equity 0.82 dovrebbe dare bet intermedia, ha {bet_mid}"
    print(f"✓ Equity 0.82 → bet {bet_mid}")

    # Test monotonia: bet cresce con equity
    bets = [bs.get_bet(e) for e in [0.75, 0.80, 0.85, 0.88, 0.90]]
    for i in range(len(bets) - 1):
        assert bets[i] <= bets[i + 1], f"Bete non monotone: {bets}"
    print(f"✓ Monotonia OK: {bets}")

    # Test curva
    x, y = bs.get_curve(20)
    assert len(x) == 20
    assert len(y) == 20
    print(f"✓ Curva 20 punti OK")

    # Test multipli
    equities = [0.5, 0.75, 0.85, 0.95]
    bets_arr = bs.get_bets(equities)
    assert len(bets_arr) == 4
    print(f"✓ get_bets([0.5, 0.75, 0.85, 0.95]) = {bets_arr}")

    print("\n=== Tutti i test passati! ===")
