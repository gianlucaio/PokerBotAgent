#!/usr/bin/env python3
# ============================================================
# Apri screenshot del PROGETTO nel browser — immagine incorporata
# ============================================================
# Cerca gli screenshot nella cartella corretta del progetto:
#   /home/hack/Documenti/progetto_pokerbot/modalità-web-9max-2colori/
# (dove stanno i veri screenshot catturati durante le partite reali)
# e li apre nel browser a scala 1:1, ancorata 0,0, coordinate mouse in giallo.
#
# Uso:
#   python3 view_project_shots.py               # menu con tutti gli screenshot
#   python3 view_project_shots.py <file.png>    # apre uno specifico
# ============================================================

import sys
import os
import base64
import webbrowser

# Cartella dove stanno i veri screenshot del progetto
PROJECT_ROOTS = [
    "/home/hack/Documenti/progetto_pokerbot",
    "/home/hack/Documenti/progetto_pokerbot/holdem-agent",
]

def find_all_shots():
    """Trova tutti gli screenshot .png nel progetto (escludendo venv/cache)."""
    shots = []
    for root in PROJECT_ROOTS:
        for dirpath, dirnames, filenames in os.walk(root):
            # Salta cartelle inutili
            dirnames[:] = [d for d in dirnames if d not in ("venv", ".git", "__pycache__", "node_modules")]
            # Cerca le sottocartelle che contengono screenshot (es. modalità-web-9max-2colori)
            for fn in filenames:
                if fn.lower().endswith((".png", ".jpg", ".jpeg")):
                    shots.append(os.path.join(dirpath, fn))
    # Ordina per data modifica (più recenti prima)
    shots.sort(key=os.path.getmtime, reverse=True)
    return shots

def build_html(img_path):
    """Costruisce HTML con immagine INCORPORATA in base64 (scala 1:1, 0,0)."""
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Screenshot</title></head>
<body style="margin:0; padding:0; background:#000;">
  <img id="shot" src="data:image/png;base64,{b64}"
       style="display:block; margin:0; padding:0; width:auto; height:auto;">
  <div id="coord" style="position:fixed; bottom:10px; left:10px;
       background:rgba(0,0,0,0.7); color:#ff0; font:14px monospace;
       padding:4px 8px; border-radius:4px; z-index:99;">x=0 y=0</div>
  <script>
    const img = document.getElementById('shot');
    const coord = document.getElementById('coord');
    document.addEventListener('mousemove', (e) => {{
      const r = img.getBoundingClientRect();
      const x = Math.round(e.clientX - r.left);
      const y = Math.round(e.clientY - r.top);
      coord.textContent = 'x=' + x + '  y=' + y;
    }});
    document.title = 'Screenshot — premi F11 per fullscreen';
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    # Se passato un percorso, usalo direttamente
    if len(sys.argv) > 1 and os.path.exists(sys.argv[1]):
        img_path = sys.argv[1]
    elif len(sys.argv) > 1:
        # Percorso relativo alla cartella degli screenshot
        cand = os.path.join(PROJECT_ROOTS[0], sys.argv[1])
        if os.path.exists(cand):
            img_path = cand
        else:
            print(f"File non trovato: {sys.argv[1]}")
            sys.exit(1)
    else:
        # Menu con tutti gli screenshot del progetto
        all_shots = find_all_shots()
        if not all_shots:
            print("Nessuno screenshot trovato nel progetto.")
            sys.exit(1)
        print(f"Trovati {len(all_shots)} screenshot nel progetto. Recenti prima:\n")
        # Mostra i primi 20 per leggibilità
        show = all_shots[:20]
        for i, s in enumerate(show):
            rel = os.path.basename(s)
            size = os.path.getsize(s) // 1024
            print(f"  {i+1}. {rel}  ({size}KB)")
        if len(all_shots) > 20:
            print(f"  ... e altri {len(all_shots)-20} (scrivi il numero giusto)")
        choice = input("\nScegli numero (Enter = primo): ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
        img_path = show[min(idx, len(show)-1)]

    # Genera e apri HTML con immagine incorporata
    html = build_html(img_path)
    out_dir = os.path.join(PROJECT_ROOTS[1], "shots")
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "_view.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nApro: {os.path.basename(img_path)}")
    print(f"  → Immagine incorporata (base64), scala 1:1, ancorata 0,0, coordinate in giallo")

    # Apri l'HTML nel browser. NOTA: lo screenshot è già corretto così com'è
    # (la barra dell'indirizzo fa parte del frame del tavolo) quindi NON serve
    # alcun posizionamento/compensazione della finestra: basta mostrare la
    # pagina HTML con l'immagine incorporata a scala 1:1. Qualsiasi tentativo di
    # ancorare la finestra a (0,0) o di compensare barre introduce solo errori
    # (es. una title bar extra di Chrome --app che nel gioco non esiste).
    webbrowser.open("file://" + html_path)