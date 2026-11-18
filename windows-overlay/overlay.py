"""DDTank Helper Overlay - protótipo Windows; reconhecimento conservador por OCR."""
from __future__ import annotations
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
import tkinter as tk

try:
    import mss
    from PIL import Image, ImageTk, ImageOps, ImageEnhance, ImageFilter
    import pytesseract
    from vision import detect_minimap, detect_red_marker_x, detect_wind_direction
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
    "wind": ("VENTO ATUAL", "Selecione somente a seta e o número superiores de Força Vento; exclua rod.ant."),
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
        r.geometry("320x285+20+100")
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
        tk.Button(body, text="Executar diagnóstico", command=self.diagnose, bg="#3b345f", fg="white",
                  activebackground="#51477c", bd=0, font=("Segoe UI", 9, "bold")).pack(
                      fill="x", pady=(7, 0), ipady=5)
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
            return None
        with mss.mss() as sct:
            shot = sct.grab(region)
            img = Image.frombytes("RGB", shot.size, shot.rgb)

        if key == "distance":
            result = detect_minimap(img)
            value = result.get("distance")
            if value is None or not 0 <= value <= 100:
                return None
            return float(value)

        if key == "power":
            marker_x = detect_red_marker_x(img)
            if marker_x is None or img.width < 2:
                return None
            # Ainda é uma estimativa provisória; não tratar como força calibrada.
            return max(0.0, min(100.0, marker_x / (img.width - 1) * 100))

        if key == "wind":
            # A direção vem da seta do indicador superior. Se ela não for clara,
            # a leitura inteira falha em vez de reaproveitar o vento anterior.
            self.current_wind_direction = detect_wind_direction(img)
            if self.current_wind_direction is None or img.width < 8:
                return None
            # Inclui os dois algarismos coloridos; o ponto decimal pode ser vermelho.
            img = img.crop((int(img.width * 0.10), 0, img.width, img.height))
        else:
            self.current_wind_direction = None

        img = ImageOps.autocontrast(img.convert("L").resize((img.width * 3, img.height * 3)))
        img = ImageEnhance.Contrast(img).enhance(2.0).filter(ImageFilter.SHARPEN)
        raw = pytesseract.image_to_string(
            img, config="--psm 7 -c tessedit_char_whitelist=0123456789.,"
        )
        match = re.search(r"\d+(?:[.,]\d+)?", raw.replace(" ", ""))
        if not match:
            return None
        try:
            value = float(match.group(0).replace(",", "."))
        except ValueError:
            return None
        if key == "angle" and not 0 <= value <= 180:
            return None
        if key == "wind":
            # O indicador usa uma casa decimal. Se o OCR perder o ponto,
            # não aceite "17" como 1.7 nem "1" como 1.0.
            decimal_match = re.search(r"\d+[.,]\d", raw.replace(" ", ""))
            if not decimal_match:
                return None
            value = float(decimal_match.group(0).replace(",", "."))
            if not 0 <= value <= 5:
                return None
            return round(value, 1)
        return value


    def diagnose(self):
        """Captura uma amostra por região e mostra evidências brutas para depuração."""
        lines = [
            "DDTANK HELPER - RELATÓRIO DE DIAGNÓSTICO",
            f"Data/hora: {datetime.now().astimezone().isoformat(timespec='seconds')}",
            f"Resolução da tela: {self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}",
            "As capturas são analisadas localmente; nenhuma imagem é enviada.",
            ""
        ]
        for key, (title, _desc) in FIELDS.items():
            region = self.cfg.get("regions", {}).get(key)
            lines.append(f"===== {title} ({key}) =====")
            if not region:
                lines.append("Região: NÃO CONFIGURADA\n")
                continue
            lines.append(f"Região: left={region.get('left')}, top={region.get('top')}, "
                         f"width={region.get('width')}, height={region.get('height')}")
            try:
                with mss.mss() as sct:
                    shot = sct.grab(region)
                    img = Image.frombytes("RGB", shot.size, shot.rgb)
                lines.append(f"Captura: {img.width}x{img.height}")
                if img.width < 2 or img.height < 2:
                    lines.append("ERRO: região muito pequena")
                    continue

                total = img.width * img.height
                red = blue = bright = 0
                for rr, gg, bb in img.getdata():
                    mx, mn = max(rr, gg, bb), min(rr, gg, bb)
                    if rr >= 90 and rr > gg * 1.35 and rr > bb * 1.25:
                        red += 1
                    if bb >= 75 and bb > rr * 1.20 and bb > gg * 1.10:
                        blue += 1
                    if mn >= 185 and mx - mn <= 35:
                        bright += 1
                lines.append(f"Pixels: vermelho={red} ({red/total:.1%}), "
                             f"azul={blue} ({blue/total:.1%}), claros={bright} ({bright/total:.1%})")

                if key in ("angle", "wind"):
                    if key == "wind":
                        direction = detect_wind_direction(img)
                        lines.append(f"Direção da seta do vento atual: {direction or 'não detectada'}")
                        # Inclui os dois algarismos; o ponto decimal pode ser vermelho.
                        ocr_source = img.crop((int(img.width * 0.10), 0, img.width, img.height))
                    else:
                        ocr_source = img
                    gray = ocr_source.convert("L")
                    processed = ImageOps.autocontrast(
                        gray.resize((ocr_source.width * 3, ocr_source.height * 3)))
                    processed = ImageEnhance.Contrast(processed).enhance(2.0).filter(ImageFilter.SHARPEN)
                    raw = pytesseract.image_to_string(
                        processed, config="--psm 7 -c tessedit_char_whitelist=0123456789.,")
                    lines.append(f"OCR bruto: {raw.strip()!r}")
                    if key == "wind":
                        match = re.search(r"\d+[.,]\d", raw.replace(" ", ""))
                        lines.append(f"Intensidade decimal interpretada: {match.group(0) if match else 'nenhuma (OCR precisa preservar a casa decimal)'}")
                    else:
                        match = re.search(r"\d+(?:[.,]\d+)?", raw.replace(" ", ""))
                        lines.append(f"Número interpretado: {match.group(0) if match else 'nenhum'}")
                elif key == "distance":
                    result = detect_minimap(img)
                    lines.append(f"Marcador jogador (azul): {result.get('player')}")
                    lines.append(f"Marcador alvo (vermelho): {result.get('target')}")
                    lines.append(f"Espaçamento da grade (px): {result.get('grid_spacing_px')}")
                    lines.append(f"Distância calculada: {result.get('distance')}")
                else:
                    marker = detect_red_marker_x(img)
                    lines.append(f"Centro do marcador vermelho X: {marker}")
                    if marker is not None:
                        lines.append(f"Força estimada atual: {marker / (img.width - 1) * 100:.1f}")
                    else:
                        lines.append("Força estimada atual: não detectada")
            except Exception as exc:
                lines.append(f"ERRO NA CAPTURA/ANÁLISE: {type(exc).__name__}: {exc}")
            lines.append("")

        report = "\n".join(lines)
        folder = BASE / "diagnostics"
        folder.mkdir(exist_ok=True)
        report_path = folder / "diagnostico.txt"
        report_path.write_text(report, encoding="utf-8")

        win = tk.Toplevel(self.root)
        win.title("Diagnóstico do reconhecimento")
        win.geometry("680x560")
        win.configure(bg="#101827")
        win.attributes("-topmost", True)
        tk.Label(win, text="Relatório gerado localmente", bg="#101827", fg="#77e6f2",
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=12, pady=(10, 4))
        tk.Label(win, text=f"Arquivo salvo em: {report_path}", bg="#101827", fg="#9eb0c9",
                 wraplength=650, justify="left").pack(anchor="w", padx=12, pady=(0, 7))
        area = tk.Text(win, wrap="word", bg="#0b1220", fg="#dce7f5",
                       insertbackground="white", font=("Consolas", 9), height=25)
        area.pack(fill="both", expand=True, padx=12, pady=4)
        area.insert("1.0", report)
        area.configure(state="disabled")

        def copy_report():
            self.root.clipboard_clear()
            self.root.clipboard_append(report)
            self.status.config(text="Relatório copiado; cole-o aqui na conversa")

        buttons = tk.Frame(win, bg="#101827")
        buttons.pack(fill="x", padx=12, pady=10)
        tk.Button(buttons, text="Copiar relatório", command=copy_report, bg="#1e4960",
                  fg="white", bd=0, padx=12, pady=7).pack(side="left")
        tk.Button(buttons, text="Fechar", command=win.destroy, bg="#263a55",
                  fg="white", bd=0, padx=12, pady=7).pack(side="right")
        self.status.config(text="Diagnóstico salvo localmente")

    def refresh(self):
        if not self.running:
            return
        # Só confirma uma leitura depois de 3 amostras próximas.
        if not hasattr(self, "samples"):
            from collections import deque
            self.samples = {k: deque(maxlen=3) for k in FIELDS}
            self.wind_direction_samples = deque(maxlen=3)
            self.current_wind_direction = None
            self.last_good = {k: None for k in FIELDS}
            self.last_good_at = {k: 0 for k in FIELDS}
        import time
        now = time.monotonic()
        tolerances = {"angle": 1.0, "wind": 0.15, "distance": 1.0, "power": 2.0}
        try:
            for key in FIELDS:
                value = self.read_region(key)
                samples = self.samples[key]
                if key == "wind":
                    if value is not None and self.current_wind_direction:
                        self.wind_direction_samples.append(self.current_wind_direction)
                    else:
                        self.wind_direction_samples.clear()
                        samples.clear()
                        # Nunca mantenha o vento da rodada anterior como se fosse atual.
                        self.last_good[key] = None
                if value is not None:
                    samples.append(float(value))
                elif key != "wind":
                    samples.clear()

                shown = "Aguardando" if key not in self.cfg.get("regions", {}) else "Lendo..."
                if len(samples) == 3:
                    spread = max(samples) - min(samples)
                    direction_stable = (
                        key != "wind" or
                        (len(self.wind_direction_samples) == 3 and
                         len(set(self.wind_direction_samples)) == 1)
                    )
                    if spread <= tolerances[key] and direction_stable:
                        stable = sum(samples) / len(samples)
                        self.last_good[key] = stable
                        self.last_good_at[key] = now
                        shown = f"{stable:.1f}" if key in ("wind", "distance") else f"{stable:.0f}"
                        if key == "wind":
                            shown += " " + ("←" if self.wind_direction_samples[-1] == "left" else "→")
                    elif key == "wind":
                        shown = "Estabilizando"
                    else:
                        # Mantém a última leitura validada por pouco tempo; não oscila com ruído.
                        if self.last_good[key] is not None and now - self.last_good_at[key] <= 1.5:
                            stable = self.last_good[key]
                            shown = f"{stable:.1f}" if key in ("wind", "distance") else f"{stable:.0f}"
                        else:
                            shown = "Estabilizando"
                elif key == "wind":
                    shown = "Não detectado" if value is None else "Estabilizando"
                elif self.last_good[key] is not None and now - self.last_good_at[key] <= 1.5:
                    stable = self.last_good[key]
                    shown = f"{stable:.1f}" if key in ("wind", "distance") else f"{stable:.0f}"
                elif key in self.cfg.get("regions", {}):
                    shown = "Não detectado" if value is None else "Estabilizando"

                suffix = "°" if key == "angle" and shown not in ("Aguardando", "Lendo...", "Não detectado", "Estabilizando") else ""
                self.labels[key].config(text=shown + suffix)

            configured = sum(1 for k in FIELDS if k in self.cfg.get("regions", {}))
            self.status.config(text=("Calibre as regiões para iniciar" if configured == 0
                                     else f"Filtro de estabilidade • {configured}/{len(FIELDS)} regiões"))
        except Exception as exc:
            self.status.config(text=f"Falha na captura: {str(exc)[:42]}")
        self.root.after(max(500, int(self.cfg.get("poll_ms", 650))), self.refresh)

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
