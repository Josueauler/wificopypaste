"""
Wifi CopyPaste  -  lado PC (receptor)
-------------------------------------
Requisitos:  pip install customtkinter pillow
Opcional:    pip install pymupdf      (mostra a miniatura da 1ª página dos PDFs)
Executar:    python transferencia_pc.py

O celular (transferencia_mobile/main.py) encontra este PC automaticamente
na mesma rede Wi-Fi, ou você digita o IP + PIN mostrados na tela.
"""
import json
import os
import platform
import queue
import random
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
from datetime import datetime
from pathlib import Path

import customtkinter as ctk
from PIL import Image, ImageChops, ImageDraw, ImageFont, ImageTk

try:  # opcional: pré-visualização de PDF
    import fitz  # PyMuPDF
except Exception:  # noqa
    fitz = None

PORT = 5055            # TCP: recebimento de dados
DISCOVERY_PORT = 5056  # UDP: descoberta automática
SAVE_DIR = Path.home() / "Downloads" / "Transferencia"
IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".heic"}
VID_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".3gp", ".m4v"}
PDF_EXT = {".pdf"}
MIME_EXT = {"application/pdf": ".pdf"}
MAX_TEXT = 5 * 1024 * 1024

ACCENT = "#4f8cff"
ACCENT_HOVER = "#3b72dd"
CARD = ("#ffffff", "#1e2230")
BG = ("#f1f3f9", "#13151f")
SIDE = ("#e6e9f3", "#191c29")
OK = "#2ecc71"
ERR = "#ff5c5c"
DANGER = "#e5484d"
DANGER_HOVER = "#c93a3f"

UNITS = {"seg": 1, "min": 60, "h": 3600}


