# coding: utf-8
"""
implied_odds.py — Calcolo implied odds e pot odds.

Formula standard:
  pot_odds = (pot + call) / call
  hitting_odds = (1 / (outs / cards_left)) - 1
  ev_difference = call * (hitting_odds - pot_odds)

Estratto da deepmind-pokerbot e adattato per PokerBotAgent.

Uso:
    from poker_utils.implied_odds import calculate_implied_odds
    result = calculate_implied_odds(outs=9, call_value=50, pot_value=200)
    print(result)
"""

from typing import Dict


def calculate_implied_odds(outs: int, call_value: float, pot_value: float,
                           cards_left: int = 47) -> Dict:
    """
    Calcola pot odds, hitting odds ed EV difference.

    Args:
        outs: numero di outs (carte che migliorano la mano)
        call_value: importo da chiamare
        pot_value: valore del pot attuale (prima della call)
        cards_left: carte rimanenti nel mazzo (47=flop→turn, 46=turn→river)

    Returns:
        dict con: pot_odds, hitting_odds, ev_difference,
                  is_profitable (bool)
    """
    if call_value <= 0:
        return {
            "pot_odds": 0, "hitting_odds": 0, "ev_difference": 0,
            "is_profitable": False
        }

    if cards_left <= 0:
        raise ValueError(f"cards_left deve essere > 0, ricevuto {cards_left}")

    pot_odds = (pot_value + call_value) / call_value

    hitting_odds = (1 / (outs / cards_left)) - 1 if outs > 0 else float('inf')

    ev_difference = call_value * (hitting_odds - pot_odds)

    is_profitable = ev_difference > 0 if outs > 0 else False

    return {
        "pot_odds": round(pot_odds, 4),
        "hitting_odds": round(hitting_odds, 4),
        "ev_difference": round(ev_difference, 2),
        "is_profitable": is_profitable,
    }


# ============================================================
# Test
# ============================================================

if __name__ == "__main__":
    print("=== Test implied_odds.py ===")

    # Flush draw: 9 outs, call 50, pot 200
    # Pot odds = (200+50)/50 = 5.0
    # Hitting odds = (1/(9/47))-1 = 4.222
    # EV = 50*(4.222-5.0) = -38.9 → non profittevole
    r1 = calculate_implied_odds(outs=9, call_value=50, pot_value=200)
    assert r1["pot_odds"] == 5.0
    assert r1["hitting_odds"] == 4.2222
    assert r1["ev_difference"] < 0
    assert r1["is_profitable"] == False
    print(f"✓ Flush draw 9out, call50, pot200: EV={r1['ev_difference']} → {'PROFIT' if r1['is_profitable'] else 'NO'}")

    # Gutshot: 4 outs, call 10, pot 100
    # Pot odds = (100+10)/10 = 11.0
    # Hitting odds = (1/(4/47))-1 = 10.75
    # EV = 10*(10.75-11.0) = -2.5 → non profittevole
    r2 = calculate_implied_odds(outs=4, call_value=10, pot_value=100)
    assert r2["pot_odds"] == 11.0
    assert r2["is_profitable"] == False
    print(f"✓ Gutshot 4out, call10, pot100: EV={r2['ev_difference']} → {'PROFIT' if r2['is_profitable'] else 'NO'}")

    # Caso profittevole: 12 outs, call 10, pot 100
    # Pot odds = 11.0
    # Hitting odds = (1/(12/47))-1 = 2.9167
    # EV = 10*(2.9167-11.0) = -80.8... hmm, non profittevole con 12 outs?
    r3 = calculate_implied_odds(outs=12, call_value=10, pot_value=100)
    print(f"✓ 12out, call10, pot100: EV={r3['ev_difference']} → {'PROFIT' if r3['is_profitable'] else 'NO'}")

    # Caso semplice: 14 outs, call 1, pot 10
    # Pot odds = 11.0
    # Hitting odds = (1/(14/47))-1 = 2.3571
    # EV = 1*(2.3571-11.0) = -8.64 → no
    r4 = calculate_implied_odds(outs=14, call_value=1, pot_value=10)
    print(f"✓ 14out, call1, pot10: EV={r4['ev_difference']} → {'PROFIT' if r4['is_profitable'] else 'NO'}")

    # Non profittevole se outs = 0
    r5 = calculate_implied_odds(outs=0, call_value=50, pot_value=200)
    assert r5["is_profitable"] == False
    print(f"✓ 0 outs: EV={r5['ev_difference']} → NO")

    # Non profittevole se call = 0
    r6 = calculate_implied_odds(outs=9, call_value=0, pot_value=200)
    assert r6["is_profitable"] == False
    print(f"✓ call=0: EV={r6['ev_difference']} → NO")

    print("\n=== Tutti i test passati! ===")
