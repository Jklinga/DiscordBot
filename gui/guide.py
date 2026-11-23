"""The in-app guide: what the bot does, how to set it up, and the commands."""
from gui import theme

# Each entry is (kind, content). Kinds: h1, h2, p, bullet, step, code, table, note
GUIDE = [
    ("h1", "How Purge Bot works"),
    ("p", "Purge Bot finds members who haven't written anything for a long time, DMs them a "
          "survey asking why they should stay, lets your mods vote on the answers, and kicks "
          "those who never reply."),
    ("p", "You don't have to keep it running. Start it when you want to work on the purge. "
          "Every time it starts, it catches up on everything that happened while it was off."),

    ("h2", "The purge, step by step"),
    ("step", ("1", "Start the bot. It syncs the member list and reads the message history of "
                   "every channel it can see. The first time it reads back a full year, which "
                   "can take a few minutes.")),
    ("step", ("2", "In Discord, type !inactive to see who hasn't written anything in a year.")),
    ("step", ("3", "Type !survey confirm (server owner only). Each inactive member gets a DM "
                   "asking them to plead their case. They have 3 days to reply.")),
    ("step", ("4", "Replies are posted in your review channel with ✅ keep, 👢 kick and 🔨 ban. "
                   "Mods vote by reacting, even while the bot is off.")),
    ("step", ("5", "When the deadline has passed, start the bot and type !process to preview, "
                   "then !process confirm (server owner only). Members who never replied are "
                   "kicked, and voted members are kept, kicked or banned.")),

    ("table", [
        ("When", "What you do"),
        ("Day 1", "Start → !inactive → !survey confirm → Stop"),
        ("Any time", "Mods react to the answers in the review channel"),
        ("Optional", "!remind to nudge those who haven't answered"),
        ("Day 4+", "Start → !process → !process confirm → Stop"),
    ]),

    ("h1", "First-time setup"),
    ("h2", "1. Create the bot in Discord"),
    ("bullet", "Click \"Open Developer Portal\" on the Run tab, open your application, and go to Bot."),
    ("bullet", "Turn on Server Members Intent and Message Content Intent."),
    ("bullet", "Click Reset Token, copy it, and paste it into the Bot token field on the Run tab."),
    ("note", "The token is like a password for the bot. It's saved in token.txt next to the app. "
             "Never share it or commit it to git. If it leaks, reset it in the Developer Portal."),

    ("h2", "2. Invite it to your server"),
    ("bullet", "Click \"Copy invite link\" on the Run tab, open the link in your browser and pick "
               "your server. You need Manage Server permission there."),
    ("bullet", "In Server Settings → Roles, drag the bot's role above the roles of anyone it might "
               "need to kick. Discord won't let it kick people with a higher role."),
    ("bullet", "The bot only sees activity in channels it can read. People who only talk in "
               "channels hidden from the bot will look inactive."),

    ("h2", "3. Pick a review channel"),
    ("bullet", "Create a channel that only mods can see, e.g. #purge-review."),
    ("bullet", "Start the bot and type !setup #purge-review in Discord."),

    ("h2", "4. Check the settings"),
    ("bullet", "On the Settings tab, choose how long counts as inactive, how long members get to "
               "answer, and how many mod votes are needed. Changes apply the next time the bot starts."),
    ("bullet", "On the Messages tab, edit what the bot says in its DMs."),

    ("h1", "Commands"),
    ("p", "Type these in a channel in your server. All of them need the Kick Members permission."),
    ("table", [
        ("Command", "Who", "What it does"),
        ("!setup #channel", "owner", "Sets the channel where answers are posted for voting"),
        ("!status", "mods", "Overview: inactive, waiting, answered, ready to process"),
        ("!inactive", "mods", "Lists inactive members and their survey status"),
        ("!survey", "owner", "Shows who would get the survey"),
        ("!survey confirm", "owner", "Sends the survey DMs"),
        ("!remind", "owner", "DMs a reminder to those who haven't answered yet"),
        ("!process", "mods", "Shows who would be kicked/banned/kept, and who is waiting"),
        ("!process confirm", "owner", "Carries out what !process showed"),
        ("!exempt @member", "mods", "Excludes someone from the purge (again to undo)"),
        ("!exempt", "mods", "Lists everyone who is exempted"),
        ("!scan", "mods", "Rescans members and messages (also done on startup)"),
        ("!help", "anyone", "Lists commands"),
    ]),

    ("h1", "Rules the bot follows"),
    ("bullet", "Never flagged: bots, the server owner, anyone with Kick Members or Administrator "
               "permission, exempted members, and people who joined more recently than the "
               "inactive limit."),
    ("bullet", "Only messages count as activity. Voice chat and reactions can't be read from history."),
    ("bullet", "Members can reply in several messages. The bot waits until they've been quiet for "
               "a while before posting their answer for the mods."),
    ("bullet", "A decision needs the set number of mod votes and a clear winner. A tie, or a mod "
               "reacting with more than one option, means no decision yet."),
    ("bullet", "A late reply still counts if it arrives before !process is run. Someone still "
               "writing at the deadline isn't kicked."),
    ("bullet", "A surveyed member who writes in the server is taken off the list automatically."),
    ("bullet", "Members the mods keep are safe for another full inactive period."),
    ("bullet", "Exempting someone who was already surveyed ends their survey straight away: no "
               "reminders, no kick, and they get the 'spared' DM."),
    ("bullet", "Replies can be text, images, files, voice messages or stickers."),
    ("bullet", "If someone's DMs are closed, they're posted for a vote straight away and never "
               "kicked automatically."),

    ("h1", "Testing safely"),
    ("bullet", "Use a separate test server and a separate test bot (its own token), so your "
               "real server isn't touched."),
    ("bullet", "Settings → Use test values makes everyone without mod permissions count as inactive "
               "and gives them about 4 minutes to reply."),
    ("bullet", "Remember Settings → Restore real defaults before using the bot on your real server."),

    ("h1", "Troubleshooting"),
    ("table", [
        ("Problem", "Fix"),
        ("\"Discord rejected the token\"", "Reset the token in the Developer Portal and paste the new one"),
        ("\"Turn on ... Intent\"", "Developer Portal → Bot → turn on both intents"),
        ("Bot is offline in Discord", "It's only online while it's running here"),
        ("Ignores ! commands", "Message Content Intent is off, or you lack Kick Members"),
        ("No posts in review channel", "Check the bot can post, embed and react there"),
        ("\"Can't kick ...\"", "Move the bot's role above that member's roles"),
    ]),
]


