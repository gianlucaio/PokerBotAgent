# coding: utf-8
"""
montecarlo.py — Monte Carlo simulation per equity.

Estratto da deepmind-pokerbot/montecarlo_python.py e riscritto usando
Treys come evaluator al posto del calc_score proprietario.

Logica:
1. Crea mazzo 52 carte (formato Treys)
2. Distribuisce carte casuali a ogni giocatore
3. Board non finito → randomizza le rimanenti
4. Valuta ogni mano con Treys.Evaluator
5. Conta vittorie per calcolare equity

Uso:
    from poker_utils.montecarlo import monte_carlo
    result = monte_carlo(["As", "Kd"], ["Th", "9c", "2d"], num_players=2)
    print(result)  # {'equity': 0.45, 'runs': 3000, ...}
"""

import random
import time
from typing import List, Optional, Dict

import treys

from poker_utils.card_map import to_treys, to_preflop_key


def _create_deck() -> List[str]:
    """Crea il mazzo completo di 52 carte (formato Treys)."""
    ranks = "23456789TJQKA"
    suits = "hdsc"
    return [r + s for r in ranks for s in suits]


def _evaluate_hand(hole: List[str], board: List[str]) -> int:
    """Valuta una mano con Treys (valore più basso = meglio)."""
    evaluator = treys.Evaluator()
    hole_int = [treys.Card.new(c) for c in hole]
    board_int = [treys.Card.new(c) for c in board]
    return evaluator.evaluate(hole_int, board_int)


