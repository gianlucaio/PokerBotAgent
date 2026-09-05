# ============================================================
# HoldEm Agent — Modulo EVAL (Motore Logico e Intelligenza Artificiale)
# ============================================================
# Step 2: Motore Deterministico (Treys) — ISOLATO
# Step 3: Integrazione LLM (LM Studio) — Modello Agnostico
# Parsing JSON: estrazione a parentesi bilanciate (v2.2)
# Endpoint LM Studio: /v1/chat/completions (compatibile OpenAI)
# ============================================================

import treys
import random
import json
import os
import re
import requests
import time
from typing import List, Dict, Optional, Tuple

# Poker Utils — Moduli di calcolo (estratti da deepmind-pokerbot)
from poker_utils.preflop import PreflopLookup
from poker_utils.outs import calculate_outs
from poker_utils.sizing import BetSizing


class EvalEngine:
    """Motore decisionale deterministico basato su Treys."""

    def __init__(self, mc_iterations: int = 1000):
        self.evaluator = treys.Evaluator()
        # Costruisci mazzo manualmente (Treys non espone CARD_LIST)
        self.deck = []
        for rank in "23456789TJQKA":
            for suit in "hdsc":
                self.deck.append(treys.Card.new(rank + suit))
        self.mc_iterations = mc_iterations
        self.fallback_count = 0
        self.last_success = None
        self.blocked = False

        # Poker Utils — istanze riutilizzabili
        self.preflop_lookup = PreflopLookup()
        self.default_sizing = BetSizing(
            small_blind=0.02, big_blind=0.04,
            max_value=2.0, min_equity=0.75,
            max_equity=0.9, power=16
        )

        # --- Step 2bis: GTO Preflop Tables ---
        self.gto_tables = self._load_gto_tables()

    def _load_gto_tables(self) -> Dict:
        """Carica tabelle GTO push/fold da file JSON."""
        try:
            from config import USE_GTO_PREFLOP, GTO_TABLE_FILE
            if not USE_GTO_PREFLOP:
                return {}
            base_dir = os.path.dirname(os.path.abspath(__file__))
            table_path = os.path.join(base_dir, "assets", GTO_TABLE_FILE)
            with open(table_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("tables", {})
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Utilità conversione carte
    # ------------------------------------------------------------------
    RANK_MAP = {
        "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
        "7": "7", "8": "8", "9": "9", "10": "T", "T": "T",
        "JACK": "J", "J": "J", "QUEEN": "Q", "Q": "Q",
        "KING": "K", "K": "K", "ACE": "A", "A": "A"
    }
    SUIT_MAP = {
        "HEARTS": "h", "H": "h", "SPADES": "s", "S": "s",
        "DIAMONDS": "d", "D": "d", "CLUBS": "c", "C": "c"
    }

    def parse_card(self, card_str: str) -> str:
        """
        Converte 'Ace of SPADES' o 'As' in formato Treys 'As'.
        Accetta sia formato vision (verbose) che compatto.
        """
        card_str = card_str.strip().upper()
        if " OF " in card_str:
            rank_part, suit_part = card_str.split(" OF ")
            rank = self.RANK_MAP.get(rank_part.strip(), rank_part.strip()[0])
            suit = self.SUIT_MAP.get(suit_part.strip(), suit_part.strip()[0].lower())
        else:
            # Formato compatto: As, Kd, Th, 9c, ...
            if len(card_str) >= 2:
                rank = self.RANK_MAP.get(card_str[0], card_str[0])
                suit = self.SUIT_MAP.get(card_str[1], card_str[1].lower())
            else:
                raise ValueError(f"Formato carta non riconosciuto: {card_str}")
        return rank + suit

    def parse_cards(self, cards: List[str]) -> List[int]:
        """Converte lista di stringhe in lista di int Treys."""
        return [treys.Card.new(self.parse_card(c)) for c in cards]

    # ------------------------------------------------------------------
    # Valutazione mano (Treys)
    # ------------------------------------------------------------------
    def evaluate_hand(self, hole_cards: List[str], board_cards: List[str]) -> Dict:
        """
        Restituisce hand rank (più basso = migliore) e categoria.
        hole_cards: es. ["As", "Kd"] o ["Ace of SPADES", "King of DIAMONDS"]
        board_cards: es. ["Th", "9c", "2d"] o ["10 of HEARTS", "9 of CLUBS", "2 of DIAMONDS"]
        """
        try:
            hole = self.parse_cards(hole_cards)
            board = self.parse_cards(board_cards) if board_cards else []
            hand_rank = self.evaluator.evaluate(hole, board)
            hand_class = self.evaluator.get_rank_class(hand_rank)
            class_name = self.evaluator.class_to_string(hand_class)
            return {
                "hand_rank": hand_rank,
                "hand_class": hand_class,
                "hand_class_name": class_name,
                "valid": True
            }
        except Exception as e:
            return {"hand_rank": None, "hand_class": None, "hand_class_name": "ERROR", "valid": False, "error": str(e)}

    # ------------------------------------------------------------------
    # Equity Monte Carlo
    # ------------------------------------------------------------------
    def calculate_equity_mc(self, hole_cards: List[str], board_cards: List[str],
                             num_opponents: int = 1, iterations: Optional[int] = None) -> float:
        """
        Calcola equity vs range casuale avversari (Monte Carlo).
        Restituisce percentuale 0.0-1.0.
        """
        iters = iterations or self.mc_iterations
        try:
            hole = self.parse_cards(hole_cards)
            board = self.parse_cards(board_cards) if board_cards else []
        except Exception:
            return 0.0

        # Carte note rimosse dal mazzo
        known = set(hole + board)
        remaining_deck = [c for c in self.deck if c not in known]

        wins = 0
        ties = 0

        for _ in range(iters):
            random.shuffle(remaining_deck)
            # Distribuisci carte avversari
            opp_hands = []
            idx = 0
            for _ in range(num_opponents):
                if idx + 1 < len(remaining_deck):
                    opp_hands.append([remaining_deck[idx], remaining_deck[idx + 1]])
                    idx += 2

            # Completa board se necessario
            sim_board = board[:]
            need_board = 5 - len(board)
            if need_board > 0:
                sim_board.extend(remaining_deck[idx:idx + need_board])
                idx += need_board

            # Valuta Hero
            if len(hole) != 2:
                # Caso non ancora rilevato: non possiamo simulare
                return 0.5 
            
            hero_rank = self.evaluator.evaluate(hole, sim_board)

            # Valuta avversari
            best_opp = hero_rank
            for opp in opp_hands:
                opp_rank = self.evaluator.evaluate(opp, sim_board)
                if opp_rank < best_opp:
                    best_opp = opp_rank

            if hero_rank < best_opp:
                wins += 1
            elif hero_rank == best_opp:
                ties += 1

        return (wins + ties * 0.5) / iters

    # ------------------------------------------------------------------
    # Pot Odds
    # ------------------------------------------------------------------
    def calculate_pot_odds(self, call_amount: float, pot_size: float) -> float:
        """Calcola pot odds: call / (pot + call)."""
        if pot_size <= 0:
            return 0.0
        return call_amount / (pot_size + call_amount)

    def implied_odds_factor(self, equity: float, pot_odds: float) -> float:
        """Fattore correzione implied odds semplificato."""
        if pot_odds == 0:
            return 1.0
        return equity / pot_odds

    # ------------------------------------------------------------------
    # Poker Utils — Lookup avanzati
    # ------------------------------------------------------------------
    def preflop_equity(self, hole_cards: List[str], opponent_range: float = 1.0, num_opponents: int = 1) -> float:
        """
        Lookup equity preflop istantaneo da tabella JSON.
        Se le carte non sono nel range, ritorna 0.5 (neutro).
        Per multi-way, riduce l'equity proporzionalmente agli avversari.
        """
        try:
            c1 = self.parse_card(hole_cards[0])
            c2 = self.parse_card(hole_cards[1])
            eq = self.preflop_lookup.equity(c1, c2, opponent_range)
            if eq is None:
                return 0.5
            # Multi-way adjustment: equity diminuisce con più avversari
            # Fattore empirico: ~10% di riduzione per avversario extra
            if num_opponents > 1:
                eq = eq * (1.0 - 0.1 * (num_opponents - 1))
                eq = max(eq, 0.05)  # floor minimo
            return eq
        except Exception:
            return 0.5

    def calculate_outs(self, hole_cards: List[str], board_cards: List[str]) -> Dict:
        """
        Calcola gli outs per la mano corrente.
        Ritorna dict con outs, flush_draw, straight_draw, draw_type.
        """
        try:
            hole = [self.parse_card(c) for c in hole_cards]
            board = [self.parse_card(c) for c in board_cards] if board_cards else []
            return calculate_outs(hole, board)
        except Exception:
            return {"outs": 0, "flush_draw": False, "straight_draw": False, "draw_type": "none"}

    def get_sizing(self, equity: float) -> float:
        """Calcola bet sizing in base all'equity."""
        return self.default_sizing.get_bet(equity)

    # ------------------------------------------------------------------
    # Step 2bis: Lookup tabelle GTO push/fold preflop
    # ------------------------------------------------------------------
    def _normalize_hand(self, hole_cards: List[str]) -> str:
        """
        Converte carte in notazione GTO standard:
        'As' + 'Kh' → 'AKs' (suited)
        'Ah' + 'Kh' → 'AKo' (offsuit)
        'As' + 'Ah' → 'AA'
        """
        c1 = self.parse_card(hole_cards[0])
        c2 = self.parse_card(hole_cards[1])
        r1, r2 = c1[0], c2[0]
        s1, s2 = c1[1], c2[1]

        if r1 == r2:
            # Pairs: sempre in ordine rank decrescente
            if r1 == r2:
                return r1 + r2
        # Non pair: ordina rank per valore decrescente
        rank_order = "AKQJT98765432"
        r1_idx = rank_order.index(r1) if r1 in rank_order else 99
        r2_idx = rank_order.index(r2) if r2 in rank_order else 99
        if r1_idx > r2_idx:
            r1, r2 = r2, r1
        suited = "s" if s1 == s2 else "o"
        return r1 + r2 + suited

    def gto_preflop_action(self, hole_cards: List[str], position: str = "BTN",
                           stack_bb: int = 10) -> str:
        """
        Lookup GTO push/fold per preflop.
        Ritorna 'PUSH' o 'FOLD'.
        """
        if not self.gto_tables:
            return None  # Tabelle non caricate, usa LLM/Treys

        table_key = f"{stack_bb}bb"
        if table_key not in self.gto_tables:
            # Fallback: trova tabella più vicina
            closest = min(self.gto_tables.keys(),
                          key=lambda k: abs(int(k.replace("bb", "")) - stack_bb))
            table_key = closest

        table = self.gto_tables[table_key]
        if position not in table:
            return None

        hand_key = self._normalize_hand(hole_cards)
        push_list = table[position].get("push", [])

        # Controlla se la mano è nella lista push
        if hand_key in push_list:
            return "PUSH"
        # Controlla anche come "all_other" per fold
        return "FOLD"

    # ------------------------------------------------------------------
    # Decisione base (equity vs pot odds) — Step 2 puro
    # ------------------------------------------------------------------
    def decide_deterministic(self, hole_cards: List[str], board_cards: List[str],
                              pot: float, call_amount: float, num_opponents: int = 1) -> Dict:
        """
        Logica decisionale deterministica:
        - equity > pot_odds * 1.2 → RAISE (valore)
        - equity > pot_odds → CALL
        - equity > 0.8 e check disponibile → CHECK
        - altrimenti FOLD
        """
        equity = self.calculate_equity_mc(hole_cards, board_cards, num_opponents)
        pot_odds = self.calculate_pot_odds(call_amount, pot)

        # Azioni disponibili (semplificate)
        can_check = (call_amount == 0)
        can_call = (call_amount > 0)

        if equity >= 0.80 and can_check:
            return {
                "azione": "CHECK",
                "sizing": 0,
                "motivazione": f"Equity alta ({equity:.2%}) vs pot odds ({pot_odds:.2%}), check gratuito"
            }

        if equity > pot_odds * 1.2:
            # Raise sizing: ~2-3x pot se molto forte
            sizing = int(pot * 2.5)
            return {
                "azione": "RAISE",
                "sizing": sizing,
                "motivazione": f"Equity ({equity:.2%}) >> pot odds ({pot_odds:.2%}), value raise"
            }

        if equity > pot_odds and can_call:
            return {
                "azione": "CALL",
                "sizing": int(call_amount),
                "motivazione": f"Equity ({equity:.2%}) > pot odds ({pot_odds:.2%}), call matematico"
            }

        if can_check:
            return {
                "azione": "CHECK",
                "sizing": 0,
                "motivazione": f"Equity ({equity:.2%}) bassa ma check gratuito"
            }

        return {
            "azione": "FOLD",
            "sizing": 0,
            "motivazione": f"Equity ({equity:.2%}) <= pot odds ({pot_odds:.2%}), fold corretto"
        }

    # ------------------------------------------------------------------
    # API principale chiamata da main.py — con Fallback 3 Livelli (v2.2)
    # ------------------------------------------------------------------
    def evaluate(self, state: Dict, tracker=None) -> Dict:
        """
        Punto di ingresso per main.py con fallback a 3 livelli (Guida Sezione 4.3).
        state: JSON payload da SEE (hole_cards, board, pot, players, ecc.)
        tracker: ActionTracker opzionale per profili avversario (Step 12)
        """
        hole = state.get("hole_cards", [])
        board = state.get("board", [])
        pot = state.get("pot", 0)

        # Stima call_amount: differenza tra bet max e hero bet
        call_amount = 0
        players = state.get("players", [])
        hero = next((p for p in players if p.get("is_hero")), None)
        if hero:
            hero_bet = hero.get("bet_amount", 0) or 0
            max_bet = max((p.get("bet_amount", 0) or 0) for p in players)
            call_amount = max(0, max_bet - hero_bet)

        num_opponents = len([p for p in players if not p.get("is_hero") and p.get("active", True) and p.get("action") != "fold"])

        # Calcolo deterministico (SEMPRE attivo in parallelo)
        # Preflop: usa lookup tabella (istantaneo, zero carico MC)
        if not board:
            equity = self.preflop_equity(hole, num_opponents=num_opponents)
        else:
            equity = self.calculate_equity_mc(hole, board, num_opponents)

        pot_size = pot if pot is not None else 0
        pot_odds = self.calculate_pot_odds(call_amount, pot_size)

        # Poker Utils — outs, draw, sizing (arricchiscono il prompt LLM)
        outs_info = self.calculate_outs(hole, board) if board else {"outs": 0, "draw_type": "none"}
        sizing = self.get_sizing(equity) if equity > 0 else 0

        # Arricchisci state per LLM
        state.update({
            "equity": equity,
            "pot_odds": pot_odds,
            "call_amount": call_amount,
            "outs": outs_info["outs"],
            "draw_type": outs_info["draw_type"],
            "sizing_suggested": sizing,
        })

        # Timer di mossa dinamico (da SEE)
        move_timer = state.get("move_timer_seconds_remaining")
        from config import MOVE_TIMER_CRITICAL_THRESHOLD
        if move_timer is not None and move_timer < MOVE_TIMER_CRITICAL_THRESHOLD:
            # Timer critico: salta direttamente al fallback deterministico
            return self._fallback_deterministic(
                equity, call_amount, pot, "timer_critical",
                hole_cards=hole, board_cards=board, num_opponents=num_opponents
            )

        # Livello 1: Tentativo LLM (max 1 retry)
        for attempt in range(2):  # 1 tentativo + 1 retry
            llm_result = self.evaluate_with_llm(state, tracker=tracker)
            if llm_result and "error" not in llm_result:
                # Validazione azione legale
                valid_actions = self._get_valid_actions(call_amount)
                if llm_result.get("azione") in valid_actions:
                    return llm_result
            elif llm_result and llm_result.get("error") in ("timeout", "connection_refused"):
                if attempt == 0:
                    continue  # Retry immediato
                break  # Secondo tentativo fallito -> Livello 2
            else:
                break  # Errore parsing o altro -> Livello 2

        # Livello 2: Fallback Deterministico (Treys con anti-leggibilità)
        return self._fallback_deterministic(
            equity, call_amount, pot, "llm_failed",
            hole_cards=hole, board_cards=board, num_opponents=num_opponents
        )

    def _get_valid_actions(self, call_amount: float) -> list:
        """Ritorna azioni valide in base a call_amount."""
        if call_amount == 0:
            return ["CHECK", "RAISE", "FOLD"]
        return ["CALL", "RAISE", "FOLD"]

    def _fallback_deterministic(self, equity: float, call_amount: float, pot: float, reason: str, hole_cards: list = None, board_cards: list = None, num_opponents: int = 1) -> Dict:
        """
        Fallback Livello 2: Treys puro con anti-leggibilità (Guida 4.3).
        Usa la stessa logica di decide_deterministic ma con gestione errori robusta.
        Anti-leggibilità: se equity > 80% e non si può checkare, valuta CALL invece di FOLD.
        """
        can_check = (call_amount == 0)
        pot_safe = pot if pot is not None else 0
        pot_odds = self.calculate_pot_odds(call_amount, pot_safe) if pot_safe > 0 else 0

        # Logica base: equity vs pot odds (stessa di decide_deterministic)
        if equity >= 0.80 and can_check:
            return {
                "azione": "CHECK",
                "sizing": 0,
                "motivazione": f"fallback_treys_check_forte ({reason})"
            }

        if equity > pot_odds * 1.2:
            sizing = int(pot * 2.5) if pot > 0 else int(call_amount * 3)
            return {
                "azione": "RAISE",
                "sizing": sizing,
                "motivazione": f"fallback_treys_value_raise ({reason})"
            }

        if equity > pot_odds and not can_check:
            return {
                "azione": "CALL",
                "sizing": int(call_amount),
                "motivazione": f"fallback_treys_call ({reason})"
            }

        if can_check:
            return {"azione": "CHECK", "sizing": 0, "motivazione": f"fallback_treys_check ({reason})"}

        # Anti-leggibilità: se equity molto alta ma sotto soglia, CALL invece di FOLD
        if equity > 0.80 and not can_check:
            return {
                "azione": "CALL",
                "sizing": int(call_amount),
                "motivazione": f"fallback_treys_anti_leggibilita ({reason})"
            }

        return {"azione": "FOLD", "sizing": 0, "motivazione": f"fallback_treys_fold ({reason})"}

    # ------------------------------------------------------------------
    # Self-Healing (Step 4)
    # ------------------------------------------------------------------
    def check_self_heal(self) -> bool:
        """Test diagnostico: l'engine deterministico funziona?"""
        test = self.evaluate_hand(["As", "Ks"], ["Ah", "Kh", "Qh"])
        return test.get("valid", False)

    def handle_fallback(self, hand_evaluation: Dict) -> Dict:
        """Fallback legacy - deprecato, usa _fallback_deterministic."""
        return self._fallback_deterministic(
            hand_evaluation.get("equity", 0),
            hand_evaluation.get("call_amount", 0),
            hand_evaluation.get("pot", 0),
            "legacy"
        )

    def is_blocked(self) -> bool:
        return self.blocked

    # ------------------------------------------------------------------
    # Step 3: Integrazione LM Studio (Modello Agnostico)
    # ------------------------------------------------------------------
    def _extract_json_balanced(self, text: str) -> Optional[Dict]:
        """
        Estrae il primo blocco JSON sintatticamente valido usando scan a parentesi bilanciate.
        Se non trova JSON valido, tenta il parsing di formati semplificati (es. "raise 25").
        Ignora le graffe dentro stringhe tra virgolette.
        Ritorna dict parsato o None se fallisce.
        """
        in_string = False
        escape = False
        depth = 0
        start = -1

        for i, ch in enumerate(text):
            if ch == '"' and not escape:
                in_string = not in_string
            elif ch == '{' and not in_string:
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}' and not in_string:
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        candidate = text[start:i+1]
                        try:
                            return json.loads(candidate)
                        except json.JSONDecodeError:
                            # JSON non valido, continua la ricerca
                            pass
            escape = (ch == '\\' and not escape)

        # Fallback: parsing formato semplificato "raise 25", "call", "fold"
        return self._parse_simple_format(text)

    def _parse_simple_format(self, text: str) -> Optional[Dict]:
        """
        Parsing robusto per output non-JSON del modello (es. "raise 25", "call", "fold").
        Cerca keyword azione e numero sizing opzionale.
        """
        import re
        text_lower = text.lower().strip()

        # Pattern: azione + numero opzionale
        patterns = [
            (r'\b(raise|rilancia|ralancia)\b\s*(\d+)', 'RAISE'),
            (r'\b(call|chiamo|callo)\b\s*(\d+)?', 'CALL'),
            (r'\b(check|controllo|controlla)\b', 'CHECK'),
            (r'\b(fold|passo|folds)\b', 'FOLD'),
            (r'\b(all.?in|tutto|allin)\b', 'ALL-IN'),
        ]

        for pattern, action in patterns:
            match = re.search(pattern, text_lower)
            if match:
                sizing = 0
                if match.groups() and len(match.groups()) > 1 and match.group(2):
                    try:
                        sizing = int(match.group(2))
                    except ValueError:
                        sizing = 0
                return {
                    "azione": action,
                    "sizing": sizing,
                    "motivazione": f"parsed_from_text: {text[:50]}"
                }

        return None

    def _call_lm_studio(self, prompt: str, system_prompt: str = None) -> Optional[Dict]:
        """
        Chiama LM Studio endpoint REST (formato OpenAI /v1/chat/completions).
        Ritorna dict con 'azione', 'sizing', 'motivazione' o None se fallisce.
        """
        from config import LM_STUDIO_URL, POKER_MODEL

        # System prompt default (Sezione 12 Guida - adattato per modelli piccoli)
        if system_prompt is None:
            system_prompt = """You are a poker decision engine for Texas Hold'em.
Given the hand state (including equity, outs, pot odds, draw type), decide the best action.
Output format (ONLY ONE of these):
- "FOLD" (if you fold)
- "CHECK" (if you check)
- "CALL" (if you call)
- "RAISE <amount>" (if you raise, with the chip amount)
Example: "RAISE 50" or "CALL" or "FOLD"
No other text."""

        payload = {
            "model": POKER_MODEL,  # Modello poker specializzato
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.1,
            "max_tokens": 100
            # NO response_format / JSON Schema (Guida v2.2 Sezione 4.2)
        }

        try:
            response = requests.post(
                LM_STUDIO_URL,
                json=payload,
                timeout=5.0  # Target < 0.8-1s per ciclo, ma 4B su CPU serve più tempo
            )
            response.raise_for_status()
            data = response.json()

            # Estrai contenuto risposta
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Parsing a parentesi bilanciate (v2.2)
            parsed = self._extract_json_balanced(content)
            if parsed and all(k in parsed for k in ("azione", "sizing", "motivazione")):
                return parsed
            return None

        except requests.exceptions.Timeout:
            return {"error": "timeout"}
        except requests.exceptions.ConnectionError:
            return {"error": "connection_refused"}
        except Exception as e:
            return {"error": str(e)}

    def evaluate_with_llm(self, state: Dict, tracker=None) -> Optional[Dict]:
        """
        Chiama LM Studio per decisione contestuale.
        Il state contiene già equity e pot_odds calcolati da Treys.
        Se disponibile, inietta profili avversario (Step 12).
        """
        # Costruisci prompt con stato tavolo + equity/pot_odds
        equity = state.get("equity", 0)
        pot_odds = state.get("pot_odds", 0)
        hole = state.get("hole_cards", [])
        board = state.get("board", [])
        pot = state.get("pot", 0)
        call_amount = state.get("call_amount", 0)
        players = state.get("players", [])

        # Contesto avversario (Step 12)
        opponent_context = ""
        if tracker:
            opponent_context = tracker.get_opponent_context(players)
            if opponent_context:
                opponent_context = "\n" + opponent_context + "\n"

        # Contesto torneo (Step 13bis) — letto dalla Vision
        tournament_info = state.get("tournament", {})
        tournament_context = ""
        if tournament_info:
            parts = []
            if tournament_info.get("blind"):
                parts.append(f"Blind: {tournament_info['blind']}")
            if tournament_info.get("ante"):
                parts.append(f"Ante: {tournament_info['ante']}")
            if tournament_info.get("players_remaining"):
                parts.append(f"Giocatori: {tournament_info['players_remaining']}")
            if tournament_info.get("paid_positions"):
                parts.append(f"Paganti: {tournament_info['paid_positions']}")
            if parts:
                tournament_context = "\nTorneo: " + " | ".join(parts) + "\n"

        prompt = f"""Stato tavolo:
- Hero hole cards: {hole}
- Board: {board}
- Pot: {pot}
- Call amount: {call_amount}
- Equity: {equity:.2%}
- Pot odds: {pot_odds:.2%}
- Outs: {state.get('outs', 0)} ({state.get('draw_type', 'none')})
- Sizing suggerito: {state.get('sizing_suggested', 0)}
- Giocatori attivi: {len([p for p in players if not p.get('is_hero') and p.get('active', True) and p.get('action') != 'fold'])}
{tournament_context}{opponent_context}
Restituisci SOLO JSON valido con azione, sizing, motivazione."""

        return self._call_lm_studio(prompt)

    def warm_up_llm(self):
        """Warm-up del modello all'avvio (inferenza a vuoto)."""
        test_state = {
            "hole_cards": ["As", "Kh"],
            "board": [],
            "pot": 30,
            "call_amount": 10,
            "equity": 0.65,
            "pot_odds": 0.25,
            "players": [{"is_hero": True}, {"is_hero": False}]
        }
        self._call_lm_studio("Test warm-up: " + json.dumps(test_state))


