"""Syncing the member list and working out who has been inactive."""
from datetime import timedelta

import discord

from config import INACTIVE_DAYS
from inactivity.helpers import is_mod, last_seen, utcnow, iso, parse
from inactivity.storage import bump_activity, guild_data, mark_dirty, member_record


def is_exempt(member):
    return (
        member.bot
        or member.id == member.guild.owner_id
        or is_mod(member)
        or str(member.id) in guild_data(member.guild)["exempt"]
    )


async def sync_members(guild):
    """Store every current member and drop people who left while the bot was offline."""
    g = guild_data(guild)
    present = set()
    async for m in guild.fetch_members(limit=None):
        if m.bot:
            continue
        member_record(m)
        present.add(str(m.id))
    for uid in list(g["members"]):
        if uid not in present:
            del g["members"][uid]
    mark_dirty()


def _readable_channels(guild):
    me = guild.me

    def readable(ch):
        p = ch.permissions_for(me)
        return p.view_channel and p.read_message_history

    channels = {}
    for ch in [*guild.text_channels, *guild.voice_channels, *guild.stage_channels, *guild.threads]:
        channels[ch.id] = ch
    return channels, readable


async def scan_history(guild):
    """Read message history since the last scan (or the last INACTIVE_DAYS on first run).

    Returns (channels scanned, channels skipped).
    """
    g = guild_data(guild)
    started = utcnow()
    since = parse(g["last_scan"]) or (started - timedelta(days=INACTIVE_DAYS))
    channels, readable = _readable_channels(guild)

    # Archived threads (a thread archived before `since` can't have newer messages)
    for parent in [*guild.text_channels, *guild.forums]:
        if not readable(parent):
            continue
        try:
            async for th in parent.archived_threads(limit=None):
                if th.archive_timestamp and th.archive_timestamp < since:
                    break
                channels[th.id] = th
        except discord.HTTPException:
            pass

    latest = {}
    scanned = skipped = 0
    for ch in channels.values():
        if not readable(ch):
            skipped += 1
            continue
        try:
            async for msg in ch.history(limit=None, after=since):
                if msg.author.bot:
                    continue
                uid = str(msg.author.id)
                if uid not in latest or msg.created_at > latest[uid]:
                    latest[uid] = msg.created_at
            scanned += 1
        except discord.HTTPException:
            skipped += 1

    for uid, when in latest.items():
        rec = g["members"].get(uid)
        if rec:
            bump_activity(rec, when)
    g["last_scan"] = iso(started)
    mark_dirty()
    return scanned, skipped


def find_inactive(guild):
    """Members (not exempt) with no activity for INACTIVE_DAYS, longest-inactive first."""
    g = guild_data(guild)
    cutoff = utcnow() - timedelta(days=INACTIVE_DAYS)
    result = []
    for m in guild.members:
        if is_exempt(m):
            continue
        rec = g["members"].get(str(m.id))
        if rec and last_seen(m, rec) < cutoff:
            result.append((m, rec))
    return sorted(result, key=lambda x: last_seen(*x))