def monte_carlo(hole_cards: List[str], board: List[str],
                num_players: int = 2, max_runs: int = 3000,
                timeout: float = 5.0,
                player_ranges: Optional[List] = None) -> Dict:
    """
    Esegue una Monte Carlo simulation per calcolare l'equity.

    Args:
        hole_cards: 2 carte formato Treys (es. ["As", "Kd"])
        board: 0-5 carte formato Treys (es. ["Th", "9c", "2d"])
        num_players: numero totale giocatori (hero incluso)
        max_runs: numero massimo di simulazioni
        timeout: timeout in secondi
        player_ranges: lista di set di chiavi preflop per ogni avversario,
                       None = range casuale (tutte le mani)

    Returns:
        dict con: equity (0-1), wins, runs, hand_types (Counter)
    """
    if len(hole_cards) != 2:
        raise ValueError(f"Servono esattamente 2 hole cards, ricevute {len(hole_cards)}")
    if len(board) > 5:
        raise ValueError(f"Max 5 board cards, ricevute {len(board)}")
    if num_players < 2:
        raise ValueError("Servono almeno 2 giocatori")

    # Normalizza in formato Treys
    hole = [to_treys(c) for c in hole_cards]
    brd = [to_treys(c) for c in board]

    # Mazzo completo
    deck = _create_deck()

    # Rimuovi carte note dal mazzo
    known = set(hole) | set(brd)
    remaining_deck = [c for c in deck if c not in known]

    evaluator = treys.Evaluator()
    wins = 0
    runs = 0
    hand_types = {}
    start_time = time.time()

    cards_needed_for_board = 5 - len(brd)

    for _ in range(max_runs):
        runs += 1

        # Copia il mazzo per questa iterazione
        iter_deck = list(remaining_deck)

        # Distribuisci carte agli avversari
        opp_cards = []
        for i in range(num_players - 1):
            p_range = player_ranges[i] if player_ranges and i < len(player_ranges) else None
            if p_range and len(p_range) > 0:
                # Range filtering
                found = False
                for _try in range(50):
                    if len(iter_deck) < 2:
                        break
                    idx1 = random.randint(0, len(iter_deck) - 1)
                    idx2 = random.randint(0, len(iter_deck) - 1)
                    while idx2 == idx1:
                        idx2 = random.randint(0, len(iter_deck) - 1)
                    c1, c2 = iter_deck[idx1], iter_deck[idx2]
                    key = to_preflop_key(c1, c2)
                    if key in p_range:
                        opp_cards.append([c1, c2])
                        # Rimuovi dal mazzo
                        max_idx = max(idx1, idx2)
                        min_idx = min(idx1, idx2)
                        iter_deck.pop(max_idx)
                        iter_deck.pop(min_idx)
                        found = True
                        break
                if not found:
                    # Fallback
                    idx1 = random.randint(0, len(iter_deck) - 1)
                    idx2 = random.randint(0, len(iter_deck) - 1)
                    while idx2 == idx1:
                        idx2 = random.randint(0, len(iter_deck) - 1)
                    opp_cards.append([iter_deck[idx1], iter_deck[idx2]])
                    max_idx = max(idx1, idx2)
                    min_idx = min(idx1, idx2)
                    iter_deck.pop(max_idx)
                    iter_deck.pop(min_idx)
            else:
                # Range casuale
                idx1 = random.randint(0, len(iter_deck) - 1)
                idx2 = random.randint(0, len(iter_deck) - 1)
                while idx2 == idx1:
                    idx2 = random.randint(0, len(iter_deck) - 1)
                opp_cards.append([iter_deck[idx1], iter_deck[idx2]])
                max_idx = max(idx1, idx2)
                min_idx = min(idx1, idx2)
                iter_deck.pop(max_idx)
                iter_deck.pop(min_idx)

        # Completa il board
        full_board = list(brd)
        used_in_board = set(brd)
        available = [c for c in iter_deck if c not in used_in_board]
        for _ in range(cards_needed_for_board):
            if not available:
                break
            idx = random.randint(0, len(available) - 1)
            full_board.append(available.pop(idx))

        # Valuta ogni mano
        hero_hand = evaluator.evaluate(
            [treys.Card.new(c) for c in hole],
            [treys.Card.new(c) for c in full_board]
        )

        # Trova il vincitore
        best_score = hero_hand
        winner = 0  # 0 = hero

        for i, opp in enumerate(opp_cards):
            opp_hand = evaluator.evaluate(
                [treys.Card.new(c) for c in opp],
                [treys.Card.new(c) for c in full_board]
            )
            # In Treys, score più basso = mano migliore
            if opp_hand < best_score:
                best_score = opp_hand
                winner = i + 1

        if winner == 0:
            wins += 1
            # Classifica il tipo di mano vittoriosa
            hand_class = evaluator.get_rank_class(hero_hand)
            hand_name = evaluator.class_to_string(hand_class)
            hand_types[hand_name] = hand_types.get(hand_name, 0) + 1

        # Timeout
        if runs > 100 and time.time() - start_time > timeout:
            break

    equity = wins / runs if runs > 0 else 0.0

    # Normalizza hand_types in percentuali
    for k in hand_types:
        hand_types[k] = hand_types[k] / runs

    return {
        "equity": round(equity, 4),
        "wins": wins,
        "runs": runs,
        "hand_types": hand_types,
        "timeout": time.time() - start_time > timeout,
    }


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=== Test montecarlo.py ===")

    # Test 1: AA vs range casuale heads-up
    r1 = monte_carlo(["As", "Ad"], [], num_players=2, max_runs=500)
    assert 0.7 < r1["equity"] < 0.95, f"AA dovrebbe avere equity alta, ha {r1['equity']}"
    print(f"✓ AA heads-up: equity={r1['equity']} (runs={r1['runs']})")

    # Test 2: 72o vs range casuale heads-up (dovrebbe essere bassa)
    r2 = monte_carlo(["7h", "2c"], [], num_players=2, max_runs=500)
    assert 0.2 < r2["equity"] < 0.5, f"72o dovrebbe avere equity bassa, ha {r2['equity']}"
    print(f"✓ 72o heads-up: equity={r2['equity']} (runs={r2['runs']})")

    # Test 3: Con board parziale
    r3 = monte_carlo(["As", "Ks"], ["Qs", "Js", "Ts"], num_players=2, max_runs=100)
    assert 0.8 < r3["equity"] <= 1.0, f"AKs con board KQJTs dovrebbe quasi vincere, ha {r3['equity']}"
    print(f"✓ AKs su KQJTs: equity={r3['equity']} (runs={r3['runs']})")

    # Test 4: 3 giocatori
    r4 = monte_carlo(["As", "Ad"], [], num_players=3, max_runs=500)
    assert 0.5 < r4["equity"] < 0.9, f"AA 3-way dovrebbe avere equity ~0.6-0.8, ha {r4['equity']}"
    print(f"✓ AA 3-way: equity={r4['equity']} (runs={r4['runs']})")

    # Test 5: Hand types
    assert "runs" in r1
    assert r1["runs"] > 0
    print(f"✓ Hand types: {r1['hand_types']}")

    print("\n=== Tutti i test passati! ===")
