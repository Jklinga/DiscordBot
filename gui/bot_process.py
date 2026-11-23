"""Runs the bot as a separate process so it can be started and stopped from the app."""
import os
import queue
import subprocess
import sys
import threading

from config import BASE_DIR

STOP_TIMEOUT_SECONDS = 15


class BotProcess:
    def __init__(self):
        self.proc = None
        # Lines of output (str), plus ("exit", code) when the bot stops
        self.output = queue.Queue()

    @property
    def running(self):
        return self.proc is not None and self.proc.poll() is None

    @staticmethod
    def _command():
        if getattr(sys, "frozen", False):
            # Built .exe: it starts a second copy of itself in bot mode
            return [sys.executable, "--run-bot"]
        exe = sys.executable
        folder, name = os.path.split(exe)
        if name.lower() == "pythonw.exe":
            # pythonw has no console output; use python.exe so the log can be shown
            candidate = os.path.join(folder, "python.exe")
            if os.path.exists(candidate):
                exe = candidate
        return [exe, "-u", os.path.join(BASE_DIR, "Bot.py")]

    def start(self):
        if self.running:
            return
        env = dict(os.environ, PURGEBOT_LAUNCHER="1", PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        self.proc = subprocess.Popen(
            self._command(), cwd=BASE_DIR, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=flags,
        )
        threading.Thread(target=self._read_output, args=(self.proc,), daemon=True).start()

    def _read_output(self, proc):
        for raw in proc.stdout:
            self.output.put(raw.decode("utf-8", errors="replace").rstrip("\r\n"))
        proc.wait()
        self.output.put(("exit", proc.returncode))

    def stop(self):
        """Ask the bot to shut down cleanly (it saves its data first); force it if it hangs."""
        if not self.running:
            return
        proc = self.proc
        try:
            proc.stdin.write(b"stop\n")
            proc.stdin.flush()
        except OSError:
            pass

        def wait_or_kill():
            try:
                proc.wait(STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                proc.kill()
        threading.Thread(target=wait_or_kill, daemon=True).start()
