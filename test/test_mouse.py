#!/usr/bin/env python3
# ============================================================
# Test Mouse / ACT Module — Verifica movimento e click
# ============================================================
# ATTENZIONE: Sposta il mouse e fa click reali!
# Esegui solo se sei pronto e hai il tavolo visibile (o area sicura).
# ============================================================

import sys
import os
import time

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)
sys.path.insert(0, _here)
sys.path.insert(0, _parent)

from act import ActModule

def test_mouse_movement():
    """Test base: movimento mouse e click in area sicura."""
    print("=" * 60)
    print("TEST MOUSE / ACT MODULE")
    print("=" * 60)
    print("⚠️  Questo sposterà il VERO mouse e farà click reali!")
    print("   Assicurati di avere un'area sicura (es. desktop vuoto)")
    print("   o il tavolo poker in posizione nota.")
    print()
    
    act = ActModule(roi_mode="web")
    print(f"[ACT] Bounding box: {act.bounding_box}")
    print()
    
    # Coordinate di test: centro della bounding box (area sicura)
    bb = act.bounding_box
    center_x = bb["x"] + bb["width"] // 2
    center_y = bb["y"] + bb["height"] // 2
    
    print(f"Coordinate test: ({center_x}, {center_y})")
    print()
    
    # Test 1: Spostamento mouse (senza click)
    print("TEST 1: Spostamento mouse...")
    try:
        import pyautogui
        pyautogui.moveTo(center_x, center_y, duration=0.5)
        print(f"  ✓ Mouse spostato a ({center_x}, {center_y})")
        time.sleep(0.5)
        
        # Torna all'angolo
        pyautogui.moveTo(bb["x"] + 10, bb["y"] + 10, duration=0.5)
        print(f"  ✓ Mouse spostato all'angolo")
        time.sleep(0.5)
    except Exception as e:
        print(f"  ✗ ERRORE movimento: {e}")
        return False
    
    # Test 2: Click singolo via ActModule (validazione coordinate)
    print()
    print("TEST 2: Click singolo via ActModule.click_action()...")
    print("  (Clickerà al centro della bounding box)")
    confirm = input("  Procedere con click reale? (s/n): ").strip().lower()
    if confirm != 's':
        print("  Annullato.")
        return True
    
    try:
        result = act.click_action(center_x, center_y)
        if result:
            print(f"  ✓ Click eseguito e validato")
        else:
            print(f"  ⚠ Click eseguito ma validazione stato fallita (normale se non c'è UI)")
    except Exception as e:
        print(f"  ✗ ERRORE click: {e}")
        return False
    
    # Test 3: Sequenza click (simula azione poker)
    print()
    print("TEST 3: Sequenza 3 click rapidi (simula fold/call/raise)...")
    confirm = input("  Procedere? (s/n): ").strip().lower()
    if confirm != 's':
        print("  Annullato.")
        return True
    
    # 3 posizioni diverse per testare movimento
    positions = [
        (center_x - 50, center_y),      # Sinistra
        (center_x, center_y),           # Centro
        (center_x + 50, center_y),      # Destra
    ]
    
    for i, (x, y) in enumerate(positions, 1):
        print(f"  Click {i}/3 a ({x}, {y})...")
        try:
            result = act.click_action(x, y)
            print(f"    {'✓' if result else '⚠'} Eseguito")
            time.sleep(0.3)
        except Exception as e:
            print(f"    ✗ ERRORE: {e}")
    
    print()
    print("=" * 60)
    print("TEST COMPLETATO")
    print("=" * 60)
    return True


def test_table_coordinates():
    """Test con coordinate note del tavolo (da layout)."""
    print()
    print("TEST COORDINATE TAVOLO (da layout_web_9max.json)")
    print("-" * 60)
    
    import json
    layout_path = os.path.join(_parent, "layouts", "layout_web_9max.json")
    if not os.path.exists(layout_path):
        print("Layout non trovato.")
        return
    
    with open(layout_path, "r") as f:
        layout = json.load(f)
    
    sub_roi = layout.get("sub_roi", {})
    
    # Pulsanti azione tipici (es. fold, call, raise)
    buttons = sub_roi.get("action_buttons", {})
    if buttons:
        print("Pulsanti azione trovati nel layout:")
        for name, coords in buttons.items():
            x = coords.get("x", 0)
            y = coords.get("y", 0)
            w = coords.get("width", 0)
            h = coords.get("height", 0)
            center_x = x + w // 2
            center_y = y + h // 2
            print(f"  {name}: centro ({center_x}, {center_y}) box {w}x{h}")
    
    # Seat Hero (es. seat 3)
    seats = sub_roi.get("player_seats", [])
    for seat in seats:
        if seat.get("seat") == 3:  # Hero tipico
            print(f"\nSeat Hero (3): carte=({seat.get('card_x')},{seat.get('card_y')}) "
                  f"nome=({seat.get('name_x')},{seat.get('name_y')}) "
                  f"stack=({seat.get('stack_x')},{seat.get('stack_y')})")


if __name__ == "__main__":
    print("Seleziona test:")
    print("  1. Test movimento + click base (centro bounding box)")
    print("  2. Mostra coordinate tavolo da layout")
    print("  3. Tutti e due")
    
    choice = input("Scelta (1/2/3): ").strip()
    
    if choice in ("1", "3"):
        test_mouse_movement()
    
    if choice in ("2", "3"):
        test_table_coordinates()