#!/usr/bin/env python3
"""
Espelhar celular — assistente em customtkinter para scrcpy + adb (macOS).

Fluxo:
  0. Tela de Boas-vindas (Glass)
  1. Aparelho: escolher um aparelho salvo ou parear um novo
  2. Preparar ferramentas (localizar scrcpy/adb e liberar o bloqueio do macOS)
  3. Parear com o celular (depuração sem fio) — só para aparelhos novos
  4. Conectar (Wi-Fi ou USB) — aparelhos salvos pedem apenas a porta
  5. Espelhamento
  6. Contribua: QR code para apoiar o desenvolvedor
  7. Dash: detalhes do aparelho conectado

Instalar:  pip3 install customtkinter pillow
Executar:  python3 espelhar_celular_ctk.py
"""
import json
import os
import platform
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import uuid
from functools import lru_cache
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk

# ----------------------------------------------------------------------------
# Paleta (tema claro)
# ----------------------------------------------------------------------------
BG = "#F6F8FB"
SURFACE = "#FFFFFF"
INK = "#1F2937"
MUTED = "#667085"
LINE = "#E4E8EF"
FIELD_LINE = "#D0D7E2"
CARD = "#F2F5FA"
IDLE = "#B8C1D0"
SOFT_TEXT = "#98A2B3"
DISABLED_TEXT = "#D0D5DD"

ACCENT = "#1A73E8"
ACCENT_DARK = "#1765CC"
ACCENT_SOFT = "#E8F0FE"
ACCENT_CIRCLE = "#4C9EEB"  # azul mais claro para o círculo dos botões

OK = "#1E8E3E"
OK_DARK = "#15692D"
OK_CIRCLE = "#46C665"  # verde mais claro para o círculo quando emparelhado

ERR = "#D93025"
ERR_DARK = "#B3261E"
ERR_SOFT = "#FDECEA"
ERR_FADED = "#F2B8B5"
STOP_GRAY = "#E4E8EF"
STOP_GRAY_GLYPH = "#98A2B3"

PURPLE_BTN = "#EED6FF"
PURPLE_BTN_HOVER = "#DEC2FF"
PURPLE_TEXT = "#6B21A8"

# ----------------------------------------------------------------------------
# Configuração e constantes gerais
# ----------------------------------------------------------------------------
FONT = "Helvetica Neue"
CFG_PATH = Path.home() / ".espelhar_celular.json"
ADDR_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}:\d{2,5}$")
PORT_RE = re.compile(r"^\d{2,5}$")

# Etapas da barra lateral (título, subtítulo)
STEPS = [
    ("Aparelho", "Escolher ou parear novo"),
    ("Preparar ferramentas", "Localizar scrcpy e adb"),
    ("Parear com o celular", "Código de pareamento"),
    ("Conectar", "Por Wi-Fi"),
    ("Espelhamento", "Espelhar tela"),
    ("Contribua", "Apoie o desenvolvedor"),  # última etapa, sem número
]
STEP_DEVICE, STEP_TOOLS, STEP_PAIR, STEP_CONN, STEP_MIRROR, STEP_CONTRIB = range(len(STEPS))

# Páginas: as etapas da barra lateral começam em S_DEVICE (página = etapa + PAGE_OFFSET)
(S_WELCOME, S_TUTORIAL, S_DEVICE, S_TOOLS, S_PAIR, S_CONN, S_MIRROR, S_CONTRIB,
 S_DASH) = range(9)
PAGE_OFFSET = S_DEVICE

# Botões
BUTTON_H = 40
BUTTON_STYLES = {
    "primary": dict(fg_color=ACCENT, hover_color=ACCENT_DARK, text_color="white", border_width=0),
    "success": dict(fg_color=OK, hover_color=OK_DARK, text_color="white", border_width=0),
    "danger": dict(fg_color=ERR, hover_color=ERR_DARK, text_color="white", border_width=0),
    "purple": dict(fg_color=PURPLE_BTN, hover_color=PURPLE_BTN_HOVER, text_color=PURPLE_TEXT,
                   border_width=0),
    "secondary": dict(fg_color=SURFACE, hover_color=ACCENT_SOFT, text_color=ACCENT,
                      border_width=1, border_color=FIELD_LINE),
}
CIRCLE_COLORS = {"primary": ACCENT_CIRCLE, "secondary": ACCENT_CIRCLE, "success": OK_CIRCLE}
ICON_CIRCLE = 28  # diâmetro do círculo do ícone
ICON_GLYPH = 14   # tamanho do ícone dentro do círculo

# Página Contribua
QR_FILE = "qr.png"
QR_SIZE = 260
CONTRIB_ICON_FILE = "cora.png"

# Painel suspenso "Detalhes dos comandos"
LOG_BAR_H = 34
LOG_PANEL_H = 190
LOG_TEXT_CLOSED = "Detalhes dos comandos  ▴"
LOG_TEXT_OPEN = "Detalhes dos comandos  ▾"