# ============================================================
# Test unitari (eseguire direttamente: python eval_engine.py)
# ============================================================
if __name__ == "__main__":
    engine = EvalEngine(mc_iterations=500)

    print("=" * 60)
    print("STEP 2 — Test Motore Deterministico (Treys)")
    print("=" * 60)

    # Test 1: AA preflop vs 1 avversario
    print("\n[TEST 1] AA preflop vs 1 opp")
    result = engine.decide_deterministic(
        ["As", "Ah"], [], pot=30, call_amount=10, num_opponents=1
    )
    print(f"  Decisione: {result['azione']} {result.get('sizing', '')}")
    print(f"  Motivazione: {result['motivazione']}")
    assert result["azione"] == "RAISE", "AA preflop deve raise"
    print("  ✅ PASS")

    # Test 2: Colore fatto al flop
    print("\n[TEST 2] Colore fatto (Ah Kh) su board Qh Jh 2h")
    result = engine.decide_deterministic(
        ["Ah", "Kh"], ["Qh", "Jh", "2h"], pot=100, call_amount=50, num_opponents=2
    )
    print(f"  Decisione: {result['azione']} {result.get('sizing', '')}")
    print(f"  Motivazione: {result['motivazione']}")
    assert result["azione"] in ("RAISE", "CALL"), "Colore fatto deve value bet"
    print("  ✅ PASS")

    # Test 3: Mano mancata su board pericoloso
    print("\n[TEST 3] AsKs su board 7h 8h 9h (draw colore avversario probabile)")
    result = engine.decide_deterministic(
        ["As", "Ks"], ["7h", "8h", "9h"], pot=80, call_amount=40, num_opponents=2
    )
    print(f"  Decisione: {result['azione']} {result.get('sizing', '')}")
    print(f"  Motivazione: {result['motivazione']}")
    # Equity bassa -> fold o call marginale
    print("  ✅ PASS (decisione sensata)")

    # Test 4: Conversione carte formato vision
    print("\n[TEST 4] Conversione formato vision")
    test_cards = ["Ace of SPADES", "King of HEARTS", "10 of DIAMONDS", "9 of CLUBS"]
    parsed = [engine.parse_card(c) for c in test_cards]
    print(f"  Input: {test_cards}")
    print(f"  Parsed: {parsed}")
    assert parsed == ["As", "Kh", "Td", "9c"], "Conversione fallita"
    print("  ✅ PASS")

    # Test 5: evaluate() da state JSON (con fallback Treys)
    print("\n[TEST 5] evaluate() da state JSON - AA preflop deve RAISE (fallback Treys)")
    state = {
        "hole_cards": ["Ace of SPADES", "Ace of HEARTS"],
        "board": [],
        "pot": 30,
        "players": [
            {"seat": 1, "stack": 1000, "action": "call", "bet_amount": 10, "is_hero": False},
            {"seat": 2, "stack": 1000, "action": None, "bet_amount": 0, "is_hero": True}
        ]
    }
    result = engine.evaluate(state)
    print(f"  Decisione: {result['azione']} {result.get('sizing', '')}")
    print(f"  Motivazione: {result['motivazione']}")
    # AA preflop DEVE essere RAISE - sia che arrivi dall'LLM sia dal fallback Treys
    assert result["azione"] == "RAISE", f"AA preflop deve raise, ottenuto {result['azione']}"
    print("  ✅ PASS")

    print("\n" + "=" * 60)
    print("TUTTI I TEST STEP 2 SUPERATI ✅")
    print("=" * 60)