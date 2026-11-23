"""The main Purge Bot window: Run, Settings, Messages and Guide tabs."""
import base64
import binascii
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import messagebox, ttk

import config
from gui import theme
from gui.bot_process import BotProcess
from gui.guide import render_guide

INVITE_PERMISSIONS = 85062  # view, send, embed, react, read history, kick, ban
PORTAL_URL = "https://discord.com/developers/applications"
MAX_LOG_LINES = 3000

# (setting, label, type, minimum, explanation)
NUMBER_FIELDS = [
    ("INACTIVE_DAYS", "Inactive after (days)", float, 0,
     "Members with no messages for this many days count as inactive."),
    ("RESPONSE_DAYS", "Time to answer (days)", float, 0,
     "How long surveyed members have to reply before they're kicked."),
    ("ANSWER_QUIET_MINUTES", "Wait after last reply (minutes)", float, 0,
     "How long the bot waits after a member's last DM before posting their answer, "
     "so they can write it in several messages."),
    ("MIN_VOTES", "Mod votes needed", int, 1,
     "How many mods must vote the same way before keep / kick / ban is decided."),
    ("DM_DELAY_SECONDS", "Pause between DMs (seconds)", float, 0,
     "Spacing between survey DMs, so Discord doesn't flag the bot as spam."),
]

# (setting, name, when it's sent)
MESSAGE_FIELDS = [
    ("SURVEY_MESSAGE", "Survey", "Sent to each inactive member by !survey confirm."),
    ("THANKS_MESSAGE", "Plea received", "Sent once their answer has been passed on to the mods."),
    ("KEEP_MESSAGE", "Spared", "Sent when the mods vote to keep them, or when a surveyed member is exempted."),
    ("REMOVED_MESSAGE", "Purged", "Sent just before they're kicked or banned."),
    ("REMINDER_MESSAGE", "Reminder", "Sent by !remind to members who haven't answered yet. "
                                     "{deadline} shows their original deadline."),
]


def asset_path(name):
    """Find a file in assets/, either inside the built .exe or next to the app."""
    for folder in (getattr(sys, "_MEIPASS", None), config.BASE_DIR):
        if folder:
            path = os.path.join(folder, "assets", name)
            if os.path.exists(path):
                return path
    return None


def app_id_from_token(token):
    """A bot token starts with the bot's ID, base64-encoded."""
    try:
        part = token.split(".")[0]
        part += "=" * (-len(part) % 4)
        value = base64.b64decode(part).decode()
        return value if value.isdigit() else None
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def format_number(value):
    return str(int(value)) if float(value).is_integer() else str(value)


