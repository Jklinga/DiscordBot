"""Colors, fonts and widget styles for the app (a dark, slightly devilish look)."""
from tkinter import ttk

BG = "#17131c"
PANEL = "#221c29"
PANEL_2 = "#2d2536"
BORDER = "#3b3146"
TEXT = "#eee8f2"
MUTED = "#a99db4"
ACCENT = "#e0413a"
ACCENT_HOVER = "#ff5a4f"
ACCENT_PRESSED = "#b8302a"
GREEN = "#4fcf7d"
AMBER = "#f0b54a"
RED = "#ff6b62"

FONT = ("Segoe UI", 10)
FONT_BOLD = ("Segoe UI Semibold", 10)
FONT_SMALL = ("Segoe UI", 9)
FONT_TITLE = ("Segoe UI Semibold", 20)
FONT_H2 = ("Segoe UI Semibold", 13)
FONT_EMOJI = ("Segoe UI Emoji", 26)
FONT_MONO = ("Consolas", 10)


def apply(root):
    root.configure(bg=BG)
    style = ttk.Style(root)
    style.theme_use("clam")

    style.configure(".", background=BG, foreground=TEXT, font=FONT, bordercolor=BORDER,
                    lightcolor=BG, darkcolor=BG, troughcolor=PANEL, focuscolor=ACCENT)
    style.configure("TFrame", background=BG)
    style.configure("Panel.TFrame", background=PANEL)
    style.configure("TLabel", background=BG, foreground=TEXT)
    style.configure("Panel.TLabel", background=PANEL, foreground=TEXT)
    style.configure("Muted.TLabel", background=BG, foreground=MUTED, font=FONT_SMALL)
    style.configure("PanelMuted.TLabel", background=PANEL, foreground=MUTED, font=FONT_SMALL)
    style.configure("PanelBold.TLabel", background=PANEL, foreground=TEXT, font=FONT_BOLD)
    style.configure("Title.TLabel", background=BG, foreground=TEXT, font=FONT_TITLE)
    style.configure("Emoji.TLabel", background=BG, foreground=ACCENT, font=FONT_EMOJI)
    style.configure("Status.TLabel", background=BG, foreground=TEXT, font=FONT_BOLD)
    style.configure("Warning.TLabel", background="#3a2a12", foreground=AMBER, font=FONT_SMALL,
                    padding=(10, 6))
    style.configure("Saved.TLabel", background=PANEL, foreground=GREEN, font=FONT_SMALL)
    style.configure("Error.TLabel", background=PANEL, foreground=RED, font=FONT_SMALL)

    style.configure("TNotebook", background=BG, borderwidth=0, bordercolor=BG,
                    lightcolor=BG, darkcolor=BG, tabmargins=(0, 4, 0, 0))
    style.configure("TNotebook.Tab", background=BG, foreground=MUTED, padding=(16, 8),
                    borderwidth=0, bordercolor=BG, lightcolor=BG, darkcolor=BG, font=FONT_BOLD)
    style.map("TNotebook.Tab",
              background=[("selected", PANEL)],
              lightcolor=[("selected", PANEL)],
              bordercolor=[("selected", PANEL)],
              foreground=[("selected", TEXT), ("active", TEXT)])

    style.configure("TButton", background=PANEL_2, foreground=TEXT, padding=(14, 7),
                    borderwidth=0, focusthickness=0)
    style.map("TButton",
              background=[("disabled", PANEL), ("pressed", BORDER), ("active", BORDER)],
              foreground=[("disabled", "#6d6377")])
    style.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=FONT_BOLD)
    style.map("Accent.TButton",
              background=[("disabled", PANEL_2), ("pressed", ACCENT_PRESSED), ("active", ACCENT_HOVER)],
              foreground=[("disabled", "#6d6377")])

    style.configure("TEntry", fieldbackground=PANEL_2, foreground=TEXT, insertcolor=TEXT,
                    bordercolor=BORDER, lightcolor=PANEL_2, darkcolor=PANEL_2, padding=6)
    style.map("TEntry", bordercolor=[("focus", ACCENT)], lightcolor=[("focus", ACCENT)])

    for name, bg in (("TCheckbutton", BG), ("Panel.TCheckbutton", PANEL),
                     ("TRadiobutton", BG), ("Panel.TRadiobutton", PANEL)):
        style.configure(name, background=bg, foreground=TEXT, indicatorbackground=PANEL_2,
                        indicatorforeground=ACCENT, focusthickness=0)
        style.map(name, background=[("active", bg)],
                  indicatorbackground=[("selected", ACCENT), ("active", BORDER)])

    style.configure("Vertical.TScrollbar", background=PANEL_2, troughcolor=PANEL,
                    bordercolor=PANEL, arrowcolor=MUTED, gripcount=0)
    style.map("Vertical.TScrollbar", background=[("active", BORDER)])


def style_text(widget, mono=False):
    """tk.Text widgets aren't themed by ttk, so color them by hand."""
    widget.configure(bg=PANEL_2, fg=TEXT, insertbackground=TEXT, selectbackground=ACCENT,
                     selectforeground="#ffffff", relief="flat", borderwidth=0,
                     highlightthickness=1, highlightbackground=BORDER, highlightcolor=ACCENT,
                     font=FONT_MONO if mono else FONT, padx=10, pady=8)
