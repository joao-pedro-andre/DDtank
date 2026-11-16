"""DDTank Helper Overlay - protótipo Windows; reconhecimento conservador por OCR."""
from __future__ import annotations
import json
import re
import shutil
from pathlib import Path
import tkinter as tk

try:
    import mss
    from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter
    import pytesseract
    from vision import detect_minimap, detect_red_marker_x
except ImportError as exc:
    raise SystemExit(f"Dependência ausente: {exc}. Execute instalar.bat primeiro.")

BASE = Path(__file__).resolve().parent
CONFIG = BASE / "config.json"
if not shutil.which("tesseract"):
    for candidate in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                      r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate

DEFAULTS = {"regions": {}, "poll_ms": 650, "always_on_top": True}
FIELDS = {
    "angle": ("ÂNGULO", "Número exibido no medidor circular"),
    "wind": ("VENTO", "Intensidade numérica, se estiver visível"),
    "distance": ("DISTÂNCIA", "Selecione o minimapa completo para localizar azul e vermelho"),
    "power": ("FORÇA", "Selecione a barra inteira, incluindo o marcador vermelho"),
}


def load_config():
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        return {**DEFAULTS, **data, "regions": data.get("regions", {})}
    except Exception:
        return json.loads(json.dumps(DEFAULTS))


