# ============================================================
# HoldEm Agent — Entry Point (Event-Driven Architecture)
# ============================================================
# Vision: loop continuo ad alta frequenza (guarda sempre il tavolo)
# Eval: si attiva SOLO quando Vision rileva azione richiesta per Hero
# Fine mano: Vision resetta stato e riparte per il giro successivo
# v0.3.0 — Adattato a PokerTableScope: layout_file invece di roi_mode/table_format
# ============================================================

import sys
import os
import time
import datetime
import json

# Aggiunge la directory del progetto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DEBUG_MODE, DEBUG_DIR, VISION_POLL_INTERVAL,
    EVAL_TRIGGER_TIMER_THRESHOLD, HERO_NAME,
    LAYOUTS_DIR, LAYOUT_FILE
)
from db import init_db
from see import SeeModule
from eval_engine import EvalEngine
from act import ActModule
from voice import VoiceModule
from tracker import ActionTracker
from mem_gc import gc_tick, get_gc_stats, clear_gc_stores


def _find_first_layout():
    """Trova il primo layout disponibile in LAYOUTS_DIR."""
    if not os.path.isdir(LAYOUTS_DIR):
        return None
    for f in sorted(os.listdir(LAYOUTS_DIR)):
        if f.startswith("layout_") and f.endswith(".json"):
            return f
    return None


