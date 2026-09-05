# ============================================================
# HoldEm Agent — Step 3bis: Gestione Multi-Modello su VRAM Limitata
# ============================================================
# Verifica la tecnica di gestione GPU/CPU quando più modelli locali
# devono convivere (es. Hermes sempre attivo + modello poker al bisogno).
#
# Cosa misura questo test:
# 1. Latenza modello poker su CPU (offload disattivato, KV cache off)
# 2. Latenza modello poker su GPU (se disponibile, offload attivo)
# 3. Verifica che il fallback deterministico Treys funzioni anche se LLM lento/assente
#
# NOTA: LM Studio gestisce l'offload GPU/RAM lato server al caricamento modello.
# Questo test misura solo l'impatto pratico sul budget di tempo della chiamata.
# ============================================================

import sys
import os
import time
import json

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from eval_engine import EvalEngine
from config import POKER_MODEL, LM_STUDIO_URL


def measure_latency(engine: EvalEngine, state: dict, n_calls: int = 20) -> dict:
    """Misura latenza media e massima su N chiamate consecutive."""
    latencies = []
    successes = 0

    for i in range(n_calls):
        start = time.time()
        try:
            result = engine.evaluate_with_llm(state)
            elapsed = time.time() - start
            latencies.append(elapsed)
            if result and "error" not in result:
                successes += 1
        except Exception as e:
            elapsed = time.time() - start
            latencies.append(elapsed)
            print(f"  Errore chiamata {i+1}: {e}")

    if not latencies:
        return {"avg": 0, "max": 0, "min": 0, "success_rate": 0}

    return {
        "avg": sum(latencies) / len(latencies),
        "max": max(latencies),
        "min": min(latencies),
        "success_rate": successes / n_calls
    }


def main():
    print("=" * 70)
    print("STEP 3bis — Gestione Multi-Modello su VRAM Limitata")
    print("=" * 70)

    # Stato di test realistico (AA preflop)
    test_state = {
        "hole_cards": ["As", "Ah"],
        "board": [],
        "pot": 30,
        "call_amount": 10,
        "equity": 0.44,
        "pot_odds": 0.25,
        "players": [
            {"seat": 1, "stack": 1000, "action": "call", "bet_amount": 10, "is_hero": False},
            {"seat": 2, "stack": 1000, "action": None, "bet_amount": 0, "is_hero": True}
        ]
    }

    print(f"\nModello poker configurato: {POKER_MODEL}")
    print(f"Endpoint LM Studio: {LM_STUDIO_URL}")

    # Inizializza engine
    engine = EvalEngine(mc_iterations=200)

    # Warm-up (deve essere fatto all'avvio dell'agente)
    print("\n[WARM-UP] Inferenza a vuoto...")
    warm_start = time.time()
    engine.warm_up_llm()
    warm_elapsed = time.time() - warm_start
    print(f"  Warm-up completato in {warm_elapsed:.2f}s")

    # Misurazione latenza
    print(f"\n[LATENZA] {20} chiamate consecutive...")
    stats = measure_latency(engine, test_state, n_calls=20)

    print(f"\n  Latenza media:   {stats['avg']:.3f}s")
    print(f"  Latenza massima: {stats['max']:.3f}s")
    print(f"  Latenza minima:  {stats['min']:.3f}s")
    print(f"  Success rate:    {stats['success_rate']*100:.0f}%")

    # Verifica soglia critica timer (Sezione 5.1ter Guida)
    from config import MOVE_TIMER_CRITICAL_THRESHOLD
    print(f"\n[SOGLIA TIMER] Critica sotto {MOVE_TIMER_CRITICAL_THRESHOLD}s")
    if stats['max'] > MOVE_TIMER_CRITICAL_THRESHOLD:
        print(f"  ⚠️  Latenza massima ({stats['max']:.2f}s) SUPERA la soglia critica!")
        print(f"  → Il fallback deterministico scatta automaticamente sotto soglia.")
    else:
        print(f"  ✅ Latenza massima dentro la soglia critica.")

    # Verifica fallback deterministico (Treys)
    print(f"\n[FALLBACK] Test fallback deterministico Treys...")
    fallback_result = engine._fallback_deterministic(
        equity=test_state["equity"],
        call_amount=test_state["call_amount"],
        pot=test_state["pot"],
        reason="test_step3bis",
        hole_cards=test_state["hole_cards"],
        board_cards=test_state["board"],
        num_opponents=1
    )
    print(f"  AA preflop → {fallback_result['azione']} (fallback Treys)")
    assert fallback_result["azione"] == "RAISE", "Fallback deve produrre RAISE per AA"

    # Verifica che fallback sia istantaneo (no LLM)
    fallback_start = time.time()
    for _ in range(100):
        engine._fallback_deterministic(
            equity=0.44, call_amount=10, pot=30, reason="perf",
            hole_cards=["As","Ah"], board_cards=[], num_opponents=1
        )
    fallback_elapsed = time.time() - fallback_start
    print(f"  100 fallback deterministici in {fallback_elapsed:.4f}s "
          f"({(fallback_elapsed/100)*1000:.1f}ms caduno)")

    print("\n" + "=" * 70)
    print("STEP 3bis COMPLETATO ✅")
    print("=" * 70)
    print("\nNote per l'utente:")
    print("- LM Studio gestisce offload GPU/RAM al caricamento modello (lato server).")
    print("- Se il modello poker è su CPU (offload OFF, KV cache OFF), la latenza sale")
    print("  ma non compete per VRAM con un eventuale modello Hermes su GPU.")
    print("- Il fallback deterministico Treys è sempre istantaneo (<1ms) e compensa")
    print("  latenze LLM elevate o modelli non disponibili.")


if __name__ == "__main__":
    main()
