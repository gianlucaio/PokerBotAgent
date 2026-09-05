#!/usr/bin/env python3
# ============================================================
# HoldEm Agent — Modulo VOICE (Comando Vocale)
# ============================================================
# STT locale con Vosk (modello italiano) + Sotto-Flussi A/B/D
# Implementato dopo lo scheletro iniziale.
# ============================================================

import os
import json
import queue
import threading
import time
from datetime import datetime

# --- Percorsi del progetto ---
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Il modello Vosk vive in <progetto>/models/vosk/vosk-model-small-it-0.4
_MODEL_CANDIDATES = [
    os.path.join(_BASE_DIR, "..", "models", "vosk", "vosk-model-small-it-0.4"),
    os.path.join(_BASE_DIR, "models", "vosk", "vosk-model-small-it-0.4"),
]
_VOSK_MODEL_PATH = next((p for p in _MODEL_CANDIDATES if os.path.isdir(p)), None)

# Soglia di ampiezza per distinguere "silenzio" da "voce".
# I livelli vanno calibrati sulla propria scheda (HDA Intel PCH).
_AMP_THRESHOLD = 1500


class VoiceModule:
    """Gestisce riconoscimento vocale (Vosk), comandi e sotto-flussi A/B/D."""

    def __init__(self, db=None):
        """db: oggetto con i metodi save_voice_correction / save_perception_correction
        (vedi db.py, tabelle voice_corrections e perception_corrections). Se None,
        le correzioni non vengono persistite (solo log in memoria)."""
        self.mode = "automatic"  # "automatic" | "assisted"
        self.pre_turn_override = None  # istruzione pre-turno per mano corrente
        self.db = db

        # Garantisce che il modulo db passato abbia i metodi di persistenza
        # per i sotto-flussi B (motivazione) e D (correzione percettiva).
        # Se db è None o non ha i metodi, _ensure_db_methods li aggiunge
        # (o lascia in log-only se non è disponibile un db valido).
        if self.db is not None:
            _ensure_db_methods(self.db)

        # Vosk
        self._model = None
        self._rec = None
        self._init_vosk()

        # Listen (thread)
        self._queue = queue.Queue()
        self._listen_thread = None
        self._listening = False
        self._last_transcription = ""
        self._last_partial = ""
        self._pending_motivation = None

    # ---------------- Setup Vosk ----------------
    def _init_vosk(self):
        """Carica il modello Vosk. Se assente, il modulo resta senza STT
        (ils parse_command() funziona comunque su testo passato manualmente)."""
        import vosk  # import locale: dipendenza opzionale
        if not _VOSK_MODEL_PATH:
            print("[VOICE] ATTENZIONE: modello Vosk non trovato. "
                  "Vocale disabilitato. Cercato in:", _MODEL_CANDIDATES)
            return
        try:
            self._model = vosk.Model(_VOSK_MODEL_PATH)
            self._rec = vosk.KaldiRecognizer(self._model, 16000)
            print(f"[VOICE] Modello Vosk caricato: {os.path.basename(_VOSK_MODEL_PATH)}")
        except Exception as e:
            print(f"[VOICE] ERRORE caricamento modello Vosk: {e}")
            self._model = None
            self._rec = None

    @property
    def stt_available(self):
        return self._rec is not None

    # ---------------- Modalità ----------------
    def set_mode(self, mode):
        """Toggle Automatica/Assistita."""
        self.mode = mode
        if mode == "assisted":
            self._start_listening()
        elif mode == "automatic":
            self._stop_listening()

    # ---------------- Override pre-turno ----------------
    def set_pre_turn_override(self, command):
        """Imposta un override pre-turno per la mano corrente (Sotto-Flusso A)."""
        self.pre_turn_override = command
        print(f"[VOICE] Override pre-turno impostato: {command}")

    def get_pre_turn_override(self):
        """Ritorna istruzione pre-turno se presente, poi la cancella.
        Se l'override è valido, EVAL va saltato (gestito dal chiamante)."""
        cmd = self.pre_turn_override
        self.pre_turn_override = None
        return cmd

    # ---------------- Ascolto microfono (Sotto-Flusso A) ----------------
    def _start_listening(self):
        """Avvia ascolto microfono in thread (sounddevice + Vosk)."""
        if self._listening or not self.stt_available:
            return
        self._listening = True
        self._queue = queue.Queue()
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        print("[VOICE] Ascolto microfono avviato (modalità assistita).")

    def _stop_listening(self):
        self._listening = False
        if self._listen_thread:
            self._listen_thread.join(timeout=1)
            self._listen_thread = None
        print("[VOICE] Ascolto microfono fermato.")

    def _listen_loop(self):
        """Loop che cattura audio dal microfono in blocchi e li passa a Vosk."""
        import sounddevice as sd
        import numpy as np
        sample_rate = 16000
        block_ms = 50
        block = int(sample_rate * block_ms / 1000)
        try:
            with sd.RawInputStream(samplerate=sample_rate, blocksize=block,
                                   channels=1, dtype="int16",
                                   callback=self._audio_callback):
                while self._listening:
                    # Processa i chunk accumulati nella coda
                    try:
                        data = self._queue.get(timeout=0.2)
                        self._process_audio(data)
                    except queue.Empty:
                        pass
        except Exception as e:
            print(f"[VOICE] ERRORE stream audio: {e}")
            self._listening = False

    def _audio_callback(self, indata, frames, time_info, status):
        """Callback sounddevice: mette il chunk audio nella coda."""
        if self._listening:
            self._queue.put(bytes(indata))

    def _process_audio(self, data):
        """Passa un chunk audio a Vosk e, a fine frase, ritorna un comando."""
        if not self._rec:
            return
        # Vosk gestisce il VAD internamente via AcceptWaveform
        if self._rec.AcceptWaveform(data):
            res = json.loads(self._rec.Result())
            text = res.get("text", "")
            if text:
                self._on_transcription(text)
            # ripristina recognizer per la frase successiva? no: quel loop
            # mantiene un recognizer unico; il reset avviene con FinalResult a fine blocco.
        # Fallback parziale
        partial = json.loads(self._rec.PartialResult())
        if partial.get("partial"):
            self._last_partial = partial["partial"]

    def _on_transcription(self, text):
        """Frase completa riconosciuta: la gestisce secondo la modalità."""
        self._last_transcription = text
        print(f"[VOICE] Riconosciuto: \"{text}\"")
        if self.mode == "assisted":
            cmd = self.parse_command(text)
            if cmd:
                # In modalità assistita, una frase di comando diventa un override pre-turno
                self.set_pre_turn_override(cmd)
                print(f"[VOICE] Override pre-turno da voce: {cmd}")

    # ---------------- Parsing comando ----------------
    def parse_command(self, transcription):
        """Parsing comando vocale -> azione normalizzata (Sotto-Flusso A)."""
        commands_map = {
            "fold": "FOLD",
            "passo": "FOLD",
            "fol": "FOLD",
            "foul": "FOLD",
            "check": "CHECK",
            "controllo": "CHECK",
            "ceck": "CHECK",
            "call": "CALL",
            "chiamo": "CALL",
            "col": "CALL",
            "cal": "CALL",
            "all in": "ALL-IN",
            "all-in": "ALL-IN",
            "tutto": "ALL-IN",
            "olin": "ALL-IN",
            "ollin": "ALL-IN",
            "raise": "RAISE",
            "rilancia": "RAISE",
            "rialza": "RAISE",
            "scommetti": "RAISE",
            "ri": "RAISE",
            "rilamcia": "RAISE",
        }
        tl = (transcription or "").lower().strip()
        for keyword, action in commands_map.items():
            if keyword in tl:
                return action
        return None

    # ---------------- Sotto-Flusso B: motivazione ----------------
    def request_motivation(self, hand_id, action_proposed, action_user):
        """Richiede la motivazione post-correzione e la salva nel DB."""
        # In un contesto con UI, qui partirebbe l'ascolto vocale per la
        # motivazione. Per ora segnaliamo la richiesta e, in modalità
        # assistita, catturiamo la prossima frase come motivazione.
        print(f"[VOICE] Richiesta motivazione (hand {hand_id}): "
              f"proposta={action_proposed}, utente={action_user}")
        self._pending_motivation = (hand_id, action_proposed, action_user)
        return None  # dopo ascolto, salvare

    def _save_motivation(self, hand_id, action_proposed, action_user, motivation):
        """Salva la motivazione in voice_corrections."""
        if self.db is not None and hasattr(self.db, "save_voice_correction"):
            self.db.save_voice_correction(hand_id, action_proposed, action_user, motivation)
        else:
            print(f"[VOICE] (nessun DB) correzione salvata in memoria: {motivation}")

    # ---------------- Sotto-Flusso D: correzione percettiva ----------------
    def handle_perception_correction(self, correction_type, value_wrong, value_correct,
                                     environment="web", table_format=None):
        """Registra una correzione percettiva runtime (Sotto-Flusso D)."""
        # Logging e persistenza
        print(f"[VOICE] Correzione percettiva: {correction_type}: "
              f"{value_wrong} -> {value_correct}")
        if self.db is not None and hasattr(self.db, "save_perception_correction"):
            self.db.save_perception_correction(
                environment, table_format, correction_type, value_wrong, value_correct
            )
        # Ritorna il valore corretto, così il chiamante può usarlo per la mano
        return value_correct