def render_guide(text):
    """Write GUIDE into a tk.Text widget with simple formatting."""
    text.configure(state="normal", wrap="word", cursor="arrow", spacing1=2, spacing3=2)
    text.tag_configure("h1", font=("Segoe UI Semibold", 16), foreground=theme.ACCENT_HOVER,
                       spacing1=18, spacing3=6)
    text.tag_configure("h2", font=theme.FONT_H2, foreground=theme.TEXT, spacing1=12, spacing3=4)
    text.tag_configure("p", font=theme.FONT, foreground=theme.TEXT, spacing3=6)
    text.tag_configure("bullet", font=theme.FONT, foreground=theme.TEXT,
                       lmargin1=12, lmargin2=28, spacing3=3)
    text.tag_configure("stepnum", font=theme.FONT_BOLD, foreground=theme.ACCENT_HOVER)
    text.tag_configure("step", font=theme.FONT, foreground=theme.TEXT,
                       lmargin1=12, lmargin2=34, spacing3=5)
    text.tag_configure("note", font=theme.FONT_SMALL, foreground=theme.AMBER,
                       lmargin1=12, lmargin2=12, spacing1=4, spacing3=6)
    text.tag_configure("table", font=theme.FONT_MONO, foreground=theme.TEXT, lmargin1=12, lmargin2=12)
    text.tag_configure("tablehead", font=("Consolas", 10, "bold"), foreground=theme.MUTED,
                       lmargin1=12, lmargin2=12, spacing1=8)
    text.tag_configure("tableend", spacing3=8)

    for kind, content in GUIDE:
        if kind in ("h1", "h2", "p", "note"):
            text.insert("end", content + "\n", kind)
        elif kind == "bullet":
            text.insert("end", "•  " + content + "\n", "bullet")
        elif kind == "step":
            num, body = content
            text.insert("end", f"{num}.  ", ("step", "stepnum"))
            text.insert("end", body + "\n", "step")
        elif kind == "table":
            widths = [max(len(row[i]) for row in content) for i in range(len(content[0]))]
            for n, row in enumerate(content):
                line = "   ".join(cell.ljust(widths[i]) for i, cell in enumerate(row)).rstrip()
                text.insert("end", line + "\n", "tablehead" if n == 0 else "table")
            text.insert("end", " \n", "tableend")
    text.configure(state="disabled")
