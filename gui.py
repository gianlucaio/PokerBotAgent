#!/usr/bin/env python3
# ============================================================
# HoldEm Agent — Pannello di Controllo GUI (configurazione)
# ============================================================
# v0.3.0 — Ristrutturato: la GUI ora configura solo parametri gioco.
# Le coordinate vengono dai layout PokerTableScope (selezionabile in GUI).
# ============================================================

import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

# --- Percorsi (relativi alla radice holdem-agent) ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import db  # noqa: E402

# ============================================================
# Temi colori
# ============================================================
THEMES = {
    "Classica": {
        "bg": "#f0f0f0", "fg": "#000000",
        "frame_bg": "#f0f0f0", "label_fg": "#000000",
        "entry_bg": "#ffffff", "entry_fg": "#000000",
        "btn_bg": "#e0e0e0", "accent": "#4a90d9",
        "section_bg": "#e8e8e8", "muted_fg": "#666666",
    },
    "Scuro": {
        "bg": "#2b2b2b", "fg": "#e0e0e0",
        "frame_bg": "#2b2b2b", "label_fg": "#e0e0e0",
        "entry_bg": "#3c3c3c", "entry_fg": "#e0e0e0",
        "btn_bg": "#404040", "accent": "#6ca0dc",
        "section_bg": "#353535", "muted_fg": "#999999",
    },
    "Poker Verde": {
        "bg": "#1a5c2a", "fg": "#f0f0f0",
        "frame_bg": "#1a5c2a", "label_fg": "#f0f0f0",
        "entry_bg": "#267538", "entry_fg": "#f0f0f0",
        "btn_bg": "#2d8a42", "accent": "#ffd700",
        "section_bg": "#1e6b30", "muted_fg": "#b0d4b8",
    },
    "Blu": {
        "bg": "#1a3a5c", "fg": "#e8f0ff",
        "frame_bg": "#1a3a5c", "label_fg": "#e8f0ff",
        "entry_bg": "#264a6e", "entry_fg": "#e8f0ff",
        "btn_bg": "#2a5580", "accent": "#66b3ff",
        "section_bg": "#1e4268", "muted_fg": "#a0b8d0",
    },
}

# ============================================================
# Mappa chiavi DB (tournament_config) + config runtime
# ============================================================
# Le opzioni dei moduli sono salvate nel DB sotto prefisso "module_" e
# "settings_" cosi' da non collidere con i parametri torneo (prefisso "t_").