# ----------------------------------------------------------------- utilidades
def recv_exact(conn, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(min(65536, n - len(buf)))
        if not chunk:
            raise ConnectionError("Conexão encerrada")
        buf.extend(chunk)
    return bytes(buf)


def recv_msg(conn):
    (ln,) = struct.unpack(">I", recv_exact(conn, 4))
    if ln > 1_000_000:
        raise ValueError("Cabeçalho inválido")
    return json.loads(recv_exact(conn, ln).decode("utf-8"))


def send_msg(conn, obj):
    data = json.dumps(obj).encode("utf-8")
    conn.sendall(struct.pack(">I", len(data)) + data)


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        try:
            return socket.gethostbyname(socket.gethostname())
        except OSError:
            return "127.0.0.1"
    finally:
        s.close()


def human_size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def human_time(sec):
    sec = max(0, int(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def unique_path(folder: Path, name: str) -> Path:
    name = os.path.basename(name).replace("\x00", "") or "arquivo"
    p = folder / name
    stem, suf, i = p.stem, p.suffix, 1
    while p.exists():
        p = folder / f"{stem} ({i}){suf}"
        i += 1
    return p


BASE_DIR = Path(__file__).resolve().parent
CARD_ICON = (32, 32)    # mesma área do emoji que ficava no cartão
TRASH_ICON = (18, 18)   # dentro do botão de lixeira
OK_ICON = (16, 16)      # ao lado de "Salvo"
MIRROR_ICON = (18, 18)  # ícone do botão de espelhar (transmitir.png)
MIRROR_SCRIPT = "script.py"  # programa de espelhamento do celular
MIRROR_COLORS = ("#B57CFF", "#4F8CFF")  # botão de espelhar: lilás -> azul (gradiente)
LOGO_ICON = (72, 72)    # logo da barra lateral
WELCOME_ICON = (260, 260)  # ícone da tela de boas-vindas
APP_NAME = "Wifi CopyPaste"
ICON_BG = "#141521"     # cor de fundo do ícone (a tela de boas-vindas usa a mesma)
PIX_FILE = "pix.png"    # imagem do Pix (na pasta do projeto)
CONFIG_FILE = Path.home() / ".wifi_copypaste.json"
IMG_RADIUS = 14         # arredondamento das imagens mostradas no app
_icon_cache = {}


def _strip_accents(text):
    return "".join(ch for ch in unicodedata.normalize("NFD", text)
                   if unicodedata.category(ch) != "Mn")


def find_asset(name):
    """Procura o arquivo na pasta do projeto (aceita nome com ou sem acento)."""
    for cand in (name, _strip_accents(name)):
        p = BASE_DIR / cand
        if p.exists():
            return p
    wanted = {unicodedata.normalize("NFC", n).casefold() for n in (name, _strip_accents(name))}
    try:
        for f in BASE_DIR.iterdir():
            if unicodedata.normalize("NFC", f.name).casefold() in wanted:
                return f
    except OSError:
        pass
    return None


def round_corners(img, radius):
    """Devolve a imagem com os cantos arredondados (transparentes)."""
    img = img.convert("RGBA")
    w, h = img.size
    radius = max(1, min(int(radius), w // 2, h // 2))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=255)
    img.putalpha(ImageChops.multiply(img.split()[3], mask))
    return img


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _bold_font(px):
    """Fonte em negrito disponível no sistema (None se nenhuma for encontrada)."""
    candidates = [
        ("/System/Library/Fonts/Helvetica.ttc", 1),
        ("/System/Library/Fonts/SFNS.ttf", 0),
        ("C:/Windows/Fonts/segoeuib.ttf", 0),
        ("C:/Windows/Fonts/arialbd.ttf", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0),
    ]
    for path, index in candidates:
        try:
            return ImageFont.truetype(path, px, index=index)
        except (OSError, TypeError):
            continue
    return None


def gradient_button_image(text, icon_name, colors=MIRROR_COLORS, height=34, hover=False):
    """Botão em pílula com gradiente horizontal, ícone e texto, desenhado com PIL.
    Retorna um CTkImage (ou None se nenhuma fonte for encontrada)."""
    scale = 4
    font = _bold_font(13 * scale)
    if font is None:
        return None
    pad_l, pad_r, icon_px, gap = 12, 18, 18, 8
    text_w = font.getlength(text) / scale
    width = round(pad_l + icon_px + gap + text_w + pad_r)
    w, h = width * scale, height * scale

    c1, c2 = _rgb(colors[0]), _rgb(colors[1])
    if hover:  # um pouco mais claro ao passar o mouse
        c1 = tuple(round(v + (255 - v) * 0.18) for v in c1)
        c2 = tuple(round(v + (255 - v) * 0.18) for v in c2)
    grad = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(grad)
    for x in range(w):
        t = x / max(1, w - 1)
        draw.line([(x, 0), (x, h)], fill=tuple(round(a + (b - a) * t) for a, b in zip(c1, c2)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w - 1, h - 1), radius=h // 2, fill=255)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)

    path = find_asset(icon_name)
    if path:
        try:
            with Image.open(path) as im:
                icon = im.convert("RGBA")
            icon = icon.resize((icon_px * scale, icon_px * scale), Image.LANCZOS)
            out.alpha_composite(icon, (pad_l * scale, (h - icon_px * scale) // 2))
        except Exception:
            pass
    ImageDraw.Draw(out).text(((pad_l + icon_px + gap) * scale, h // 2), text,
                             font=font, fill="white", anchor="lm")
    return ctk.CTkImage(light_image=out, dark_image=out, size=(width, height))


def load_icon(name, size, round_frac=0.0):
    """Carrega um PNG da pasta do projeto, ajustado (sem distorcer) ao tamanho pedido.
    Retorna None se o arquivo não existir (o app usa o emoji como reserva)."""
    key = (name, size, round_frac)
    if key in _icon_cache:
        return _icon_cache[key]
    ci = None
    path = find_asset(name)
    if path:
        try:
            with Image.open(path) as im:
                img = im.convert("RGBA")
            img.thumbnail((size[0] * 3, size[1] * 3), Image.LANCZOS)
            if round_frac:
                img = round_corners(img, round_frac * min(img.size))
            scale = min(size[0] / img.width, size[1] / img.height)
            disp = (max(1, round(img.width * scale)), max(1, round(img.height * scale)))
            ci = ctk.CTkImage(light_image=img, dark_image=img, size=disp)
        except Exception:
            ci = None
    _icon_cache[key] = ci
    return ci


def icon_button(parent, name, command, fallback, size=TRASH_ICON, state="normal"):
    """Ícone clicável (PNG da pasta do projeto), sem contorno e sem texto."""
    img = load_icon(name, size)
    return ctk.CTkButton(
        parent, text="" if img else fallback, image=img, width=34, height=30,
        corner_radius=10, fg_color="transparent", border_width=0, text_color=ACCENT,
        hover_color=("#dde6ff", "#262c44"), state=state, command=command)


ICON_BY_KIND = {          # tipo do item -> PNG na pasta do projeto
    "texto": "mensagem.png",
    "imagem": "imagem.png",
    "video": "vídeo.png",
    "arquivo": "arquivo.png",
}


def type_icon_name(ext):
    if ext in IMG_EXT:
        return ICON_BY_KIND["imagem"]
    if ext in VID_EXT:
        return ICON_BY_KIND["video"]
    return ICON_BY_KIND["arquivo"]


def load_config():
    try:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_config(data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
    except OSError:
        pass


def open_path(path, reveal=False):
    path = str(path)
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", "-R", path] if reveal else ["open", path])
        elif system == "Windows":
            if reveal:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
            else:
                os.startfile(path)  # noqa
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path) if reveal else path])
    except Exception:
        pass


def delete_file(path, tries=5):
    """Apaga o arquivo da pasta de recebidos (com novas tentativas se estiver em uso)."""
    if not path:
        return True
    for _ in range(tries):
        try:
            if os.path.exists(path):
                os.remove(path)
            return True
        except OSError:
            time.sleep(0.15)
    return not os.path.exists(path)


def copy_image_to_clipboard(path):
    """Copia a imagem para a área de transferência do sistema. Retorna True/False."""
    tmp = None
    try:
        with Image.open(path) as im:
            img = im.convert("RGBA")
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        img.save(tmp, "PNG")
        system = platform.system()
        if system == "Darwin":
            script = f'set the clipboard to (read (POSIX file "{tmp}") as «class PNGf»)'
            r = subprocess.run(["osascript", "-e", script], capture_output=True, timeout=15)
        elif system == "Windows":
            ps = ("Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing; "
                  f"$i=[System.Drawing.Image]::FromFile('{tmp}'); "
                  "[System.Windows.Forms.Clipboard]::SetImage($i); $i.Dispose()")
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command", ps],
                               capture_output=True, timeout=20)
        else:
            try:
                with open(tmp, "rb") as f:
                    r = subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png"],
                                       stdin=f, capture_output=True, timeout=15)
            except FileNotFoundError:
                with open(tmp, "rb") as f:
                    r = subprocess.run(["wl-copy", "--type", "image/png"],
                                       stdin=f, capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False
    finally:
        if tmp:
            try:
                os.remove(tmp)
            except OSError:
                pass


def copy_file_to_clipboard(path):
    """Copia o arquivo (como arquivo, para colar no Finder/Explorer). Retorna True/False."""
    try:
        path = str(path)
        system = platform.system()
        if system == "Darwin":
            esc = path.replace("\\", "\\\\").replace('"', '\\"')
            r = subprocess.run(["osascript", "-e", f'set the clipboard to (POSIX file "{esc}")'],
                               capture_output=True, timeout=15)
        elif system == "Windows":
            esc = path.replace("'", "''")
            r = subprocess.run(["powershell", "-NoProfile", "-STA", "-Command",
                                f"Set-Clipboard -LiteralPath '{esc}'"],
                               capture_output=True, timeout=20)
        else:
            uri = (Path(path).resolve().as_uri() + "\n").encode()
            try:
                r = subprocess.run(["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
                                   input=uri, capture_output=True, timeout=15)
            except FileNotFoundError:
                r = subprocess.run(["wl-copy", "--type", "text/uri-list"],
                                   input=uri, capture_output=True, timeout=15)
        return r.returncode == 0
    except Exception:
        return False


def pdf_first_page(path, max_size=(360, 220)):
    """Retorna uma imagem PIL da 1ª página do PDF, ou None se não for possível."""
    if fitz is None:
        return None
    try:
        doc = fitz.open(path)
        page = doc.load_page(0)
        pix = page.get_pixmap(matrix=fitz.Matrix(1.2, 1.2))
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        doc.close()
        img.thumbnail(max_size)
        return img
    except Exception:
        return None


# -------------------------------------------------------------------- servidor
class TransferServer:
    def __init__(self, events: queue.Queue):
        self.events = events
        self.pin = f"{random.randint(0, 999999):06d}"
        self.running = False
        self._uid = 0
        self._lock = threading.Lock()
        self.sock = None

    def new_pin(self):
        self.pin = f"{random.randint(0, 999999):06d}"
        return self.pin

    def start(self):
        self.running = True
        SAVE_DIR.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self._tcp_loop, daemon=True).start()
        threading.Thread(target=self._udp_loop, daemon=True).start()

    # descoberta automática: o celular manda um broadcast e o PC responde
    def _udp_loop(self):
        try:
            u = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            u.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            u.bind(("", DISCOVERY_PORT))
        except OSError:
            return
        while self.running:
            try:
                data, addr = u.recvfrom(1024)
                if data.strip() == b"CLIPWIFI?":
                    resp = json.dumps({"name": socket.gethostname(), "port": PORT}).encode()
                    u.sendto(resp, addr)
            except OSError:
                break

    def _tcp_loop(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind(("", PORT))
            self.sock.listen(8)
        except OSError as e:
            self.events.put(("fatal", f"Não foi possível abrir a porta {PORT}: {e}"))
            return
        while self.running:
            try:
                conn, addr = self.sock.accept()
            except OSError:
                break
            threading.Thread(target=self._handle, args=(conn, addr), daemon=True).start()

    def _next_id(self):
        with self._lock:
            self._uid += 1
            return self._uid

    def _handle(self, conn, addr):
        uid = None
        try:
            conn.settimeout(30)
            meta = recv_msg(conn)
            if meta.get("pin") != self.pin:
                send_msg(conn, {"ok": False, "error": "PIN incorreto"})
                self.events.put(("denied", addr[0]))
                return
            kind = meta.get("type")
            if kind == "ping":
                send_msg(conn, {"ok": True, "name": socket.gethostname()})
                self.events.put(("hello", meta.get("device", addr[0]), addr[0]))
                return

            size = int(meta.get("size", 0))
            device = meta.get("device", addr[0])
            uid = self._next_id()

            if kind == "text":
                if size > MAX_TEXT:
                    send_msg(conn, {"ok": False, "error": "Texto grande demais"})
                    return
                send_msg(conn, {"ok": True})
                text = recv_exact(conn, size).decode("utf-8", "replace")
                self.events.put(("text", uid, device, text))
            else:
                name = meta.get("name", "arquivo")
                # se o celular mandou o nome sem extensão mas informou o tipo (ex.: PDF)
                mime = (meta.get("mime") or "").lower()
                if not Path(name).suffix and mime in MIME_EXT:
                    name += MIME_EXT[mime]
                path = unique_path(SAVE_DIR, name)
                send_msg(conn, {"ok": True})
                self.events.put(("file_start", uid, device, path.name, size))
                got, last = 0, 0.0
                with open(path, "wb") as f:
                    while got < size:
                        chunk = conn.recv(min(262144, size - got))
                        if not chunk:
                            raise ConnectionError("Transferência interrompida")
                        f.write(chunk)
                        got += len(chunk)
                        now = time.time()
                        if now - last > 0.1:
                            last = now
                            self.events.put(("progress", uid, got, size))
                self.events.put(("file_done", uid, str(path)))
            send_msg(conn, {"ok": True})
        except Exception as e:  # noqa
            if uid is not None:
                self.events.put(("error", uid, str(e)))
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def stop(self):
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except OSError:
            pass


# ------------------------------------------------------------------------ UI
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        self.title(APP_NAME)
        self.geometry("1040x720")
        self.minsize(900, 620)
        self.configure(fg_color=BG)
        self._set_window_icon()

        self.events = queue.Queue()
        self.server = TransferServer(self.events)
        self.cards = {}
        self._imgs = []
        self.auto_copy = ctk.BooleanVar(value=True)
        self.auto_del = ctk.BooleanVar(value=False)
        self.unit_var = ctk.StringVar(value="min")

        self.protocol("WM_DELETE_WINDOW", self._close)

        self._welcome = None
        self._mirror_proc = None
        self._started = False
        if load_config().get("welcome_seen"):
            self._start_app()
        else:
            # Primeira abertura: só a boas-vindas é criada. A interface, o servidor
            # e os temporizadores só começam depois de sair desta tela.
            self._show_welcome()

    def _start_app(self):
        """Cria a interface e inicia o servidor (executado após a tela inicial)."""
        if self._started:
            return
        self._started = True
        self._build_sidebar()
        self._build_main()

        self.server.start()
        self.ip = local_ip()
        self.ip_label.configure(text=f"{self.ip}:{PORT}")
        self.pin_label.configure(text=self.server.pin)
        self.after(100, self._poll)
        self.after(1000, self._tick)

    # ---- tela de boas-vindas (apenas na primeira abertura)
    def _show_welcome(self):
        frame = ctk.CTkFrame(self, fg_color=ICON_BG, corner_radius=0)
        frame.place(x=0, y=0, relwidth=1, relheight=1)
        frame.lift()
        self._welcome = frame

        box = ctk.CTkFrame(frame, fg_color="transparent")
        box.place(relx=.5, rely=.46, anchor="center")
        # o fundo do ícone tem a mesma cor da tela: o ícone parece um PNG solto
        ctk.CTkLabel(box, text="", image=load_icon("icone.png", WELCOME_ICON),
                     fg_color=ICON_BG).pack()
        ctk.CTkLabel(box, text="Bem-vindo ao", text_color="gray60",
                     font=ctk.CTkFont(size=15)).pack(pady=(6, 0))
        ctk.CTkLabel(box, text=APP_NAME, text_color="white",
                     font=ctk.CTkFont(size=38, weight="bold")).pack()
        ctk.CTkLabel(box, text="Copie no celular, cole no PC.\nTextos, fotos e arquivos pelo Wi-Fi.",
                     text_color="gray60", font=ctk.CTkFont(size=15), justify="center").pack(
            pady=(8, 28))
        ctk.CTkButton(box, text="Começar", width=220, height=46, corner_radius=14,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      font=ctk.CTkFont(size=16, weight="bold"),
                      command=self._close_welcome).pack()

        link = self._donate_link(frame)
        link.place(relx=.5, rely=1.0, y=-26, anchor="s")

    def _donate_link(self, parent):
        """Link sublinhado "Doe um café pro dev" (abre o pix.png)."""
        link = ctk.CTkLabel(parent, text="Doe um café pro dev", text_color=ACCENT,
                            font=ctk.CTkFont(size=13, underline=True))
        try:  # cursor de "mãozinha" sobre o link
            link.configure(cursor="hand2")
        except Exception:
            pass
        link.bind("<Button-1>", lambda e: self._show_pix())
        link.bind("<Enter>", lambda e: link.configure(text_color=ACCENT_HOVER))
        link.bind("<Leave>", lambda e: link.configure(text_color=ACCENT))
        return link

    def _close_welcome(self):
        cfg = load_config()
        cfg["welcome_seen"] = True
        save_config(cfg)
        if self._welcome is not None:
            self._welcome.destroy()
            self._welcome = None
        self._start_app()

    def _show_pix(self):
        """Abre uma janela com o pix.png (QR Code / chave Pix)."""
        win = ctk.CTkToplevel(self)
        win.title("Doe um café pro dev")
        win.configure(fg_color=ICON_BG)
        win.resizable(False, False)
        ctk.CTkLabel(win, text="Doe um café pro dev", text_color="white",
                     font=ctk.CTkFont(size=20, weight="bold")).pack(padx=40, pady=(26, 4))

        img = None
        path = find_asset(PIX_FILE)
        if path:
            try:
                with Image.open(path) as im:
                    pil = im.convert("RGB")
                pil.thumbnail((420, 420), Image.LANCZOS)
                pil = round_corners(pil, IMG_RADIUS)
                img = ctk.CTkImage(light_image=pil, dark_image=pil, size=pil.size)
            except Exception:
                img = None
        if img is not None:
            self._pix_img = img  # mantém a referência
            ctk.CTkLabel(win, text="Obrigado pelo apoio! Use o Pix abaixo.",
                         text_color="gray60", font=ctk.CTkFont(size=13)).pack()
            ctk.CTkLabel(win, text="", image=img).pack(padx=40, pady=(14, 28))
        else:
            ctk.CTkLabel(win, text=f"Coloque o arquivo {PIX_FILE} na pasta do programa.",
                         text_color=ERR, font=ctk.CTkFont(size=13)).pack(padx=40, pady=(10, 30))
        win.after(150, win.focus)

    def _set_window_icon(self):
        """Usa icone.png (na pasta do projeto) como ícone da janela."""
        path = find_asset("icone.png")
        if not path:
            return
        try:
            with Image.open(path) as im:
                img = round_corners(im.convert("RGBA").resize((256, 256), Image.LANCZOS), 56)
            self._win_icon = ImageTk.PhotoImage(img)
            self.iconphoto(True, self._win_icon)
            # o customtkinter troca o ícone ao abrir a janela; reaplica logo depois
            self.after(300, lambda: self.iconphoto(True, self._win_icon))
        except Exception:
            pass

    # ---- layout
    def _build_sidebar(self):
        side = ctk.CTkFrame(self, width=310, corner_radius=0, fg_color=SIDE)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)

        logo = load_icon("icone.png", LOGO_ICON, round_frac=0.22)
        ctk.CTkLabel(side, text="", image=logo).pack(pady=(22, 0))
        ctk.CTkLabel(side, text=APP_NAME,
                     font=ctk.CTkFont(size=22, weight="bold")).pack()
        self.status = ctk.CTkLabel(side, text="●  Aguardando conexões",
                                   text_color=OK, font=ctk.CTkFont(size=13))
        self.status.pack(pady=(4, 16))

        box = ctk.CTkFrame(side, corner_radius=16, fg_color=CARD)
        box.pack(fill="x", padx=20)
        ctk.CTkLabel(box, text="ENDEREÇO DESTE PC", text_color="gray60",
                     font=ctk.CTkFont(size=11, weight="bold")).pack(pady=(12, 0))
        self.ip_label = ctk.CTkLabel(box, text="...", font=ctk.CTkFont(size=20, weight="bold"))
        self.ip_label.pack(pady=(2, 8))
        ctk.CTkLabel(box, text="PIN DE PAREAMENTO", text_color="gray60",
                     font=ctk.CTkFont(size=11, weight="bold")).pack()
        self.pin_label = ctk.CTkLabel(box, text="------", text_color=ACCENT,
                                      font=ctk.CTkFont(size=34, weight="bold"))
        self.pin_label.pack(pady=(0, 6))
        ctk.CTkButton(box, text="Gerar novo PIN", height=30, corner_radius=10,
                      fg_color="transparent", border_width=1, border_color=ACCENT,
                      text_color=ACCENT, hover_color=("#dde6ff", "#262c44"),
                      command=self._new_pin).pack(pady=(0, 12), padx=16, fill="x")

        ctk.CTkSwitch(side, text="Copiar textos recebidos\nautomaticamente",
                      variable=self.auto_copy, progress_color=ACCENT).pack(
            anchor="w", padx=24, pady=(16, 0))

        # exclusão automática: switch + tempo digitado ao lado
        row = ctk.CTkFrame(side, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(14, 0))
        ctk.CTkSwitch(row, text="Auto-excluir", variable=self.auto_del,
                      progress_color=ACCENT, width=110).pack(side="left")
        self.unit_menu = ctk.CTkOptionMenu(
            row, values=list(UNITS), variable=self.unit_var, width=64, height=28,
            fg_color=ACCENT, button_color=ACCENT_HOVER, button_hover_color=ACCENT_HOVER)
        self.unit_menu.pack(side="right")
        self.time_entry = ctk.CTkEntry(row, width=56, height=28, justify="center",
                                       placeholder_text="10")
        self.time_entry.pack(side="right", padx=(0, 6))
        ctk.CTkLabel(side, text="Apaga cada item depois deste tempo,\ncontado a partir do recebimento.",
                     text_color="gray55", font=ctk.CTkFont(size=11), justify="left").pack(
            anchor="w", padx=24, pady=(4, 0))

        ctk.CTkButton(side, text="Pasta de recebidos", height=40, corner_radius=12,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda: open_path(SAVE_DIR)).pack(
            fill="x", padx=20, pady=(18, 8))
        ctk.CTkButton(side, text="Excluir tudo", height=36, corner_radius=12,
                      fg_color=("#d5d9e8", "#2a2f45"), text_color=("gray20", "gray90"),
                      hover_color=("#c4c9dc", "#353b57"),
                      command=self._clear).pack(fill="x", padx=20)
        self._donate_link(side).pack(pady=(16, 0))

        ctk.CTkLabel(side, text=f"Salvando em:\n{SAVE_DIR}", text_color="gray55",
                     font=ctk.CTkFont(size=11), wraplength=260, justify="left").pack(
            side="bottom", pady=12, padx=20, anchor="w")

    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(side="right", fill="both", expand=True, padx=24, pady=20)
        head = ctk.CTkFrame(main, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text="Itens recebidos",
                     font=ctk.CTkFont(size=26, weight="bold")).pack(side="left")
        self.counter = ctk.CTkLabel(head, text="0 itens", text_color="gray60")
        self.counter.pack(side="right")
        img = gradient_button_image("Espelhar celular", "transmitir.png")
        if img is not None:
            img_hover = gradient_button_image("Espelhar celular", "transmitir.png", hover=True)
            self.mirror_btn = ctk.CTkLabel(head, text="", image=img)
            try:
                self.mirror_btn.configure(cursor="hand2")
            except Exception:
                pass
            self.mirror_btn.bind("<Button-1>", lambda e: self._open_mirror())
            self.mirror_btn.bind("<Enter>", lambda e: self.mirror_btn.configure(image=img_hover))
            self.mirror_btn.bind("<Leave>", lambda e: self.mirror_btn.configure(image=img))
        else:  # sem fonte para desenhar o gradiente: botão lilás liso
            self.mirror_btn = ctk.CTkButton(
                head, text="Espelhar celular", image=load_icon("transmitir.png", MIRROR_ICON),
                compound="left", height=34, corner_radius=17, fg_color=MIRROR_COLORS[0],
                hover_color="#C79BFF", font=ctk.CTkFont(size=13, weight="bold"),
                command=self._open_mirror)
        self.mirror_btn.pack(side="right", padx=(0, 16))

        self.list = ctk.CTkScrollableFrame(main, fg_color="transparent")
        self.list.pack(fill="both", expand=True, pady=(12, 0))
        self.empty = ctk.CTkLabel(
            self.list, text="Nada por aqui ainda.\nAbra o app no celular e envie algo ✨",
            text_color="gray55", font=ctk.CTkFont(size=15))
        self.empty.pack(pady=120)

    # ---- espelhamento do celular (script.py)
    def _open_mirror(self):
        """Abre o programa de espelhamento (script.py) em uma janela própria."""
        script = find_asset(MIRROR_SCRIPT)
        if not script:
            self._flash(f"●  Coloque o {MIRROR_SCRIPT} na pasta do programa", ERR)
            return
        if self._mirror_proc is not None and self._mirror_proc.poll() is None:
            self._flash("●  O espelhamento já está aberto")
            return
        try:
            self._mirror_proc = subprocess.Popen([sys.executable, str(script)],
                                                 cwd=str(script.parent))
        except Exception as e:  # noqa
            self._flash(f"●  Não foi possível abrir o espelhamento: {e}", ERR)

    # ---- ações
    def _new_pin(self):
        self.pin_label.configure(text=self.server.new_pin())

    def _delete_item(self, uid):
        c = self.cards.pop(uid, None)
        if not c:
            return
        delete_file(c.get("path"))
        if c.get("img") in self._imgs:
            self._imgs.remove(c["img"])
        c["frame"].destroy()
        self._refresh_counter()

    def _clear(self):
        for uid in list(self.cards):
            self._delete_item(uid)
        self._refresh_counter()

    def _refresh_counter(self):
        n = len(self.cards)
        self.counter.configure(text=f"{n} {'item' if n == 1 else 'itens'}")
        if n == 0:
            self.empty.pack(pady=120)
        else:
            self.empty.pack_forget()

    def _flash(self, text, color=OK):
        self.status.configure(text=text, text_color=color)
        self.after(3500, lambda: self.status.configure(
            text="●  Aguardando conexões", text_color=OK))

    def _blink(self, btn, ok=True):
        """Feedback no ícone: fundo verde (ok) ou vermelho (falha) por instantes."""
        if not btn:
            return
        try:
            btn.configure(fg_color=("#d9f7e5", "#1f3a2c") if ok else ("#ffe3e3", "#3a2024"))
            self.after(1200, lambda: btn.winfo_exists() and btn.configure(fg_color="transparent"))
        except Exception:
            pass

    def _copy(self, text, btn=None):
        self.clipboard_clear()
        self.clipboard_append(text)
        self._blink(btn)
        if btn:
            self._flash("●  Texto copiado")

    def _copy_image(self, path, btn):
        ok = copy_image_to_clipboard(path)
        self._blink(btn, ok)
        self._flash("●  Imagem copiada" if ok else "●  Não foi possível copiar a imagem",
                    OK if ok else ERR)

    def _copy_item(self, uid):
        """Ícone de copiar do cabeçalho: texto -> texto; imagem -> imagem; outros -> arquivo."""
        c = self.cards.get(uid)
        if not c:
            return
        btn = c["copy_btn"]
        if c.get("text") is not None:
            self._copy(c["text"], btn)
        elif c.get("ext") in IMG_EXT:
            self._copy_image(c["path"], btn)
        else:
            ok = copy_file_to_clipboard(c["path"])
            self._blink(btn, ok)
            self._flash("●  Arquivo copiado" if ok else "●  Não foi possível copiar o arquivo",
                        OK if ok else ERR)

    # ---- exclusão automática
    def _auto_seconds(self):
        """Tempo digitado convertido em segundos (0 = inválido/desligado)."""
        raw = self.time_entry.get().strip().replace(",", ".")
        try:
            val = float(raw)
        except ValueError:
            return 0
        return max(0, val * UNITS.get(self.unit_var.get(), 60))

    def _tick(self):
        secs = self._auto_seconds() if self.auto_del.get() else 0
        now = time.time()
        for uid, c in list(self.cards.items()):
            created = c.get("created")
            if created is None:  # ainda recebendo
                continue
            if secs:
                remaining = secs - (now - created)
                if remaining <= 0:
                    self._delete_item(uid)
                else:
                    c["timer"].configure(text=f"⏱ {human_time(remaining)}")
            else:
                c["timer"].configure(text="")
        self.after(1000, self._tick)

    # ---- cartões
    def _new_card(self, uid, title, subtitle, deletable=True, icon_img=None):
        self.empty.pack_forget()
        frame = ctk.CTkFrame(self.list, corner_radius=16, fg_color=CARD)
        frame.pack(fill="x", pady=6, padx=2)
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(12, 0))
        ctk.CTkLabel(top, text="", image=icon_img,
                     width=CARD_ICON[0], height=CARD_ICON[1]).pack(side="left")
        info = ctk.CTkFrame(top, fg_color="transparent")
        info.pack(side="left", padx=10)
        ctk.CTkLabel(info, text=title, anchor="w",
                     font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(info, text=subtitle, anchor="w", text_color="gray60",
                     font=ctk.CTkFont(size=11)).pack(anchor="w")

        trash = load_icon("lixeira.png", TRASH_ICON)
        del_btn = ctk.CTkButton(
            top, text="" if trash else "Excluir", image=trash, width=34, height=30, corner_radius=10,
            fg_color="transparent", border_width=0,
            text_color=DANGER, hover_color=("#ffe3e3", "#3a2024"),
            state="normal" if deletable else "disabled",
            command=lambda: self._delete_item(uid))
        del_btn.pack(side="right")
        copy_btn = icon_button(top, "copiar.png", lambda: self._copy_item(uid), "Copiar",
                               state="normal" if deletable else "disabled")
        copy_btn.pack(side="right", padx=(0, 2))
        timer = ctk.CTkLabel(top, text="", text_color="gray60", font=ctk.CTkFont(size=11))
        timer.pack(side="right", padx=(0, 10))

        body = ctk.CTkFrame(frame, fg_color="transparent")
        body.pack(fill="x", padx=16, pady=(8, 12))
        self.cards[uid] = {"frame": frame, "body": body, "del_btn": del_btn,
                           "copy_btn": copy_btn, "timer": timer, "created": None, "path": None}
        self._refresh_counter()
        return body

    def _on_text(self, uid, device, text):
        stamp = datetime.now().strftime("%H:%M:%S")
        body = self._new_card(uid, "Texto", f"{device} • {stamp}",
                              icon_img=load_icon(ICON_BY_KIND["texto"], CARD_ICON))
        self.cards[uid]["created"] = time.time()
        self.cards[uid]["text"] = text
        preview = text if len(text) < 1200 else text[:1200] + "…"
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        box = ctk.CTkTextbox(row, height=min(160, 28 + 20 * preview.count("\n") + 20 * (len(preview) // 70)),
                             corner_radius=10, fg_color=("#eef0f8", "#161926"), wrap="word")
        box.insert("1.0", preview)
        box.configure(state="disabled")
        box.pack(fill="x")
        if self.auto_copy.get():
            self._copy(text)
        self._flash("●  Texto recebido")

    def _on_file_start(self, uid, device, name, size):
        ext = Path(name).suffix.lower()
        stamp = datetime.now().strftime("%H:%M:%S")
        body = self._new_card(uid, name,
                              f"{device} • {human_size(size)} • {stamp}", deletable=False,
                              icon_img=load_icon(type_icon_name(ext), CARD_ICON))
        bar = ctk.CTkProgressBar(body, progress_color=ACCENT, height=8)
        bar.set(0)
        bar.pack(fill="x", pady=(0, 4))
        lbl = ctk.CTkLabel(body, text="Recebendo… 0%", text_color="gray60",
                           font=ctk.CTkFont(size=11))
        lbl.pack(anchor="w")
        self.cards[uid].update(bar=bar, lbl=lbl, ext=ext, path=str(SAVE_DIR / name))
        self.status.configure(text="●  Recebendo arquivo…", text_color=ACCENT)

    def _on_progress(self, uid, got, size):
        c = self.cards.get(uid)
        if not c or "bar" not in c:
            return
        frac = got / size if size else 1
        c["bar"].set(frac)
        c["lbl"].configure(text=f"Recebendo… {frac * 100:.0f}%  ({human_size(got)} / {human_size(size)})")

    def _on_file_done(self, uid, path):
        c = self.cards.get(uid)
        if not c:
            return
        c["bar"].destroy()
        c["lbl"].destroy()
        c["path"] = path
        c["created"] = time.time()
        c["del_btn"].configure(state="normal")
        c["copy_btn"].configure(state="normal")
        body = c["body"]

        preview = None
        if c["ext"] in IMG_EXT:
            try:
                with Image.open(path) as im:
                    preview = im.copy()
                preview.thumbnail((360, 220))
            except Exception:
                preview = None
        elif c["ext"] in PDF_EXT:
            preview = pdf_first_page(path)
        if preview is not None:
            preview = round_corners(preview, IMG_RADIUS)
            ci = ctk.CTkImage(light_image=preview, dark_image=preview, size=preview.size)
            self._imgs.append(ci)
            c["img"] = ci
            img_row = ctk.CTkFrame(body, fg_color="transparent")
            img_row.pack(fill="x", pady=(0, 8))
            ctk.CTkLabel(img_row, text="", image=ci).pack(side="left")
            if c["ext"] in IMG_EXT:  # copiar imagem: botão ao lado do elemento
                cbtn = icon_button(img_row, "copiar.png", lambda: None, "Copiar")
                cbtn.configure(command=lambda b=cbtn, p=path: self._copy_image(p, b))
                cbtn.pack(side="left", anchor="n", padx=(10, 0))

        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        ctk.CTkButton(row, text="Abrir", width=90, height=30, corner_radius=10,
                      fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda: open_path(path)).pack(side="left")
        ctk.CTkButton(row, text="Mostrar na pasta", width=130, height=30, corner_radius=10,
                      fg_color=("#d5d9e8", "#2a2f45"), text_color=("gray20", "gray90"),
                      hover_color=("#c4c9dc", "#353b57"),
                      command=lambda: open_path(path, reveal=True)).pack(side="left", padx=8)
        ok_img = load_icon("ok.png", OK_ICON)
        ctk.CTkLabel(row, text=" Salvo", image=ok_img, compound="left",
                     text_color=OK).pack(side="right")
        self._flash("●  Arquivo recebido")

    def _on_error(self, uid, msg):
        c = self.cards.get(uid)
        if c:
            if "lbl" in c:
                c["lbl"].configure(text=f"Falhou: {msg}", text_color=ERR)
            c["del_btn"].configure(state="normal")  # permite remover o cartão com erro
        self._flash("●  Erro na transferência", ERR)

    # ---- loop de eventos (thread-safe)
    def _poll(self):
        try:
            while True:
                ev = self.events.get_nowait()
                k = ev[0]
                if k == "text":
                    self._on_text(*ev[1:])
                elif k == "file_start":
                    self._on_file_start(*ev[1:])
                elif k == "progress":
                    self._on_progress(*ev[1:])
                elif k == "file_done":
                    self._on_file_done(*ev[1:])
                elif k == "error":
                    self._on_error(*ev[1:])
                elif k == "hello":
                    self._flash(f"●  {ev[1]} conectado")
                elif k == "denied":
                    self._flash(f"●  PIN incorreto de {ev[1]}", ERR)
                elif k == "fatal":
                    self._flash(ev[1], ERR)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _close(self):
        self.server.stop()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
