# coding: utf-8
"""
card_map.py — Mappatura bidirezionale tra formati carta.

Formati supportati:
  - Treys:    "As", "Kd", "Th", "9c"  (rank maiuscolo, suit minuscolo)
  - Deepmind: "AS", "KD", "TH", "9C"  (tutto maiuscolo)
  - Preflop:  "KAS" (suited), "KAO" (offsuit), "AA" (pair)
  - Vision:   "Ace of SPADES", "King of DIAMONDS" (verbose)

Esempi:
    >>> to_deepmind("As")
    'AS'
    >>> to_treys("AS")
    'As'
    >>> to_preflop_key("As", "Kd")
    'KAO'
    >>> from_preflop_key("KAS")
    ('KS', 'AS')
"""

import re
from typing import Tuple

# Treys è una dipendenza runtime richiesta da PokerBotAgent (già installata).
import treys

# ============================================================
# Costanti
# ============================================================

RANKS = "23456789TJQKA"
SUITS_TREYS = "hdsc"          # Treys: h=hearts, d=diamonds, s=spades, c=clubs
SUITS_DEEPMIND = "HDSC"       # Deepmind: H=hearts, D=diamonds, S=spades, C=clubs

# Mappatura Treys → Deepmind (suit)
_TREYS_TO_DM = str.maketrans("hdsc", "HDSC")
_DM_TO_TREYS = str.maketrans("HDSC", "hdsc")

# Regex di validazione carta: rank [2-9TJQKA] + suit [HDSC]
_CARD_RE = re.compile(r"^[2-9TJQKA][HDSC]$")
# Regex di validazione chiave preflop: pair "XX" oppure "XY" + S/O
_PREFLOP_RE = re.compile(r"^([2-9TJQKA]{2})([SO])?$")


# ============================================================
# Funzioni di conversione singola carta
# ============================================================

def _normalize_card(card: str) -> str:
    """
    Normalizza una carta in formato Deepmind (2 caratteri maiuscoli),
    rigorosamente: lunghezza esatta, rank e suit validi.
    """
    card = card.strip()
    if len(card) != 2:
        raise ValueError(f"Formato carta non valido (lunghezza ≠ 2): '{card}'")
    rank = card[0].upper()
    suit = card[1].upper()
    if rank not in RANKS:
        raise ValueError(f"Rank non valido: '{rank}'")
    if suit not in SUITS_DEEPMIND:
        raise ValueError(f"Suit non valido: '{suit}'")
    return rank + suit


def to_deepmind(card: str) -> str:
    """
    Converte una carta dal formato Treys in formato Deepmind.

    >>> to_deepmind("As")
    'AS'
    >>> to_deepmind("Kd")
    'KD'
    """
    return _normalize_card(card).translate(_TREYS_TO_DM)


def to_treys(card: str) -> str:
    """
    Converte una carta dal formato Deepmind in formato Treys.

    >>> to_treys("AS")
    'As'
    >>> to_treys("KD")
    'Kd'
    """
    return _normalize_card(card).translate(_DM_TO_TREYS)


def to_treys_int(card: str) -> int:
    """
    Converte una carta (formato Treys o Deepmind) in intero Treys.

    >>> to_treys_int("As")  # Ace of Spades
    268442665
    >>> to_treys_int("AS")
    268442665
    """
    return treys.Card.new(to_treys(card))


def from_treys_int(card_int: int) -> str:
    """
    Converte un intero Treys in formato Treys string.

    >>> from_treys_int(268442665)
    'As'
    """
    return treys.Card.int_to_str(card_int)


