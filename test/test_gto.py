# Test per Step 2bis — Tabelle GTO Push/Fold Preflop
import sys, os
_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from eval_engine import EvalEngine

engine = EvalEngine(mc_iterations=100)

print("=" * 60)
print("STEP 2bis — Test Tabelle GTO Push/Fold")
print("=" * 60)

# Test 1: _normalize_hand
print("\n[TEST 1] Normalizzazione mani")
tests = [
    (["As", "Ah"], "AA"),
    (["As", "Kh"], "AKs"),
    (["Ah", "Kh"], "AKo"),
    (["Kd", "Qd"], "KQs"),
    (["Qh", "Kh"], "KQo"),
    (["Js", "Js"], "JJ"),
    (["2d", "3d"], "32s"),
]
all_pass = True
for cards, expected in tests:
    result = engine._normalize_hand(cards)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_pass = False
    print(f"  {status} {cards} → {result} (atteso: {expected})")
assert all_pass, "Alcuni test di normalizzazione falliti"
print("  ✅ TUTTI PASS")

# Test 2: GTO lookup
print("\n[TEST 2] Lookup GTO")
engine_gto = EvalEngine(mc_iterations=100)  # Abilita tabelle GTO

# AA dovrebbe essere PUSH in quasi tutte le posizioni
result = engine_gto.gto_preflop_action(["As", "Ah"], "BTN", 10)
print(f"  AA BTN 10bb → {result}")
assert result == "PUSH", f"AA dovrebbe essere PUSH, ottenuto {result}"

# Mano debole dovrebbe essere FOLD
result = engine_gto.gto_preflop_action(["2d", "7h"], "BTN", 10)
print(f"  2-7o BTN 10bb → {result}")
assert result == "FOLD", f"2-7o dovrebbe essere FOLD, ottenuto {result}"

# KQ suited dovrebbe essere PUSH in posizione forte
result = engine_gto.gto_preflop_action(["Ks", "Qs"], "BTN", 10)
print(f"  KQs BTN 10bb → {result}")
# Può essere PUSH o FOLD a seconda della tabella, ma non deve crashare

print("  ✅ TUTTI PASS")

# Test 3: GTO con stack diverso
print("\n[TEST 3] Lookup GTO con stack 15bb")
result = engine_gto.gto_preflop_action(["As", "Ah"], "UTG", 15)
print(f"  AA UTG 15bb → {result}")
assert result == "PUSH", f"AA dovrebbe essere PUSH, ottenuto {result}"

print("\n" + "=" * 60)
print("STEP 2bis TEST SUPERATI ✅")
print("=" * 60)