def main():
    print("=" * 60)
    print("HoldEm Agent v0.3.0 — Avvio (Event-Driven + PokerTableScope)")
    print("=" * 60)

    # Trova il layout selezionato dall'utente in gui.py (salvato in DB)
    db.init_db()
    selected_layout = db.get_tournament_config("layout_file") or _find_first_layout()
    if selected_layout:
        layout_path = os.path.join(LAYOUTS_DIR, selected_layout)
        if not os.path.exists(layout_path):
            print(f"[AGENTE] ATTENZIONE: Layout {selected_layout} non trovato in {LAYOUTS_DIR}")
            layout_path = None
    else:
        layout_path = None
        print("[AGENTE] ATTENZIONE: Nessun layout selezionato. Usa il primo disponibile.")

    if layout_path is None:
        if os.path.isdir(LAYOUTS_DIR):
            for f in sorted(os.listdir(LAYOUTS_DIR)):
                if f.startswith("layout_") and f.endswith(".json"):
                    layout_path = os.path.join(LAYOUTS_DIR, f)
                    print(f"Layout usato: {f}")
                    break

    see = SeeModule(layout_file=layout_path)
    eval_engine = EvalEngine()
    act = ActModule(layout=see.layout)
    voice = VoiceModule(db=__import__("db", fromlist=["save_voice_correction", "save_perception_correction"]))
    voice = VoiceModule(db=__import__("db", fromlist=["save_voice_correction", "save_perception_correction"]))

    print("[SEE] Modulo percezione pronto (Vision Live).")
    print("[EVAL] Motore decisionale pronto (attivazione su evento).")
    print("[ACT] Modulo azione pronto.")
    print("[VOICE] Modulo vocale pronto (Vosk Italiano, override pre-turno attivo).")

    # Init tracker azioni avversari (Step 12)
    tracker = ActionTracker()
    print("[TRACKER] Profilazione avversari attiva.")

    # Init Garbage Collector (Step 13)
    print("[GC] Garbage Collector attivo (TTL=600s, max=200MB, ogni 50 cicli).")
    print()

    # Stato persistente tra cicli vision
    last_state_hash = None
    hand_in_progress = False
    last_decision = None
    proposed_action = None  # Decisione proposta (cambio fase, in attesa turno Hero)
    consecutive_no_change = 0

    # Loop principale — Event Driven
    print("Avvio loop event-driven (CTRL+C per fermare)...")
    print("=" * 60)
    print("MODALITÀ LOG-ONLY — Vision continuo, Eval solo su trigger")
    print("=" * 60)

    try:
        while True:
            cycle_start = time.time()

            # 1. CATTURA + VISION (sempre attivo, alta frequenza)
            img = see.capture_screen()
            vision_raw = see.parse_state_vision(img)

            # Debug Mode: salva screenshot e output Vision (Step 13)
            if DEBUG_MODE:
                _debug_log_frame(DEBUG_DIR, cycle_start, img, vision_raw, "vision")

            # 2. PARSE output vision in stato strutturato per EVAL
            current_state = _parse_vision_output(vision_raw, see)

            # 2b. TRACKER: registra azioni avversari (Step 12)
            tracker.on_state_change(current_state)

            # 3. RILEVA CAMBI DI STATO SIGNIFICATIVI
            state_hash = _hash_state(current_state)
            state_changed = (state_hash != last_state_hash)

            # Log periodico stato vision (ogni 10 cicli ~10-20s)
            if consecutive_no_change % 10 == 0:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Vision: {current_state.get('phase', 'UNKNOWN')} | Pot: {current_state.get('pot')} | Board: {current_state.get('board')} | Hero cards: {current_state.get('hole_cards')}")

            # 4. LOGICA TRIGGER EVAL
            should_eval = False
            should_propose = False  # Nuovo: proposta anticipata (non è turno di Hero)
            trigger_reason = ""
            move_timer = current_state.get("move_timer_seconds_remaining")
            is_hero_turn = move_timer is not None and 0 < move_timer < EVAL_TRIGGER_TIMER_THRESHOLD

            # Trigger 1: Timer attivo per Hero (tocca a noi) → ESECUZIONE
            if is_hero_turn:
                should_eval = True
                trigger_reason = f"timer_attivo_{move_timer}s"

            # Trigger 2: Nuova mano rilevata (carte Hero apparse, pot > 0, board cambiato)
            elif state_changed and _is_actionable_state(current_state):
                should_eval = True
                trigger_reason = "stato_actionable"

            # Trigger 3: Cambio fase (nuove carte board, es. flop->turn->river)
            elif state_changed and _phase_changed(current_state, last_state_hash):
                # Se Hero NON è in turno → calcola proposta anticipata
                if not is_hero_turn:
                    should_propose = True
                    trigger_reason = "cambio_fase_proposta"
                else:
                    should_eval = True
                    trigger_reason = "cambio_fase"

            # 5a. PROPOMA ANTICIPATA (cambio fase, non è turno Hero)
            if should_propose:
                try:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> PROPOMA (in attesa turno Hero): {trigger_reason}")
                    proposed_decision = eval_engine.evaluate(current_state, tracker=tracker)
                    azione = proposed_decision.get('azione', '?')
                    sizing = proposed_decision.get('sizing', '')
                    sizing_str = f" sizing={sizing}" if sizing else ""
                    print(f"  [PROPOSTA] Azione: {azione}{sizing_str}")
                    print(f"  [PROPOSTA] Motivazione: {proposed_decision.get('motivazione', '')}")
                    proposed_action = proposed_decision  # salva per esecuzione al turno di Hero
                    hand_in_progress = True
                except Exception as e:
                    print(f"[EVAL] ERRORE proposta: {e}")
                    proposed_action = None
                consecutive_no_change = 0

            # 5b. ESECUZIONE DECISIONE (turno di Hero)
            elif should_eval:
                # Priorità 1: Override vocale pre-turno (Sotto-Flusso A)
                override = voice.get_pre_turn_override()
                if override:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> OVERRIDE VOCALE: {override} — salto EVAL")
                    decision = {"azione": override, "sizing": None, "motivazione": "Override vocale pre-turno"}
                    proposed_action = None  # reset proposta dopo override
                    hand_in_progress = True
                    # Mappa override su pulsante reale via ACT (coordinate calibrate)
                    act.click_by_action(override)
                # Priorità 2: Proposta salvata dal cambio fase precedente
                elif proposed_action is not None:
                    azione = proposed_action.get('azione', '?')
                    sizing = proposed_action.get('sizing', '')
                    sizing_str = f" sizing={sizing}" if sizing else ""
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> ESEGUO PROPOSTA: {azione}{sizing_str}")
                    decision = proposed_action
                    proposed_action = None  # consumata
                    hand_in_progress = True
                    act.click_by_action(azione)
                # Priorità 3: Nessuna proposta né override → ricalcolo fresco
                else:
                    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> TRIGGER EVAL: {trigger_reason}")
                    try:
                        decision = eval_engine.evaluate(current_state, tracker=tracker)
                        print(f"[EVAL] Decisione: {decision.get('azione')} sizing={decision.get('sizing')} — {decision.get('motivazione')}")
                        last_decision = decision
                        hand_in_progress = True

                        # Debug Mode: salva decisione EVAL (Step 13)
                        if DEBUG_MODE:
                            _debug_log_frame(DEBUG_DIR, cycle_start, None, decision, "eval")
                    except Exception as e:
                        print(f"[EVAL] ERRORE: {e}")
                        decision = None
                consecutive_no_change = 0
            else:
                consecutive_no_change += 1

            # 6. RILEVA FINE MANO (tutti fold tranne uno, o showdown, o pot=0 con carte note)
            if hand_in_progress and _hand_ended(current_state, last_state_hash):
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] >>> FINE MANO rilevata — Reset stato Vision")
                # Step 12: calcola e salva statistiche avversari
                tracker.on_hand_end()
                # Log statistiche tracker
                stats_summary = tracker.get_stats_summary()
                if stats_summary and stats_summary != "Nessun profilo avversario ancora registrato.":
                    print(f"[TRACKER] {stats_summary}")
                hand_in_progress = False
                last_decision = None
                proposed_action = None  # Reset proposta a fine mano
                # Forza re-identificazione Hero al prossimo giro
                see.hero_seat = None

            # 7. UPDATE STATO
            last_state_hash = state_hash

            # 7b. GC: pulizia periodica (Step 13)
            gc_result = gc_tick()
            if gc_result and "skipped" not in gc_result:
                total_expired = sum(v for k, v in gc_result.items()
                                    if k.endswith("_expired"))
                if total_expired > 0:
                    print(f"[GC] Puliti {total_expired} dati scaduti "
                          f"(mem {gc_result.get('memory_mb', 0):.0f}MB)")
                if gc_result.get("python_gc", 0) > 0:
                    print(f"[GC] Forzato gc.collect() → raccolti "
                          f"{gc_result['python_gc']} oggetti")

            # 8. SLEEP dinamico: più veloce se c'è azione, più lento se fermo
            elapsed = time.time() - cycle_start
            sleep_time = max(0.1, VISION_POLL_INTERVAL - elapsed)
            if should_eval or hand_in_progress:
                sleep_time = min(sleep_time, 1.0)  # Max 1s durante azione
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[AGENTE] Arresto manuale.")
        # Pulizia GC e statos finale (Step 13)
        gc_stats = get_gc_stats()
        if gc_stats and not gc_stats.get("disabled"):
            print(f"[GC] Statistiche finali: {gc_stats.get('total_entries', 0)} "
                  f"entry in memoria, {gc_stats.get('memory_mb', 0):.0f}MB")
        clear_gc_stores()
        print("[GC] Store puliti.")