class PokerGui:
    def __init__(self, root):
        self.root = root
        root.title("PokerBot Agent — Pannello di Controllo")
        root.geometry("940x780")
        root.minsize(940, 780)

        # Variabili di stato (leggono valori correnti dal DB se presenti)
        self.vars = {}
        self.layouts_available = []  # Lista layout disponibili in layouts/

        # --- Layout principale: scorrevole ---
        self.canvas = tk.Canvas(root, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(root, orient="vertical", command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas)
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # Mouse wheel scroll (supporto cross-platform)
        self.canvas.bind_all("<MouseWheel>", self._on_wheel)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        # --- Sezioni ---
        self._build_tournament_section()
        self._build_voice_section()
        self._build_module_section()
        self._build_test_section()
        self._build_action_bar()

        # Applica tema di default
        self._apply_theme("Classica")

        # Carica valori salvati
        self._load_from_db()

    # ------------------------------------------------------------------
    def _on_wheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    def _section(self, parent, title):
        lbl = tk.Label(parent, text=title, font=("", 11, "bold"), anchor="w")
        lbl.pack(fill="x", pady=(10, 2))
        sep = ttk.Separator(parent, orient="horizontal")
        sep.pack(fill="x", pady=(0, 4))
        return tk.Frame(parent)

    # ==================================================================
    # SEZIONE 1 — PARAMETRI TORNEO (Guida 4.2bis, alimenta DB profili)
    # ============================================================
    def _build_tournament_section(self):
        f = self._section(self.inner, "Parametri Torneo Pre-Gara (DB profili di gioco)")
        f.pack(fill="x", padx=10)

        self.vars["t_format"] = tk.StringVar(value="6max")          # 6max | K.O. | 9max
        self.vars["t_type"] = tk.StringVar(value="MTT")             # MTT | Sit&Go | Cash
        self.vars["t_blind"] = tk.StringVar(value="25/50")          # Blind di partenza
        self.vars["t_blind_min"] = tk.StringVar(value="15")         # Durata blind (minuti)
        self.vars["t_stack"] = tk.StringVar(value="3000")           # Stack iniziale
        self.vars["t_players"] = tk.StringVar(value="9")            # Numero giocatori
        self.vars["t_rebuy"] = tk.BooleanVar(value=False)           # Rebuy disponibile?
        self.vars["t_rebuy_times"] = tk.StringVar(value="1")        # Quante volte
        self.vars["t_rebuy_level"] = tk.StringVar(value="5")        # Entro quale livello
        self.vars["t_addon"] = tk.BooleanVar(value=False)           # Add-on disponibile?
        self.vars["t_entries"] = tk.StringVar(value="")             # Iscritti previsti

        grid = ttk.Frame(f)
        grid.pack(fill="x")
        row = 0

        def field(label, var, column=1, is_combo=None, values=None):
            nonlocal row
            ttk.Label(grid, text=label).grid(row=row, column=0, sticky="w", pady=1)
            if is_combo:
                w = ttk.Combobox(grid, textvariable=var, values=values, state="readonly", width=16)
            else:
                w = ttk.Entry(grid, textvariable=var, width=18)
            w.grid(row=row, column=column, sticky="w", pady=1)
            row += 1
            return w

        # Tipo torneo (6max / K.O. / 9max)
        ttk.Label(grid, text="Tipo torneo (formato)").grid(row=row, column=0, sticky="w", pady=1)
        ttk.Combobox(grid, textvariable=self.vars["t_format"],
                     values=["6max", "K.O.", "9max"], state="readonly", width=16
                     ).grid(row=row, column=1, sticky="w", pady=1)
        row += 1

        # Tipologia
        ttk.Label(grid, text="Tipologia").grid(row=row, column=0, sticky="w", pady=1)
        ttk.Combobox(grid, textvariable=self.vars["t_type"],
                     values=["MTT", "Sit&Go", "Cash Game"], state="readonly", width=16
                     ).grid(row=row, column=1, sticky="w", pady=1)
        row += 1

        field("Blind di partenza", self.vars["t_blind"])
        field("Durata blind (minuti)", self.vars["t_blind_min"])
        field("Stack iniziale (fiches)", self.vars["t_stack"])
        field("Numero giocatori", self.vars["t_players"])
        field("Iscritti previsti (opz.)", self.vars["t_entries"])

        # Rebuy
        ttk.Label(grid, text="Rebuy disponibile").grid(row=row, column=0, sticky="w", pady=1)
        ttk.Checkbutton(grid, text="Sì", variable=self.vars["t_rebuy"]).grid(row=row, column=1, sticky="w", pady=1)
        row += 1
        field("Rebuy: quante volte", self.vars["t_rebuy_times"])
        field("Rebuy: entro livello", self.vars["t_rebuy_level"])

        # Add-on
        ttk.Label(grid, text="Add-on disponibile").grid(row=row, column=0, sticky="w", pady=1)
        ttk.Checkbutton(grid, text="Sì", variable=self.vars["t_addon"]).grid(row=row, column=1, sticky="w", pady=1)
        row += 1

    # ==================================================================
    # SEZIONE 2 — MODULO VOICE (modalita' + toggle)
    # ==================================================================
    def _build_voice_section(self):
        f = self._section(self.inner, "Modulo VOICE (Guida Sez 6)")
        f.pack(fill="x", padx=10)

        self.vars["voice_enabled"] = tk.BooleanVar(value=True)
        self.vars["voice_mode"] = tk.StringVar(value="automatic")   # automatic | assisted
        self.vars["voice_override"] = tk.BooleanVar(value=True)     # override pre-turno
        self.vars["voice_flow_b"] = tk.BooleanVar(value=True)       # Sotto-Flusso B motivazione
        self.vars["voice_flow_d"] = tk.BooleanVar(value=True)       # Sotto-Flusso D correzione

        ttk.Checkbutton(f, text="Abilita Modulo VOICE (Vosk)", variable=self.vars["voice_enabled"]).pack(anchor="w")
        ttk.Label(f, text="Modalità operativa:").pack(anchor="w", pady=(6, 0))
        ttk.Radiobutton(f, text="Automatica (default)", variable=self.vars["voice_mode"],
                        value="automatic").pack(anchor="w")
        ttk.Radiobutton(f, text="Assistita (intervento utente)", variable=self.vars["voice_mode"],
                        value="assisted").pack(anchor="w")
        ttk.Label(f, text="Sotto-flussi:").pack(anchor="w", pady=(6, 0))
        ttk.Checkbutton(f, text="Override pre-turno (Sotto-Flusso A)", variable=self.vars["voice_override"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Spiegazione guidata (Sotto-Flusso B)", variable=self.vars["voice_flow_b"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Correzione percettiva (Sotto-Flusso D)", variable=self.vars["voice_flow_d"]).pack(anchor="w")
        tk.Label(f, text="Ricorda: il riconoscimento vocale va azionato apposta (pulsante Attiva/ascolto)",
                 fg="#666", font=("", 9)).pack(anchor="w", pady=(4, 0))

    # ==================================================================
    # SEZIONE 3 — MODULI & IMPOSTAZIONI (semplificata)
    # ==================================================================
    def _build_module_section(self):
        f = self._section(self.inner, "Moduli & Impostazioni")
        f.pack(fill="x", padx=10)

        self.vars["cfg_playstyle"] = tk.StringVar(value="normal")   # tight|normal|aggressive|auto
        self.vars["hero_name"] = tk.StringVar(value="hero")        # Nome Hero (configurabile)
        self.vars["mod_gto"] = tk.BooleanVar(value=False)           # Preflop GTO vs LLM
        self.vars["mod_sitout"] = tk.BooleanVar(value=True)         # Recupero auto Sit-Out
        self.vars["mod_selfheal"] = tk.BooleanVar(value=True)       # Fallback/Self-Healing
        self.vars["mod_debug"] = tk.BooleanVar(value=False)         # Debug Mode
        self.vars["mod_testrec"] = tk.BooleanVar(value=False)       # Modalita' Test Riconoscimento
        self.vars["layout_file"] = tk.StringVar(value="")           # Layout PokerTableScope

        # Profilo tattico
        ttk.Label(f, text="Profilo tattico (DB profili):").pack(anchor="w")
        ttk.Combobox(f, textvariable=self.vars["cfg_playstyle"], state="readonly", width=16,
                     values=["tight", "normal", "aggressive", "auto_adaptant"]).pack(anchor="w", pady=(0, 4))
        # Nome Hero
        ttk.Label(f, text="Nome utente Hero:").pack(anchor="w")
        ttk.Entry(f, textvariable=self.vars["hero_name"], width=20).pack(anchor="w", pady=(0, 4))

        # Toggle moduli
        ttk.Label(f, text="— Interruttori moduli —").pack(anchor="w", pady=(6, 2))
        ttk.Checkbutton(f, text="Preflop deterministico GTO (anziché LLM)", variable=self.vars["mod_gto"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Recupero automatico da Sit-Out", variable=self.vars["mod_sitout"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Fallback / Self-Healing", variable=self.vars["mod_selfheal"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Debug Mode (log su disco)", variable=self.vars["mod_debug"]).pack(anchor="w")
        ttk.Checkbutton(f, text="Modalità Test Riconoscimento (mai in live)", variable=self.vars["mod_testrec"]).pack(anchor="w")

        # Selezione layout PokerTableScope
        ttk.Label(f, text="Layout PokerTableScope:").pack(anchor="w", pady=(6, 2))
        self._update_layout_list()
        ttk.Combobox(f, textvariable=self.vars["layout_file"], state="readonly", width=22,
                     values=self.layouts_available).pack(anchor="w")

    def _update_layout_list(self):
        """Aggiorna la lista dei layout disponibili in layouts/"""
        layouts_dir = os.path.join(BASE_DIR, "layouts")
        self.layouts_available = []
        if os.path.isdir(layouts_dir):
            for f in sorted(os.listdir(layouts_dir)):
                if f.startswith("layout_") and f.endswith(".json"):
                    self.layouts_available.append(f)
            # Imposta il primo layout disponibile come default
            if self.layouts_available:
                self.vars["layout_file"].set(self.layouts_available[0])
            else:
                self.vars["layout_file"].set("")

    # ==================================================================
    # SEZIONE TEST
    # ==================================================================
    def _build_test_section(self):
        """Crea la sezione con i pulsanti per avviare gli script di test."""
        frame = ttk.LabelFrame(self.inner, text="🧪 Test & Verifica", padding=8)
        frame.pack(fill="x", padx=10, pady=(6, 2))

        # Descrizione
        ttk.Label(frame, text="Avvia gli script di test per verificare che il bot funzioni.",
                  wraplength=500).pack(anchor="w", pady=(0, 6))

        # Griglia pulsanti (2 colonne)
        grid = tk.Frame(frame)
        grid.pack(fill="x")

        tests = [
            ("Test Pipeline Completa", "test_pipeline_completa.py", "Vision → Eval → Mouse"),
            ("Test Vocale", "test_voce_screenshot.py", "Microfono + Vosk + parser"),
            ("Test Visione", "test_carte_desktop.py", "Riconoscimento carte"),
            ("Test 6-max", "test_6max_vision.py", "Layout tavolo 6 giocatori"),
            ("Test 9-max", "test_9max_vision.py", "Layout tavolo 9 giocatori"),
            ("Test Calibrazione", "test_calibrazione_vision.py", "Ottimizza parametri"),
            ("Test Riconoscimento Hero", "test_hero_recognition.py", "Verifica identificazione Hero"),
        ]

        for i, (label, script, desc) in enumerate(tests):
            row = i // 2
            col = i % 2
            btn_frame = tk.Frame(grid)
            btn_frame.grid(row=row, column=col, sticky="w", padx=4, pady=2)
            ttk.Button(btn_frame, text=label,
                       command=lambda s=script: self._run_test(s)).pack(anchor="w")
            ttk.Label(btn_frame, text=desc, foreground="gray").pack(anchor="w")

        # Pulsante "Apri cartella test"
        ttk.Button(frame, text="📁 Apri cartella test",
                   command=self._open_test_folder).pack(anchor="w", pady=(8, 0))

    def _run_test(self, script_name):
        """Esegue uno script di test in un subprocess e mostra l'output."""
        import subprocess
        import threading

        test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test")
        script_path = os.path.join(test_dir, script_name)

        if not os.path.exists(script_path):
            from tkinter import messagebox
            messagebox.showerror("Errore", f"Script non trovato: {script_name}")
            return

        # Finestra di output
        win = tk.Toplevel(self.root)
        win.title(f"Test: {script_name}")
        win.geometry("700x500")

        text_widget = tk.Text(win, wrap="word", font=("Courier", 10))
        text_widget.pack(fill="both", expand=True, padx=5, pady=5)

        scrollbar = ttk.Scrollbar(text_widget)
        scrollbar.pack(side="right", fill="y")
        text_widget.configure(yscrollcommand=scrollbar.set)

        ttk.Button(win, text="Chiudi", command=win.destroy).pack(pady=5)

        def run():
            try:
                venv_python = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)),
                    ".venv", "bin", "python3"
                )
                if not os.path.exists(venv_python):
                    venv_python = sys.executable

                proc = subprocess.Popen(
                    [venv_python, "-u", script_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )

                for line in proc.stdout:
                    text_widget.insert("end", line)
                    text_widget.see("end")
                    win.update_idletasks()

                proc.wait()
                text_widget.insert("end", f"\n--- Script terminato (exit code: {proc.returncode}) ---\n")
            except Exception as e:
                text_widget.insert("end", f"\nERRORE: {e}\n")

        threading.Thread(target=run, daemon=True).start()

    def _open_test_folder(self):
        """Apre la cartella test nel file manager."""
        import subprocess
        test_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test")
        subprocess.Popen(["xdg-open", test_dir])

    # ==================================================================
    # BARRA AZIONI
    # ==================================================================
    def _build_action_bar(self):
        bar = tk.Frame(self.root)
        bar.pack(fill="x", padx=10, pady=8)
        ttk.Button(bar, text="Salva configurazione", command=self._save).pack(side="left", padx=(0, 6))
        ttk.Button(bar, text="Salva & Avvia", command=self._save_and_start).pack(side="left")
        ttk.Button(bar, text="Esci", command=self.root.destroy).pack(side="right")

        # Selettore tema colori (a destra, prima di Esci)
        theme_frame = tk.Frame(bar)
        theme_frame.pack(side="right", padx=(0, 12))
        tk.Label(theme_frame, text="🎨 Tema:", font=("", 9)).pack(side="left", padx=(0, 4))
        self.theme_var = tk.StringVar(value="Classica")
        theme_menu = tk.OptionMenu(theme_frame, self.theme_var, *THEMES.keys(),
                                    command=self._apply_theme)
        theme_menu.config(width=10, font=("", 9))
        theme_menu.pack(side="left")

    # ==================================================================
    # TEMA COLORI
    # ==================================================================
    def _apply_theme(self, theme_name=None):
        """Applica un tema colori a tutta la GUI."""
        if theme_name is None:
            theme_name = self.theme_var.get()
        t = THEMES.get(theme_name, THEMES["Classica"])

        # Root
        self.root.configure(bg=t["bg"])

        # Stile ttk
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=t["bg"], foreground=t["fg"])
        style.configure("TLabel", background=t["bg"], foreground=t["fg"])
        style.configure("TButton", background=t["btn_bg"], foreground=t["fg"])
        style.map("TButton",
                   background=[("active", t["accent"])],
                   foreground=[("active", t["fg"])])
        style.configure("TCheckbutton", background=t["bg"], foreground=t["fg"])
        style.configure("TCombobox", fieldbackground=t["entry_bg"],
                         background=t["btn_bg"], foreground=t["entry_fg"])
        style.configure("TEntry", fieldbackground=t["entry_bg"],
                         foreground=t["entry_fg"])
        style.configure("TLabelframe", background=t["bg"],
                         foreground=t["fg"])
        style.configure("TLabelframe.Label", background=t["bg"],
                         foreground=t["accent"])

        # Ricorsivo:_colora tutti i widget tk (Frame, Label, Entry, ecc.)
        self._color_widgets(self.root, t)

    def _color_widgets(self, widget, t):
        """Colora ricorsivamente i widget tk."""
        try:
            wclass = widget.winfo_class()
            if wclass in ("Frame", "Labelframe"):
                widget.configure(bg=t["frame_bg"])
            elif wclass == "Label":
                fg = t.get("muted_fg", t["fg"])
                try:
                    cur = widget.cget("foreground")
                    if cur in ("#666", "#999", "gray", "gray50"):
                        fg = t["muted_fg"]
                except Exception:
                    pass
                widget.configure(bg=t["bg"], fg=fg)
            elif wclass == "Entry":
                widget.configure(bg=t["entry_bg"], fg=t["entry_fg"],
                                 insertbackground=t["fg"])
            elif wclass == "Frame":
                widget.configure(bg=t["frame_bg"])
        except Exception:
            pass

        for child in widget.winfo_children():
            self._color_widgets(child, t)

    # ==================================================================
    # CARICA / SALVA
    # ==================================================================
    def _load_from_db(self):
        """Legge i valori correnti salvati nel DB per riempire i campi."""
        db.init_db()
        for key, var in self.vars.items():
            val = db.get_tournament_config(key)
            if val is None:
                continue
            try:
                if isinstance(var, tk.BooleanVar):
                    var.set(val in ("1", "True", "true", "yes"))
                else:
                    var.set(val)
            except Exception:
                pass

    def _collect_values(self):
        data = {}
        for key, var in self.vars.items():
            if isinstance(var, tk.BooleanVar):
                data[key] = "1" if var.get() else "0"
            else:
                data[key] = var.get().strip()
        return data

    def _save(self):
        try:
            db.init_db()
            values = self._collect_values()
            for key, val in values.items():
                db.save_tournament_config(key, val)
            messagebox.showinfo("Salvato", "Configurazione salvata nel DB (tournament_config).")
        except Exception as e:
            messagebox.showerror("Errore", f"Salvataggio fallito:\n{e}")

    def _write_config_runtime(self):
        """Scrive le opzioni scelte in config.py affinché main.py le legga all'avvio."""
        cfg_path = os.path.join(BASE_DIR, "config.py")
        values = self._collect_values()

        mapping = {
            "t_format": "TABLE_FORMAT",
            "cfg_playstyle": "DEFAULT_PLAYSTYLE",
            "hero_name": "HERO_NAME",
            "mod_gto": "USE_GTO_PREFLOP",
            "mod_debug": "DEBUG_MODE",
        }
        try:
            with open(cfg_path, "r", encoding="utf-8") as fh:
                content = fh.read()
            for gui_key, attr in mapping.items():
                if attr is None:
                    continue
                val = values.get(gui_key)
                pyval = val
                if isinstance(self.vars.get(gui_key), tk.BooleanVar):
                    pyval = "True" if val == "1" else "False"
                else:
                    pyval = repr(val)
                import re
                pattern = re.compile(rf"^{attr}\s*=.*$", re.MULTILINE)
                if pattern.search(content):
                    content = pattern.sub(f"{attr} = {pyval}", content)
            with open(cfg_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            return True
        except Exception as e:
            print(f"[GUI] Errore scrittura config.py: {e}")
            return False

    def _save_and_start(self):
        self._save()
        ok = self._write_config_runtime()
        if not ok:
            messagebox.showwarning("Attenzione",
                                   "Configurazione salvata nel DB, ma scrittura config.py fallita.")
        # Avvia main.py
        main_script = os.path.join(BASE_DIR, "main.py")
        try:
            self.root.withdraw()
            subprocess.Popen([sys.executable, main_script])
        except Exception as e:
            messagebox.showerror("Errore", f"Impossibile avviare main.py:\n{e}")


def main():
    root = tk.Tk()
    PokerGui(root)
    root.mainloop()


if __name__ == "__main__":
    main()