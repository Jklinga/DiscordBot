"""Small shared helpers: dates, permissions and sending messages."""
from datetime import datetime, timezone

import discord

from config import ANSWER_QUIET_MINUTES

NO_PINGS = discord.AllowedMentions.none()

# Survey statuses that are still in progress:
#   pending   = DM sent, no reply yet
#   answering = has replied, waiting ANSWER_QUIET_MINUTES in case they send more
#   answered  = passed on to mods for a vote
#   no_dm     = couldn't be DM'd, passed on to mods for a vote
# Finished statuses: cleared (wrote in the server again), exempted, kept, kicked, banned
OPEN_STATUSES = ("pending", "answering", "answered", "no_dm")


# ---------- Dates ----------

def utcnow():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat() if dt else None


def parse(s):
    return datetime.fromisoformat(s) if s else None


def ts(dt, style="R"):
    """Discord timestamp that shows in each viewer's local time."""
    return f"<t:{int(dt.timestamp())}:{style}>"


def fill(template, guild, member=None, deadline=None):
    """Fill in a message from settings. Every message may use {name}, {server}, {deadline} and {quiet}."""
    return template.format(
        name=member.display_name if member else "",
        server=guild.name,
        deadline=f"{ts(deadline, 'F')} ({ts(deadline)})" if deadline else "the deadline",
        quiet=ANSWER_QUIET_MINUTES,
    )


# ---------- Members ----------

def is_mod(member):
    p = member.guild_permissions
    return p.administrator or p.kick_members


def survey_open(rec):
    s = rec.get("survey")
    return bool(s) and s["status"] in OPEN_STATUSES


def last_seen(member, rec):
    """Most recent of: last message, join date, or last time mods chose to keep them."""
    dates = [parse(rec.get("last_active")), member.joined_at, parse(rec.get("kept_at"))]
    return max((d for d in dates if d), default=utcnow())


def describe(member, rec):
    last = parse(rec.get("last_active"))
    seen = f"last message {ts(last)}" if last else "no messages in the scanned period"
    joined = ts(member.joined_at) if member.joined_at else "unknown"
    return f"{member.mention} (@{member.name}): {seen}, joined {joined}"


# ---------- Sending ----------

async def try_dm(member, text):
    """DM a member. Returns the message, or None if their DMs are closed."""
    try:
        return await member.send(text)
    except discord.HTTPException:
        return None


async def send_lines(dest, header, lines):
    """Send a list that may be longer than Discord's 2000-character limit."""
    chunk = header
    for line in lines:
        if len(chunk) + len(line) + 1 > 1900:
            await dest.send(chunk, allowed_mentions=NO_PINGS)
            chunk = ""
        chunk += ("\n" if chunk else "") + line
    if chunk:
        await dest.send(chunk, allowed_mentions=NO_PINGS)
