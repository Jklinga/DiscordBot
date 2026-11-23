"""Settings for Purge Bot.

The values below are the defaults. Anything saved in settings.json (which the
Purge Bot app edits for you) overrides them, so you normally don't edit this file.
"""
import json
import os
import runpy
import sys

# Folder the bot's files live in. When built into an .exe, that's the .exe's folder.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
    # Started straight from PyInstaller's dist\ folder: use the bot folder above it
    _parent = os.path.dirname(BASE_DIR)
    if os.path.basename(BASE_DIR).lower() == "dist" and os.path.exists(os.path.join(_parent, "Bot.py")):
        BASE_DIR = _parent
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATA_FILE = os.path.join(BASE_DIR, "Members.json")
SETTINGS_FILE = os.path.join(BASE_DIR, "settings.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.txt")
LEGACY_KEYS_FILE = os.path.join(BASE_DIR, "Keys.py")

# Reactions mods use on survey answers in the review channel
VOTES = {"✅": "keep", "👢": "kick", "🔨": "ban"}

# {name}, {server}, {deadline} and {quiet} are filled in automatically in every message.
MESSAGE_PLACEHOLDERS = {"name": "Alex", "server": "My Server", "deadline": "<date>", "quiet": 10}

DEFAULTS = {
    "INACTIVE_DAYS": 365,         # no messages for this many days = inactive
    "RESPONSE_DAYS": 3,           # how long people get to answer the survey
    "MIN_VOTES": 2,               # mod votes needed before a keep/kick/ban decision counts
    "DM_DELAY_SECONDS": 3,        # pause between survey DMs (avoids Discord spam flags)
    "ANSWER_QUIET_MINUTES": 10,   # wait this long after a member's last reply before passing it to mods
    "COMMAND_PREFIX": "!",

    "SURVEY_MESSAGE": (
        "Well, well, well... **{name}**. 😈\n\n"
        "It is I, **Purge Bot**. My records show you haven't made a peep in **{server}** "
        "for over a *year*. Your name has been written in my Little Black Book of Purging. "
        "*Muahahaha!*\n\n"
        "But I am a merciful demon (occasionally). If you wish to keep your soul... "
        "er, your *spot*, **reply to this message** and plead your case:\n"
        "1. Why should you be spared from the purge?\n"
        "2. Do you swear to obey the Mods?\n\n"
        "Grovel in as many messages as you like. Once you've gone quiet for {quiet} minutes, "
        "I'll deliver your plea to the Council of Moderators, who will decide your fate.\n\n"
        "Stay silent past {deadline} and I shall **banish you from the server**. 🔥"
    ),
    "THANKS_MESSAGE": (
        "*Excellent...* 😈 Your plea has been delivered to the Council of Moderators of **{server}**. "
        "Now we wait. Try not to sweat too much."
    ),
    "KEEP_MESSAGE": (
        "Bah! The Council of Moderators of **{server}** has decided to **spare you**. 😤\n"
        "You may stay... *this time*. Don't make me come back for you."
    ),
    "REMOVED_MESSAGE": (
        "The deed is done. You have been **purged** from **{server}** for inactivity. 🔥😈\n"
        "Farewell, mortal. *Muahahaha!*"
    ),
    "REMINDER_MESSAGE": (
        "Tick tock, **{name}**... ⏳😈\n\n"
        "I'm still waiting for your plea, and the Council of Moderators of **{server}** grows "
        "impatient. Not a single word from you yet.\n\n"
        "If you want to stay, tell us why you should be spared. "
        "As many messages as you like.\n\n"
        "Your time runs out {deadline}. After that... you shall be purged from the server. 🔥"
    ),
}

# Quick preset for trying the bot out in a test server
TEST_VALUES = {
    "INACTIVE_DAYS": 0,
    "RESPONSE_DAYS": 0.003,       # about 4 minutes
    "MIN_VOTES": 1,
    "DM_DELAY_SECONDS": 1,
    "ANSWER_QUIET_MINUTES": 1,
}


# ---------- Settings file ----------

def load_settings():
    values = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            values.update({k: v for k, v in saved.items() if k in DEFAULTS})
        except (OSError, ValueError) as e:
            print(f"Could not read settings.json ({e}), using defaults.")
    return values


def save_settings(values):
    clean = {k: values[k] for k in DEFAULTS if k in values}
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=4, ensure_ascii=False)


# ---------- Bot token ----------

def load_token():
    """Token from token.txt, or from an old-style Keys.py if that's all there is."""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    if os.path.exists(LEGACY_KEYS_FILE):
        try:
            return str(runpy.run_path(LEGACY_KEYS_FILE).get("discord_key", "")).strip()
        except Exception:
            pass
    return ""


def save_token(token):
    with open(TOKEN_FILE, "w", encoding="utf-8") as f:
        f.write(token.strip())


# ---------- Values the bot uses ----------

_s = load_settings()
INACTIVE_DAYS = _s["INACTIVE_DAYS"]
RESPONSE_DAYS = _s["RESPONSE_DAYS"]
MIN_VOTES = _s["MIN_VOTES"]
DM_DELAY_SECONDS = _s["DM_DELAY_SECONDS"]
ANSWER_QUIET_MINUTES = _s["ANSWER_QUIET_MINUTES"]
COMMAND_PREFIX = _s["COMMAND_PREFIX"]
SURVEY_MESSAGE = _s["SURVEY_MESSAGE"]
THANKS_MESSAGE = _s["THANKS_MESSAGE"]
KEEP_MESSAGE = _s["KEEP_MESSAGE"]
REMOVED_MESSAGE = _s["REMOVED_MESSAGE"]
REMINDER_MESSAGE = _s["REMINDER_MESSAGE"]
