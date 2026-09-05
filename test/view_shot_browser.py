#!/usr/bin/env python3
# ============================================================
# Apri screenshot nel BROWSER — immagine INCORPORATA (base64), scala 1:1
# ============================================================
# L'immagine è incorporata direttamente nel file HTML come base64:
# nessuna dipendenza da percorsi file → il browser la mostra SEMPRE.
# Scala 1:1, ancorata a 0,0, niente cornici, coordinate mouse in giallo.
#
# Uso:
#   python3 view_shot_browser.py <immagine.png>
#   python3 view_shot_browser.py              # menu screenshot da shots/
# ============================================================

import sys
import os
import glob
import base64
import webbrowser

def build_html(img_path):
    """Costruisce HTML con immagine INCORPORATA in base64."""
    with open(img_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Screenshot Pixel-Perfect</title>
</head>
<body style="margin:0; padding:0; background:#000;">
  <!-- Immagine incorporata, scala 1:1, ancorata a 0,0 -->
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
    // Coordinata=0,0 se il mouse è sopra l'immagine all'angolo
    document.title = 'Screenshot — premi F11 per fullscreen';
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
    else:
        base = os.path.dirname(os.path.abspath(__file__))
        shots = sorted(glob.glob(os.path.join(base, "shots", "*.png")))
        if not shots:
            print("Nessuno screenshot in shots/. Passa un percorso: python3 view_shot_browser.py <file>")
            sys.exit(1)
        print("Screenshot disponibili:")
        for i, s in enumerate(shots):
            print(f"  {i+1}. {os.path.basename(s)}")
        choice = input("Scegli numero (Enter = primo): ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
        img_path = shots[min(idx, len(shots)-1)]

    if not os.path.exists(img_path):
        print(f"File non trovato: {img_path}")
        sys.exit(1)

    html = build_html(img_path)
    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shots")
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "_view.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Apro nel browser: {img_path}")
    print("  → Immagine incorporata (base64), scala 1:1, ancorata 0,0")
    print("  → Premi F11 per fullscreen, coordinate mouse in giallo in basso")
    webbrowser.open("file://" + html_path)