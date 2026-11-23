"""Reacts to Discord events: startup, joins/leaves, name changes and messages."""
from discord.ext import commands, tasks

from inactivity.decisions import refresh_guild, summary_lines
from inactivity.helpers import send_lines
from inactivity.storage import (bump_activity, guild_data, member_record,
                                remove_member, work_lock)
from inactivity.surveys import mod_channel, refresh_answer, submit_quiet_answers


class Events(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.startup_done = False

    async def cog_unload(self):
        self.answer_check.cancel()

    @tasks.loop(minutes=1)
    async def answer_check(self):
        """Pass on answers from members who have finished writing."""
        if work_lock.locked():  # a scan or command is busy; try again next minute
            return
        async with work_lock:
            for guild in self.bot.guilds:
                await submit_quiet_answers(guild)

    @commands.Cog.listener()
    async def on_ready(self):
        print(f"Logged in as {self.bot.user}")
        if self.startup_done:  # on_ready also fires on reconnects
            return
        self.startup_done = True

        for guild in self.bot.guilds:
            async with work_lock:
                print(f"[{guild.name}] Syncing members and scanning message history...")
                scanned, skipped = await refresh_guild(guild)
                print(f"[{guild.name}] Done: {scanned} channels scanned, {skipped} skipped (no access).")
            channel = mod_channel(guild)
            if channel:
                lines = await summary_lines(guild)
                await send_lines(channel, "**Inactivity check: bot is online, here's where things stand**", lines)

        self.answer_check.start()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        if not member.bot:
            member_record(member)
            print(f"[JOIN] {member}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if remove_member(member.guild, member.id):
            print(f"[LEAVE] {member}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.bot:
            return
        if (before.nick, before.name, before.display_name) != (after.nick, after.name, after.display_name):
            member_record(after)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        # Username / global display name changes come through here, not on_member_update
        for guild in self.bot.guilds:
            member = guild.get_member(after.id)
            if member and not member.bot:
                member_record(member)

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        if message.guild is None:
            # A DM: might be a survey answer for one of the bot's servers. Waits for any
            # running scan or command, so an answer can't be posted for review twice.
            async with work_lock:
                for guild in self.bot.guilds:
                    rec = guild_data(guild)["members"].get(str(message.author.id))
                    member = guild.get_member(message.author.id)
                    survey = rec.get("survey") if rec else None
                    if member and survey and survey["status"] in ("pending", "answering", "answered"):
                        await refresh_answer(guild, member, rec)
            return

        bump_activity(member_record(message.author), message.created_at)
