#!/usr/bin/env python3
"""
Test vocale con stato hardcoded (già validato).
NON usa la Vision — usa lo stato reale dello screenshot.
Testa: Eval propone FOLD → utente dice "call" → override vince → azione = CALL
"""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# --- Stato reale dello screenshot (validato) ---
STATO = {
    "hole_cards": ["9d", "6d"],
    "board": ["As", "6h", "Qh"],
    "pot": 400,
    "timer": None,
    "hero_seat": 3,
    "players": [
        {"seat": 1, "name": "cipigi", "stack": 21046, "bet": 0, "action": None, "active": True},
        {"seat": 2, "name": "sappiero", "stack": 12555, "bet": 0, "action": None, "active": True},
        {"seat": 3, "name": "hero", "stack": 6406, "bet": 150, "action": "raise", "active": True},
        {"seat": 4, "name": "testone53", "stack": 46701, "bet": 0, "action": None, "active": True},
        {"seat": 5, "name": "michael1968", "stack": 23775, "bet": 0, "action": None, "active": True},
        {"seat": 6, "name": "bytomy60", "stack": 1735, "bet": 0, "action": None, "active": True},
        {"seat": 7, "name": "xxcatanesexx", "stack": 4575, "bet": 0, "action": None, "active": True},
        {"seat": 8, "name": "massimogemello", "stack": 21258, "bet": 0, "action": None, "active": True},
        {"seat": 9, "name": "asd00", "stack": 10905, "bet": 0, "action": None, "active": True}
    ]
}


def eval_calcola_decisione(stato):
    print("\n[1] CALCOLO LA DECISIONE CON EVAL (equity + modello poker)...")
    from eval_engine import EvalEngine
    engine = EvalEngine()
    try:
        decision = engine.evaluate(stato)
        print(f"  ✓ Proposta: {decision.get('azione', '?')}")
        print(f"    Sizing: {decision.get('sizing', 'N/A')}")
        print(f"    Motivazione: {decision.get('motivazione', '')}")
        return decision
    except Exception as e:
        print(f"  ERRORE Eval: {e}")
        return None


def ascolto_vocale(durata_secondi=10):
    print(f"\n[2] ASCOLTO VOCALE ({durata_secondi}s) — dimmi qualcosa al microfono...")
    print(f"  (es: 'call', 'fold', 'raise', 'check')")

    try:
        import vosk
        import sounddevice as sd
        import queue, json as json_mod

        # Cerca il modello in entrambe le posizioni (come voice.py)
        candidates = [
            os.path.join(os.path.dirname(__file__), "..", "models", "vosk", "vosk-model-small-it-0.4"),
            os.path.join(os.path.dirname(__file__), "..", "..", "models", "vosk", "vosk-model-small-it-0.4"),
        ]
        model_path = next((p for p in candidates if os.path.isdir(p)), None)
        if not model_path:
            print("  ⚠ Modello Vosk non trovato in nessuna posizione")
            return None

        model = vosk.Model(model_path)
        rec = vosk.KaldiRecognizer(model, 16000)
        q = queue.Queue()

        def callback(indata, frames, time_info, status):
            q.put(bytes(indata))

        print("  🎤 In ascolto...")
        with sd.RawInputStream(samplerate=16000, blocksize=8000, dtype='int16',
                               channels=1, callback=callback):
            start = time.time()
            while time.time() - start < durata_secondi:
                try:
                    data = q.get(timeout=0.5)
                    if rec.AcceptWaveform(data):
                        result = json_mod.loads(rec.Result())
                        text = result.get("text", "").strip()
                        if text:
                            print(f"  🗣️ Riconosciuto: \"{text}\"")
                            return text
                    else:
                        partial = json_mod.loads(rec.PartialResult())
                        pt = partial.get("partial", "").strip()
                        if pt:
                            print(f"  🔊 (parziale: \"{pt}\")", end="\r")
                except queue.Empty:
                    pass
            # Ultimo tentativo
            final = json_mod.loads(rec.FinalResult())
            text = final.get("text", "").strip()
            if text:
                print(f"  🗣️ Riconosciuto (finale): \"{text}\"")
                return text
            print("  ⏰ Timeout — nessun comando vocale riconosciuto")
            return None
    except Exception as e:
        print(f"  ERRORE ascolto vocale: {e}")
        return None


def main():
    print("=" * 60)
    print("TEST VOCALE CON STATO HARDCODED (senza Vision)")
    print("=" * 60)
    print(f"  Hero: {STATO['players'][2]['name']} (Seat 3)")
    print(f"  Carte: {STATO['hole_cards']}")
    print(f"  Board: {STATO['board']}")
    print(f"  Pot: {STATO['pot']}")

    # Step 1: Eval
    proposta = eval_calcola_decisione(STATO)
    if not proposta:
        print("\n✗ Test fallito: Eval non ha restituito decisione")
        return

    # Step 2: Ascolto vocale
    comando_vocale = ascolto_vocale(durata_secondi=10)

    # Step 3: Decisione finale
    print("\n" + "=" * 60)
    print("DECISIONE FINALE")
    print("=" * 60)

    if comando_vocale:
        from voice import VoiceModule
        vm = VoiceModule(db=None)
        azione = vm.parse_command(comando_vocale)
        if azione:
            print(f"  OVERRIDE VOCALE → {azione} (da: \"{comando_vocale}\")")
            print(f"  (la proposta era: {proposta.get('azione', '?')})")
            print(f"\n  ✓ L'azione che verrebbe eseguita è: {azione}")
        else:
            print(f"  ⚠ Comando non riconosciuto: \"{comando_vocale}\"")
            print(f"  La proposta resta: {proposta.get('azione', '?')}")
    else:
        print(f"  Nessun override vocale")
        print(f"  La proposta del modello resta: {proposta.get('azione', '?')}")
        print(f"  Motivazione: {proposta.get('motivazione', '')}")

    print("\n  (Il click non è stato eseguito — è un test controllato)")
    print("=" * 60)


if __name__ == "__main__":
    main()
