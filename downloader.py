# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════╗
║              SOCIAL MEDIA VIDEO DOWNLOADER                    ║
║         YouTube · TikTok · Facebook · Pinterest               ║
║                                                                ║
║  Descarga videos de las principales redes sociales             ║
║  con control de resolución y máxima calidad de audio.          ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import re
import sys
import json
import threading
from datetime import datetime


def _configure_tk_environment():
    """Ensure Tcl/Tk paths are available when running from a venv on Windows."""
    if os.name != "nt" or os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidate_roots = []
    if getattr(sys, "base_prefix", None):
        candidate_roots.append(sys.base_prefix)
    candidate_roots.append(sys.prefix)

    for root in candidate_roots:
        tcl_dir = os.path.join(root, "tcl", "tcl8.6")
        tk_dir = os.path.join(root, "tcl", "tk8.6")
        if os.path.exists(os.path.join(tcl_dir, "init.tcl")) and os.path.exists(os.path.join(tk_dir, "tk.tcl")):
            os.environ["TCL_LIBRARY"] = tcl_dir
            os.environ["TK_LIBRARY"] = tk_dir
            break


_configure_tk_environment()

import customtkinter as ctk
from tkinter import filedialog, messagebox

try:
    import yt_dlp
except ImportError:
    print("ERROR: yt-dlp no está instalado. Ejecuta: pip install yt-dlp")
    sys.exit(1)


# ──────────────────────────────────────────────
# Tema y Colores
# ──────────────────────────────────────────────
COLORS = {
    "bg_dark":       "#0f0f1a",
    "bg_card":       "#1a1a2e",
    "bg_input":      "#16213e",
    "accent":        "#e94560",
    "accent_hover":  "#ff6b81",
    "accent_dim":    "#c23152",
    "text_primary":  "#ffffff",
    "text_secondary":"#a0a0b8",
    "text_muted":    "#6c6c80",
    "success":       "#00d26a",
    "warning":       "#ffbe0b",
    "error":         "#ff4757",
    "youtube":       "#FF0000",
    "tiktok":        "#00f2ea",
    "facebook":      "#1877F2",
    "pinterest":     "#E60023",
    "border":        "#2a2a4a",
    "progress_bg":   "#1e1e3a",
}