def _debug_log_frame(debug_dir: str, timestamp: float, img, data, label: str):
    """Salva screenshot e/o dati in /tmp/holdem_debug/ quando DEBUG_MODE è attivo."""
    import cv2
    os.makedirs(debug_dir, exist_ok=True)
    ts_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S_%f")

    if img is not None:
        path = os.path.join(debug_dir, f"{ts_str}_{label}.png")
        cv2.imwrite(path, img)

    if data is not None:
        import json as _json
        path = os.path.join(debug_dir, f"{ts_str}_{label}.json")
        with open(path, "w") as f:
            _json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def _parse_vision_output(vision_text: str, see_module: SeeModule) -> dict:
    """Converte l'output JSON del modello Vision in dict strutturato
    compatibile con eval_engine.evaluate(state).
    """
    import json
    state = {
        "hole_cards": [],
        "board": [],
        "pot": None,
        "move_timer_seconds_remaining": None,
        "players": [],
        "phase": "UNKNOWN",
        "tournament": {},
        "raw_vision": vision_text[:200]
    }

    text = vision_text.strip()

    # Prova a parsare come JSON
    try:
        # Estrae il primo blocco JSON valido (gestisce eventuale testo prima/dopo)
        start = text.find('{')
        end = text.rfind('}') + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            data = json.loads(json_str)

            # Carte Hero
            if isinstance(data.get("hole_cards"), list):
                state["hole_cards"] = [c for c in data["hole_cards"] if isinstance(c, str) and len(c) >= 2]

            # Board
            if isinstance(data.get("board"), list):
                state["board"] = [c for c in data["board"] if isinstance(c, str) and len(c) >= 2]

            # Pot
            if data.get("pot") is not None:
                try:
                    state["pot"] = int(data["pot"])
                except (ValueError, TypeError):
                    pass

            # Timer
            if data.get("timer") is not None:
                try:
                    state["move_timer_seconds_remaining"] = int(data["timer"])
                except (ValueError, TypeError):
                    pass

            # Info torneo dalla barra in alto
            state["tournament"] = {}
            tournament_data = data.get("tournament", {})
            if isinstance(tournament_data, dict):
                for key, field in [
                    ("blind", "blind"),
                    ("ante", "ante"),
                    ("players_remaining", "players_remaining"),
                    ("paid_positions", "paid_positions"),
                ]:
                    val = tournament_data.get(key)
                    if val is not None and str(val).strip().lower() not in ("", "non visibile", "none", "null"):
                        state["tournament"][field] = str(val).strip()

            # Hero seat - aggiorna SeeModule
            if data.get("hero_seat") is not None and isinstance(data["hero_seat"], int):
                see_module.hero_seat = data["hero_seat"]

            # Players
            if isinstance(data.get("players"), list):
                state["players"] = []
                for p in data["players"]:
                    if isinstance(p, dict):
                        # Stato attivo del seat: derivato dall'output Vision
                        raw_active = p.get("active")
                        if isinstance(raw_active, bool):
                            active = raw_active
                        elif isinstance(raw_active, str):
                            active = raw_active.strip().lower() not in ("false", "0", "no", "inactive", "folded", "oscuro", "inattivo")
                        else:
                            active = True
                        player = {
                            "seat": p.get("seat"),
                            "name": p.get("name"),
                            "stack": p.get("stack"),
                            "bet_amount": p.get("bet", 0),
                            "action": p.get("action"),
                            "active": active,
                            "is_hero": (p.get("name", "").lower() == HERO_NAME.lower())
                        }
                        state["players"].append(player)
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"[PARSE VISION] Errore parsing JSON: {e} - Raw: {text[:100]}")
        # Fallback: vecchio parsing regex se JSON fallisce
        return _parse_vision_fallback(text)

    # Determina fase dal board
    board_len = len(state["board"])
    if board_len == 0:
        state["phase"] = "PREFLOP"
    elif board_len == 3:
        state["phase"] = "FLOP"
    elif board_len == 4:
        state["phase"] = "TURN"
    elif board_len == 5:
        state["phase"] = "RIVER"
    else:
        state["phase"] = f"BOARD_{board_len}"

    return state


