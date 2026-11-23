"""Loading and saving Members.json, and keeping each member's record up to date."""
import asyncio
import json
import os

from discord.ext import tasks

from config import DATA_FILE
from inactivity.helpers import iso, parse

# Stops scans, surveys and processing from running at the same time
work_lock = asyncio.Lock()

_dirty = False


def _load():
    if not os.path.exists(DATA_FILE):
        return {"guilds": {}}
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if "guilds" not in raw:
        # Old format from the first version of the bot: back it up and rebuild
        # (the history scan recovers everyone's activity anyway).
        backup = DATA_FILE.replace("Members.json", "Members.old.json")
        os.replace(DATA_FILE, backup)
        print("Old Members.json backed up to Members.old.json, rebuilding.")
        return {"guilds": {}}
    return raw


data = _load()


def save_data():
    global _dirty
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    os.replace(tmp, DATA_FILE)  # atomic: a crash mid-save can't corrupt the file
    _dirty = False


def mark_dirty():
    global _dirty
    _dirty = True


@tasks.loop(seconds=60)
async def autosave():
    """Saves at most once a minute instead of on every message."""
    if _dirty:
        save_data()


def guild_data(guild):
    g = data["guilds"].setdefault(str(guild.id), {})
    g.setdefault("mod_channel_id", None)
    g.setdefault("last_scan", None)
    g.setdefault("exempt", [])
    g.setdefault("members", {})
    return g


def member_record(member):
    """Create or update a member's stored info without wiping other fields."""
    rec = guild_data(member.guild)["members"].setdefault(str(member.id), {})
    rec.setdefault("last_active", None)
    rec.setdefault("survey", None)
    rec["username"] = member.name
    rec["display_name"] = member.display_name
    rec["nickname"] = member.nick
    rec["joined_at"] = iso(member.joined_at)
    mark_dirty()
    return rec


def remove_member(guild, user_id):
    if guild_data(guild)["members"].pop(str(user_id), None) is not None:
        mark_dirty()
        return True
    return False


def bump_activity(rec, when):
    current = parse(rec.get("last_active"))
    if current is None or when > current:
        rec["last_active"] = iso(when)
        mark_dirty()