# ----------------------------------------------------------------------------
# Base de Dados Interna de Modelos (2017 até agora) e Ícones de Marca
# ----------------------------------------------------------------------------
DEVICE_DATABASE = {
    # --- SAMSUNG ---
    "SM-S928": ("Samsung Galaxy S24 Ultra", "samsung.png"),
    "SM-S926": ("Samsung Galaxy S24+", "samsung.png"),
    "SM-S921": ("Samsung Galaxy S24", "samsung.png"),
    "SM-S918": ("Samsung Galaxy S23 Ultra", "samsung.png"),
    "SM-S916": ("Samsung Galaxy S23+", "samsung.png"),
    "SM-S911": ("Samsung Galaxy S23", "samsung.png"),
    "SM-S908": ("Samsung Galaxy S22 Ultra", "samsung.png"),
    "SM-S906": ("Samsung Galaxy S22+", "samsung.png"),
    "SM-S901": ("Samsung Galaxy S22", "samsung.png"),
    "SM-G998": ("Samsung Galaxy S21 Ultra", "samsung.png"),
    "SM-G996": ("Samsung Galaxy S21+", "samsung.png"),
    "SM-G991": ("Samsung Galaxy S21", "samsung.png"),
    "SM-G988": ("Samsung Galaxy S20 Ultra", "samsung.png"),
    "SM-G986": ("Samsung Galaxy S20+", "samsung.png"),
    "SM-G980": ("Samsung Galaxy S20", "samsung.png"),
    "SM-G781": ("Samsung Galaxy S20 FE", "samsung.png"),
    "SM-G780": ("Samsung Galaxy S20 FE", "samsung.png"),
    "SM_G781": ("Samsung Galaxy S20 FE", "samsung.png"),
    "SM_G780": ("Samsung Galaxy S20 FE", "samsung.png"),
    "SM-G975": ("Samsung Galaxy S10+", "samsung.png"),
    "SM-G973": ("Samsung Galaxy S10", "samsung.png"),
    "SM-G970": ("Samsung Galaxy S10e", "samsung.png"),
    "SM-G965": ("Samsung Galaxy S9+", "samsung.png"),
    "SM-G960": ("Samsung Galaxy S9", "samsung.png"),
    "SM-G955": ("Samsung Galaxy S8+", "samsung.png"),
    "SM-G950": ("Samsung Galaxy S8", "samsung.png"),
    "SM-F946": ("Samsung Galaxy Z Fold5", "samsung.png"),
    "SM-F731": ("Samsung Galaxy Z Flip5", "samsung.png"),
    "SM-F936": ("Samsung Galaxy Z Fold4", "samsung.png"),
    "SM-F721": ("Samsung Galaxy Z Flip4", "samsung.png"),
    "SM-F926": ("Samsung Galaxy Z Fold3", "samsung.png"),
    "SM-F711": ("Samsung Galaxy Z Flip3", "samsung.png"),
    "SM-A546": ("Samsung Galaxy A54 5G", "samsung.png"),
    "SM-A536": ("Samsung Galaxy A53 5G", "samsung.png"),
    "SM-A525": ("Samsung Galaxy A52", "samsung.png"),
    "SM-A515": ("Samsung Galaxy A51", "samsung.png"),
    "SM-A736": ("Samsung Galaxy A73 5G", "samsung.png"),
    "SM-A346": ("Samsung Galaxy A34 5G", "samsung.png"),
    "SM-A256": ("Samsung Galaxy A25", "samsung.png"),
    "SM-A156": ("Samsung Galaxy A15", "samsung.png"),

    # --- MOTOROLA ---
    "XT2401": ("Motorola Edge 50 Pro", "motorola.png"),
    "XT2303": ("Motorola Razr 40", "motorola.png"),
    "XT2341": ("Motorola Edge 40", "motorola.png"),
    "XT2243": ("Moto G72", "motorola.png"),
    "XT2211": ("Moto G22", "motorola.png"),
    "XT2131": ("Moto G60", "motorola.png"),
    "XT2125": ("Moto G100", "motorola.png"),
    "XT2091": ("Moto G9 Plus", "motorola.png"),
    "XT2043": ("Moto G8 Power", "motorola.png"),
    "XT1965": ("Moto G7 Plus", "motorola.png"),
    "XT1922": ("Moto G6", "motorola.png"),

    # --- XIAOMI ---
    "23127PN0CG": ("Xiaomi 14 Pro", "xiaomi.png"),
    "23117RK66C": ("Xiaomi K70", "xiaomi.png"),
    "2306EPN60G": ("Xiaomi 13T Pro", "xiaomi.png"),
    "22101316G": ("Xiaomi 13", "xiaomi.png"),
    "2112123G": ("Xiaomi 12", "xiaomi.png"),
    "M2101K9G": ("Xiaomi Mi 11 Lite", "xiaomi.png"),
    "M2007J20CG": ("Xiaomi Mi 10T Pro", "xiaomi.png"),
    "M1901F7G": ("Xiaomi Mi 9", "xiaomi.png"),
    "23078PC58G": ("POCO X6 Pro", "xiaomi.png"),
    "2312FPCA6G": ("POCO X6", "xiaomi.png"),
    "2201116SG": ("POCO X4 Pro 5G", "xiaomi.png"),
    "21091116AI": ("Xiaomi Redmi Note 11", "xiaomi.png"),
    "2201117TY": ("Xiaomi Redmi Note 11 Pro", "xiaomi.png"),
    "23021RAAEG": ("Xiaomi Redmi Note 12", "xiaomi.png"),
    "2312DRA5BC": ("Xiaomi Redmi Note 13 Pro", "xiaomi.png"),

    # --- HUAWEI ---
    "ALT-L29": ("Huawei Pura 70", "hawei.png"),
    "MNA-LX9": ("Huawei P60 Pro", "hawei.png"),
    "CET-LX9": ("Huawei Mate 60 Pro", "hawei.png"),
    "JAD-LX9": ("Huawei P50 Pro", "hawei.png"),
    "ANA-NX9": ("Huawei P40 Pro", "hawei.png"),
    "ELS-NX9": ("Huawei P40 Pro+", "hawei.png"),
    "MAR-LX1A": ("Huawei P30 Lite", "hawei.png"),
    "VOG-L29": ("Huawei P30 Pro", "hawei.png"),
    "CLT-L29": ("Huawei P20 Pro", "hawei.png"),
    "BLA-L29": ("Huawei Mate 10 Pro", "hawei.png"),

    # --- OPPO ---
    "CPH2581": ("Oppo Find X7", "oppo.png"),
    "CPH2451": ("Oppo Find X5 Pro", "oppo.png"),
    "CPH2389": ("Oppo Reno 8", "oppo.png"),
    "CPH2525": ("Oppo Reno 10 Pro", "oppo.png"),
    "CPH2239": ("Oppo Reno 6", "oppo.png"),
    "CPH2015": ("Oppo Find X2", "oppo.png"),
    "CPH1931": ("Oppo Reno", "oppo.png"),

    # --- APPLE ---
    "iPhone16,2": ("Apple iPhone 15 Pro Max", "apple.png"),
    "iPhone16,1": ("Apple iPhone 15 Pro", "apple.png"),
    "iPhone15,4": ("Apple iPhone 15", "apple.png"),
    "iPhone15,2": ("Apple iPhone 14 Pro", "apple.png"),
    "iPhone14,7": ("Apple iPhone 14", "apple.png"),
    "iPhone14,3": ("Apple iPhone 13 Pro Max", "apple.png"),
    "iPhone13,4": ("Apple iPhone 12 Pro Max", "apple.png"),
    "iPhone12,1": ("Apple iPhone 11", "apple.png"),
    "iPhone11,8": ("Apple iPhone XR", "apple.png"),
    "iPhone10,6": ("Apple iPhone X", "apple.png"),
    "iPhone9,3": ("Apple iPhone 7", "apple.png"),
    "iPhone8,1": ("Apple iPhone 6s", "apple.png"),
}


def identify_device(raw_model):
    """Identifica o nome comercial e o ícone com base no modelo do ADB."""
    if not raw_model:
        return "Dispositivo Android", "default.png"

    clean = raw_model.strip().replace("_", "-")
    clean_raw = raw_model.strip()

    for key, (market_name, icon_file) in DEVICE_DATABASE.items():
        key_norm = key.replace("_", "-")
        if key_norm.upper() in clean.upper() or clean.upper() in key_norm.upper():
            return market_name, icon_file
        if key.upper() in clean_raw.upper():
            return market_name, icon_file

    upper = clean.upper()
    if any(k in upper for k in ["SM-", "SAMSUNG", "GALAXY"]):
        return clean, "samsung.png"
    elif any(k in upper for k in ["XT", "MOTO", "MOTOROLA"]):
        return clean, "motorola.png"
    elif any(k in upper for k in ["IPHONE", "APPLE"]):
        return clean, "apple.png"
    elif any(k in upper for k in ["HW", "HUAWEI", "ALT", "MNA", "CET", "JAD", "ANA", "ELS", "VOG", "CLT"]):
        return clean, "hawei.png"
    elif any(k in upper for k in ["XIAOMI", "REDMI", "POCO", "M2"]):
        return clean, "xiaomi.png"
    elif any(k in upper for k in ["OPPO", "CPH"]):
        return clean, "oppo.png"

    return clean, "default.png"


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
def resource_path(name):
    """Arquivo de recurso (png etc.): ao lado do script ou dentro do .app empacotado."""
    base = getattr(sys, "_MEIPASS", None) or Path(__file__).resolve().parent
    return Path(base) / name


def load_cfg():
    try:
        return json.loads(CFG_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {}


def save_cfg(cfg):
    try:
        CFG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    except Exception:  # noqa: BLE001
        pass


def detect_tools_dir():
    """Procura a pasta scrcpy-macos-* em Downloads, preferindo a arquitetura do Mac."""
    arch = "aarch64" if platform.machine() in ("arm64", "aarch64") else "x86_64"
    base = Path.home() / "Downloads"
    for d in sorted(base.glob(f"scrcpy-macos-{arch}*"), reverse=True):
        if d.is_dir() and (d / "scrcpy").exists() and (d / "adb").exists():
            return str(d)
    return ""


def font(size, weight="normal"):
    return ctk.CTkFont(family=FONT, size=size, weight=weight)


@lru_cache(maxsize=None)
def brand_image(icon_file, size):
    """Ícone de marca como CTkImage (ou None se o arquivo não existir)."""
    path = resource_path(icon_file)
    if not path.exists():
        return None
    try:
        pil_img = Image.open(path)
        return ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=size)
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=None)
def circle_icon(icon_file, color):
    """Círculo colorido com o ícone centralizado (desenhado em alta resolução)."""
    scale = 4
    side = ICON_CIRCLE * scale
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).ellipse([0, 0, side - 1, side - 1], fill=color)
    try:
        glyph_side = ICON_GLYPH * scale
        glyph = Image.open(resource_path(icon_file)).convert("RGBA")
        glyph = glyph.resize((glyph_side, glyph_side), Image.Resampling.LANCZOS)
        offset = (side - glyph_side) // 2
        canvas.paste(glyph, (offset, offset), glyph)
    except Exception:  # noqa: BLE001
        pass
    return ctk.CTkImage(light_image=canvas, dark_image=canvas, size=(ICON_CIRCLE, ICON_CIRCLE))


@lru_cache(maxsize=None)
def square_icon(color, size=14):
    """Quadradinho de 'parar' na cor indicada."""
    scale = 4
    side = size * scale
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(canvas).rounded_rectangle([0, 0, side - 1, side - 1], radius=3 * scale, fill=color)
    return ctk.CTkImage(light_image=canvas, dark_image=canvas, size=(size, size))