def _blend(hex_fg, hex_bg, alpha):
    """Blend foreground color onto background with given alpha (0-1)."""
    fg = tuple(int(hex_fg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    bg = tuple(int(hex_bg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    blended = tuple(int(fg[i] * alpha + bg[i] * (1 - alpha)) for i in range(3))
    return f"#{blended[0]:02x}{blended[1]:02x}{blended[2]:02x}"

# Pre-compute blended "transparent" tint colors for each platform
PLATFORM_TINTS = {
    "youtube_hover":   _blend(COLORS["youtube"],   COLORS["bg_dark"], 0.2),
    "youtube_sel":     _blend(COLORS["youtube"],   COLORS["bg_dark"], 0.13),
    "tiktok_hover":    _blend(COLORS["tiktok"],    COLORS["bg_dark"], 0.2),
    "tiktok_sel":      _blend(COLORS["tiktok"],    COLORS["bg_dark"], 0.13),
    "facebook_hover":  _blend(COLORS["facebook"],  COLORS["bg_dark"], 0.2),
    "facebook_sel":    _blend(COLORS["facebook"],  COLORS["bg_dark"], 0.13),
    "pinterest_hover": _blend(COLORS["pinterest"], COLORS["bg_dark"], 0.2),
    "pinterest_sel":   _blend(COLORS["pinterest"], COLORS["bg_dark"], 0.13),
    "accent_hover_bg": _blend(COLORS["accent"],    COLORS["bg_dark"], 0.25),
}

PLATFORM_INFO = {
    "YouTube": {
        "color": COLORS["youtube"],
        "icon": "▶",
        "has_resolution": True,
        "has_audio": True,
        "description": "Videos, Shorts, Playlists",
        "hover": PLATFORM_TINTS["youtube_hover"],
        "sel": PLATFORM_TINTS["youtube_sel"],
    },
    "TikTok": {
        "color": COLORS["tiktok"],
        "icon": "♪",
        "has_resolution": False,
        "has_audio": False,
        "description": "Máxima calidad automática",
        "hover": PLATFORM_TINTS["tiktok_hover"],
        "sel": PLATFORM_TINTS["tiktok_sel"],
    },
    "Facebook": {
        "color": COLORS["facebook"],
        "icon": "f",
        "has_resolution": True,
        "has_audio": True,
        "description": "Videos, Reels, Stories",
        "hover": PLATFORM_TINTS["facebook_hover"],
        "sel": PLATFORM_TINTS["facebook_sel"],
    },
    "Pinterest": {
        "color": COLORS["pinterest"],
        "icon": "P",
        "has_resolution": True,
        "has_audio": True,
        "description": "Videos y Pins de video",
        "hover": PLATFORM_TINTS["pinterest_hover"],
        "sel": PLATFORM_TINTS["pinterest_sel"],
    },
}

RESOLUTIONS = [
    "Mejor disponible",
    "4K (2160p)",
    "1440p",
    "1080p",
    "720p",
    "480p",
    "360p",
]

RESOLUTION_MAP = {
    "Mejor disponible": "bestvideo+bestaudio/best",
    "4K (2160p)": "bestvideo[height<=2160]+bestaudio/best[height<=2160]",
    "1440p": "bestvideo[height<=1440]+bestaudio/best[height<=1440]",
    "1080p": "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
    "720p": "bestvideo[height<=720]+bestaudio/best[height<=720]",
    "480p": "bestvideo[height<=480]+bestaudio/best[height<=480]",
    "360p": "bestvideo[height<=360]+bestaudio/best[height<=360]",
}


class PlatformButton(ctk.CTkButton):
    """Botón de selección de plataforma con estilo personalizado."""

    def __init__(self, master, platform_name, on_select, **kwargs):
        info = PLATFORM_INFO[platform_name]
        self.platform_name = platform_name
        self.platform_color = info["color"]
        self.on_select = on_select
        self._is_selected = False

        super().__init__(
            master,
            text=f" {info['icon']}  {platform_name}",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            fg_color="transparent",
            border_color=COLORS["border"],
            border_width=2,
            corner_radius=12,
            height=55,
            hover_color=info["hover"],
            text_color=COLORS["text_secondary"],
            anchor="center",
            command=self._handle_click,
            **kwargs,
        )

    def _handle_click(self):
        self.on_select(self.platform_name)

    def set_selected(self, selected: bool):
        self._is_selected = selected
        if selected:
            self.configure(
                fg_color=PLATFORM_INFO[self.platform_name]["sel"],
                border_color=self.platform_color,
                text_color=self.platform_color,
            )
        else:
            self.configure(
                fg_color="transparent",
                border_color=COLORS["border"],
                text_color=COLORS["text_secondary"],
            )


class DownloadLogEntry(ctk.CTkFrame):
    """Entrada individual del log de descargas."""

    def __init__(self, master, title, status, platform, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_input"], corner_radius=8, height=40, **kwargs)

        info = PLATFORM_INFO.get(platform, {"icon": "?", "color": COLORS["accent"]})

        icon_label = ctk.CTkLabel(
            self,
            text=info["icon"],
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=info["color"],
            width=30,
        )
        icon_label.pack(side="left", padx=(10, 5), pady=6)

        title_label = ctk.CTkLabel(
            self,
            text=title if len(title) < 55 else title[:52] + "...",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_primary"],
            anchor="w",
        )
        title_label.pack(side="left", fill="x", expand=True, padx=5, pady=6)

        status_colors = {
            "descargando": COLORS["warning"],
            "completado": COLORS["success"],
            "error": COLORS["error"],
        }

        status_label = ctk.CTkLabel(
            self,
            text=f"● {status.capitalize()}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=status_colors.get(status, COLORS["text_muted"]),
            width=100,
        )
        status_label.pack(side="right", padx=10, pady=6)


class App(ctk.CTk):
    """Aplicación principal del descargador de videos."""

    def __init__(self):
        super().__init__()

        # ── Configuración de la ventana ──
        self.title("⬇ Social Media Downloader")
        self.geometry("920x780")
        self.minsize(820, 700)
        self.configure(fg_color=COLORS["bg_dark"])

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")

        # ── Estado ──
        self.selected_platform = "YouTube"
        self.is_downloading = False
        self.download_history = []
        self.download_folder = os.path.join(os.path.expanduser("~"), "Downloads")

        # ── Construir UI ──
        self._build_ui()
        self._update_platform_options()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  CONSTRUIR INTERFAZ
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _build_ui(self):
        # Contenedor principal con scroll
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=15)

        # ── Header ──
        self._build_header()

        # ── Selector de plataforma ──
        self._build_platform_selector()

        # ── Input de URL ──
        self._build_url_input()

        # ── Opciones de descarga ──
        self._build_download_options()

        # ── Carpeta de destino ──
        self._build_folder_selector()

        # ── Botón de descarga ──
        self._build_download_button()

        # ── Progreso ──
        self._build_progress_section()

        # ── Historial ──
        self._build_history_section()

    def _build_header(self):
        header = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))

        title_label = ctk.CTkLabel(
            header,
            text="⬇  Social Media Downloader",
            font=ctk.CTkFont(family="Segoe UI", size=26, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        title_label.pack(side="left")

        subtitle = ctk.CTkLabel(
            header,
            text="YouTube · TikTok · Facebook · Pinterest",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
        )
        subtitle.pack(side="left", padx=(15, 0), pady=(8, 0))

    def _build_platform_selector(self):
        section = ctk.CTkFrame(self.main_container, fg_color=COLORS["bg_card"], corner_radius=16)
        section.pack(fill="x", pady=(5, 10))

        label = ctk.CTkLabel(
            section,
            text="Selecciona la plataforma",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        label.pack(anchor="w", padx=20, pady=(15, 8))

        buttons_frame = ctk.CTkFrame(section, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.platform_buttons = {}
        for i, name in enumerate(PLATFORM_INFO.keys()):
            btn = PlatformButton(buttons_frame, name, on_select=self._select_platform)
            btn.pack(side="left", fill="x", expand=True, padx=5)
            self.platform_buttons[name] = btn

        self.platform_buttons["YouTube"].set_selected(True)

        # Descripción de la plataforma
        self.platform_desc = ctk.CTkLabel(
            section,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self.platform_desc.pack(anchor="w", padx=25, pady=(0, 12))
        self._update_platform_desc()

    def _build_url_input(self):
        section = ctk.CTkFrame(self.main_container, fg_color=COLORS["bg_card"], corner_radius=16)
        section.pack(fill="x", pady=5)

        label = ctk.CTkLabel(
            section,
            text="URL del video",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        label.pack(anchor="w", padx=20, pady=(15, 8))

        input_frame = ctk.CTkFrame(section, fg_color="transparent")
        input_frame.pack(fill="x", padx=15, pady=(0, 15))

        self.url_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Pega aquí la URL del video...",
            font=ctk.CTkFont(family="Segoe UI", size=14),
            height=48,
            corner_radius=12,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=2,
            text_color=COLORS["text_primary"],
            placeholder_text_color=COLORS["text_muted"],
        )
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(5, 10))

        paste_btn = ctk.CTkButton(
            input_frame,
            text="📋 Pegar",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=90,
            height=48,
            corner_radius=12,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=2,
            hover_color=PLATFORM_TINTS["accent_hover_bg"],
            text_color=COLORS["text_secondary"],
            command=self._paste_url,
        )
        paste_btn.pack(side="right", padx=5)

    def _build_download_options(self):
        self.options_section = ctk.CTkFrame(
            self.main_container, fg_color=COLORS["bg_card"], corner_radius=16
        )
        self.options_section.pack(fill="x", pady=5)

        label = ctk.CTkLabel(
            self.options_section,
            text="Opciones de descarga",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        label.pack(anchor="w", padx=20, pady=(15, 8))

        options_inner = ctk.CTkFrame(self.options_section, fg_color="transparent")
        options_inner.pack(fill="x", padx=15, pady=(0, 15))

        # ── Resolución ──
        self.resolution_frame = ctk.CTkFrame(options_inner, fg_color="transparent")
        self.resolution_frame.pack(side="left", fill="x", expand=True, padx=5)

        res_label = ctk.CTkLabel(
            self.resolution_frame,
            text="🎬  Resolución",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
        )
        res_label.pack(anchor="w", pady=(0, 5))

        self.resolution_var = ctk.StringVar(value=RESOLUTIONS[0])
        self.resolution_menu = ctk.CTkOptionMenu(
            self.resolution_frame,
            variable=self.resolution_var,
            values=RESOLUTIONS,
            font=ctk.CTkFont(family="Segoe UI", size=13),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
            height=42,
            corner_radius=10,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=PLATFORM_TINTS["accent_hover_bg"],
            text_color=COLORS["text_primary"],
        )
        self.resolution_menu.pack(fill="x")

        # ── Audio ──
        self.audio_frame = ctk.CTkFrame(options_inner, fg_color="transparent")
        self.audio_frame.pack(side="left", fill="x", expand=True, padx=5)

        audio_label = ctk.CTkLabel(
            self.audio_frame,
            text="🎵  Audio",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
        )
        audio_label.pack(anchor="w", pady=(0, 5))

        self.audio_var = ctk.StringVar(value="Máxima calidad")
        self.audio_menu = ctk.CTkOptionMenu(
            self.audio_frame,
            variable=self.audio_var,
            values=["Máxima calidad", "Solo audio (MP3)", "Solo audio (M4A)"],
            font=ctk.CTkFont(family="Segoe UI", size=13),
            dropdown_font=ctk.CTkFont(family="Segoe UI", size=12),
            height=42,
            corner_radius=10,
            fg_color=COLORS["bg_input"],
            button_color=COLORS["accent_dim"],
            button_hover_color=COLORS["accent"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=PLATFORM_TINTS["accent_hover_bg"],
            text_color=COLORS["text_primary"],
        )
        self.audio_menu.pack(fill="x")

        # ── Info TikTok (oculto por defecto) ──
        self.tiktok_info_frame = ctk.CTkFrame(self.options_section, fg_color="transparent")

        self.tiktok_info_label = ctk.CTkLabel(
            self.tiktok_info_frame,
            text="ℹ️  TikTok se descarga automáticamente en la máxima calidad disponible con el nombre original.",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["tiktok"],
            wraplength=600,
        )
        self.tiktok_info_label.pack(padx=20, pady=10)

    def _build_folder_selector(self):
        section = ctk.CTkFrame(self.main_container, fg_color=COLORS["bg_card"], corner_radius=16)
        section.pack(fill="x", pady=5)

        inner = ctk.CTkFrame(section, fg_color="transparent")
        inner.pack(fill="x", padx=15, pady=12)

        folder_label = ctk.CTkLabel(
            inner,
            text="📁  Guardar en:",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        folder_label.pack(side="left", padx=(5, 10))

        self.folder_display = ctk.CTkLabel(
            inner,
            text=self.download_folder,
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
            anchor="w",
        )
        self.folder_display.pack(side="left", fill="x", expand=True)

        browse_btn = ctk.CTkButton(
            inner,
            text="Cambiar",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            width=80,
            height=34,
            corner_radius=10,
            fg_color=COLORS["bg_input"],
            border_color=COLORS["border"],
            border_width=1,
            hover_color=PLATFORM_TINTS["accent_hover_bg"],
            text_color=COLORS["text_secondary"],
            command=self._browse_folder,
        )
        browse_btn.pack(side="right", padx=5)

    def _build_download_button(self):
        btn_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        btn_frame.pack(fill="x", pady=10)

        self.download_btn = ctk.CTkButton(
            btn_frame,
            text="⬇  DESCARGAR VIDEO",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            height=56,
            corner_radius=14,
            fg_color=COLORS["accent"],
            hover_color=COLORS["accent_hover"],
            text_color=COLORS["text_primary"],
            command=self._start_download,
        )
        self.download_btn.pack(fill="x", padx=5)

    def _build_progress_section(self):
        self.progress_frame = ctk.CTkFrame(
            self.main_container, fg_color=COLORS["bg_card"], corner_radius=16
        )
        # No se muestra hasta que inicia una descarga

        self.progress_title = ctk.CTkLabel(
            self.progress_frame,
            text="Preparando descarga...",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        self.progress_title.pack(anchor="w", padx=20, pady=(15, 5))

        self.progress_detail = ctk.CTkLabel(
            self.progress_frame,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self.progress_detail.pack(anchor="w", padx=20, pady=(0, 8))

        self.progress_bar = ctk.CTkProgressBar(
            self.progress_frame,
            height=10,
            corner_radius=5,
            fg_color=COLORS["progress_bg"],
            progress_color=COLORS["accent"],
        )
        self.progress_bar.pack(fill="x", padx=20, pady=(0, 5))
        self.progress_bar.set(0)

        self.progress_percent = ctk.CTkLabel(
            self.progress_frame,
            text="0%",
            font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
            text_color=COLORS["accent"],
        )
        self.progress_percent.pack(anchor="e", padx=20, pady=(0, 12))

    def _build_history_section(self):
        self.history_frame = ctk.CTkFrame(
            self.main_container, fg_color=COLORS["bg_card"], corner_radius=16
        )
        self.history_frame.pack(fill="x", pady=(5, 0))

        header = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(12, 5))

        ctk.CTkLabel(
            header,
            text="📋  Historial de descargas",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="bold"),
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        self.history_count = ctk.CTkLabel(
            header,
            text="0 descargas",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self.history_count.pack(side="right")

        self.history_list = ctk.CTkScrollableFrame(
            self.history_frame,
            fg_color="transparent",
            height=100,
            corner_radius=0,
        )
        self.history_list.pack(fill="x", padx=10, pady=(0, 10))

        # Mensaje vacío
        self.empty_label = ctk.CTkLabel(
            self.history_list,
            text="No hay descargas aún. ¡Pega una URL y comienza!",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
        )
        self.empty_label.pack(pady=15)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  LÓGICA DE PLATAFORMA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _select_platform(self, name: str):
        self.selected_platform = name
        for btn_name, btn in self.platform_buttons.items():
            btn.set_selected(btn_name == name)
        self._update_platform_desc()
        self._update_platform_options()

    def _update_platform_desc(self):
        info = PLATFORM_INFO[self.selected_platform]
        self.platform_desc.configure(
            text=f"{info['icon']}  {info['description']}",
            text_color=info["color"],
        )

    def _update_platform_options(self):
        info = PLATFORM_INFO[self.selected_platform]
        if info["has_resolution"]:
            self.resolution_frame.pack(side="left", fill="x", expand=True, padx=5)
            self.resolution_menu.pack(fill="x")
            self.tiktok_info_frame.pack_forget()
        else:
            self.resolution_frame.pack_forget()
            self.tiktok_info_frame.pack(fill="x", padx=15, pady=(0, 10))

        if info["has_audio"]:
            self.audio_frame.pack(side="left", fill="x", expand=True, padx=5)
            self.audio_menu.pack(fill="x")
        else:
            self.audio_frame.pack_forget()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  ACCIONES UI
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _paste_url(self):
        try:
            text = self.clipboard_get()
            self.url_entry.delete(0, "end")
            self.url_entry.insert(0, text.strip())
        except Exception:
            pass

    def _browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.download_folder)
        if folder:
            self.download_folder = folder
            display = folder if len(folder) < 60 else "..." + folder[-57:]
            self.folder_display.configure(text=display)

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    #  DESCARGA
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    def _start_download(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showwarning("URL vacía", "Por favor, pega la URL del video que deseas descargar.")
            return
        if self.is_downloading:
            messagebox.showinfo("En progreso", "Ya hay una descarga en curso. Espera a que termine.")
            return

        self.is_downloading = True
        self.download_btn.configure(
            text="⏳  Descargando...",
            fg_color=COLORS["accent_dim"],
            state="disabled",
        )

        # Mostrar barra de progreso
        self.progress_frame.pack(fill="x", pady=5, before=self.history_frame)
        self.progress_bar.set(0)
        self.progress_percent.configure(text="0%")
        self.progress_title.configure(text="Preparando descarga...")
        self.progress_detail.configure(text=url[:80])

        # Color de la plataforma en la barra
        info = PLATFORM_INFO[self.selected_platform]
        self.progress_bar.configure(progress_color=info["color"])

        thread = threading.Thread(
            target=self._download_thread,
            args=(url,),
            daemon=True,
        )
        thread.start()

    def _get_ydl_opts(self, url: str) -> dict:
        """Construir opciones de yt-dlp según la plataforma y configuración."""
        platform = self.selected_platform
        info = PLATFORM_INFO[platform]

        # Nombre de archivo: usar el título original del video
        outtmpl = os.path.join(self.download_folder, "%(title)s.%(ext)s")

        opts = {
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "progress_hooks": [self._progress_hook],
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            # Evitar errores de certificados en Windows
            "nocheckcertificate": True,
        }

        audio_choice = self.audio_var.get() if info["has_audio"] else "Máxima calidad"

        if platform == "TikTok":
            # TikTok: máxima calidad, sin marca de agua si es posible
            opts["format"] = "best"
            # Intentar quitar marca de agua usando el formato de API
            opts["extractor_args"] = {"tiktok": {"api_hostname": ["api22-normal-c-useast2a.tiktokv.com"]}}

        elif audio_choice == "Solo audio (MP3)":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]
            opts["outtmpl"] = os.path.join(self.download_folder, "%(title)s.%(ext)s")

        elif audio_choice == "Solo audio (M4A)":
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "0",
            }]

        else:
            # Video con resolución seleccionada
            resolution = self.resolution_var.get() if info["has_resolution"] else "Mejor disponible"
            fmt = RESOLUTION_MAP.get(resolution, "bestvideo+bestaudio/best")
            opts["format"] = fmt

        # Embeber metadatos
        if "postprocessors" not in opts:
            opts["postprocessors"] = []
        opts["postprocessors"].append({"key": "FFmpegMetadata"})

        return opts

    def _progress_hook(self, d):
        """Callback de progreso de yt-dlp."""
        if d["status"] == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes", 0)

            if total > 0:
                pct = downloaded / total
                self.after(0, self._update_progress, pct, d)
            else:
                pct_str = d.get("_percent_str", "").strip()
                if pct_str:
                    try:
                        pct = float(pct_str.replace("%", "")) / 100
                        self.after(0, self._update_progress, pct, d)
                    except ValueError:
                        pass

        elif d["status"] == "finished":
            self.after(0, self._update_progress, 1.0, d)

    def _update_progress(self, pct: float, d: dict):
        """Actualizar UI de progreso desde el hilo principal."""
        self.progress_bar.set(pct)
        percent_text = f"{pct * 100:.1f}%"
        self.progress_percent.configure(text=percent_text)

        if d["status"] == "downloading":
            speed = d.get("_speed_str", "").strip()
            eta = d.get("_eta_str", "").strip()
            filename = d.get("filename", "")
            basename = os.path.basename(filename) if filename else ""

            self.progress_title.configure(text=f"Descargando: {basename[:60]}")

            detail_parts = []
            if speed:
                detail_parts.append(f"Velocidad: {speed}")
            if eta:
                detail_parts.append(f"Tiempo restante: {eta}")
            self.progress_detail.configure(text="  ·  ".join(detail_parts))

        elif d["status"] == "finished":
            self.progress_title.configure(text="✅ Procesando archivo...")
            self.progress_detail.configure(text="Fusionando video y audio...")

    def _download_thread(self, url: str):
        """Hilo de descarga."""
        video_title = url[:50]
        try:
            opts = self._get_ydl_opts(url)
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                video_title = info.get("title", url[:50])
                self.after(0, self._update_title_progress, video_title)

                ydl.download([url])

            self.after(0, self._download_complete, video_title, True, "")

        except Exception as e:
            error_msg = str(e)
            self.after(0, self._download_complete, video_title, False, error_msg)

    def _update_title_progress(self, title: str):
        self.progress_title.configure(text=f"Descargando: {title[:60]}")

    def _download_complete(self, title: str, success: bool, error: str):
        """Callback cuando la descarga termina."""
        self.is_downloading = False
        self.download_btn.configure(
            text="⬇  DESCARGAR VIDEO",
            fg_color=COLORS["accent"],
            state="normal",
        )

        if success:
            self.progress_bar.set(1.0)
            self.progress_percent.configure(text="100%")
            self.progress_title.configure(text=f"✅ ¡Descarga completada!")
            self.progress_detail.configure(text=f"{title}")
            self.progress_bar.configure(progress_color=COLORS["success"])

            self._add_history(title, "completado")
            self.url_entry.delete(0, "end")

        else:
            self.progress_bar.set(1.0)
            self.progress_title.configure(text="❌ Error en la descarga")
            self.progress_detail.configure(
                text=error[:100] if error else "Error desconocido"
            )
            self.progress_bar.configure(progress_color=COLORS["error"])
            self.progress_percent.configure(text="Error")

            self._add_history(title, "error")

    def _add_history(self, title: str, status: str):
        """Agregar entrada al historial de descargas."""
        # Quitar mensaje vacío
        if self.empty_label.winfo_exists():
            self.empty_label.destroy()

        entry = DownloadLogEntry(
            self.history_list,
            title=title,
            status=status,
            platform=self.selected_platform,
        )
        entry.pack(fill="x", pady=2)

        self.download_history.append({
            "title": title,
            "status": status,
            "platform": self.selected_platform,
            "time": datetime.now().strftime("%H:%M:%S"),
        })

        count = len(self.download_history)
        self.history_count.configure(text=f"{count} descarga{'s' if count != 1 else ''}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PUNTO DE ENTRADA
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

if __name__ == "__main__":
    app = App()
    app.mainloop()
