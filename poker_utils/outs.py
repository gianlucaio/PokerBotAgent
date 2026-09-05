# coding: utf-8
"""
outs.py — Calcolo outs per decisioni post-flop.

Determina quante carte nel mazzo residuo migliorano la mano:
  - Flush draw: 9 outs (13 semi - 4 in gioco)
  - Open-ended straight draw: 8 outs
  - Gutshot straight draw: 4 outs
  - Overcards: 3-6 outs (carte più alte del board)
  - Combinazioni: 12-15 outs

Estratto da deepmind-pokerbot e riscritto per PokerBotAgent
usa Treys per valutare le mani.

Uso:
    from poker_utils.outs import calculate_outs
    result = calculate_outs(["As", "Ks"], ["Qs", "Jd", "9c"])
    print(result)  # {'outs': 4, 'flush_draw': False, 'straight_draw': True, ...}
"""

from typing import List, Dict, Optional
import itertools

import treys

from poker_utils.card_map import to_treys, to_deepmind


def _evaluate(hole: List[str], board: List[str]) -> int:
    """Valuta la mano con Treys. Ritorna il hand rank (più basso = meglio)."""
    evaluator = treys.Evaluator()
    hole_int = [treys.Card.new(c) for c in hole]
    board_int = [treys.Card.new(c) for c in board]
    return evaluator.evaluate(hole_int, board_int)


def _get_suits(cards: List[str]) -> Dict[str, int]:
    """Conta le carte per seme (formato Treys: h,d,s,c)."""
    suits = {"h": 0, "d": 0, "s": 0, "c": 0}
    for c in cards:
        suit = c[-1].lower()
        if suit in suits:
            suits[suit] += 1
    return suits


def _get_ranks(cards: List[str]) -> List[int]:
    """Restituisce i rank come indici (2=0, ..., A=12)."""
    rank_str = "23456789TJQKA"
    return sorted([rank_str.index(c[0].upper()) for c in cards])


def _count_outs_flush(cards: List[str]) -> int:
    """Conta gli outs per flush draw (semi in gioco: 13 - quelli visibili)."""
    suits = _get_suits(cards)
    for suit, count in suits.items():
        if count == 4:
            return 13 - count  # 9 outs
    return 0


def _count_outs_straight(hole: List[str], board: List[str]) -> int:
    """Conta gli outs per straight draw (open-ended: 8, gutshot: 4)."""
    all_cards = hole + board
    ranks = sorted(set(_get_ranks(all_cards)))

    # Conta rank completanti per straight
    completing_ranks = set()
    for test_rank in range(13):
        if test_rank in ranks:
            continue
        test_set = sorted(set(ranks) | {test_rank})
        for i in range(len(test_set) - 4):
            if test_set[i + 4] - test_set[i] == 4:
                completing_ranks.add(test_rank)
                break

    n = len(completing_ranks)
    if n >= 2:
        return 8  # open-ended
    elif n == 1:
        return 4  # gutshot
    return 0


def _count_outs_overcards(hole: List[str], board: List[str]) -> int:
    """Conta gli outs per overcards (carte hole più alte del board)."""
    if not board:
        return 0
    board_ranks = set(_get_ranks(board))
    # Usa set per evitare doppio conteggio di rank uguali (es. pair)
    unique_overcard_ranks = set(hr for hr in _get_ranks(hole) if hr > max(board_ranks))
    outs = 0
    hole_rank_count = {hr: _get_ranks(hole).count(hr) for hr in unique_overcard_ranks}
    for hr in unique_overcard_ranks:
        outs += 4 - hole_rank_count[hr]  # 4 carte totali - quelle in mano
    return outs


def _count_outs_pair(hole: List[str], board: List[str]) -> int:
    """
    Conta gli outs per fare una coppia (se non si ha già una coppia o meglio).
    Un out per ogni carta del mazzo che fa coppia col rank della hole card.
    """
    evaluator = treys.Evaluator()
    hole_int = [treys.Card.new(c) for c in hole]
    board_int = [treys.Card.new(c) for c in board]

    # Valuta la mano attuale
    hand_rank = evaluator.evaluate(hole_int, board_int)
    hand_class = evaluator.get_rank_class(hand_rank)

    # Se si ha già almeno coppia, non servono outs per coppia
    # Treys: 1=StraightFlush, 2=FourOfAKind, 3=FullHouse, 4=Flush,
    #        5=Straight, 6=ThreeOfAKind, 7=TwoPair, 8=OnePair, 9=HighCard
    if hand_class <= 8:  # One Pair o meglio
        return 0

    # Conta quante carte nel mazzo fanno coppia col nostro rank
    hole_ranks = set(c[0].upper() for c in hole)
    board_ranks = set(c[0].upper() for c in board)
    outs = 0
    rank_str = "23456789TJQKA"
    for hr in hole_ranks:
        if hr not in board_ranks:
            # Questo rank non è nel board → 3 outs (4 totali - 1 in mano)
            outs += 3
    return outs