# ----------------------------------------------------------------------------
# Widgets
# ----------------------------------------------------------------------------
class StepRow(ctk.CTkFrame):
    """Linha de passo da barra lateral."""
    H = 76

    def __init__(self, master, index, total, title, subtitle, on_click, glyph=None):
        super().__init__(master, height=self.H, corner_radius=12, fg_color="transparent")
        self.pack_propagate(False)
        self.index, self.total = index, total
        self.state, self.active = "pending", False
        self.on_click = on_click
        self.glyph = glyph  # texto no círculo; None = número da etapa
        self.icon_photo = None
        if index == STEP_CONTRIB and resource_path(CONTRIB_ICON_FILE).exists():
            try:
                icon = Image.open(resource_path(CONTRIB_ICON_FILE)).convert("RGBA")
                icon.thumbnail((18, 18), Image.Resampling.LANCZOS)
                self.icon_photo = ImageTk.PhotoImage(icon)
            except Exception:  # noqa: BLE001
                self.icon_photo = None

        self.canvas = tk.Canvas(self, width=40, height=self.H, bg=SURFACE,
                                highlightthickness=0, bd=0)
        self.canvas.pack(side="left", padx=(6, 0))
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(side="left", fill="both", expand=True, padx=(6, 8))
        inner = ctk.CTkFrame(box, fg_color="transparent")
        inner.place(relx=0, rely=0.5, anchor="w")
        self.t = ctk.CTkLabel(inner, text=title, font=font(14, "bold"),
                              text_color=INK, anchor="w")
        self.s = ctk.CTkLabel(inner, text=subtitle, font=font(12),
                              text_color=MUTED, anchor="w")
        self.t.pack(anchor="w")
        self.s.pack(anchor="w")

        for w in (self, self.canvas, box, inner, self.t, self.s):
            w.bind("<Button-1>", lambda e: self.on_click(self.index))
        self.redraw()

    def set_state(self, state):
        self.state = state
        self.redraw()

    def set_active(self, active):
        self.active = active
        self.configure(fg_color=ACCENT_SOFT if active else "transparent")
        self.redraw()

    def redraw(self):
        c = self.canvas
        c.configure(bg=ACCENT_SOFT if self.active else SURFACE)
        c.delete("all")
        cx, cy, r = 20, self.H // 2, 13

        if self.index > 0:
            c.create_line(cx, 0, cx, cy - r - 6, fill=LINE, width=2)
        if self.index < self.total - 1:
            c.create_line(cx, cy + r + 6, cx, self.H, fill=LINE, width=2)

        if self.state == "done":
            fill, ring, glyph = OK, OK, "white"
        elif self.state == "error":
            fill, ring, glyph = ERR, ERR, "white"
        elif self.active:
            fill, ring, glyph = ACCENT, ACCENT, "white"
        else:
            fill, ring, glyph = SURFACE, IDLE, MUTED
        c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill, outline=ring, width=2)

        if self.state == "done":
            c.create_line(cx - 5, cy + 0.5, cx - 1.5, cy + 4, cx + 5.5, cy - 4,
                          fill=glyph, width=2.5, capstyle="round", joinstyle="round")
        elif self.glyph and self.icon_photo:
            c.create_image(cx, cy, image=self.icon_photo)
        else:
            text = "!" if self.state == "error" else (self.glyph or str(self.index + 1))
            c.create_text(cx, cy, text=text, fill=glyph, font=(FONT, 13, "bold"))


