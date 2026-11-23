"""Sending surveys, reading DM replies and posting them for mods to vote on."""
import asyncio
from datetime import timedelta

import discord

from config import (ANSWER_QUIET_MINUTES, DM_DELAY_SECONDS, KEEP_MESSAGE, MIN_VOTES,
                    REMINDER_MESSAGE, RESPONSE_DAYS, SURVEY_MESSAGE, THANKS_MESSAGE, VOTES)
from inactivity.activity import is_exempt
from inactivity.helpers import NO_PINGS, fill, iso, parse, survey_open, try_dm, ts, utcnow
from inactivity.storage import guild_data, mark_dirty, save_data


def mod_channel(guild):
    cid = guild_data(guild)["mod_channel_id"]
    return guild.get_channel(cid) if cid else None


async def send_surveys(guild, targets):
    """DM the survey to each (member, record) pair. Returns (sent, failed)."""
    sent = failed = 0
    for m, rec in targets:
        now = utcnow()
        deadline = now + timedelta(days=RESPONSE_DAYS)
        dm = await try_dm(m, fill(SURVEY_MESSAGE, guild, m, deadline))
        rec["survey"] = {
            "status": "pending" if dm else "no_dm",
            "dm_failed": dm is None,
            "sent_at": iso(now),
            "deadline": iso(deadline),
            "dm_message_id": dm.id if dm else None,
            "answer": None,
            "review_message_id": None,
            "review_channel_id": None,
        }
        if dm:
            sent += 1
        else:
            failed += 1
            await post_or_update_review(guild, str(m.id), rec)  # mods decide on these
        save_data()
        await asyncio.sleep(DM_DELAY_SECONDS)
    return sent, failed


def reminder_targets(guild):
    """Surveyed members who haven't replied at all and whose deadline hasn't passed.

    Returns (targets, overdue_count). Run collect_replies() first so it's up to date.
    """
    now = utcnow()
    targets, overdue = [], 0
    for uid, rec in guild_data(guild)["members"].items():
        s = rec.get("survey")
        if not s or s["status"] != "pending":
            continue
        member = guild.get_member(int(uid))
        if member is None or is_exempt(member):
            continue
        if parse(s["deadline"]) <= now:
            overdue += 1  # !process will kick them, no point reminding
        else:
            targets.append((member, rec))
    targets.sort(key=lambda t: t[1]["survey"]["deadline"])
    return targets, overdue


async def send_reminders(guild, targets):
    """DM a reminder to each (member, record). Their original deadline stays. Returns (sent, failed)."""
    sent = failed = 0
    for m, rec in targets:
        s = rec["survey"]
        if await try_dm(m, fill(REMINDER_MESSAGE, guild, m, parse(s["deadline"]))):
            s["reminders"] = s.get("reminders", 0) + 1
            s["reminded_at"] = iso(utcnow())
            sent += 1
        else:
            failed += 1
        mark_dirty()
        await asyncio.sleep(DM_DELAY_SECONDS)
    save_data()
    return sent, failed


async def close_survey(guild, uid, rec, status, outcome, notify=False):
    """End a member's open survey (e.g. when they're exempted) and mark their review post."""
    s = rec["survey"]
    s["status"] = status
    s["closed_at"] = iso(utcnow())
    mark_dirty()
    await post_or_update_review(guild, uid, rec, outcome=outcome, create=False)
    member = guild.get_member(int(uid))
    if notify and member:
        await try_dm(member, fill(KEEP_MESSAGE, guild, member, parse(s.get("deadline"))))


# ---------- Review posts in the mod channel ----------

def build_review_embed(rec, outcome=None):
    s = rec["survey"]
    if s.get("answer"):
        desc = s["answer"][:4000]
    elif s.get("dm_failed"):
        desc = "*Could not DM this member (DMs closed or blocked). Decide based on what you know.*"
    else:
        desc = "*No answer.*"
    embed = discord.Embed(
        title=f"{rec['display_name']} (@{rec['username']})",
        description=desc,
        color=discord.Color.dark_grey() if outcome else discord.Color.blurple(),
    )
    last = parse(rec.get("last_active"))
    embed.add_field(name="Joined", value=ts(parse(rec["joined_at"]), "D") if rec.get("joined_at") else "?")
    embed.add_field(name="Last message", value=ts(last, "D") if last else "None in scanned period")
    embed.add_field(name="Surveyed", value=ts(parse(s["sent_at"]), "D"))
    if outcome:
        embed.add_field(name="Outcome", value=outcome, inline=False)
    else:
        embed.set_footer(text=f"Vote: ✅ keep · 👢 kick · 🔨 ban ({MIN_VOTES} mod votes needed). "
                              "Applied when the server owner runs !process confirm.")
    return embed