class Overlay:
    def __init__(self, root):
        self.root = root
        self.cfg = load_config()
        self.running = True
        self.visible = True
        self.keyboard = None
        self._build()
        self._register_hotkey()
        self.root.after(400, self.refresh)
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self):
        r = self.root
        r.title("DDTank Helper")
        r.geometry("320x250+20+100")
        r.resizable(False, False)
        r.attributes("-topmost", bool(self.cfg.get("always_on_top", True)))
        r.attributes("-alpha", 0.94)
        r.configure(bg="#101827")
        head = tk.Frame(r, bg="#17263b", height=34)
        head.pack(fill="x")
        tk.Label(head, text="DDTANK  /  ASSISTENTE", bg="#17263b", fg="#77e6f2",
                 font=("Segoe UI", 9, "bold")).pack(side="left", padx=10, pady=8)
        tk.Button(head, text="—", command=self.hide, bg="#263a55", fg="white",
                  activebackground="#385578", width=3, bd=0).pack(side="right", padx=5, pady=4)
        body = tk.Frame(r, bg="#101827", padx=12, pady=8)
        body.pack(fill="both", expand=True)
        self.labels = {}
        for key in FIELDS:
            line = tk.Frame(body, bg="#101827")
            line.pack(fill="x", pady=2)
            tk.Label(line, text=FIELDS[key][0], width=11, anchor="w", bg="#101827",
                     fg="#9eb0c9", font=("Segoe UI", 9, "bold")).pack(side="left")
            value = tk.Label(line, text="—", anchor="e", bg="#101827", fg="#70e3ad",
                             font=("Segoe UI", 15, "bold"))
            value.pack(side="right")
            self.labels[key] = value
        self.status = tk.Label(body, text="Aguardando calibração das regiões", bg="#101827",
                               fg="#e8bd68", anchor="w", font=("Segoe UI", 8))
        self.status.pack(fill="x", pady=(5, 6))
        buttons = tk.Frame(body, bg="#101827")
        buttons.pack(fill="x")
        tk.Button(buttons, text="Calibrar", command=self.calibrate_menu, bg="#1e4960", fg="white",
                  activebackground="#28627c", bd=0, font=("Segoe UI", 9, "bold")).pack(
                      side="left", fill="x", expand=True, padx=(0, 4), ipady=5)
        tk.Button(buttons, text="Configurações", command=self.settings, bg="#263a55", fg="white",
                  activebackground="#385578", bd=0, font=("Segoe UI", 9)).pack(
                      side="left", fill="x", expand=True, padx=(4, 0), ipady=5)
        tk.Label(body, text="F8: mostrar/ocultar  •  F9: calibrar ângulo", bg="#101827",
                 fg="#71839d", font=("Segoe UI", 7)).pack(anchor="w", pady=(6, 0))

    def _register_hotkey(self):
        try:
            import keyboard
            keyboard.add_hotkey("F8", lambda: self.root.after(0, self.toggle))
            keyboard.add_hotkey("F9", lambda: self.root.after(0, lambda: self.start_calibration("angle")))
            self.keyboard = keyboard
        except Exception:
            self.status.config(text="Atalhos globais indisponíveis; use os botões")

    def hide(self):
        self.visible = False
        self.root.withdraw()

    def show(self):
        self.visible = True
        self.root.deiconify()
        self.root.attributes("-topmost", bool(self.cfg.get("always_on_top", True)))

    def toggle(self):
        self.show() if not self.visible else self.hide()

    def calibrate_menu(self):
        win = tk.Toplevel(self.root)
        win.title("Calibrar reconhecimento")
        win.configure(bg="#101827")
        win.attributes("-topmost", True)
        tk.Label(win, text="Selecione na tela a área que contém o valor:", bg="#101827",
                 fg="white", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(12, 6))
        for key, (title, desc) in FIELDS.items():
            tk.Button(win, text=f"{title} — {desc}", anchor="w",
                      command=lambda k=key: (win.destroy(), self.start_calibration(k)),
                      bg="#20334d", fg="white", bd=0, padx=10, pady=8).pack(fill="x", padx=12, pady=3)
        tk.Label(win, text="A força é uma barra gráfica; será calibrada em uma etapa própria.",
                 bg="#101827", fg="#e8bd68", wraplength=340, justify="left").pack(padx=12, pady=10)

    def start_calibration(self, key):
        self.hide()
        self.root.update_idletasks()
        with mss.mss() as sct:
            shot = sct.grab(sct.monitors[0])
            image = Image.frombytes("RGB", shot.size, shot.rgb)
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        scale = min(screen_w / image.width, screen_h / image.height)
        display = image.resize((int(image.width * scale), int(image.height * scale)))
        top = tk.Toplevel(self.root)
        top.attributes("-fullscreen", True)
        top.attributes("-topmost", True)
        top.configure(bg="black")
        canvas = tk.Canvas(top, width=screen_w, height=screen_h, cursor="crosshair", highlightthickness=0)
        canvas.pack(fill="both", expand=True)
        photo = ImageTk.PhotoImage(display)
        canvas.create_image(0, 0, image=photo, anchor="nw")
        canvas.image = photo
        canvas.create_text(20, screen_h - 28, anchor="w",
                           text=f"Selecione a região de {FIELDS[key][0]} • ESC cancela",
                           fill="#ffff88", font=("Segoe UI", 14, "bold"))
        start = {}
        rect = None

        def down(event):
            nonlocal rect
            start["x"], start["y"] = event.x, event.y
            rect = canvas.create_rectangle(event.x, event.y, event.x, event.y,
                                           outline="#00ffff", width=3)

        def drag(event):
            if rect is not None:
                canvas.coords(rect, start["x"], start["y"], event.x, event.y)

        def up(event):
            x1, y1 = start["x"], start["y"]
            x2, y2 = event.x, event.y
            left, topy = min(x1, x2), min(y1, y2)
            width, height = abs(x2-x1), abs(y2-y1)
            if width < 5 or height < 5:
                return
            self.cfg["regions"][key] = {
                "left": int(left / scale), "top": int(topy / scale),
                "width": int(width / scale), "height": int(height / scale)
            }
            CONFIG.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")
            top.destroy()
            self.show()
            self.status.config(text=f"Região {FIELDS[key][0]} salva")

        canvas.bind("<ButtonPress-1>", down)
        canvas.bind("<B1-Motion>", drag)
        canvas.bind("<ButtonRelease-1>", up)
        top.bind("<Escape>", lambda _e: (top.destroy(), self.show()))

    def settings(self):
        win = tk.Toplevel(self.root)
        win.title("Configurações")
        win.configure(bg="#101827")
        win.attributes("-topmost", True)
        tk.Label(win, text="Sempre no topo", bg="#101827", fg="white").pack(anchor="w", padx=12, pady=(12, 3))
        top_var = tk.BooleanVar(value=bool(self.cfg.get("always_on_top", True)))
        tk.Checkbutton(win, text="Manter janela sobre o jogo", variable=top_var, bg="#101827",
                       fg="white", selectcolor="#20334d", activebackground="#101827",
                       activeforeground="white").pack(anchor="w", padx=12)

        def save():
            self.cfg["always_on_top"] = top_var.get()
            CONFIG.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")
            self.root.attributes("-topmost", top_var.get())
            win.destroy()

        tk.Button(win, text="Salvar", command=save, bg="#1e4960", fg="white",
                  bd=0, padx=16, pady=7).pack(pady=12)

    def read_region(self, key):
        region = self.cfg.get("regions", {}).get(key)
        if not region:
            return "—"
        with mss.mss() as sct:
            shot = sct.grab(region)
            img = Image.frombytes("RGB", shot.size, shot.rgb)

        if key == "distance":
            result = detect_minimap(img)
            if result["distance"] is None:
                return "?"
            return f'{result["distance"]:.1f}'

        if key == "power":
            marker_x = detect_red_marker_x(img)
            if marker_x is None or img.width < 2:
                return "?"
            value = max(0, min(100, marker_x / (img.width - 1) * 100))
            return f"{value:.0f}"

        img = ImageOps.autocontrast(img.convert("L").resize((img.width * 3, img.height * 3)))
        img = ImageEnhance.Contrast(img).enhance(2.0).filter(ImageFilter.SHARPEN)
        raw = pytesseract.image_to_string(
            img, config="--psm 7 -c tessedit_char_whitelist=0123456789.,"
        )
        match = re.search(r"\d+(?:[.,]\d+)?", raw.replace(" ", ""))
        return match.group(0).replace(",", ".") if match else "?"

    def refresh(self):
        if not self.running:
            return
        try:
            for key in FIELDS:
                value = self.read_region(key)
                suffix = "°" if key == "angle" and value not in ("—", "?") else ""
                self.labels[key].config(text=value + suffix)
            configured = sum(1 for k in FIELDS if k in self.cfg.get("regions", {}))
            self.status.config(text=("Calibre as regiões para iniciar a leitura" if configured == 0
                                     else f"Leitura experimental • {configured}/{len(FIELDS)} regiões calibradas"))
        except Exception as exc:
            self.status.config(text=f"Falha na captura/OCR: {str(exc)[:42]}")
        self.root.after(max(350, int(self.cfg.get("poll_ms", 650))), self.refresh)

    def close(self):
        self.running = False
        if self.keyboard:
            try:
                self.keyboard.unhook_all()
            except Exception:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = Overlay(root)
    root.mainloop()