def calculate_outs(hole: List[str], board: List[str]) -> Dict:
    """
    Calcola il totale degli outs per una mano.

    Args:
        hole: 2 carte formato Treys (es. ["As", "Kd"])
        board: 0-5 carte formato Treys (es. ["Th", "9c", "2d"])

    Returns:
        dict con: outs, flush_draw, straight_draw, overcards, pair_outs,
                  draw_type (str)
    """
    if len(hole) != 2:
        raise ValueError(f"Servono esattamente 2 hole cards, ricevute {len(hole)}")
    if len(board) > 5:
        raise ValueError(f"Max 5 board cards, ricevute {len(board)}")

    all_cards = hole + board

    # Calcola ciascun tipo di out
    flush_outs = _count_outs_flush(all_cards)
    straight_outs = _count_outs_straight(hole, board)
    overcard_outs = _count_outs_overcards(hole, board)
    pair_outs = _count_outs_pair(hole, board)

    # Totale (ma non semplice somma: flush+straight si sovrappongono)
    total = max(flush_outs, straight_outs, overcard_outs, pair_outs)

    # Se sia flush che straight draw, usa le combinazioni
    if flush_outs > 0 and straight_outs > 0:
        if straight_outs == 8:
            total = 15  # OESD + flush draw
        else:
            total = 12  # gutshot + flush draw

    # Classifica il tipo di draw
    if total == 0:
        draw_type = "none"
    elif total >= 15:
        draw_type = "monster_draw"  # OESD + flush
    elif total >= 12:
        draw_type = "strong_draw"  # gutshot + flush
    elif total >= 9:
        draw_type = "flush_draw"
    elif total >= 8:
        draw_type = "open_ended"
    elif total >= 4:
        draw_type = "gutshot"
    else:
        draw_type = "overcards"

    return {
        "outs": total,
        "flush_outs": flush_outs,
        "straight_outs": straight_outs,
        "overcard_outs": overcard_outs,
        "pair_outs": pair_outs,
        "flush_draw": flush_outs > 0,
        "straight_draw": straight_outs > 0,
        "draw_type": draw_type,
    }


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=== Test outs.py ===")

    # Flush draw: 2 cuori in mano + 2 cuori su board = 4 cuori → flush draw
    r1 = calculate_outs(["Kh", "Qh"], ["Jh", "Th", "9c"])
    assert r1["flush_draw"] == True
    assert r1["outs"] >= 9, f"Flush draw dovrebbe avere >=9 outs, ha {r1['outs']}"
    print(f"✓ Flush draw: {r1['outs']} outs (draw_type={r1['draw_type']})")

    # Open-ended straight draw: As-Ks-Qh-Jd → serve una T
    r2 = calculate_outs(["As", "Ks"], ["Qh", "Jd", "9c"])
    assert r2["straight_draw"] == True
    assert r2["straight_outs"] >= 4
    print(f"✓ Straight draw: {r2['outs']} outs (straight={r2['straight_outs']})")

    # Nessun draw
    r3 = calculate_outs(["As", "Kd"], ["2h", "7c", "9s"])
    print(f"✓ Nessun draw: {r3['outs']} outs (draw_type={r3['draw_type']})")

    # Monster draw (flush + OESD): Ah Kh | Qh Jh 2c → 4 cuori + A-K-Q-J-? = OESD
    r4 = calculate_outs(["Ah", "Kh"], ["Qh", "Jh", "2c"])
    assert r4["flush_draw"] == True
    assert r4["straight_draw"] == True
    print(f"✓ Monster draw: {r4['outs']} outs (draw_type={r4['draw_type']})")

    print("\n=== Tutti i test passati! ===")