async def post_or_update_review(guild, uid, rec, outcome=None, create=True):
    """Edit the member's review post, or post a new one if there isn't one (and create=True)."""
    s = rec["survey"]
    embed = build_review_embed(rec, outcome)
    if s.get("review_message_id"):
        ch = guild.get_channel(s.get("review_channel_id") or 0)
        if ch:
            try:
                msg = await ch.fetch_message(s["review_message_id"])
                await msg.edit(embed=embed)
                return
            except discord.NotFound:
                s["review_message_id"] = None  # deleted by someone, post a new one
            except discord.HTTPException:
                return
    channel = mod_channel(guild)
    if not create or channel is None:
        return
    msg = await channel.send(f"<@{uid}>", embed=embed, allowed_mentions=NO_PINGS)
    for emoji in VOTES:
        await msg.add_reaction(emoji)
    s["review_message_id"] = msg.id
    s["review_channel_id"] = channel.id
    mark_dirty()


# ---------- Reading replies ----------

async def refresh_answer(guild, member, rec):
    """Read everything the member has DM'd back since the survey was sent.

    The first reply only starts the 'answering' phase. The answer is passed to mods by
    submit_if_quiet() once they've stopped writing. Replies after that update the post.
    """
    s = rec["survey"]
    try:
        ch = member.dm_channel or await member.create_dm()
        parts = []
        last_reply = None
        async for msg in ch.history(limit=100, after=discord.Object(id=s["dm_message_id"]), oldest_first=True):
            if msg.author.id != member.id:
                continue
            lines = ([msg.content.strip()] + [a.url for a in msg.attachments]
                     + [f"[sticker: {st.name}]" for st in msg.stickers])
            text = "\n".join(line for line in lines if line)
            if text:
                parts.append(text)
                last_reply = msg.created_at
    except discord.HTTPException:
        return
    answer = "\n\n".join(parts)
    if not answer or answer == s.get("answer"):
        return
    s["answer"] = answer
    s["last_reply_at"] = iso(last_reply)
    if s["status"] == "pending":
        s["status"] = "answering"
    mark_dirty()
    if s["status"] == "answered":
        await post_or_update_review(guild, str(member.id), rec)  # late addition: update the post


async def submit_if_quiet(guild, member, rec):
    """Pass the answer to mods once the member hasn't written for ANSWER_QUIET_MINUTES."""
    s = rec["survey"]
    if s["status"] != "answering":
        return
    if utcnow() - parse(s["last_reply_at"]) < timedelta(minutes=ANSWER_QUIET_MINUTES):
        return
    s["status"] = "answered"
    s["answered_at"] = iso(utcnow())
    mark_dirty()
    await post_or_update_review(guild, str(member.id), rec)
    await try_dm(member, fill(THANKS_MESSAGE, guild, member, parse(s.get("deadline"))))


async def submit_quiet_answers(guild):
    """Called every minute: hand over answers whose quiet period has passed."""
    for uid, rec in list(guild_data(guild)["members"].items()):
        s = rec.get("survey")
        if s and s["status"] == "answering":
            member = guild.get_member(int(uid))
            if member:
                await submit_if_quiet(guild, member, rec)


async def collect_replies(guild):
    """Pick up replies that came in (even while the bot was offline) and post them for review."""
    g = guild_data(guild)
    for uid, rec in list(g["members"].items()):
        if not survey_open(rec):
            continue
        s = rec["survey"]
        member = guild.get_member(int(uid))
        if member is None:
            continue
        # Exempted (or became a mod) after being surveyed: they're out of the purge
        if is_exempt(member):
            await close_survey(guild, uid, rec, "exempted", "🛡️ Exempted")
            continue
        # They've posted in the server since being surveyed: no longer inactive
        if s["status"] == "pending":
            last = parse(rec.get("last_active"))
            if last and last > parse(s["sent_at"]):
                s["status"] = "cleared"
                mark_dirty()
                continue
        if s["status"] in ("pending", "answering", "answered"):
            await refresh_answer(guild, member, rec)
        await submit_if_quiet(guild, member, rec)
        # Old review channel deleted: forget the lost post so it's reposted in the current one
        if s.get("review_message_id") and guild.get_channel(s.get("review_channel_id") or 0) is None:
            s["review_message_id"] = None
            mark_dirty()
        if s["status"] in ("answered", "no_dm") and not s.get("review_message_id"):
            await post_or_update_review(guild, uid, rec)
