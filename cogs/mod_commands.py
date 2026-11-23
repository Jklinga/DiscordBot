"""Commands for moderators. All of them need the Kick Members permission."""
import discord
from discord.ext import commands

from config import DM_DELAY_SECONDS, INACTIVE_DAYS, RESPONSE_DAYS
from inactivity.activity import find_inactive
from inactivity.decisions import apply_action, build_plan, refresh_guild, summary_lines
from inactivity.helpers import NO_PINGS, describe, is_mod, parse, send_lines, survey_open, ts
from inactivity.storage import guild_data, save_data, work_lock
from inactivity.surveys import (close_survey, collect_replies, mod_channel, reminder_targets,
                                send_reminders, send_surveys)


class ModCommands(commands.Cog, name="Inactivity check"):
    def __init__(self, bot):
        self.bot = bot

    async def cog_check(self, ctx):
        if ctx.guild is None:
            raise commands.NoPrivateMessage()
        if not ctx.author.guild_permissions.kick_members:
            raise commands.MissingPermissions(["kick_members"])
        return True

    async def cog_command_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            return
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("You need the **Kick Members** permission to use this.")
        elif isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.send(f"{error}\nSee `!help {ctx.command}`.")
        else:
            await ctx.send(f"Something went wrong: {error}")
            raise error

    @staticmethod
    async def owner_only(ctx):
        """Returns True if the author is the server owner; otherwise tells them no."""
        if ctx.author.id == ctx.guild.owner_id:
            return True
        await ctx.send("😈 Only the **server owner** may do that, mortal.")
        return False

    @staticmethod
    async def wait_for_lock(ctx):
        if work_lock.locked():
            await ctx.send("⏳ Busy with another task (probably the startup scan). Will run when it's done...")

    @commands.command(name="setup", help="(Owner only) Set the channel where survey answers are posted for mods to vote on.")
    async def setup_cmd(self, ctx, channel: discord.TextChannel):
        if not await self.owner_only(ctx):
            return
        g = guild_data(ctx.guild)
        g["mod_channel_id"] = channel.id
        save_data()
        lines = [f"New survey answers will be posted in {channel.mention}. Make sure only mods can see it."]

        # Answers already posted in an earlier review channel stay where they are
        elsewhere = {}
        for rec in g["members"].values():
            s = rec.get("survey")
            if survey_open(rec) and s.get("review_message_id") and s.get("review_channel_id") != channel.id:
                elsewhere[s["review_channel_id"]] = elsewhere.get(s["review_channel_id"], 0) + 1
        for cid, count in elsewhere.items():
            old = ctx.guild.get_channel(cid)
            if old:
                lines.append(f"{count} answer(s) already waiting for votes stay in {old.mention}. "
                             "Votes there still count, so keep that channel until they're processed.")
            else:
                lines.append(f"{count} answer(s) from a deleted review channel will be reposted here "
                             "(earlier votes on them are lost).")

        p = channel.permissions_for(ctx.guild.me)
        missing = [name for name, ok in (
            ("View Channel", p.view_channel), ("Send Messages", p.send_messages),
            ("Embed Links", p.embed_links), ("Add Reactions", p.add_reactions),
            ("Read Message History", p.read_message_history)) if not ok]
        if missing:
            lines.append(f"⚠️ The bot is missing these permissions in {channel.mention}: {', '.join(missing)}.")
        await ctx.send("\n".join(lines))
        if any(ctx.guild.get_channel(cid) is None for cid in elsewhere):
            await self.wait_for_lock(ctx)
            async with work_lock:
                await collect_replies(ctx.guild)  # reposts the lost answers now

    @commands.command(help="Show an overview of the inactivity check.")
    async def status(self, ctx):
        await self.wait_for_lock(ctx)
        async with work_lock:
            await collect_replies(ctx.guild)
            lines = await summary_lines(ctx.guild)
        await send_lines(ctx, "**Inactivity check status**", lines)

    @commands.command(help="Re-sync members and scan new messages (also done automatically on startup).")
    async def scan(self, ctx):
        await self.wait_for_lock(ctx)
        async with work_lock:
            await ctx.send("Scanning...")
            scanned, skipped = await refresh_guild(ctx.guild)
        await ctx.send(f"Done. Scanned {scanned} channels ({skipped} skipped, no access).")

    @commands.command(help="List inactive members and their survey status.")
    async def inactive(self, ctx):
        await self.wait_for_lock(ctx)
        async with work_lock:
            found = find_inactive(ctx.guild)
        if not found:
            return await ctx.send("No inactive members found.")
        lines = []
        for m, rec in found:
            note = f" [survey: {rec['survey']['status']}]" if survey_open(rec) else ""
            lines.append("• " + describe(m, rec) + note)
        await send_lines(ctx, f"**{len(found)} members inactive for {INACTIVE_DAYS}+ days:**", lines)

    @commands.command(help="(Owner only) DM the survey to inactive members. Use '!survey confirm' to actually send.")
    async def survey(self, ctx, confirm: str = ""):
        if not await self.owner_only(ctx):
            return
        guild = ctx.guild
        if not mod_channel(guild):
            return await ctx.send("Set a review channel first with `!setup #channel`.")
        await self.wait_for_lock(ctx)
        async with work_lock:
            targets = [(m, rec) for m, rec in find_inactive(guild) if not survey_open(rec)]
            if not targets:
                return await ctx.send("Nobody new to survey.")
            if confirm.lower() != "confirm":
                lines = ["• " + describe(m, rec) for m, rec in targets]
                lines.append(f"\nThey'll have {RESPONSE_DAYS} days to reply. Run `!survey confirm` to send.")
                return await send_lines(ctx, f"**This will DM {len(targets)} members:**", lines)

            await ctx.send(f"Sending {len(targets)} DMs, roughly {len(targets) * DM_DELAY_SECONDS}s...")
            sent, failed = await send_surveys(guild, targets)
        result = f"Done. {sent} survey(s) sent."
        if failed:
            result += (f" {failed} couldn't be DM'd (DMs closed). They were posted in "
                       f"{mod_channel(guild).mention} for a mod vote.")
        await ctx.send(result)

    @commands.command(help="(Owner only) DM a reminder to surveyed members who haven't answered yet.")
    async def remind(self, ctx):
        if not await self.owner_only(ctx):
            return
        guild = ctx.guild
        await self.wait_for_lock(ctx)
        async with work_lock:
            await collect_replies(guild)  # pick up any new replies first
            targets, overdue = reminder_targets(guild)
            skipped = (f"{overdue} member(s) are already past their deadline. `!process` will kick them, "
                       "so they got no reminder.") if overdue else None
            if not targets:
                return await ctx.send("Everyone surveyed has answered (or is past the deadline). "
                                      "Nobody to remind." + (f"\n{skipped}" if skipped else ""))

            await ctx.send(f"Sending {len(targets)} reminders, roughly {len(targets) * DM_DELAY_SECONDS}s...")
            sent, failed = await send_reminders(guild, targets)

        lines = []
        for m, rec in targets:
            s = rec["survey"]
            line = f"• {m.mention} (@{m.name}): deadline {ts(parse(s['deadline']))}"
            if s.get("reminders"):
                line += f", reminded {s['reminders']}x"
            lines.append(line)
        if failed:
            lines.append(f"\n{failed} couldn't be DM'd (they've closed their DMs since the survey).")
        if skipped:
            lines.append(skipped)
        await send_lines(ctx, f"**Done. {sent} reminder(s) sent. Their deadlines stay the same.**", lines)

    @commands.command(help="Preview kicks/bans/keeps. Use '!process confirm' (owner only) to carry them out.")
    async def process(self, ctx, confirm: str = ""):
        if confirm.lower() == "confirm" and not await self.owner_only(ctx):
            return
        guild = ctx.guild
        await self.wait_for_lock(ctx)
        async with work_lock:
            await collect_replies(guild)
            actions, waiting = await build_plan(guild)
            if confirm.lower() != "confirm":
                icons = {"keep": "✅ keep", "kick": "👢 kick", "ban": "🔨 ban"}
                lines = [f"• {icons[a]} {m.mention} (@{m.name}): {r}" for m, _, a, r in actions] or ["• nothing"]
                lines.append("\n**Still waiting:**")
                lines += [f"• {w}" for w in waiting] or ["• nobody"]
                if actions:
                    lines.append("\nThe server owner can run `!process confirm` to carry out the actions above.")
                return await send_lines(ctx, "**Would do:**", lines)

            results = [await apply_action(guild, m, rec, a, r) for m, rec, a, r in actions]
            save_data()
        await send_lines(ctx, "**Done:**", results or ["Nothing to do."])

    @commands.command(usage="[@member]",
                      help="Exclude a member from the purge, or include them again (run it twice). "
                           "Exempting someone who was already surveyed ends their survey: they won't be "
                           "reminded or kicked, and get the 'spared' DM. Without a member, lists everyone exempted.")
    async def exempt(self, ctx, member: discord.Member = None):
        guild = ctx.guild
        ex = guild_data(guild)["exempt"]
        if member is None:
            names = []
            for uid in ex:
                m = guild.get_member(int(uid))
                names.append(f"• {m.mention} (@{m.name})" if m else f"• <@{uid}> (no longer in the server)")
            if not names:
                return await ctx.send("Nobody is exempted. Use `!exempt @member` to exempt someone.")
            return await send_lines(ctx, f"**{len(names)} exempted member(s):**", names)

        if member.bot or member.id == guild.owner_id or is_mod(member):
            return await ctx.send(f"{member.mention} is a bot, the owner or a mod, so they're never purged anyway.",
                                  allowed_mentions=NO_PINGS)

        uid = str(member.id)
        await self.wait_for_lock(ctx)
        async with work_lock:
            if uid in ex:
                ex.remove(uid)
                msg = (f"{member.mention} is no longer exempt. If they're inactive, `!inactive` "
                       "will list them again and `!survey` can survey them.")
            else:
                ex.append(uid)
                msg = f"{member.mention} is now exempt from the purge."
                rec = guild_data(guild)["members"].get(uid)
                if rec and survey_open(rec):
                    await close_survey(guild, uid, rec, "exempted", f"🛡️ Exempted by {ctx.author.display_name}",
                                       notify=True)
                    msg += (" Their survey is closed: no reminders, no kick, and their review post "
                            "is marked as exempted. They got the 'spared' DM.")
            save_data()
        await ctx.send(msg, allowed_mentions=NO_PINGS)