def _parse_vision_fallback(text: str) -> dict:
    """Vecchio parsing regex come fallback se JSON fallisce."""
    import re
    state = {
        "hole_cards": [],
        "board": [],
        "pot": None,
        "move_timer_seconds_remaining": None,
        "players": [],
        "phase": "UNKNOWN",
        "raw_vision": text[:200]
    }

    card_matches = re.findall(r"\b([A23456789TJQK][hds♠♥♦♣♤♡♢♧])\b", text, re.IGNORECASE)
    suit_map = {"♥": "h", "♦": "d", "♠": "s", "♣": "c", "♤": "s", "♡": "h", "♢": "d", "♧": "c"}
    cards_norm = [c[0].upper() + suit_map.get(c[1], c[1].lower()) for c in card_matches]

    if "hole" in text.lower() or "hero" in text.lower() or HERO_NAME.lower() in text.lower():
        if len(cards_norm) >= 2:
            state["hole_cards"] = cards_norm[:2]
            state["board"] = cards_norm[2:]
        else:
            state["board"] = cards_norm
    else:
        if len(cards_norm) >= 2:
            state["hole_cards"] = cards_norm[:2]
            state["board"] = cards_norm[2:]
        else:
            state["board"] = cards_norm

    pot_match = re.search(r"(?:pot|piatto)\D*(\d[\d.,]*)", text, re.IGNORECASE)
    if pot_match:
        pot_str = pot_match.group(1).replace(".", "").replace(",", "")
        try:
            state["pot"] = int(pot_str)
        except ValueError:
            pass

    timer_match = re.search(r"(?:timer|tempo|time)\D*(\d+)", text, re.IGNORECASE)
    if timer_match:
        try:
            state["move_timer_seconds_remaining"] = int(timer_match.group(1))
        except ValueError:
            pass

    board_len = len(state["board"])
    if board_len == 0:
        state["phase"] = "PREFLOP"
    elif board_len == 3:
        state["phase"] = "FLOP"
    elif board_len == 4:
        state["phase"] = "TURN"
    elif board_len == 5:
        state["phase"] = "RIVER"
    else:
        state["phase"] = f"BOARD_{board_len}"

    return state


def _hash_state(state: dict) -> str:
    """Hash compatto dello stato per rilevare cambiamenti."""
    key_parts = [
        str(state.get("hole_cards", [])),
        str(state.get("board", [])),
        str(state.get("pot")),
        str(state.get("move_timer_seconds_remaining")),
        state.get("phase", "")
    ]
    return "|".join(key_parts)


def _is_actionable_state(state: dict) -> bool:
    """True se lo stato richiede una decisione (Hero ha carte, c'è pot, timer o bet da chiamare)."""
    has_hole = len(state.get("hole_cards", [])) >= 2
    has_pot = (state.get("pot") or 0) > 0
    has_timer = state.get("move_timer_seconds_remaining") is not None and state["move_timer_seconds_remaining"] > 0
    return has_hole and (has_pot or has_timer)


def _phase_changed(current: dict, last_hash: str) -> bool:
    """True se la fase di gioco è cambiata (es. flop -> turn)."""
    if not last_hash:
        return False
    last_phase = last_hash.split("|")[-1] if "|" in last_hash else ""
    return current.get("phase") != last_phase and current.get("phase") != "UNKNOWN"


def _hand_ended(current: dict, last_hash: str) -> bool:
    """True se la mano è finita (showdown, tutti fold, o reset tavolo)."""
    if not last_hash:
        return False
    # Reset: pot torna 0/None, board vuoto, niente carte Hero
    pot_zero = (current.get("pot") or 0) == 0
    no_board = len(current.get("board", [])) == 0
    no_hole = len(current.get("hole_cards", [])) == 0
    # Se prima c'era roba e ora tutto vuoto/pulito
    had_content = "[]" not in last_hash or "None" not in last_hash
    return pot_zero and no_board and no_hole and had_content


if __name__ == "__main__":
    main()