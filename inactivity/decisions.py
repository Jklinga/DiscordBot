"""Counting mod votes, deciding who gets kept/kicked/banned, and carrying it out."""
import discord

from config import ANSWER_QUIET_MINUTES, INACTIVE_DAYS, KEEP_MESSAGE, MIN_VOTES, REMOVED_MESSAGE, VOTES
from inactivity.activity import find_inactive, is_exempt, scan_history, sync_members
from inactivity.helpers import fill, is_mod, iso, parse, survey_open, try_dm, ts, utcnow
from inactivity.storage import guild_data, mark_dirty, save_data
from inactivity.surveys import collect_replies, post_or_update_review


async def refresh_guild(guild):
    """Full refresh: sync members, scan new messages, collect survey replies."""
    await sync_members(guild)
    scanned, skipped = await scan_history(guild)
    await collect_replies(guild)
    save_data()
    return scanned, skipped


async def tally_votes(guild, s):
    """Returns (decision or None, note)."""
    ch = guild.get_channel(s.get("review_channel_id") or 0)
    if not s.get("review_message_id") or ch is None:
        return None, "no review post yet (set a review channel with !setup)"
    try:
        msg = await ch.fetch_message(s["review_message_id"])
    except discord.NotFound:
        s["review_message_id"] = None
        mark_dirty()
        return None, "review post was deleted, it will be reposted"
    except discord.HTTPException:
        return None, "couldn't read review post"

    choices_by_mod = {}
    for reaction in msg.reactions:
        choice = VOTES.get(str(reaction.emoji))
        if not choice:
            continue
        async for user in reaction.users():
            voter = guild.get_member(user.id)
            if voter and not voter.bot and is_mod(voter):
                choices_by_mod.setdefault(voter.id, set()).add(choice)

    counts = {"keep": 0, "kick": 0, "ban": 0}
    for choices in choices_by_mod.values():
        if len(choices) == 1:  # mods who picked several options don't count
            counts[next(iter(choices))] += 1

    best = max(counts, key=counts.get)
    top = counts[best]
    tally = ", ".join(f"{k} {v}" for k, v in counts.items())
    if top >= MIN_VOTES and list(counts.values()).count(top) == 1:
        return best, tally
    return None, f"waiting for votes ({tally})"


async def build_plan(guild):
    """Work out what !process would do. Returns (actions, waiting)."""
    g = guild_data(guild)
    now = utcnow()
    actions, waiting = [], []
    for uid, rec in list(g["members"].items()):
        if not survey_open(rec):
            continue
        member = guild.get_member(int(uid))
        if member is None or is_exempt(member):
            continue
        s = rec["survey"]
        if s["status"] == "pending":
            deadline = parse(s["deadline"])
            if now > deadline:
                actions.append((member, rec, "kick", "no answer before the deadline"))
            else:
                waiting.append(f"{member.mention}: no answer yet, deadline {ts(deadline)}")
        elif s["status"] == "answering":
            waiting.append(f"{member.mention}: still writing their answer, goes to mods "
                           f"after {ANSWER_QUIET_MINUTES} min of silence")
        else:
            decision, note = await tally_votes(guild, s)
            if decision:
                actions.append((member, rec, decision, f"mod vote: {note}"))
            else:
                waiting.append(f"{member.mention}: {note}")
    return actions, waiting


async def apply_action(guild, member, rec, action, reason):
    """Keep, kick or ban one member. Returns a line describing the result."""
    s = rec["survey"]
    uid = str(member.id)
    name = f"{member.mention} (@{member.name})"

    if action == "keep":
        s["status"] = "kept"
        rec["kept_at"] = iso(utcnow())  # safe for another INACTIVE_DAYS
        mark_dirty()
        await try_dm(member, fill(KEEP_MESSAGE, guild, member, parse(s.get("deadline"))))
        await post_or_update_review(guild, uid, rec, outcome="✅ Kept", create=False)
        return f"✅ Kept {name}"

    perms = guild.me.guild_permissions
    allowed = perms.kick_members if action == "kick" else perms.ban_members
    if not allowed or member.top_role >= guild.me.top_role:
        return f"❌ Can't {action} {name}: the bot lacks permission or its role is not above theirs"

    await try_dm(member, fill(REMOVED_MESSAGE, guild, member, parse(s.get("deadline"))))
    try:
        if action == "kick":
            await guild.kick(member, reason=f"Inactivity check: {reason}")
        else:
            await guild.ban(member, reason=f"Inactivity check: {reason}", delete_message_seconds=0)
    except discord.HTTPException as e:
        return f"❌ Failed to {action} {name}: {e}"
    s["status"] = "kicked" if action == "kick" else "banned"
    mark_dirty()
    label = "👢 Kicked" if action == "kick" else "🔨 Banned"
    await post_or_update_review(guild, uid, rec, outcome=f"{label} ({reason})", create=False)
    return f"{label} {name} ({reason})"


async def summary_lines(guild):
    g = guild_data(guild)
    not_surveyed = [m for m, rec in find_inactive(guild) if not survey_open(rec)]
    pending = answered = 0
    for rec in g["members"].values():
        if survey_open(rec):
            if rec["survey"]["status"] in ("pending", "answering"):
                pending += 1
            else:
                answered += 1
    actions, _ = await build_plan(guild)
    lines = [
        f"• Inactive for {INACTIVE_DAYS}+ days and not surveyed yet: **{len(not_surveyed)}** "
        "(`!inactive` to list, `!survey` to DM them)",
        f"• Surveyed, waiting for (or still writing) an answer: **{pending}**",
        f"• Answered or couldn't be DM'd, waiting for mod votes: **{answered}**",
        f"• Ready to act on (past deadline or voted on): **{len(actions)}** (`!process` to preview)",
    ]
    if not g["mod_channel_id"]:
        lines.append("⚠️ No review channel set. Run `!setup #channel` first.")
    return lines