def from_vision(verbose: str) -> str:
    """
    Converte il formato Vision ("Ace of SPADES") in formato Treys.

    >>> from_vision("Ace of SPADES")
    'As'
    >>> from_vision("King of DIAMONDS")
    'Kd'
    """
    verbose = verbose.strip()
    if not verbose:
        raise ValueError("Stringa carta vuota")
    upper = verbose.upper()
    if " OF " not in upper:
        # Formato compatto
        return to_treys(verbose)

    rank_part, suit_part = upper.split(" OF ", 1)
    rank_part = rank_part.strip()
    suit_part = suit_part.strip()
    if not rank_part or not suit_part:
        raise ValueError(f"Formato Vision non valido: '{verbose}'")

    rank_map = {
        "ACE": "A", "KING": "K", "QUEEN": "Q", "JACK": "J",
        "TEN": "T", "10": "T", "9": "9", "8": "8", "7": "7",
        "6": "6", "5": "5", "4": "4", "3": "3", "2": "2",
    }
    suit_map = {
        "HEARTS": "h", "SPADES": "s", "DIAMONDS": "d", "CLUBS": "c",
    }
    rank = rank_map.get(rank_part)
    suit = suit_map.get(suit_part)
    if rank is None:
        raise ValueError(f"Rank Vision non riconosciuto: '{rank_part}'")
    if suit is None:
        raise ValueError(f"Suit Vision non riconosciuto: '{suit_part}'")
    return rank + suit


# ============================================================
# Preflop key (deepmind format)
# ============================================================

def to_preflop_key(card1: str, card2: str) -> str:
    """
    Genera la chiave preflop equity da due carte (formato Treys o Deepmind).

    Le chiavi deepmind usano: rank1 + rank2 + S/O
      - S se suited (stesso seme)
      - O se offsuit (semi diversi)
      - Nessuna lettera se pair

    Le chiavi sono ordinate per rank decrescente (A>K>Q>...>2).

    >>> to_preflop_key("As", "Kd")  # Ace-King offsuit
    'KAO'
    >>> to_preflop_key("As", "Ks")  # Ace-King suited
    'KAS'
    >>> to_preflop_key("As", "Ad")  # Pocket Aces
    'AA'
    """
    c1 = to_deepmind(card1)
    c2 = to_deepmind(card2)
    if c1 == c2:
        raise ValueError(f"Carta duplicata: '{c1}' e '{c2}'")
    r1, s1 = c1[0], c1[1]
    r2, s2 = c2[0], c2[1]

    # Ordina per rank crescente (convenzione deepmind: più basso prima)
    i1, i2 = RANKS.index(r1), RANKS.index(r2)
    if i1 > i2:
        r1, r2 = r2, r1
        s1, s2 = s2, s1
    elif i1 == i2:
        # Pair — nessuna lettera
        return r1 + r2

    if s1 == s2:
        return r1 + r2 + "S"
    else:
        return r1 + r2 + "O"


def from_preflop_key(key: str) -> Tuple[str, str]:
    """
    Converte una chiave preflop in due carte Deepmind.

    >>> from_preflop_key("KAS")
    ('KS', 'AS')
    >>> from_preflop_key("KAO")
    ('KS', 'AD')
    >>> from_preflop_key("AA")
    ('AS', 'AD')
    """
    key = key.strip().upper()
    m = _PREFLOP_RE.match(key)
    if not m:
        raise ValueError(f"Chiave preflop non valida: '{key}'")
    r1, r2 = m.group(1)[0], m.group(1)[1]
    stype = m.group(2)

    if r1 == r2:
        # Pair — non deve avere suffisso S/O (mani same-suit impossibili)
        if stype is not None:
            raise ValueError(f"Chiave pair con suffisso non valida: '{key}'")
        return (r1 + "S", r1 + "D")

    # Non-pair: imponiamo ordine canonico (rank1 <= rank2, più basso prima)
    if RANKS.index(r1) > RANKS.index(r2):
        raise ValueError(f"Chiave non canonica (rank1 > rank2): '{key}'")

    if stype == "S":
        return (r1 + "S", r2 + "S")
    elif stype == "O":
        return (r1 + "S", r2 + "D")
    raise ValueError(f"Chiave preflop non valida: '{key}'")


# ============================================================
# Conversione mazzo completo
# ============================================================

def treys_deck_to_deepmind() -> list:
    """
    Restituisce il mazzo completo nel formato Deepmind (52 stringhe).
    """
    deck = []
    for rank in RANKS:
        for suit in SUITS_DEEPMIND:
            deck.append(rank + suit)
    return deck


def deepmind_deck_to_treys() -> list:
    """
    Restituisce il mazzo completo nel formato Treys (52 stringhe).
    """
    return [to_treys(c) for c in treys_deck_to_deepmind()]


