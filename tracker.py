#!/usr/bin/env python3
# ============================================================
# HoldEm Agent — Tracker Azioni Avversari (Step 12)
# ============================================================
# Traccia le azioni di ogni giocatore durante la mano.
# Al showdown calcola VPIP/PFR/AF/Fold-to-Cbet e aggiorna il DB.
# Legge i profili per iniettarli nel prompt LLM.
# ============================================================

import time
from typing import Dict, Optional
from db import get_connection


class ActionTracker:
    """Traccia azioni di ogni giocatore per mano e calcola statistiche."""

    def __init__(self):
        # Stato mano corrente: {player_id: [{"action": "raise", "phase": "preflop", "amount": 50}, ...]}
        self._hand_actions: Dict[str, list] = {}
        self._hand_id: Optional[str] = None
        self._hand_start_time: float = 0
        self._last_pot: int = 0
        self._last_hero_cards: list = []

    def reset_hand(self, hand_id: str = None):
        """Reset stato per nuova mano."""
        self._hand_actions = {}
        self._hand_id = hand_id or f"hand_{int(time.time())}"
        self._hand_start_time = time.time()
        self._last_pot = 0
        self._last_hero_cards = []

    def on_state_change(self, state: Dict):
        """
        Chiamato ad ogni ciclo Vision quando lo stato cambia.
        Registra le azioni osservate.
        """
        pot = state.get("pot", 0) or 0
        players = state.get("players", [])
        phase = state.get("phase", "PREFLOP")
        hero_cards = state.get("hole_cards", [])

        # Inizializza mano corrente se vuota
        if not self._hand_actions:
            self._hand_id = f"hand_{int(time.time())}"
            self._hand_start_time = time.time()

        # Registra stato corrente di ogni giocatore (escluso Hero)
        for p in players:
            if p.get("is_hero"):
                continue
            pid = p.get("name", "unknown")
            if not pid or pid == "unknown":
                continue

            if pid not in self._hand_actions:
                self._hand_actions[pid] = []

            # Rileva azione: confronta stato attuale con precedente
            action = self._detect_action(p, phase)
            if action:
                self._hand_actions[pid].append(action)

        self._last_pot = pot
        self._last_hero_cards = hero_cards

    def _detect_action(self, player: Dict, phase: str) -> Optional[Dict]:
        """
        Rileva l'azione di un giocatore basandosi sullo stato.
        Confronta con l'ultima azione registrata per quel giocatore.
        """
        pid = player.get("name", "unknown")
        action_str = player.get("action", "").lower()
        bet = player.get("bet_amount", 0) or 0
        active = player.get("active", True)

        if not action_str:
            return None

        # Controlla se è un'azione nuova rispetto all'ultima registrata
        recorded = self._hand_actions.get(pid, [])
        # Normalizza prima del confronto dedup
        action_type = self._normalize_action(action_str)
        if recorded:
            last = recorded[-1]
            if last["action"] == action_type and last.get("amount", 0) == bet:
                return None  # Stessa azione, non registrare

        return {
            "action": action_type,
            "phase": phase.lower(),
            "amount": bet,
            "timestamp": time.time()
        }

    def _normalize_action(self, action_str: str) -> str:
        """Normalizza le azioni in categorie standard."""
        a = action_str.lower().strip()
        if a in ("fold", "passo", "fol", "foul"):
            return "fold"
        elif a in ("check", "controllo", "ceck"):
            return "check"
        elif a in ("call", "chiamo", "col", "cal"):
            return "call"
        elif a.startswith("raise") or a in ("rilancia", "rialza", "scommetti", "ri", "rilamcia"):
            return "raise"
        elif a in ("all in", "all-in", "tutto", "olin", "ollin"):
            return "allin"
        elif a == "bet":
            return "bet"
        return a

    # ------------------------------------------------------------------
    # Calcolo statistiche al showdown
    # ------------------------------------------------------------------

    def on_hand_end(self):
        """Chiamato da main.py quando rileva fine mano. Calcola e salva statistiche."""
        from db import update_opponent_stats, save_hand_history

        for pid, actions in self._hand_actions.items():
            if not actions:
                continue

            stats = self._compute_stats(actions)

            # Carica statistiche esistenti dal DB
            existing = self._get_existing_stats(pid)
            if existing:
                stats = self._merge_stats(existing, stats)

            update_opponent_stats(pid, stats)

        # Salva storico mano
        if self._hand_actions:
            save_hand_history(
                hand_id=self._hand_id,
                hero_cards=str(self._last_hero_cards),
                board="",
                pot=self._last_pot,
                action_taken="",
                action_eval="",
                outcome="showdown" if self._last_pot > 0 else "fold_win",
                fallback_used=0
            )

    def _compute_stats(self, actions: list) -> Dict:
        """Calcola VPIP/PFR/AF/Fold-to-Cbet da una lista di azioni."""
        preflop = [a for a in actions if a["phase"] == "preflop"]
        postflop = [a for a in actions if a["phase"] != "preflop"]

        # Se nessuna azione preflop, il giocatore non era nella mano
        if not preflop:
            return {"hands_observed": 0, "vpip": 0, "pfr": 0, "af": 0, "fold_to_cbet": 0}

        # VPIP: 1 se ha messo soldi volontariamente preflop (call o raise), 0 altrimenti
        vpip = 1 if any(a["action"] in ("call", "raise", "allin") for a in preflop) else 0

        # PFR: 1 se ha rilanciato preflop, 0 altrimenti
        pfr = 1 if any(a["action"] in ("raise", "allin") for a in preflop) else 0

        # AF: rapporto raise/call postflop
        postflop_raises = sum(1 for a in postflop if a["action"] in ("raise", "allin", "bet"))
        postflop_calls = sum(1 for a in postflop if a["action"] == "call")
        af = postflop_raises / max(postflop_calls, 1)

        # Fold-to-Cbet: di quante volte ha affrontato un bet/raise, quante ha foldato
        faced_bet = 0
        folded_after = 0
        for i, a in enumerate(actions):
            if i == 0:
                continue
            # Ha affrontato un bet/raise nella finestra precedente?
            faced = any(
                actions[j]["action"] in ("bet", "raise", "allin")
                for j in range(max(0, i - 2), i)
            )
            if faced:
                faced_bet += 1
                if a["action"] == "fold":
                    folded_after += 1
        fold_to_cbet = folded_after / max(faced_bet, 1)

        return {
            "hands_observed": 1,
            "vpip": vpip,
            "pfr": pfr,
            "af": af,
            "fold_to_cbet": fold_to_cbet
        }

    def _get_existing_stats(self, player_id: str) -> Optional[Dict]:
        """Carica statistiche esistenti dal DB."""
        conn = get_connection()
        row = conn.execute(
            "SELECT hands_observed, vpip, pfr, af, fold_to_cbet "
            "FROM opponent_stats WHERE player_id = ?",
            (player_id,)
        ).fetchone()
        conn.close()
        if not row:
            return None
        return {
            "hands_observed": row[0],
            "vpip": row[1],
            "pfr": row[2],
            "af": row[3],
            "fold_to_cbet": row[4]
        }

    def _merge_stats(self, old: Dict, new: Dict) -> Dict:
        """Unisce statistiche vecchie con nuove (media ponderata)."""
        h = old["hands_observed"]
        # Nuova media ponderata: ((vecchia * n) + nuova) / (n + 1)
        return {
            "hands_observed": h + 1,
            "vpip": (old["vpip"] * h + new["vpip"]) / (h + 1),
            "pfr": (old["pfr"] * h + new["pfr"]) / (h + 1),
            "af": (old["af"] * h + new["af"]) / (h + 1),
            "fold_to_cbet": (old["fold_to_cbet"] * h + new["fold_to_cbet"]) / (h + 1),
        }

    # ------------------------------------------------------------------
    # Contesto avversario per prompt LLM
    # ------------------------------------------------------------------

    def get_opponent_context(self, players: list) -> str:
        """
        Genera il testo con le statistiche degli avversari
        da iniettare nel prompt del modello poker.
        """
        lines = []
        for p in players:
            if p.get("is_hero"):
                continue
            pid = p.get("name", "")
            if not pid:
                continue
            stats = self._get_existing_stats(pid)
            if stats and stats["hands_observed"] >= 3:
                profile = self._classify_player(stats)
                lines.append(
                    f"- {pid}: VPIP={stats['vpip']:.0%} PFR={stats['pfr']:.0%} "
                    f"AF={stats['af']:.1f} ({profile}) "
                    f"[{stats['hands_observed']} mani osservate]"
                )
        if not lines:
            return ""
        return "Profilo avversari noti:\n" + "\n".join(lines)

    def _classify_player(self, stats: Dict) -> str:
        """Classifica il giocatore in base alle statistiche."""
        vpip = stats["vpip"]
        pfr = stats["pfr"]
        af = stats["af"]

        if vpip < 0.20 and pfr < 0.10:
            return "tight-passivo"
        elif vpip < 0.20 and pfr >= 0.10:
            return "tight-aggressivo"
        elif vpip >= 0.40 and af < 1.0:
            return "loose-passivo (calling station)"
        elif vpip >= 0.40 and af >= 1.0:
            return "loose-aggressivo (LAG)"
        elif vpip >= 0.25:
            return "medio"
        else:
            return "unknown"

    def get_stats_summary(self) -> str:
        """Ritorna un riepilogo di tutti i profili noti (per debug)."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT player_id, hands_observed, vpip, pfr, af, fold_to_cbet "
            "FROM opponent_stats ORDER BY hands_observed DESC"
        ).fetchall()
        conn.close()
        if not rows:
            return "Nessun profilo avversario ancora registrato."
        lines = ["Profili avversari:"]
        for r in rows:
            profile = self._classify_player({
                "vpip": r[2], "pfr": r[3], "af": r[4]
            })
            lines.append(
                f"  {r[0]}: {r[1]} mani, VPIP={r[2]:.0%}, PFR={r[3]:.0%}, "
                f"AF={r[4]:.1f}, Fold-CBet={r[5]:.0%} — {profile}"
            )
        return "\n".join(lines)
