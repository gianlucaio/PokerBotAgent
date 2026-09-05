#!/usr/bin/env python3
# ============================================================
# HoldEm Agent — Garbage Collection (Step 13)
# ============================================================
# Pulizia automatica dei dati accumulati in memoria per
# evitare memory leak in sessioni lunghe.
# ============================================================

import time
import gc
import os
import sys
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

# Importa config per parametri GC
try:
    from config import GC_ENABLED, GC_TTL_SECONDS, GC_MAX_MEMORY_MB, GC_INTERVAL_CYCLES
except ImportError:
    GC_ENABLED = True
    GC_TTL_SECONDS = 600
    GC_MAX_MEMORY_MB = 200
    GC_INTERVAL_CYCLES = 50


class MemoryStore:
    """
    Store generico per dati con TTL.
    Ogni entry ha timestamp di creazione e accesso.
    """

    def __init__(self, ttl_seconds: int = GC_TTL_SECONDS):
        self._data: Dict[str, Dict] = {}
        self._ttl = ttl_seconds

    def set(self, key: str, value: Any, metadata: Dict = None):
        """Salva un valore con timestamp."""
        self._data[key] = {
            "value": value,
            "created": time.time(),
            "metadata": metadata or {}
        }

    def get(self, key: str) -> Optional[Any]:
        """Recupera un valore. Elimina se scaduto."""
        if key not in self._data:
            return None
        entry = self._data[key]
        if time.time() - entry["created"] > self._ttl:
            del self._data[key]
            return None
        return entry["value"]

    def delete(self, key: str) -> bool:
        """Elimina una chiave."""
        if key in self._data:
            del self._data[key]
            return True
        return False

    def cleanup_expired(self) -> int:
        """Rimuove entry scadute. Ritorna il numero rimosso."""
        now = time.time()
        expired = [
            k for k, v in self._data.items()
            if now - v["created"] > self._ttl
        ]
        for k in expired:
            del self._data[k]
        return len(expired)

    def size(self) -> int:
        """Numero di entry."""
        return len(self._data)

    def clear(self):
        """Svuota tutto."""
        self._data.clear()


class GarbageCollector:
    """
    Coordinatore GC per il bot.
    - Pulisce store TTL
    - Monitora memoria processo
    - Forza GC Python se necessario
    """

    def __init__(self):
        self.vision_store = MemoryStore()      # stati Vision passati
        self.eval_store = MemoryStore()        # risposte LLM
        self.voice_store = MemoryStore()       # trascrizioni vocali
        self.hand_store = MemoryStore()        # storico mani
        self.debug_store = MemoryStore()       # debug frames

        self._cycle_count = 0
        self._last_gc_time = time.time()
        self._last_memory_check = time.time()

    def tick(self, force: bool = False) -> Dict[str, int]:
        """
        Esegue un ciclo GC. Chiamato ad ogni ciclo Vision.
        Ritorna statistiche della pulizia.
        """
        self._cycle_count += 1

        if not force and self._cycle_count % GC_INTERVAL_CYCLES != 0:
            return {"skipped": True}

        stats = {
            "vision_expired": self.vision_store.cleanup_expired(),
            "eval_expired": self.eval_store.cleanup_expired(),
            "voice_expired": self.voice_store.cleanup_expired(),
            "hand_expired": self.hand_store.cleanup_expired(),
            "debug_expired": self.debug_store.cleanup_expired(),
            "python_gc": 0,
            "memory_mb": self._get_memory_mb()
        }

        # Controlla memoria e forza GC Python se supera soglia
        if stats["memory_mb"] > GC_MAX_MEMORY_MB:
            collected = gc.collect()
            stats["python_gc"] = collected
            stats["memory_mb_after"] = self._get_memory_mb()

        self._last_gc_time = time.time()
        return stats

    def _get_memory_mb(self) -> float:
        """Ritorna memoria RSS corrente del processo in MB (Linux: /proc/self/statm)."""
        try:
            with open("/proc/self/statm", "r") as f:
                # Campo 1 = RSS (resident set size) in pagine da 4KB
                rss_pages = int(f.read().split()[1])
                return (rss_pages * 4) / 1024  # KB → MB
        except Exception:
            # Fallback per sistemi non-Linux
            try:
                import resource
                rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                return rss / 1024 if sys.platform != "darwin" else rss / 1024 / 1024
            except Exception:
                return 0.0

    def store_vision(self, state_hash: str, state: Dict):
        """Salva stato Vision con TTL."""
        self.vision_store.set(state_hash, state, {"type": "vision"})

    def store_eval(self, state_hash: str, decision: Dict):
        """Salva decisione EVAL con TTL."""
        self.eval_store.set(state_hash, decision, {"type": "eval"})

    def store_voice(self, key: str, data: Dict):
        """Salva dato vocale con TTL."""
        self.voice_store.set(key, data, {"type": "voice"})

    def store_hand(self, hand_id: str, data: Dict):
        """Salva storico mano con TTL."""
        self.hand_store.set(hand_id, data, {"type": "hand"})

    def store_debug(self, key: str, data: Any):
        """Salva dato debug con TTL."""
        self.debug_store.set(key, data, {"type": "debug"})

    def get_stats(self) -> Dict:
        """Statistiche correnti degli store."""
        return {
            "vision_entries": self.vision_store.size(),
            "eval_entries": self.eval_store.size(),
            "voice_entries": self.voice_store.size(),
            "hand_entries": self.hand_store.size(),
            "debug_entries": self.debug_store.size(),
            "total_entries": (self.vision_store.size() + self.eval_store.size() +
                             self.voice_store.size() + self.hand_store.size() +
                             self.debug_store.size()),
            "memory_mb": self._get_memory_mb(),
            "cycles_since_gc": self._cycle_count % GC_INTERVAL_CYCLES
        }

    def clear_all(self):
        """Svuota tutti gli store (es. a fine sessione)."""
        self.vision_store.clear()
        self.eval_store.clear()
        self.voice_store.clear()
        self.hand_store.clear()
        self.debug_store.clear()


# Istanza globale
gc_instance = GarbageCollector()


def gc_tick(force: bool = False) -> Dict:
    """Funzione comoda per il loop principale."""
    if not GC_ENABLED:
        return {"skipped": "disabled"}
    return gc_instance.tick(force=force)


def get_gc_stats() -> Dict:
    """Statistiche GC per logging."""
    if not GC_ENABLED:
        return {"disabled": True}
    return gc_instance.get_stats()


def clear_gc_stores():
    """Svuota tutto."""
    gc_instance.clear_all()