# ============================================================
# Validazione
# ============================================================

def is_valid_card(card: str) -> bool:
    """Controlla se una stringa è una carta valida (qualsiasi formato)."""
    try:
        to_deepmind(card)
        return True
    except ValueError:
        return False


def is_valid_preflop_key(key: str) -> bool:
    """Controlla se una stringa è una chiave preflop valida."""
    try:
        from_preflop_key(key)
        return True
    except ValueError:
        return False


# ============================================================
# Test rapido (solo se eseguito direttamente)
# ============================================================

if __name__ == "__main__":
    print("=== Test card_map.py ===")

    # Test conversione singola
    assert to_deepmind("As") == "AS"
    assert to_deepmind("Kd") == "KD"
    assert to_treys("AS") == "As"
    assert to_treys("KD") == "Kd"
    print("✓ Conversione singola OK")

    # Test preflop key (ordine rank crescente: più basso prima)
    assert to_preflop_key("As", "Kd") == "KAO"
    assert to_preflop_key("As", "Ks") == "KAS"
    assert to_preflop_key("As", "Ad") == "AA"
    assert to_preflop_key("Ks", "Ad") == "KAO"  # Ordine crescente
    print("✓ Preflop key OK")

    # Test from_preflop_key
    # La prima carta corrisponde al primo rank della chiave ("K" prima di "A")
    assert from_preflop_key("KAS") == ("KS", "AS")
    assert from_preflop_key("KAO") == ("KS", "AD")
    assert from_preflop_key("AA") == ("AS", "AD")
    # Round-trip da chiave
    for k in ["AA", "QQ", "22", "KAS", "KAO", "9KS", "7TO"]:
        c1, c2 = from_preflop_key(k)
        assert to_preflop_key(c1, c2) == k, f"Round-trip chiave fallito per {k}"
    print("✓ From preflop key (incl. round-trip) OK")

    # Test round-trip carta
    for card in ["As", "Kd", "Th", "9c", "2s", "Ad"]:
        assert to_treys(to_deepmind(card)) == card, f"Round-trip fallito per {card}"
    print("✓ Round-trip Treys↔Deepmind OK")

    # Test mazzo
    deck_dm = treys_deck_to_deepmind()
    deck_tr = deepmind_deck_to_treys()
    assert len(deck_dm) == 52
    assert len(deck_tr) == 52
    assert len(set(deck_dm)) == 52
    assert len(set(deck_tr)) == 52
    print("✓ Mazzo completo 52 carte OK")

    # Test validazione
    assert is_valid_card("As")
    assert is_valid_card("KD")
    assert not is_valid_card("Xx")
    assert not is_valid_card("Asx")          # B5: lunghezza > 2
    assert not is_valid_card("A")            # B5: lunghezza < 2
    assert is_valid_preflop_key("KAS")       # canonico (K < A)
    assert is_valid_preflop_key("AA")        # pair
    assert not is_valid_preflop_key("AKS")   # non canonico (A > K)
    assert not is_valid_preflop_key("XYZ")   # B3: rank non validi
    assert not is_valid_preflop_key("KA")    # B3: non canonica / senza S|O
    assert not is_valid_preflop_key("AAS")   # B2: pair con suffisso
    assert not is_valid_preflop_key("1AS")   # B3: rank '1' non valido
    print("✓ Validazione OK")

    # Test from_vision
    assert from_vision("Ace of SPADES") == "As"
    assert from_vision("King of DIAMONDS") == "Kd"
    assert from_vision("Ten of HEARTS") == "Th"   # B4: TEN ora mappato
    try:
        from_vision("X of SPADES")
        raise AssertionError("Doveva sollevare ValueError (rank X)")
    except ValueError:
        pass
    print("✓ From vision OK")

    # Test duplicati (B1)
    try:
        to_preflop_key("As", "As")
        raise AssertionError("Doveva sollevare ValueError (carta duplicata)")
    except ValueError:
        pass
    print("✓ Rilevamento carta duplicata OK")

    print("\n=== Tutti i test passati! ===")