def is_test_mode(settings):
    return settings["INACTIVE_DAYS"] < 30 or settings["RESPONSE_DAYS"] < 1


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Purge Bot")
        self.geometry("960x700")
        self.minsize(780, 580)
        self._set_window_icon()
        theme.apply(self)

        self.bot = BotProcess()
        self.settings = config.load_settings()
        self.unsaved = False
        self.closing = False

        self._build_header()
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for title, builder in (("  Run  ", self._build_run_tab), ("Settings", self._build_settings_tab),
                               ("Messages", self._build_messages_tab), ("Guide", self._build_guide_tab)):
            frame = ttk.Frame(notebook, style="Panel.TFrame", padding=18)
            builder(frame)
            notebook.add(frame, text=title)

        self._refresh_test_banner()
        self._set_status("stopped")
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self._poll_bot)

    # ------------------------------------------------------------------ header

    def _set_window_icon(self):
        ico, png = asset_path("purgebot.ico"), asset_path("icon.png")
        try:
            if ico and os.name == "nt":
                self.iconbitmap(ico)  # sharper at small sizes on Windows
            elif png:
                self.iconphoto(True, tk.PhotoImage(file=png))
        except tk.TclError:
            pass

    def _build_header(self):
        header = ttk.Frame(self, padding=(16, 14, 16, 10))
        header.pack(fill="x")
        picture = asset_path("header.png")
        try:
            self.header_image = tk.PhotoImage(file=picture) if picture else None
        except tk.TclError:
            self.header_image = None
        if self.header_image:
            ttk.Label(header, image=self.header_image).pack(side="left", padx=(0, 12))
        else:
            ttk.Label(header, text="😈", style="Emoji.TLabel").pack(side="left", padx=(0, 10))
        titles = ttk.Frame(header)
        titles.pack(side="left")
        ttk.Label(titles, text="Purge Bot", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titles, text="Finds the silent, makes them plead, and purges the ones who don't.",
                  style="Muted.TLabel").pack(anchor="w")

        status = ttk.Frame(header)
        status.pack(side="right")
        self.status_dot = tk.Canvas(status, width=14, height=14, bg=theme.BG, highlightthickness=0)
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status_label = ttk.Label(status, text="", style="Status.TLabel")
        self.status_label.pack(side="left")

    def _set_status(self, state, detail=""):
        colors = {"stopped": theme.MUTED, "starting": theme.AMBER, "running": theme.GREEN,
                  "stopping": theme.AMBER, "error": theme.RED}
        names = {"stopped": "Stopped", "starting": "Starting...", "running": "Running",
                 "stopping": "Stopping...", "error": "Stopped with an error"}
        self.status_dot.delete("all")
        self.status_dot.create_oval(2, 2, 12, 12, fill=colors[state], outline="")
        self.status_label.configure(text=names[state] + (f": {detail}" if detail else ""))
        self.state = state
        busy = state in ("starting", "running", "stopping")
        self.start_btn.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if state in ("starting", "running") else "disabled")

    # ------------------------------------------------------------------ run tab

    def _build_run_tab(self, tab):
        self.test_banner = ttk.Label(tab, style="Warning.TLabel", wraplength=860, justify="left")

        token_box = ttk.Frame(tab, style="Panel.TFrame")
        token_box.pack(fill="x")
        self.token_box = token_box
        ttk.Label(token_box, text="Bot token", style="PanelBold.TLabel").pack(anchor="w")
        row = ttk.Frame(token_box, style="Panel.TFrame")
        row.pack(fill="x", pady=(4, 2))
        self.token_var = tk.StringVar(value=config.load_token())
        self._token_save_job = None
        self.token_var.trace_add("write", lambda *_: self._schedule_token_save())
        self.token_entry = ttk.Entry(row, textvariable=self.token_var, show="•", font=theme.FONT_MONO)
        self.token_entry.pack(side="left", fill="x", expand=True)
        self.show_token = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, text="Show", variable=self.show_token, style="Panel.TCheckbutton",
                        command=lambda: self.token_entry.configure(show="" if self.show_token.get() else "•")
                        ).pack(side="left", padx=(10, 0))
        ttk.Label(token_box, style="PanelMuted.TLabel",
                  text="Developer Portal → your application → Bot → Reset Token. It's saved "
                       "automatically in token.txt next to this app. Never share it.").pack(anchor="w")

        buttons = ttk.Frame(tab, style="Panel.TFrame")
        buttons.pack(fill="x", pady=(16, 12))
        self.start_btn = ttk.Button(buttons, text="▶  Start bot", style="Accent.TButton", command=self._start)
        self.start_btn.pack(side="left")
        self.stop_btn = ttk.Button(buttons, text="■  Stop bot", command=self._stop)
        self.stop_btn.pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Open Developer Portal",
                   command=lambda: webbrowser.open(PORTAL_URL)).pack(side="right")
        ttk.Button(buttons, text="Copy invite link", command=self._copy_invite).pack(side="right", padx=(0, 8))

        log_head = ttk.Frame(tab, style="Panel.TFrame")
        log_head.pack(fill="x")
        ttk.Label(log_head, text="Bot log", style="PanelBold.TLabel").pack(side="left")
        ttk.Button(log_head, text="Clear", command=self._clear_log).pack(side="right")

        log_frame = ttk.Frame(tab, style="Panel.TFrame")
        log_frame.pack(fill="both", expand=True, pady=(6, 0))
        self.log = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        theme.style_text(self.log, mono=True)
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        self.log.tag_configure("error", foreground=theme.RED)
        self.log.tag_configure("dim", foreground=theme.MUTED)
        self.log.tag_configure("app", foreground=theme.ACCENT_HOVER)
        self._log("Press Start to summon the bot. Its output will appear here.", "app")

    def _schedule_token_save(self):
        """Save the token shortly after it's pasted or edited."""
        if self._token_save_job:
            self.after_cancel(self._token_save_job)
        self._token_save_job = self.after(600, self._save_token_if_valid)

    def _save_token_if_valid(self):
        self._token_save_job = None
        token = self.token_var.get().strip()
        if token and app_id_from_token(token) and len(token.split(".")) == 3:
            if token != config.load_token():
                config.save_token(token)
                self._log("Token saved.", "app")

    def _log(self, line, tag=None):
        if tag is None:
            if any(w in line for w in ("ERROR", "Traceback", "Exception", "Error:")):
                tag = "error"
            elif "[INFO" in line or "[WARNING" in line or "[DEBUG" in line:
                tag = "dim"  # routine discord.py log lines
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n", tag or ())
        lines = int(self.log.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            self.log.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        self.log.configure(state="disabled")
        self.log.see("end")

    def _clear_log(self):
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def _refresh_test_banner(self):
        s = self.settings
        if is_test_mode(s):
            self.test_banner.configure(text=(
                f"⚠  Test settings are active: members count as inactive after "
                f"{format_number(s['INACTIVE_DAYS'])} days and get "
                f"{format_number(s['RESPONSE_DAYS'])} days to answer. Only use these in a test server. "
                f"Go to Settings → Restore real defaults before using the bot for real."))
            self.test_banner.pack(fill="x", pady=(0, 14), before=self.token_box)
        else:
            self.test_banner.pack_forget()

    def _start(self):
        token = self.token_var.get().strip()
        if not token:
            messagebox.showwarning("No token", "Paste your bot token first.\n\n"
                                   "Developer Portal → your application → Bot → Reset Token.")
            return
        if len(token.split(".")) != 3 or app_id_from_token(token) is None:
            messagebox.showwarning("That doesn't look like a bot token",
                                   "A bot token has three parts separated by dots.\n\n"
                                   "Make sure you copied it from the Bot page, not the "
                                   "Client Secret or Public Key.")
            return
        if self.unsaved:
            answer = messagebox.askyesnocancel("Unsaved changes",
                                               "You have unsaved settings or messages. Save them before starting?")
            if answer is None or (answer and not self._save_all()):
                return
        config.save_token(token)
        try:
            self.bot.start()
        except OSError as e:
            messagebox.showerror("Couldn't start the bot", str(e))
            return
        self._log("--- Starting bot ---", "app")
        self._set_status("starting")

    def _stop(self):
        if self.bot.running:
            self._log("--- Stopping bot (saving data first) ---", "app")
            self.bot.stop()
            self._set_status("stopping")

    def _poll_bot(self):
        while not self.bot.output.empty():
            item = self.bot.output.get_nowait()
            if isinstance(item, tuple):
                code = item[1]
                self._log(f"--- Bot stopped (exit code {code}) ---", "app")
                self._set_status("stopped" if code == 0 else "error")
                if self.closing:
                    self.destroy()
                    return
            else:
                self._log(item)
                if "Logged in as" in item:
                    self._set_status("running", item.split("Logged in as", 1)[1].strip())
                elif "Syncing members" in item and self.state == "running":
                    self.status_label.configure(text="Running: scanning message history...")
                elif "channels scanned" in item and self.state == "running":
                    self.status_label.configure(text="Running: ready")
        self.after(150, self._poll_bot)

    def _copy_invite(self):
        app_id = app_id_from_token(self.token_var.get().strip())
        if not app_id:
            messagebox.showwarning("No valid token", "Paste your bot token first. The invite link is "
                                   "built from it.")
            return
        link = (f"https://discord.com/oauth2/authorize?client_id={app_id}"
                f"&scope=bot&permissions={INVITE_PERMISSIONS}")
        self.clipboard_clear()
        self.clipboard_append(link)
        if messagebox.askyesno("Invite link copied", f"{link}\n\nThe link is copied. Open it in your browser now?"):
            webbrowser.open(link)

    # ------------------------------------------------------------------ settings tab

    def _build_settings_tab(self, tab):
        ttk.Label(tab, text="Changes take effect the next time the bot starts.",
                  style="PanelMuted.TLabel").pack(anchor="w", pady=(0, 12))
        grid = ttk.Frame(tab, style="Panel.TFrame")
        grid.pack(fill="x")
        grid.columnconfigure(2, weight=1)

        self.number_vars = {}
        rows = NUMBER_FIELDS + [("COMMAND_PREFIX", "Command prefix", str, None,
                                 "What commands start with, e.g. ! for !survey.")]
        for r, (key, label, _, _, help_text) in enumerate(rows):
            value = self.settings[key]
            var = tk.StringVar(value=format_number(value) if key != "COMMAND_PREFIX" else value)
            var.trace_add("write", lambda *_: self._mark_unsaved())
            self.number_vars[key] = var
            ttk.Label(grid, text=label, style="PanelBold.TLabel").grid(row=r, column=0, sticky="w", pady=7)
            ttk.Entry(grid, textvariable=var, width=10).grid(row=r, column=1, sticky="w", padx=14)
            ttk.Label(grid, text=help_text, style="PanelMuted.TLabel", wraplength=480,
                      justify="left").grid(row=r, column=2, sticky="w")

        buttons = ttk.Frame(tab, style="Panel.TFrame")
        buttons.pack(fill="x", pady=(22, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save_all).pack(side="left")
        ttk.Button(buttons, text="Use test values",
                   command=lambda: self._fill_numbers(config.TEST_VALUES)).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="Restore real defaults",
                   command=lambda: self._fill_numbers(config.DEFAULTS)).pack(side="left", padx=(8, 0))
        self.settings_msg = ttk.Label(tab, text="", style="Saved.TLabel")
        self.settings_msg.pack(anchor="w", pady=(10, 0))

        ttk.Label(tab, style="PanelMuted.TLabel", wraplength=860, justify="left",
                  text="Test values make everyone without mod permissions count as inactive and give "
                       "them about 4 minutes to reply. Use them only in a test server, with a test bot. "
                       "Press Save after choosing either preset.").pack(anchor="w", pady=(18, 0))

    def _fill_numbers(self, values):
        for key, var in self.number_vars.items():
            if key in values:
                var.set(format_number(values[key]) if key != "COMMAND_PREFIX" else values[key])

    def _mark_unsaved(self):
        self.unsaved = True
        if hasattr(self, "settings_msg"):
            self.settings_msg.configure(text="Unsaved changes", style="Error.TLabel")

    def _collect_numbers(self):
        values = {}
        for key, label, kind, minimum, _ in NUMBER_FIELDS:
            raw = self.number_vars[key].get().strip().replace(",", ".")
            try:
                value = kind(float(raw)) if kind is int else float(raw)
            except ValueError:
                raise ValueError(f"\"{label}\" must be a number.")
            if kind is int and float(raw) != int(float(raw)):
                raise ValueError(f"\"{label}\" must be a whole number.")
            if value < minimum:
                raise ValueError(f"\"{label}\" can't be less than {minimum}.")
            values[key] = int(value) if float(value).is_integer() else value
        prefix = self.number_vars["COMMAND_PREFIX"].get().strip()
        if not prefix or " " in prefix:
            raise ValueError("\"Command prefix\" can't be empty or contain spaces.")
        values["COMMAND_PREFIX"] = prefix
        return values

    # ------------------------------------------------------------------ messages tab

    def _build_messages_tab(self, tab):
        ttk.Label(tab, style="PanelMuted.TLabel", wraplength=860, justify="left",
                  text="What the bot says in its DMs. These words are filled in for you in every message: "
                       "{name} (their name), {server} (server name), {deadline} (their reply deadline) and "
                       "{quiet} (the wait-after-last-reply minutes). Discord formatting like **bold** and "
                       "*italic* works.").pack(anchor="w", pady=(0, 12))

        body = ttk.Frame(tab, style="Panel.TFrame")
        body.pack(fill="both", expand=True)
        picker = ttk.Frame(body, style="Panel.TFrame")
        picker.pack(side="left", fill="y", padx=(0, 16))

        self.message_buffers = {key: self.settings[key] for key, _, _ in MESSAGE_FIELDS}
        self.current_message = tk.StringVar(value=MESSAGE_FIELDS[0][0])
        self.shown_message = None
        for key, name, _ in MESSAGE_FIELDS:
            ttk.Radiobutton(picker, text=name, value=key, variable=self.current_message,
                            style="Panel.TRadiobutton", command=self._show_message).pack(anchor="w", pady=4)

        editor = ttk.Frame(body, style="Panel.TFrame")
        editor.pack(side="left", fill="both", expand=True)
        self.message_when = ttk.Label(editor, style="PanelMuted.TLabel")
        self.message_when.pack(anchor="w", pady=(0, 6))
        self.message_text = tk.Text(editor, wrap="word", height=12, undo=True)
        theme.style_text(self.message_text)
        self.message_text.pack(fill="both", expand=True)
        self.message_text.bind("<<Modified>>", self._on_message_edit)

        buttons = ttk.Frame(tab, style="Panel.TFrame")
        buttons.pack(fill="x", pady=(14, 0))
        ttk.Button(buttons, text="Save", style="Accent.TButton", command=self._save_all).pack(side="left")
        ttk.Button(buttons, text="Reset this message to default",
                   command=self._reset_message).pack(side="left", padx=(8, 0))
        self.message_count = ttk.Label(buttons, style="PanelMuted.TLabel")
        self.message_count.pack(side="right")
        self._show_message()

    def _store_message(self):
        if self.shown_message:
            self.message_buffers[self.shown_message] = self.message_text.get("1.0", "end-1c")

    def _show_message(self):
        self._store_message()
        key = self.current_message.get()
        self.shown_message = key
        self.message_when.configure(text=next(when for k, _, when in MESSAGE_FIELDS if k == key))
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", self.message_buffers[key])
        self.message_text.edit_modified(False)
        self._update_count()

    def _on_message_edit(self, _event=None):
        if self.message_text.edit_modified():
            self.message_text.edit_modified(False)
            self._mark_unsaved()
            self._update_count()

    def _update_count(self):
        n = len(self.message_text.get("1.0", "end-1c"))
        self.message_count.configure(text=f"{n} / 2000 characters")

    def _reset_message(self):
        key = self.current_message.get()
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", config.DEFAULTS[key])

    def _collect_messages(self):
        self._store_message()
        values = {}
        for key, name, _ in MESSAGE_FIELDS:
            text = self.message_buffers[key].strip()
            if not text:
                raise ValueError(f"The \"{name}\" message is empty.")
            try:
                filled = text.format(**config.MESSAGE_PLACEHOLDERS)
            except (KeyError, IndexError, ValueError):
                raise ValueError(f"The \"{name}\" message has an unknown {{word}} in curly braces. "
                                 "Only {name}, {server}, {deadline} and {quiet} are allowed.")
            if len(filled) > 1900:
                raise ValueError(f"The \"{name}\" message is too long for a Discord DM "
                                 "(keep it under about 1900 characters).")
            values[key] = text
        return values

    # ------------------------------------------------------------------ guide tab

    def _build_guide_tab(self, tab):
        text = tk.Text(tab, height=10)
        theme.style_text(text)
        text.configure(bg=theme.PANEL, highlightthickness=0, padx=6)
        scroll = ttk.Scrollbar(tab, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        render_guide(text)

    # ------------------------------------------------------------------ saving & closing

    def _save_all(self):
        try:
            values = {**self.settings, **self._collect_numbers(), **self._collect_messages()}
        except ValueError as e:
            messagebox.showerror("Can't save", str(e))
            return False
        config.save_settings(values)
        self.settings = values
        self.unsaved = False
        note = "Saved. Stop and start the bot to apply." if self.bot.running else "Saved."
        self.settings_msg.configure(text="✓ " + note, style="Saved.TLabel")
        self._refresh_test_banner()
        return True

    def _on_close(self):
        self._save_token_if_valid()
        if self.unsaved:
            answer = messagebox.askyesnocancel("Unsaved changes", "Save your changes before closing?")
            if answer is None or (answer and not self._save_all()):
                return
        if self.bot.running:
            if not messagebox.askyesno("Purge Bot is running", "Closing the app stops the bot. Close anyway?"):
                return
            self.closing = True
            self._stop()  # the window closes once the bot has saved and exited
            return
        self.destroy()
