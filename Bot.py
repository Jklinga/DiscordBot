"""Starts Purge Bot. Run `python Bot.py`, or use the Purge Bot app (PurgeBot.pyw)."""
import asyncio
import os
import sys
import threading

import discord
from discord.ext import commands

from cogs.events import Events
from cogs.mod_commands import ModCommands
from config import COMMAND_PREFIX, load_token
from inactivity import storage

# Set by the app when it starts the bot, so it can ask the bot to shut down cleanly
LAUNCHED_BY_APP = os.environ.get("PURGEBOT_LAUNCHER") == "1"


class InactivityBot(commands.Bot):
    async def setup_hook(self):
        await self.add_cog(Events(self))
        await self.add_cog(ModCommands(self))
        storage.autosave.start()
        if LAUNCHED_BY_APP:
            self._listen_for_stop(asyncio.get_running_loop())

    def _listen_for_stop(self, loop):
        """The app sends 'stop' on stdin when you press Stop."""
        def wait():
            for line in sys.stdin:
                if line.strip() == "stop":
                    break
            print("Stopping...", flush=True)
            asyncio.run_coroutine_threadsafe(self.close(), loop)
        threading.Thread(target=wait, daemon=True).start()


def main():
    # Emoji in names/messages must not crash printing on Windows
    for stream in (sys.stdout, sys.stderr):
        if stream and hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)

    token = load_token()
    if not token:
        print("ERROR: No bot token found. Enter it in the Purge Bot app, or put it in token.txt.")
        sys.exit(2)

    intents = discord.Intents.default()
    intents.members = True
    intents.message_content = True
    bot = InactivityBot(command_prefix=COMMAND_PREFIX, intents=intents)

    try:
        bot.run(token)
    except discord.LoginFailure:
        print("ERROR: Discord rejected the token. It may have been reset. "
              "Copy a new one from Developer Portal -> Bot -> Reset Token.")
        sys.exit(3)
    except discord.PrivilegedIntentsRequired:
        print("ERROR: Turn on 'Server Members Intent' and 'Message Content Intent' in "
              "Developer Portal -> Bot, then start again.")
        sys.exit(4)
    finally:
        storage.save_data()  # save once more after the bot is shut down
    print("Bot stopped.")


if __name__ == "__main__":
    main()