class IconButton(ctk.CTkFrame):
    """Botão em pílula com um círculo de ícone à esquerda do texto.

    O círculo tem a mesma folga (INSET) da borda esquerda, de cima e de baixo,
    então fica sempre bem encaixado na pílula. Aceita `configure(text=, state=, kind=)`
    e `cget("text")`, como um CTkButton.
    """
    INSET = (BUTTON_H - ICON_CIRCLE) // 2

    def __init__(self, master, text, icon, kind, command):
        super().__init__(master, corner_radius=BUTTON_H // 2, cursor="pointinghand")
        self.icon, self.kind, self.command = icon, kind, command
        self.state, self._text, self._hovering = "normal", text, False
        self._has_icon = resource_path(icon).exists()

        self.icon_lbl = ctk.CTkLabel(self, text="", width=ICON_CIRCLE, height=ICON_CIRCLE)
        if self._has_icon:
            self.icon_lbl.pack(side="left", padx=(self.INSET, 0), pady=self.INSET)
        self.text_lbl = ctk.CTkLabel(self, text=text, font=font(13, "bold"))
        self.text_lbl.pack(side="left", padx=(10 if self._has_icon else 20, 20), pady=self.INSET)

        for w in (self, self.icon_lbl, self.text_lbl):
            w.bind("<Button-1>", self._on_click)
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
        self._apply()

    # --- API compatível com CTkButton
    def configure(self, require_redraw=False, **kwargs):
        self._text = kwargs.pop("text", self._text)
        self.state = kwargs.pop("state", self.state)
        self.kind = kwargs.pop("kind", self.kind)
        if kwargs:
            super().configure(require_redraw=require_redraw, **kwargs)
        self._apply()

    def cget(self, attribute_name):
        if attribute_name == "text":
            return self._text
        if attribute_name == "state":
            return self.state
        return super().cget(attribute_name)

    # --- aparência
    def _apply(self):
        style = BUTTON_STYLES[self.kind]
        disabled = self.state == "disabled"
        fg = style["hover_color"] if self._hovering and not disabled else style["fg_color"]
        ctk.CTkFrame.configure(self, fg_color=fg, border_width=style["border_width"],
                               border_color=style.get("border_color", fg))
        self.text_lbl.configure(text=self._text,
                                text_color=DISABLED_TEXT if disabled else style["text_color"])
        if self._has_icon:
            self.icon_lbl.configure(image=circle_icon(self.icon, CIRCLE_COLORS[self.kind]))

    # --- eventos
    def _on_click(self, _event):
        if self.state != "disabled" and self.command:
            self.command()

    def _on_enter(self, _event):
        if not self._hovering:
            self._hovering = True
            self._apply()

    def _on_leave(self, _event):
        self.after(20, self._sync_hover)

    def _sync_hover(self):
        try:
            under = self.winfo_containing(*self.winfo_pointerxy())
        except (KeyError, tk.TclError):
            under = None
        path, mine = str(under), str(self)
        hovering = under is not None and (path == mine or path.startswith(mine + "."))
        if hovering != self._hovering:
            self._hovering = hovering
            self._apply()


# ----------------------------------------------------------------------------
# Aplicativo
# ----------------------------------------------------------------------------
class App(ctk.CTk):
    # ======================================================== ciclo de vida
    def __init__(self):
        ctk.set_appearance_mode("light")
        super().__init__()
        self.title("Espelhar celular")
        self.geometry("1040x760")
        self.minsize(940, 700)
        self.configure(fg_color=BG)

        self.cfg = load_cfg()
        self.cfg.setdefault("devices", [])
        self.tools_dir = self.cfg.get("tools_dir") or detect_tools_dir()
        self.serial = ""
        self.cur_dev = None
        self.cur_ip = ""
        self.editing_id = None
        self.current = 0
        self.proc = None
        self.mirroring = False
        self.stopping = False
        self.pairing_in_progress = False
        self.log_open = False
        self.q = queue.Queue()
        self.welcome_logo_img = None

        self.current_market_name = "Nenhum"
        self.current_icon_file = "default.png"
        self.current_conn_addr = "-"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.welcome_host = ctk.CTkFrame(self, fg_color="transparent")
        self.welcome_host.grid(row=0, column=0, sticky="nsew")

        self.pages = {
            S_WELCOME: self._page_welcome(self.welcome_host),
            S_TUTORIAL: self._page_tutorial(self.welcome_host),
        }

        self.go(S_WELCOME)
        self.after(100, self._poll)
        self.protocol("WM_DELETE_WINDOW", self._close)

    def init_main_app(self):
        self.welcome_host.destroy()
        self.pages.clear()

        self.grid_columnconfigure(0, weight=0, minsize=260)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()

        self.content_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=28, pady=(30, 20))
        self._build_log()

        host = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        host.pack(side="top", fill="both", expand=True)
        self.pages[S_DEVICE] = self._page_devices(host)
        self.pages[S_TOOLS] = self._page_tools(host)
        self.pages[S_PAIR] = self._page_pair(host)
        self.pages[S_CONN] = self._page_connect(host)
        self.pages[S_MIRROR] = self._page_mirror(host)
        self.pages[S_CONTRIB] = self._page_contrib(host)
        self.pages[S_DASH] = self._page_dash(host)

        self.go(S_DEVICE)

    def _close(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.destroy()

    # ================================================== barra lateral e log
    def _build_sidebar(self):
        self.side = ctk.CTkFrame(self, width=260, corner_radius=0, fg_color=SURFACE, border_width=0)
        self.side.grid(row=0, column=0, sticky="nsew")
        self.side.grid_propagate(False)
        self.side.pack_propagate(False)
        self.side_line = ctk.CTkFrame(self, width=1, corner_radius=0, fg_color=LINE)
        self.side_line.grid(row=0, column=0, sticky="nse")

        ctk.CTkLabel(self.side, text="Espelhar celular", font=font(20, "bold"), text_color=INK,
                     anchor="w").pack(fill="x", padx=20, pady=(30, 0))
        ctk.CTkLabel(self.side, text="Veja e controle a tela do Android no Mac.", font=font(13),
                     text_color=MUTED, anchor="w", justify="left",
                     wraplength=220).pack(fill="x", padx=20, pady=(4, 22))

        self.rows = []
        for i, (title, subtitle) in enumerate(STEPS):
            row = StepRow(self.side, i, len(STEPS), title, subtitle, self.go_step_from_sidebar,
                          glyph="♥" if i == STEP_CONTRIB else None)
            row.pack(fill="x", padx=12)
            self.rows.append(row)

        # Chip do aparelho (rodapé da barra lateral)
        self.chip_frame = ctk.CTkFrame(self.side, fg_color=CARD, corner_radius=12,
                                       cursor="pointinghand")
        self.chip_frame.pack(side="bottom", fill="x", padx=12, pady=(0, 20))
        chip_inner = ctk.CTkFrame(self.chip_frame, fg_color="transparent")
        chip_inner.pack(fill="x", padx=10, pady=10)

        self.dot = tk.Canvas(chip_inner, width=14, height=14, bg=CARD, highlightthickness=0, bd=0)
        self.dot.pack(side="left", padx=(0, 8))
        self.chip_icon_lbl = ctk.CTkLabel(chip_inner, text="")
        self.chip_label = ctk.CTkLabel(chip_inner, text="", font=font(13, "bold"), text_color=INK,
                                       anchor="w", justify="left", wraplength=150)
        self.chip_label.pack(side="left", fill="x", expand=True)

        for w in (self.chip_frame, chip_inner, self.dot, self.chip_icon_lbl, self.chip_label):
            w.bind("<Button-1>", lambda e: self.go(S_DASH))

        self.set_device("Aparelho desconectado", False, "default.png")

    def _build_log(self):
        """Barra fixa no rodapé + painel suspenso com os detalhes dos comandos."""
        bar = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        bar.pack(side="bottom", fill="x", pady=(6, 0))
        self.log_toggle = ctk.CTkButton(
            bar, text=LOG_TEXT_CLOSED, width=190, height=28, corner_radius=100,
            fg_color="transparent", hover_color=ACCENT_SOFT, text_color=MUTED,
            font=font(13), command=self.toggle_log)
        self.log_toggle.pack(side="left")

        self.log_panel = ctk.CTkFrame(self.content_frame, height=LOG_PANEL_H, corner_radius=12,
                                      fg_color=SURFACE, border_width=1, border_color=FIELD_LINE)
        self.log_panel.pack_propagate(False)
        head = ctk.CTkFrame(self.log_panel, fg_color="transparent")
        head.pack(fill="x", padx=14, pady=(8, 4))
        ctk.CTkLabel(head, text="Detalhes dos comandos", font=font(13),
                     text_color=MUTED).pack(side="left")
        ctk.CTkButton(head, text="Limpar", width=60, height=24, fg_color="transparent",
                      hover_color=ACCENT_SOFT, text_color=ACCENT, font=font(13, "bold"),
                      corner_radius=100, command=self.clear_log).pack(side="right")
        self.logbox = ctk.CTkTextbox(self.log_panel, corner_radius=12, fg_color="#FBFCFE",
                                     border_width=1, border_color=LINE, text_color="#3B4658",
                                     font=("Menlo", 11), wrap="word")
        self.logbox.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        self.logbox.configure(state="disabled")

    def toggle_log(self):
        self.log_open = not self.log_open
        if self.log_open:
            self.log_panel.place(relx=0, rely=1.0, y=-LOG_BAR_H, relwidth=1, anchor="sw")
            self.log_panel.lift()
        else:
            self.log_panel.place_forget()
        self.log_toggle.configure(text=LOG_TEXT_OPEN if self.log_open else LOG_TEXT_CLOSED)

    def log(self, text):
        if hasattr(self, "logbox"):
            self.logbox.configure(state="normal")
            self.logbox.insert("end", text + "\n")
            self.logbox.see("end")
            self.logbox.configure(state="disabled")

    def clear_log(self):
        if hasattr(self, "logbox"):
            self.logbox.configure(state="normal")
            self.logbox.delete("1.0", "end")
            self.logbox.configure(state="disabled")

    # ================================================== infraestrutura
    def post(self, fn, *args):
        self.q.put((fn, args))

    def _poll(self):
        try:
            while True:
                fn, args = self.q.get_nowait()
                fn(*args)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def tool(self, name):
        if self.tools_dir:
            return str(Path(self.tools_dir) / name)
        return shutil.which(name) or name

    def tools_ready(self):
        if self.tools_dir:
            d = Path(self.tools_dir)
            return (d / "adb").exists() and (d / "scrcpy").exists()
        return bool(shutil.which("adb") and shutil.which("scrcpy"))

    def run(self, args, callback, stdin=None, timeout=30, button=None, busy="Aguarde…"):
        self.log("$ " + " ".join(shlex.quote(a) for a in args))
        original = None
        if button is not None:
            original = button.cget("text")
            button.configure(state="disabled", text=busy)
        cwd = self.tools_dir if self.tools_dir and Path(self.tools_dir).is_dir() else None

        def finish(rc, out):
            if button is not None:
                button.configure(state="normal", text=original)
            if out:
                self.log(out)
            callback(rc, out)

        def work():
            try:
                p = subprocess.run(args, input=stdin, capture_output=True, text=True,
                                   timeout=timeout, cwd=cwd)
                rc, out = p.returncode, (p.stdout + p.stderr).strip()
            except subprocess.TimeoutExpired:
                rc, out = -1, "O comando demorou demais e foi cancelado."
            except FileNotFoundError:
                rc, out = 127, "Programa não encontrado."
            except Exception as exc:  # noqa: BLE001
                rc, out = -1, str(exc)
            self.post(finish, rc, out)

        threading.Thread(target=work, daemon=True).start()

    # ================================================== componentes de UI
    def _build_page(self, host, title, desc):
        page = ctk.CTkFrame(host, fg_color="transparent")
        ctk.CTkLabel(page, text=title, font=font(24, "bold"), text_color=INK,
                     anchor="w").pack(fill="x")
        d = ctk.CTkLabel(page, text=desc, font=font(13), text_color=MUTED, anchor="w",
                         justify="left", wraplength=560)
        d.pack(fill="x", pady=(4, 14))
        self._wrap(d, page, 8)
        panel = ctk.CTkFrame(page, fg_color=SURFACE, corner_radius=14,
                             border_width=1, border_color=LINE)
        panel.pack(fill="x")
        form = ctk.CTkFrame(panel, fg_color="transparent")
        form.pack(fill="x", padx=20, pady=20)
        return page, form

    def _wrap(self, label, host, margin):
        host.bind("<Configure>",
                  lambda e: label.configure(wraplength=max(200, e.width - margin)), add="+")

    def _field(self, form, label, placeholder, text=""):
        lab = ctk.CTkLabel(form, text=label, font=font(12, "bold"), text_color=INK, anchor="w")
        lab.pack(fill="x", pady=(0, 6))
        e = ctk.CTkEntry(form, placeholder_text=placeholder, height=40, corner_radius=100,
                         fg_color=SURFACE, border_color=FIELD_LINE, border_width=1,
                         text_color=INK, placeholder_text_color="#98A2B3", font=font(13))
        if text:
            e.insert(0, text)
        e.pack(fill="x", pady=(0, 14))
        e.caption = lab
        return e

    def _note(self, form, text):
        box = ctk.CTkFrame(form, fg_color=CARD, corner_radius=10)
        box.pack(fill="x", pady=(0, 14))
        lab = ctk.CTkLabel(box, text=text, font=font(12), text_color=MUTED, anchor="w",
                           justify="left", wraplength=500)
        lab.pack(fill="x", padx=12, pady=10)
        self._wrap(lab, box, 28)

    def _button(self, parent, text, kind, command):
        return ctk.CTkButton(parent, text=text, command=command, height=BUTTON_H,
                             corner_radius=100, font=font(13, "bold"), **BUTTON_STYLES[kind])

    def _small(self, parent, text, kind, command, width=84):
        return ctk.CTkButton(parent, text=text, command=command, width=width, height=32,
                             corner_radius=100, font=font(13, "bold"), **BUTTON_STYLES[kind])

    def _switch(self, parent, text, on=False):
        sw = ctk.CTkSwitch(parent, text=text, font=font(13), text_color=INK,
                           progress_color=ACCENT, fg_color="#C5CDDA",
                           button_color="white", button_hover_color="#F2F5FA",
                           switch_width=40, switch_height=22)
        if on:
            sw.select()
        sw.pack(anchor="w", pady=(0, 12))
        return sw

    def _status(self, form):
        s = ctk.CTkLabel(form, text="", font=font(13), text_color=MUTED, anchor="w",
                         justify="left", wraplength=500)
        s.pack(fill="x", pady=(14, 0))
        self._wrap(s, form, 8)
        return s

    def set_status(self, label, text, kind="info"):
        color = {"ok": OK, "err": ERR, "info": MUTED, "blue": ACCENT}[kind]
        label.configure(text=text, text_color=color)

    def set_device(self, text, ok, icon_file="default.png"):
        if hasattr(self, "dot"):
            self.dot.delete("all")
            self.dot.create_oval(2, 2, 12, 12, fill=OK if ok else IDLE, outline="")
            self.chip_label.configure(text=text)

            img = brand_image(icon_file, (20, 20))
            if img and ok:
                self.chip_icon_lbl.configure(image=img)
                self.chip_icon_lbl.pack(side="left", padx=(0, 6))
            else:
                self.chip_icon_lbl.pack_forget()

    # ================================================== páginas
    def _page_welcome(self, host):
        page = ctk.CTkFrame(host, fg_color="transparent")

        center_box = ctk.CTkFrame(page, fg_color=SURFACE, corner_radius=20, border_width=1,
                                  border_color=LINE)
        center_box.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.96, relheight=0.96)
        inner = ctk.CTkFrame(center_box, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        logo_path = "Logotipo  Ateliê de Costura Claro Rosa Azul e Amarelo.png"
        logo_path = resource_path(logo_path)
        if logo_path.exists():
            try:
                pil_logo = Image.open(logo_path)
                self.welcome_logo_img = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo,
                                                     size=(120, 120))
                ctk.CTkLabel(inner, image=self.welcome_logo_img, text="").pack(pady=(0, 12))
            except Exception:  # noqa: BLE001
                pass

        ctk.CTkLabel(inner, text="Bem-vindo ao Glass.", font=font(24, "bold"),
                     text_color=INK).pack(pady=(0, 8))

        desc_text = (
            "O Glass é um assistente completo para espelhamento e controle de dispositivos Android "
            "diretamente no seu macOS de forma rápida e fluida via Wi-Fi ou cabo USB. "
            "Gerencie aparelhos salvos e configure resoluções com facilidade."
        )
        ctk.CTkLabel(inner, text=desc_text, font=font(13), text_color=MUTED, justify="center",
                     wraplength=480).pack(pady=(0, 16))

        self._button(inner, "Iniciar", "primary", self.init_main_app).pack(ipadx=30, pady=(0, 8))

        tutorial_lbl = ctk.CTkLabel(inner, text="tutorial",
                                    font=ctk.CTkFont(family=FONT, size=13, underline=True),
                                    text_color=ACCENT, cursor="pointinghand")
        tutorial_lbl.pack()
        tutorial_lbl.bind("<Button-1>", lambda e: self.go(S_TUTORIAL))
        return page

    def _page_tutorial(self, host):
        page = ctk.CTkFrame(host, fg_color="transparent")

        center_box = ctk.CTkFrame(page, fg_color=SURFACE, corner_radius=20, border_width=1,
                                  border_color=LINE)
        center_box.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.96, relheight=0.96)
        inner = ctk.CTkFrame(center_box, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="Guia de Conexão e Tutoriais", font=font(22, "bold"),
                     text_color=INK).pack(pady=(0, 14))

        tut_text = (
            "• Android Padrão:\n"
            "Ative as 'Opções do desenvolvedor' (clique 7 vezes no 'Número da versão' em Sobre o telefone), "
            "habilite a 'Depuração USB' e a 'Depuração sem fio'.\n\n"
            "• Xiaomi (MIUI / HyperOS):\n"
            "Além da depuração sem fio, vá em Opções do desenvolvedor e ative 'Depuração USB (Configurações de segurança)' "
            "para permitir o controle de toque pelo computador.\n\n"
            "• iOS / iPhone:\n"
            "Atualmente o espelhamento nativo via scrcpy é voltado para dispositivos Android. Para iPhone, utilize soluções "
            "compatíveis com AirPlay ou cabos de reflexão específicos."
        )
        ctk.CTkLabel(inner, text=tut_text, font=font(13), text_color=MUTED, justify="left",
                     wraplength=540).pack(pady=(0, 20))

        self._button(inner, "Voltar", "secondary", lambda: self.go(S_WELCOME)).pack(ipadx=20)
        return page

    def _page_devices(self, host):
        page, f = self._build_page(
            host, "Aparelhos", "Escolha um aparelho salvo ou pareie um novo.")
        self.dev_list = ctk.CTkScrollableFrame(
            f, fg_color="transparent", height=60, scrollbar_button_color=FIELD_LINE,
            scrollbar_button_hover_color=IDLE)
        self.dev_list.pack(fill="x")
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(anchor="w", pady=(14, 0))
        self._button(row, "Parear novo aparelho", "primary", self.new_device).pack(
            side="left", padx=(0, 10))
        self.btn_usb = IconButton(row, "Usar cabo USB", "usb.png", "secondary", self.do_usb)
        self.btn_usb.pack(side="left")
        self.st_usb = self._status(f)
        self.rebuild_devices()
        return page

    def _page_tools(self, host):
        page, f = self._build_page(
            host, "Preparar ferramentas",
            "O app usa o scrcpy e o adb. Aponte para a pasta que você extraiu do download.")
        ctk.CTkLabel(f, text="Pasta do scrcpy", font=font(12, "bold"), text_color=INK,
                     anchor="w").pack(fill="x", pady=(0, 6))
        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(fill="x", pady=(0, 14))
        self.tools_entry = ctk.CTkEntry(
            row, placeholder_text="~/Downloads/scrcpy-macos-x86_64-v5.0.1", height=40,
            corner_radius=100, fg_color=SURFACE, border_color=FIELD_LINE, text_color=INK,
            placeholder_text_color="#98A2B3", font=font(13))
        if self.tools_dir:
            self.tools_entry.insert(0, self.tools_dir)
        self.tools_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self._button(row, "Escolher pasta", "secondary", self.pick_folder).pack(side="left")
        self._note(f, "A pasta precisa conter os arquivos scrcpy e adb. O app também libera o "
                      "bloqueio que o macOS coloca em arquivos baixados.")
        self.btn_verify = self._button(f, "Verificar ferramentas", "primary", self.verify_tools)
        self.btn_verify.pack(anchor="w")
        self.st_tools = self._status(f)
        return page

    def _page_pair(self, host):
        page, f = self._build_page(
            host, "Parear com o celular",
            "O pareamento é feito uma única vez. Depois disso, basta conectar.")
        self._note(f, "No celular: Configurações > Opções do desenvolvedor > Depuração sem "
                      "fio > Parear dispositivo com código de pareamento. Deixe essa tela aberta.")
        self.pair_addr = self._field(f, "IP e porta do pareamento", "192.168.0.15:37123")
        self.pair_code = self._field(f, "Código de 6 dígitos", "123456")

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(anchor="w")
        self.btn_pair = self._button(row, "Parear", "primary", self.do_pair)
        self.btn_pair.pack(side="left", padx=(0, 10))
        self.btn_cancel_pair = self._button(row, "Cancelar", "purple", self.cancel_pairing)
        self.btn_cancel_pair.pack(side="left", padx=(0, 10))
        self.btn_cancel_pair.configure(state="disabled")
        self._button(row, "Já pareei antes", "secondary",
                     lambda: self.mark(STEP_PAIR, "done", advance=True)).pack(side="left")
        self.st_pair = self._status(f)
        return page

    def _page_connect(self, host):
        page, f = self._build_page(
            host, "Conectar",
            "Conecte por Wi-Fi ou, se o cabo funcionar, direto por USB.")
        self._note(f, "Use a porta da tela principal de Depuração sem fio. Ela é diferente da "
                      "usada no pareamento e muda de tempos em tempos. Com o IP salvo, basta "
                      "digitar a porta.")

        self.port_entry = self._field(f, "IP e porta da conexão", "192.168.0.15:33467")
        self.port_entry.bind("<Return>", lambda e: self.do_connect())
        self.sw_save = self._switch(f, "Salvar este aparelho", on=True)

        row = ctk.CTkFrame(f, fg_color="transparent")
        row.pack(anchor="w")
        self.btn_connect = IconButton(row, "Conectar por Wi-Fi", "wifi.png", "primary",
                                      self.do_connect)
        self.btn_connect.pack(side="left")
        self.st_conn = self._status(f)
        return page

    def _page_mirror(self, host):
        page, f = self._build_page(
            host, "Espelhamento", "Controle o espelhamento na resolução original do aparelho.")

        mirror_box = ctk.CTkFrame(f, fg_color=CARD, corner_radius=12)
        mirror_box.pack(fill="x", pady=(0, 14))
        m_inner = ctk.CTkFrame(mirror_box, fg_color="transparent")
        m_inner.pack(fill="x", padx=16, pady=16)

        ctk.CTkLabel(m_inner, text="Espelhamento de Tela", font=font(15, "bold"),
                     text_color=INK).pack(anchor="w", pady=(0, 8))

        self.sw_off = self._switch(m_inner, "Apagar a tela do celular durante o espelhamento")
        self.sw_awake = self._switch(m_inner, "Manter o celular acordado", on=True)
        self.sw_top = self._switch(m_inner, "Manter a janela sempre por cima")

        # Botão principal + quadrado vermelho que encerra o espelhamento
        row = ctk.CTkFrame(m_inner, fg_color="transparent")
        row.pack(anchor="w", pady=(0, 6))
        self.btn_mirror = IconButton(row, "Iniciar espelhamento", "screencast.png", "primary",
                                     self.start_mirror)
        self.btn_mirror.pack(side="left")
        self.btn_stop = ctk.CTkButton(row, text="", width=BUTTON_H, height=BUTTON_H,
                                      corner_radius=10, command=self.stop_mirror)
        self.btn_stop.pack(side="left", padx=(10, 0))
        self._refresh_mirror_controls()

        self.st_mirror = self._status(f)
        return page

    def _page_contrib(self, host):
        page, f = self._build_page(
            host, "Contribua", "Apoie o desenvolvedor pelo QR code abaixo.")

        qr_path = resource_path(QR_FILE)
        self.qr_img = None
        if qr_path.exists():
            try:
                pil_qr = Image.open(qr_path)
                ratio = QR_SIZE / max(pil_qr.size)
                size = (round(pil_qr.width * ratio), round(pil_qr.height * ratio))
                self.qr_img = ctk.CTkImage(light_image=pil_qr, dark_image=pil_qr, size=size)
            except Exception:  # noqa: BLE001
                pass
        if self.qr_img:
            ctk.CTkLabel(f, image=self.qr_img, text="").pack(pady=(0, 14))
        else:
            ctk.CTkLabel(f, text=f"Coloque o arquivo {QR_FILE} na pasta do app.",
                         font=font(13), text_color=MUTED, height=QR_SIZE // 2).pack(pady=(0, 14))

        ctk.CTkLabel(f, text="JOSUÉ AULER KREISCHER", font=font(16, "bold"),
                     text_color=INK).pack()
        ctk.CTkLabel(f, text="BANCO SANTANDER", font=font(14, "bold"),
                     text_color=MUTED).pack(pady=(2, 14))
        ctk.CTkLabel(f, text="Obrigado pela preferência! Se o app te ajudou,\n considere dar uma "
                             "força no café do dev. ☕", font=font(12), text_color=SOFT_TEXT,
                     justify="center", wraplength=420).pack()
        return page

    def _page_dash(self, host):
        page, f = self._build_page(
            host, "Dash do Aparelho", "Informações detalhadas sobre o aparelho atualmente conectado.")

        self.dash_card = ctk.CTkFrame(f, fg_color=CARD, corner_radius=12)
        self.dash_card.pack(fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(self.dash_card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=20)

        header = ctk.CTkFrame(inner, fg_color="transparent")
        header.pack(fill="x", pady=(0, 15))
        self.dash_icon_lbl = ctk.CTkLabel(header, text="")
        self.dash_icon_lbl.pack(side="left", padx=(0, 10))
        self.dash_title = ctk.CTkLabel(header, text="Nenhum aparelho conectado",
                                       font=font(18, "bold"), text_color=INK)
        self.dash_title.pack(side="left", anchor="w")

        grid = ctk.CTkFrame(inner, fg_color="transparent")
        grid.pack(fill="x")
        self.dash_lbl_ip = ctk.CTkLabel(grid, text="Endereço de Conexão: -", font=font(13),
                                        text_color=MUTED, anchor="w")
        self.dash_lbl_ip.pack(fill="x", pady=2)
        self.dash_lbl_serial = ctk.CTkLabel(grid, text="Identificador ADB: -", font=font(13),
                                            text_color=MUTED, anchor="w")
        self.dash_lbl_serial.pack(fill="x", pady=2)
        self.dash_lbl_status = ctk.CTkLabel(grid, text="Status: Desconectado", font=font(13),
                                            text_color=MUTED, anchor="w")
        self.dash_lbl_status.pack(fill="x", pady=2)
        return page

    def update_dash_view(self):
        if hasattr(self, "dash_title"):
            self.dash_title.configure(text=self.current_market_name)
            self.dash_lbl_ip.configure(text=f"Endereço de Conexão: {self.current_conn_addr}")
            self.dash_lbl_serial.configure(
                text=f"Identificador ADB: {self.serial if self.serial else '-'}")
            st = "Conectado" if self.serial else "Desconectado"
            self.dash_lbl_status.configure(text=f"Status: {st}")

            img = brand_image(self.current_icon_file, (28, 28))
            if img:
                self.dash_icon_lbl.configure(image=img)
                self.dash_icon_lbl.pack(side="left", padx=(0, 10))
            else:
                self.dash_icon_lbl.pack_forget()

    # ================================================== navegação
    def go(self, index):
        self.current = index
        if index == S_DASH:
            self.update_dash_view()

        for page in self.pages.values():
            page.pack_forget()
        if index in self.pages:
            self.pages[index].pack(fill="both", expand=True)

        if hasattr(self, "rows"):
            active = index - PAGE_OFFSET if index >= S_DEVICE else None
            for i, row in enumerate(self.rows):
                row.set_active(i == active)

    def go_step_from_sidebar(self, step):
        self.go(step + PAGE_OFFSET)

    def mark(self, step, state, advance=False, to=None):
        page = step + PAGE_OFFSET
        self.rows[step].set_state(state)
        if advance and state == "done":
            target = (to if to is not None else step + 1) + PAGE_OFFSET
            if target in self.pages:
                self.after(700, lambda: self.go(target) if self.current == page else None)

    def reset_from(self, step):
        for i in range(step, len(STEPS)):
            self.rows[i].set_state("pending")

    # ================================================== etapa 1: aparelhos
    def rebuild_devices(self):
        for w in self.dev_list.winfo_children():
            w.destroy()
        devs = self.cfg["devices"]
        if not devs:
            self.dev_list.configure(height=34)
            ctk.CTkLabel(self.dev_list, text="Nenhum aparelho salvo ainda. Pareie um novo "
                                             "para começar.", font=font(13),
                         text_color=MUTED, anchor="w").pack(fill="x")
            return
        self.dev_list.configure(height=min(len(devs) * 66, 264))
        for d in devs:
            self._device_row(d)

    def _device_row(self, d):
        row = ctk.CTkFrame(self.dev_list, fg_color=CARD, corner_radius=12)
        row.pack(fill="x", pady=(0, 8))
        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="x", padx=14, pady=10)

        market_name, icon_file = identify_device(d.get("name", ""))
        d["name"] = market_name
        d["icon"] = icon_file

        if self.editing_id == d["id"]:
            self._small(inner, "Cancelar", "secondary", self.cancel_rename, 84).pack(side="right")
            entry = ctk.CTkEntry(inner, height=34, corner_radius=100, fg_color=SURFACE,
                                 border_color=ACCENT, border_width=1.5, text_color=INK,
                                 font=font(13))
            self._small(inner, "Salvar", "primary",
                        lambda: self.rename_device(d["id"], entry.get()), 76).pack(
                side="right", padx=(0, 8))
            entry.insert(0, d["name"])
            entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
            entry.bind("<Return>", lambda e: self.rename_device(d["id"], entry.get()))
            entry.bind("<Escape>", lambda e: self.cancel_rename())
            entry.after(80, entry.focus_set)
            return

        self._small(inner, "Excluir", "danger", lambda: self.delete_device(d["id"]), 70).pack(
            side="right")
        self._small(inner, "Renomear", "secondary", lambda: self.start_rename(d["id"]), 92).pack(
            side="right", padx=(0, 8))
        self._small(inner, "Usar", "primary", lambda: self.choose_device(d), 64).pack(
            side="right", padx=(0, 8))

        icon_img = brand_image(icon_file, (20, 20))
        if icon_img:
            ctk.CTkLabel(inner, image=icon_img, text="").pack(side="left", padx=(0, 8))

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(info, text=market_name, font=font(14, "bold"), text_color=INK,
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(info, text=d["ip"], font=font(12), text_color=MUTED,
                     anchor="w").pack(anchor="w")

    def start_rename(self, dev_id):
        self.editing_id = dev_id
        self.rebuild_devices()

    def cancel_rename(self):
        self.editing_id = None
        self.rebuild_devices()

    def rename_device(self, dev_id, new_name):
        new_name = new_name.strip()
        if not new_name:
            return
        for d in self.cfg["devices"]:
            if d["id"] == dev_id:
                d["name"] = new_name
        save_cfg(self.cfg)
        self.editing_id = None
        self.rebuild_devices()

    def delete_device(self, dev_id):
        dev = next((d for d in self.cfg["devices"] if d["id"] == dev_id), None)
        if not dev:
            return
        if not messagebox.askyesno("Excluir aparelho",
                                   f"Excluir \"{dev['name']}\" da lista de aparelhos salvos?"):
            return
        self.cfg["devices"] = [d for d in self.cfg["devices"] if d["id"] != dev_id]
        if self.cur_dev and self.cur_dev["id"] == dev_id:
            self.cur_dev = None
        save_cfg(self.cfg)
        self.rebuild_devices()

    def _prepare_switch(self):
        """Zera o estado do aparelho atual antes de escolher ou parear outro."""
        if self.mirroring and self.proc:
            self.proc.terminate()
        self.mirroring, self.stopping, self.proc = False, False, None
        self.serial = ""
        self.current_market_name = "Nenhum"
        self.current_icon_file = "default.png"
        self.current_conn_addr = "-"
        self.set_device("Nenhum celular conectado", False, "default.png")
        self._refresh_mirror_controls()
        for st in (self.st_usb, self.st_pair, self.st_conn, self.st_mirror):
            self.set_status(st, "")
        self.port_entry.delete(0, "end")
        self.pair_addr.delete(0, "end")
        self.pair_code.delete(0, "end")

    def choose_device(self, dev):
        self._prepare_switch()
        self.cur_dev, self.cur_ip = dev, dev["ip"]
        self.sw_save.select()
        self.update_conn_context()
        self.reset_from(STEP_TOOLS)
        self.mark(STEP_DEVICE, "done")
        self.mark(STEP_PAIR, "done")
        if self.tools_ready():
            self.mark(STEP_TOOLS, "done")
            self.go(S_CONN)
            self.port_entry.after(100, self.port_entry.focus_set)
        else:
            self.go(S_TOOLS)

    def new_device(self):
        self._prepare_switch()
        self.cur_dev, self.cur_ip = None, ""
        self.sw_save.select()
        self.update_conn_context()
        self.reset_from(STEP_TOOLS)
        self.mark(STEP_DEVICE, "done")
        if self.tools_ready():
            self.mark(STEP_TOOLS, "done")
            self.go(S_PAIR)
        else:
            self.go(S_TOOLS)

    def update_conn_context(self):
        if self.cur_ip:
            self.port_entry.caption.configure(text=f"Porta (IP do aparelho: {self.cur_ip})")
            self.port_entry.configure(placeholder_text="Ex.: 33467")
        else:
            self.port_entry.caption.configure(text="IP e porta da conexão")
            self.port_entry.configure(placeholder_text="192.168.0.15:33467")

    def save_current_device(self, ip, raw_model):
        if not self.sw_save.get():
            return
        market_name, icon_file = identify_device(raw_model)
        self.current_market_name = market_name
        self.current_icon_file = icon_file
        for d in self.cfg["devices"]:
            if d["ip"] == ip:
                d["name"] = market_name
                d["icon"] = icon_file
                self.cur_dev = d
                break
        else:
            self.cur_dev = {"id": uuid.uuid4().hex[:8], "name": market_name, "ip": ip,
                            "icon": icon_file}
            self.cfg["devices"].append(self.cur_dev)
        save_cfg(self.cfg)
        self.rebuild_devices()

    # ================================================== etapa 2: ferramentas
    def pick_folder(self):
        start = self.tools_entry.get().strip() or str(Path.home() / "Downloads")
        folder = filedialog.askdirectory(title="Escolher a pasta do scrcpy", initialdir=start)
        if folder:
            self.tools_entry.delete(0, "end")
            self.tools_entry.insert(0, folder)

    def verify_tools(self):
        self.tools_dir = self.tools_entry.get().strip()
        self.cfg["tools_dir"] = self.tools_dir
        save_cfg(self.cfg)
        adb, scr = shlex.quote(self.tool("adb")), shlex.quote(self.tool("scrcpy"))
        cmd = ""
        if self.tools_dir:
            cmd += f"xattr -dr com.apple.quarantine {shlex.quote(self.tools_dir)} 2>/dev/null; "
        cmd += f"{adb} start-server 2>&1; {adb} version && {scr} --version"
        self.run(["/bin/sh", "-c", cmd], self._after_verify, button=self.btn_verify,
                 timeout=60, busy="Verificando…")

    def _after_verify(self, rc, out):
        low = out.lower()
        if rc == 0 and "android debug bridge" in low and "scrcpy" in low:
            self.mark(STEP_TOOLS, "done", advance=True, to=STEP_PAIR)
            self.set_status(self.st_tools, "Tudo certo. adb e scrcpy estão funcionando.", "ok")
        else:
            self.mark(STEP_TOOLS, "error")
            self.set_status(
                self.st_tools,
                "Não encontrei o scrcpy e o adb nessa pasta. Confira se ela é a pasta extraída "
                "do download (com os arquivos scrcpy e adb dentro).", "err")

    # ================================================== etapa 3: parear
    def do_pair(self):
        addr = self.pair_addr.get().strip()
        code = self.pair_code.get().strip()
        if not ADDR_RE.match(addr):
            self.set_status(self.st_pair, "Digite o IP e a porta como aparecem no celular, "
                                          "por exemplo 192.168.0.15:37123.", "err")
            return
        if not re.fullmatch(r"\d{6}", code):
            self.set_status(self.st_pair, "O código de pareamento tem 6 dígitos.", "err")
            return
        self.set_status(self.st_pair, "")
        self.pairing_in_progress = True
        self.btn_cancel_pair.configure(state="normal")
        self.run([self.tool("adb"), "pair", addr],
                 lambda rc, out: self._after_pair(rc, out, addr),
                 stdin=code + "\n", button=self.btn_pair, busy="Pareando…")

    def cancel_pairing(self):
        self.pairing_in_progress = False
        if hasattr(self, "btn_cancel_pair"):
            self.btn_cancel_pair.configure(state="disabled")
        if hasattr(self, "btn_pair"):
            self.btn_pair.configure(state="normal", text="Parear")
        self.go(S_DEVICE)

    def _after_pair(self, rc, out, addr):
        self.pairing_in_progress = False
        if hasattr(self, "btn_cancel_pair"):
            self.btn_cancel_pair.configure(state="disabled")

        if "successfully paired" in out.lower():
            self.cur_ip = addr.split(":")[0]
            self.update_conn_context()
            self.mark(STEP_PAIR, "done", advance=True)
            self.set_status(self.st_pair, "Celular pareado.", "ok")
        else:
            if not self.pairing_in_progress:
                return
            self.mark(STEP_PAIR, "error")
            self.set_status(
                self.st_pair,
                "Não foi possível parear. Mantenha a tela de pareamento aberta no celular e use "
                "o IP, a porta e o código que aparecem agora (eles mudam a cada tentativa).",
                "err")

    # ================================================== etapa 4: conectar
    def resolve_addr(self, text):
        text = text.strip()
        if ADDR_RE.match(text):
            return text
        if PORT_RE.match(text) and self.cur_ip:
            return f"{self.cur_ip}:{text}"
        return None

    def do_connect(self):
        text = self.port_entry.get().strip()
        addr = self.resolve_addr(text)
        if not addr:
            if PORT_RE.match(text):
                msg = ("Ainda não sei o IP deste aparelho. Digite o IP e a porta juntos, por "
                       "exemplo 192.168.0.15:33467. Depois de salvo, basta a porta.")
            else:
                msg = "Digite a porta da tela principal de Depuração sem fio (ou IP:porta)."
            self.set_status(self.st_conn, msg, "err")
            return
        self.set_status(self.st_conn, "")
        self.run([self.tool("adb"), "connect", addr],
                 lambda rc, out: self._after_connect(rc, out, addr),
                 button=self.btn_connect, busy="Conectando…")

    def _after_connect(self, rc, out, addr):
        low = out.lower()
        if "connected to" in low and "failed" not in low and "cannot" not in low:
            self.refresh_devices(prefer=addr)
        else:
            self.mark(STEP_CONN, "error")
            self.set_status(
                self.st_conn,
                "Não consegui conectar. Confira se a Depuração sem fio está ligada, se celular "
                "e Mac estão na mesma rede Wi-Fi e se a porta é a da tela principal (não a do "
                "pareamento).", "err")

    def do_usb(self):
        """Conecta por cabo: procura aparelhos USB no adb e leva ao espelhamento."""
        self.set_status(self.st_usb, "")
        self.run([self.tool("adb"), "devices", "-l"], self._after_usb,
                 button=self.btn_usb, busy="Procurando…", timeout=60)

    def _after_usb(self, rc, out):
        usb = [d for d in self._parse_adb_devices(out)
               if d[1] == "device" and ":" not in d[0] and "_adb-tls" not in d[0]]
        if not usb:
            self.set_status(self.st_usb, "Erro: tente conexão via WI-FI", "blue")
            return

        self._prepare_switch()
        self.cur_dev, self.cur_ip = None, ""
        self.serial, _, raw_model = usb[0]
        market_name, icon_file = identify_device(raw_model)
        self.current_market_name = market_name
        self.current_icon_file = icon_file
        self.current_conn_addr = "Conexão USB"

        self.set_device(f"{market_name} conectado", True, icon_file)
        self._refresh_mirror_controls()
        self.reset_from(STEP_TOOLS)
        self.mark(STEP_DEVICE, "done")
        self.mark(STEP_TOOLS, "done")
        self.mark(STEP_CONN, "done")
        self.set_status(self.st_usb, f"Conectado a {market_name}.", "ok")
        self.after(700, lambda: self.go(S_MIRROR) if self.current == S_DEVICE else None)

    @staticmethod
    def _parse_adb_devices(out):
        """Lê a saída de `adb devices -l` como (serial, estado, modelo)."""
        found = []
        for line in out.splitlines()[1:]:
            m = re.match(r"^(\S+)\s+(device|unauthorized|offline)\b(.*)$", line.strip())
            if m:
                model = re.search(r"model:(\S+)", m.group(3))
                found.append((m.group(1), m.group(2), model.group(1) if model else m.group(1)))
        return found

    def refresh_devices(self, prefer=None):
        self.run([self.tool("adb"), "devices", "-l"],
                 lambda rc, out: self._after_devices(rc, out, prefer),
                 busy="Procurando…")

    def _after_devices(self, rc, out, prefer):
        found = self._parse_adb_devices(out)
        ready = [d for d in found if d[1] == "device"]

        if ready:
            chosen = next((d for d in ready if d[0] == prefer), ready[0])
            self.serial = chosen[0]
            raw_model = chosen[2]

            market_name, icon_file = identify_device(raw_model)
            self.current_market_name = market_name
            self.current_icon_file = icon_file
            self.current_conn_addr = prefer if prefer else "Conexão USB"

            if prefer and chosen[0] == prefer:
                self.cur_ip = prefer.split(":")[0]
                self.update_conn_context()
                self.save_current_device(self.cur_ip, raw_model)

            self.set_device(f"{market_name} conectado", True, icon_file)
            self.mark(STEP_CONN, "done", advance=True)
            self.set_status(self.st_conn, f"Conectado a {market_name}.", "ok")
        elif any(d[1] == "unauthorized" for d in found):
            self.serial = ""
            self.set_device("Nenhum celular conectado", False, "default.png")
            self.mark(STEP_CONN, "error")
            self.set_status(self.st_conn, "O celular pediu autorização. Toque em Permitir na "
                                          "tela dele e tente de novo.", "err")
        else:
            self.serial = ""
            self.set_device("Nenhum celular conectado", False, "default.png")
            self.mark(STEP_CONN, "error")
            self.set_status(
                self.st_conn,
                "Nenhum celular encontrado. Por USB, use um cabo de dados, escolha Transferência "
                "de arquivos e aceite a depuração. Ou conecte por Wi-Fi.", "err")

        self._refresh_mirror_controls()

    # ================================================== etapa 5: espelhamento
    def _refresh_mirror_controls(self):
        """Botão principal: 'Iniciar espelhamento' (sem aparelho), 'Espelhar' (aparelho
        emparelhado, azul) e 'Espelhando' (em andamento). O quadrado vermelho só fica
        ativo durante o espelhamento; depois de clicado, fica cinza até o fim da tarefa."""
        if self.mirroring:
            self.btn_mirror.configure(text="Espelhando", kind="success")
        elif self.serial:
            self.btn_mirror.configure(text="Espelhar", kind="primary")
        else:
            self.btn_mirror.configure(text="Iniciar espelhamento", kind="primary")

        if self.mirroring and self.stopping:
            self.btn_stop.configure(state="disabled", fg_color=STOP_GRAY, hover_color=STOP_GRAY,
                                    image=square_icon(STOP_GRAY_GLYPH))
        elif self.mirroring:
            self.btn_stop.configure(state="normal", fg_color=ERR, hover_color=ERR_DARK,
                                    image=square_icon("white"))
        else:
            self.btn_stop.configure(state="disabled", fg_color=ERR_SOFT, hover_color=ERR_SOFT,
                                    image=square_icon(ERR_FADED))

    def start_mirror(self):
        if self.mirroring:
            return
        if not self.serial:
            self.set_status(self.st_mirror, "Conecte o celular antes de espelhar.", "err")
            self.go(S_CONN)
            return

        args = [self.tool("scrcpy"), "-s", self.serial]
        if self.sw_off.get():
            args.append("--turn-screen-off")
        if self.sw_awake.get():
            args.append("--stay-awake")
        if self.sw_top.get():
            args.append("--always-on-top")
        self._launch(args)

    def _launch(self, args, note=""):
        env = dict(os.environ)
        cwd = None
        if self.tools_dir and Path(self.tools_dir).is_dir():
            env["ADB"] = self.tool("adb")
            env["SCRCPY_SERVER_PATH"] = self.tool("scrcpy-server")
            cwd = self.tools_dir

        self.log("$ " + " ".join(shlex.quote(a) for a in args))
        try:
            self.proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, env=env, cwd=cwd)
        except Exception:  # noqa: BLE001
            self.mark(STEP_MIRROR, "error")
            self.set_status(self.st_mirror, "Não foi possível abrir o scrcpy. Volte ao passo "
                                            "de ferramentas e verifique a pasta.", "err")
            return

        self.mirroring = True
        self._refresh_mirror_controls()
        self.set_status(self.st_mirror, (note + " " if note else "") +
                        "Espelhamento em andamento. Feche a janela do celular "
                        "ou clique no quadrado vermelho para parar.", "info")
        self.mark(STEP_MIRROR, "done")
        proc = self.proc

        def reader():
            for line in proc.stdout:
                self.post(self.log, line.rstrip())
            proc.wait()
            self.post(self._mirror_finished, proc)

        threading.Thread(target=reader, daemon=True).start()

    def stop_mirror(self):
        if self.mirroring and self.proc and not self.stopping:
            self.stopping = True
            self._refresh_mirror_controls()
            self.proc.terminate()

    def _mirror_finished(self, proc):
        if proc is not self.proc:  # espelhamento já descartado (ex.: troca de aparelho)
            return
        self.mirroring, self.stopping, self.proc = False, False, None
        self._refresh_mirror_controls()
        self.set_status(self.st_mirror, "Espelhamento encerrado.", "info")
        self.go(S_DEVICE)


if __name__ == "__main__":
    App().mainloop()
