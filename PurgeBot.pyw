"""Double-click this file to open the Purge Bot app."""
import sys


def main():
    if "--run-bot" in sys.argv:
        # Used by the built .exe: the app starts a second copy of itself to run the bot
        import Bot
        Bot.main()
        return
    if sys.platform == "win32":
        # Show Purge Bot's own icon in the taskbar instead of Python's
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("PurgeBot.App")
    from gui.app import App
    App().mainloop()


if __name__ == "__main__":
    main()
