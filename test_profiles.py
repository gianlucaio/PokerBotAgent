#!/usr/bin/env python3
"""
Test profili di gioco con eval_engine usando mock game states.
Esegue eval_engine.evaluate() con ogni profilo su scenari mock.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from eval_engine import PokerEvaluator
import json

# ============================================================
# MOCK GAME STATES
# ============================================================

MOCK_STATES = [
    {
        "name": "PREMIUM_PREFLOP_AA",
        "description": "AA preflop vs raise 3bb, stack 100bb",
        "hole_cards": ["As", "Ah"],
        "board": [],
        "pot": 45,  # 3bb raise + blinds
        "move_timer_seconds_remaining": 30,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 30, "action": "raise", "active": True},
        ],
        "phase": "PREFLOP",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "MARGINAL_PREFLOP_72O",
        "description": "72 offsuit preflop vs raise 3bb",
        "hole_cards": ["7c", "2d"],
        "board": [],
        "pot": 45,
        "move_timer_seconds_remaining": 30,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 30, "action": "raise", "active": True},
        ],
        "phase": "PREFLOP",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "TOP_PAIR_FLOP",
        "description": "Top pair (AK) su flop A-7-2 rainbow vs bet 1/2 pot",
        "hole_cards": ["As", "Kh"],
        "board": ["Ad", "7c", "2h"],
        "pot": 100,
        "move_timer_seconds_remaining": 25,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 50, "action": "bet", "active": True},
        ],
        "phase": "FLOP",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "FLUSH_DRAW_FLOP",
        "description": "Flush draw (9h 8h) su flop Kh-7h-2c vs bet 2/3 pot",
        "hole_cards": ["9h", "8h"],
        "board": ["Kh", "7h", "2c"],
        "pot": 150,
        "move_timer_seconds_remaining": 25,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 100, "action": "bet", "active": True},
        ],
        "phase": "FLOP",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "SET_ON_FLOP",
        "description": "Set di 9 (99) su flop 9-5-2 rainbow vs bet 1/2 pot",
        "hole_cards": ["9c", "9d"],
        "board": ["9h", "5s", "2d"],
        "pot": 120,
        "move_timer_seconds_remaining": 25,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 60, "action": "bet", "active": True},
        ],
        "phase": "FLOP",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "NOTHING_FLOP",
        "description": "Niente (KQ) su flop A-7-2 rainbow vs bet 1/2 pot",
        "hole_cards": ["Kc", "Qd"],
        "board": ["Ah", "7c", "2h"],
        "pot": 100,
        "move_timer_seconds_remaining": 25,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 50, "action": "bet", "active": True},
        ],
        "phase": "FLOP",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "TURN_VALUE_BET",
        "description": "Top pair su turn A-7-2-K vs check",
        "hole_cards": ["As", "Kh"],
        "board": ["Ad", "7c", "2h", "Ks"],
        "pot": 200,
        "move_timer_seconds_remaining": 20,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 0, "action": "check", "active": True},
        ],
        "phase": "TURN",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
    {
        "name": "RIVER_BLUFF_CATCH",
        "description": "Second pair su river A-7-2-K-Q vs bet 2/3 pot",
        "hole_cards": ["Ac", "Qd"],
        "board": ["Ad", "7c", "2h", "Ks", "Qs"],
        "pot": 300,
        "move_timer_seconds_remaining": 15,
        "players": [
            {"seat": 1, "name": "Hero", "stack": 10000, "bet": 0, "action": "none", "active": True},
            {"seat": 2, "name": "Villain", "stack": 10000, "bet": 200, "action": "bet", "active": True},
        ],
        "phase": "RIVER",
        "tournament": {"blind": "10/20", "ante": 0, "players_remaining": 9, "paid_positions": 2}
    },
]

# ============================================================
# PROFILI DA TESTARE
# ============================================================

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")

def load_profile(name):
    """Carica un profilo da file JSON."""
    path = os.path.join(PROFILES_DIR, f"{name}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

PROFILES = {
    "tight": load_profile("tight"),
    "aggressive": load_profile("aggressive"),
    "auto_adaptive": load_profile("auto_adaptive"),
    "normal": load_profile("normal"),
}

# ============================================================
# TEST RUNNER
# ============================================================

def run_test():
    """Esegue i test per tutti i profili su tutti gli scenari mock."""
    
    print("=" * 80)
    print("TEST PROFILI DI GIOCO - EVAL_ENGINE CON MOCK STATES")
    print("=" * 80)
    print()
    
    # Verifica profili caricati
    print("Profili caricati:")
    for name, profile in PROFILES.items():
        if profile:
            print(f"  ✅ {name}: {profile.get('description', 'N/A')}")
        else:
            print(f"  ❌ {name}: NON TROVATO")
    print()
    
    # Inizializza evaluator
    evaluator = PokerEvaluator()
    
    # Risultati: {profile_name: {scenario_name: action}}
    results = {name: {} for name in PROFILES.keys()}
    
    for scenario in MOCK_STATES:
        print(f"\n{'='*80}")
        print(f"SCENARIO: {scenario['name']}")
        print(f"Descrizione: {scenario['description']}")
        print(f"Fase: {scenario['phase']} | Pot: {scenario['pot']} | Hole: {scenario['hole_cards']} | Board: {scenario['board']}")
        print("-" * 80)
        
        for profile_name, profile in PROFILES.items():
            if not profile:
                print(f"  {profile_name:15} → SKIP (profilo non trovato)")
                results[profile_name][scenario['name']] = "SKIP"
                continue
            
            try:
                # Crea evaluator con profilo specifico
                evaluator = PokerEvaluator(profile=profile)
                
                # Chiama evaluate
                action, amount, reasoning = evaluator.evaluate(scenario)
                
                results[profile_name][scenario['name']] = action
                print(f"  {profile_name:15} → {action:6} (amount: {amount}) | {reasoning[:80]}...")
                
            except Exception as e:
                print(f"  {profile_name:15} → ERROR: {e}")
                results[profile_name][scenario['name']] = f"ERROR: {e}"
    
    # ============================================================
    # RIEPILOGO FINALE
    # ============================================================
    print("\n" + "=" * 80)
    print("RIEPILOGO DECISIONI PER PROFILO")
    print("=" * 80)
    
    # Tabella: Scenario x Profilo
    scenarios = [s['name'] for s in MOCK_STATES]
    profiles_list = list(PROFILES.keys())
    
    # Header
    header = f"{'Scenario':25}"
    for p in profiles_list:
        header += f" | {p:15}"
    print(header)
    print("-" * len(header))
    
    for scenario in MOCK_STATES:
        row = f"{scenario['name']:25}"
        for p in profiles_list:
            action = results[p].get(scenario['name'], "N/A")
            row += f" | {action:15}"
        print(row)
    
    print()
    
    # Analisi differenze
    print("ANALISI DIFFERENZE TRA PROFILI:")
    print("-" * 80)
    
    for i, scenario in enumerate(MOCK_STATES):
        actions = [results[p].get(scenario['name']) for p in profiles_list]
        unique_actions = set(actions)
        
        if len(unique_actions) > 1:
            print(f"  🔄 {scenario['name']}: DIVERSE → {dict(zip(profiles_list, actions))}")
        else:
            print(f"  ✅ {scenario['name']}: UGUALI ({list(unique_actions)[0]})")

if __name__ == "__main__":
    run_test()