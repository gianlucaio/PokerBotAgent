# coding: utf-8
"""
straight_draw.py — Rilevamento straight draw.

Determina se una collezione di carte contiene uno straight draw
(4 o 5 carte consecutive, incluse le lacune per gutshot/open-ended).

Estratto da deepmind-pokerbot e adattato per PokerBotAgent.

Uso:
    >>> is_straight_draw("As", "Ks", "Qh", "Jd")
    True
    >>> is_straight_draw("As", "Ks", "Qh", "Td")
    True
    >>> is_straight_draw("As", "Ks", "Qh", "9d")
    False
"""

from typing import List

# Costanti
RANKS = "23456789TJQKA"
RANK_TO_IDX = {r: i for i, r in enumerate(RANKS)}


def _rank_index(card: str) -> int:
    """Estrae l'indice del rank da una carta (formato Treys 'As' o Deepmind 'AS')."""
    rank = card.strip()[0].upper()
    idx = RANK_TO_IDX.get(rank)
    if idx is None:
        raise ValueError(f"Rank non valido: '{rank}'")
    return idx


def is_straight_draw(*cards: str) -> bool:
    """
    Controlla se le carte (hole cards + board) formano uno straight draw.

    Supporta qualsiasi numero di carte (da 2 a 7).
    Rileva: gutshot (4 consecutive con 1 buco), open-ended (5 consecutive),
    e tutte le combinazioni.

    Args:
        *cards: carte in formato Treys ("As") o Deepmind ("AS")

    Returns:
        True se c'è uno straight draw, False altrimenti.

    >>> is_straight_draw("As", "Ks", "Qh", "Jd")
    True
    >>> is_straight_draw("As", "Ks", "Qh", "9d")
    False
    >>> is_straight_draw("As", "Ks", "Qh", "Jd", "Td")
    True
    """
    if len(cards) < 2:
        return False

    # Estrai indici rank unici
    indices = sorted(set(_rank_index(c) for c in cards))

    if len(indices) < 4:
        return False

    # Controlla se ci sono 4+ indici consecutivi
    # (con la particularità dell'As che può valere 1 per A-2-3-4-5)
    for start in range(len(indices)):
        consecutive = 1
        for i in range(start + 1, len(indices)):
            if indices[i] == indices[start] + consecutive:
                consecutive += 1
            elif consecutive >= 4:
                break
        if consecutive >= 4:
            return True

    # Controlla se c'è un gutshot (4 consecutive con 1 buco)
    # Es: 2-3-4-6 (manca il 5), 3-4-5-7 (manca il 6)
    if len(indices) >= 4:
        for i in range(len(indices) - 3):
            # Controlla se 4 carte su 5 consecutive (con 1 buco)
            gap = indices[i + 3] - indices[i]
            if gap == 4:  # 4 buchi in 4 carte = 3 consecutive + 1 gap
                return True

    # Particularità: As basso (A-2-3-4-5 wheel straight)
    # Controlla se 4+ delle 5 carte del wheel {A(1),2,3,4,5} sono in mano
    if 12 in indices:  # Ace presente
        wheel = {12, 0, 1, 2, 3}  # A, 2, 3, 4, 5 (A può valere 1)
        has_wheel = len(wheel & set(indices))
        if has_wheel >= 4:
            return True

    return False


def straight_draw_info(*cards: str) -> dict:
    """
    Info dettagliata sullo straight draw.

    Returns:
        dict con: is_draw (bool), outs (int), draw_type (str)

    >>> straight_draw_info("As", "Ks", "Qh", "Jd")
    {'is_draw': True, 'outs': 4, 'draw_type': 'open_ended'}
    """
    if not is_straight_draw(*cards):
        return {"is_draw": False, "outs": 0, "draw_type": "none"}

    indices = sorted(set(_rank_index(c) for c in cards))

    # Carte fisiche di ogni rank già in gioco (per ridurre gli outs)
    rank_in_play: dict = {}
    for c in cards:
        r = _rank_index(c)
        rank_in_play[r] = rank_in_play.get(r, 0) + 1

    hand_ranks = set(indices)

    # Conta gli outs fisici (carte che completano lo straight).
    # Un rank che completa fornisce fino a 4 carte fisiche, meno quelle
    # già in gioco con quel rank.
    outs = 0
    completing_ranks = set()

    for test_rank in range(13):
        if test_rank in hand_ranks:
            continue
        test_set = sorted(hand_ranks | {test_rank})
        # Controlla se 5 consecutive
        for i in range(len(test_set) - 4):
            if test_set[i + 4] - test_set[i] == 4:
                outs += 4 - rank_in_play.get(test_rank, 0)
                completing_ranks.add(test_rank)
                break

    # Classifica il tipo di draw in base al numero di rank completanti
    n_ranks = len(completing_ranks)
    if n_ranks >= 2:
        draw_type = "open_ended" if outs >= 8 else "double_gutshot"
    elif n_ranks == 1:
        draw_type = "gutshot"
    else:
        draw_type = "inside"

    return {"is_draw": True, "outs": outs, "draw_type": draw_type}


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=== Test straight_draw.py ===")

    # Open-ended straight draw (OESD): As Ks Qh Jd → serve una T
    assert is_straight_draw("As", "Ks", "Qh", "Jd") == True
    print("✓ As-Ks-Qh-Jd → OESD OK")

    # Non straight draw
    assert is_straight_draw("As", "Ks", "Qh", "9d") == False
    print("✓ As-Ks-Qh-9d → NO draw OK")

    # Gutshot: As Ks Qh Td → serve una J
    assert is_straight_draw("As", "Ks", "Qh", "Td") == True
    print("✓ As-Ks-Qh-Td → gutshot OK")

    # 5 carte con straight
    assert is_straight_draw("As", "Ks", "Qh", "Jd", "Td") == True
    print("✓ As-Ks-Qh-Jd-Td → straight OK")

    # Pochi draw
    assert is_straight_draw("As", "Kd") == False
    print("✓ As-Kd → 2 carte, no draw OK")

    # Info dettagliata
    info = straight_draw_info("As", "Ks", "Qh", "Jd")
    assert info["is_draw"] == True
    assert info["outs"] > 0
    print(f"✓ Info: {info}")

    print("\n=== Tutti i test passati! ===")
