#!/usr/bin/env python3
# ============================================================
# Apri screenshot a dimensione REALE, senza cornici, ancorato a (0,0)
# ============================================================
# Mostra l'immagine a scala 1:1, in alto a sinistra, senza barre/bordi,
# esattamente come la cattura mss. Le coordinate sullo schermo =
# coordinate nello screenshot.
#
# Uso:
#   python3 view_shot.py <immagine.png>
#   python3 view_shot.py                      # scegli dal menu
# ============================================================

import sys
import os
import tkinter as tk
from PIL import Image, ImageTk

def show_pixel_perfect(path):
    """Mostra immagine a scala 1:1 in alto a sinistra senza cornici."""
    # Carica immagine a dimensione originale
    img = Image.open(path)
    w, h = img.size
    print(f"Immagine: {path}  ({w}x{h} px)")

    # Finestra senza decorazioni (no barra titolo, no bordi)
    root = tk.Tk()
    root.overrideredirect(True)  # rimuove tutte le cornici della finestra
    root.attributes("-topmost", True)

    # Posiziona in alto a sinistra (0,0) e usa dimensione reale
    root.geometry(f"{w}x{h}+0+0")

    # Render immagine
    tk_img = ImageTk.PhotoImage(img)
    canvas = tk.Canvas(root, width=w, height=h, highlightthickness=0, bd=0)
    canvas.pack()
    canvas.create_image(0, 0, anchor="nw", image=tk_img)

    def update_coords(event):
        # Mostra coordinata reale del pixel sotto il mouse
        canvas.itemconfig(coord_label, text=f"x={event.x}  y={event.y}")

    coord_label = canvas.create_text(
        10, h - 20, anchor="sw",
        text="x=0  y=0", fill="yellow", font=("Courier", 14), tags="coord"
    )
    canvas.tag_raise("coord")
    canvas.bind("<Motion>", update_coords)

    # Esci: tasto qualunque / click
    def quit_app(_=None):
        root.destroy()
    root.bind("<KeyPress>", quit_app)
    canvas.bind("<Button-1>", quit_app)

    print("=== MODALITA' PIXEL-PERFECT ===")
    print("  - Immagine a scala 1:1, ancorata a (0,0), senza cornici")
    print("  - Coordinata del mouse in giallo in basso a sinistra")
    print("  - Queste coordinate = coordinate reali dello screenshot")
    print("  - Premi un tasto o clicca per uscire")
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        show_pixel_perfect(sys.argv[1])
    else:
        # Menu: scegli uno screenshot recente dalla cartella
        import glob
        shots = sorted(glob.glob("shots/*.png") + glob.glob("*.png"),
                       key=os.path.getmtime, reverse=True)
        if not shots:
            print("Nessuno screenshot trovato. Passa un percorso: python3 view_shot.py <file>")
            sys.exit(1)
        print("Screenshot disponibili (recenti per primi):")
        for i, s in enumerate(shots[:10]):
            print(f"  {i+1}. {s}")
        choice = input("Scegli numero (Enter = primo): ").strip()
        idx = int(choice) - 1 if choice.isdigit() else 0
        show_pixel_perfect(shots[idx])