# ============================================================
# Thin wrapper attorno a db.py per non aggiungere dipendenze
# circolari: VoiceModule riceve un db "duck-typed".
# ============================================================
def _ensure_db_methods(db_module):
    """Aggiunge a db_module i metodi save_voice_correction / save_perception_correction
    se non esistono già. Da chiamare in init."""
    if not hasattr(db_module, "save_voice_correction"):
        def save_voice_correction(hand_id, action_proposed, action_user, motivation,
                                  conn=None):
            import db
            conn = conn or db.get_connection()
            conn.execute(
                "INSERT INTO voice_corrections (timestamp, hand_id, action_proposed, "
                "action_user, motivation) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), hand_id, action_proposed, action_user,
                 motivation))
            conn.commit(); conn.close()
        db_module.save_voice_correction = save_voice_correction

    if not hasattr(db_module, "save_perception_correction"):
        def save_perception_correction(environment, table_format, data_type,
                                       value_wrong, value_correct, conn=None):
            import db
            conn = conn or db.get_connection()
            conn.execute(
                "INSERT INTO perception_corrections (timestamp, environment, "
                "table_format, data_type, value_wrong, value_correct) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), environment, table_format, data_type,
                 value_wrong, value_correct))
            conn.commit(); conn.close()
        db_module.save_perception_correction = save_perception_correction
