"""smmap.live.shell builds the exact command lines the plan allows, and nothing
that could break out of them.

The Windows lines are checked character for character: they are what the
launcher shows the user and what CreateProcess receives, so "close enough" is
not a pass.
"""

import os
import subprocess
import sys
import unittest
from unittest import mock

from smmap.live import shell

CMD = r"C:\Windows\System32\cmd.exe"


class WindowsLines(unittest.TestCase):

    def test_open_url(self):
        c = shell.open_url("http://127.0.0.1:8765/", platform="win32")
        self.assertEqual(c.line, CMD + ' /c start "" "http://127.0.0.1:8765/"')
        self.assertEqual(c.shown, c.line)

    def test_launch_game(self):
        c = shell.launch_game(platform="win32")
        self.assertEqual(c.line,
                         CMD + ' /c start "" "steam://rungameid/387990"')

    def test_run_bat(self):
        c = shell.run_bat(r"C:\Games\Scoutbot\Make map.bat", platform="win32")
        self.assertEqual(c.line, CMD + r' /c "C:\Games\Scoutbot\Make map.bat"')

    def test_run_bat_unc(self):
        c = shell.run_bat(r"\\nas\share\go.cmd", platform="win32")
        self.assertEqual(c.line, CMD + r' /c "\\nas\share\go.cmd"')

    def test_lines_are_strings(self):
        # A list would be re-quoted by list2cmdline into start \"\".
        for c in (shell.open_url("https://example.com/a?b=1", platform="win32"),
                  shell.launch_game(platform="win32")):
            self.assertIsInstance(c.line, str)

    def test_never_a_bare_cmd(self):
        c = shell.open_url("http://127.0.0.1:8765/", platform="win32")
        self.assertTrue(c.line.startswith(CMD + " "))


class Refusals(unittest.TestCase):

    BAD_URLS = [
        'http://x/"&calc&"',          # closes the quotes
        "http://x/%PATH%",            # cmd.exe expands it inside quotes
        "http://x/a&b",               # command separator
        "http://x/a|b",
        "http://x/a^b",
        "http://x/a b",
        "http://x/a\nb",
        "file:///C:/Windows/notepad.exe",   # a file: opens by extension
        "C:\\map.html",
        "javascript:alert(1)",
        "",
        None,
        b"http://x/",
    ]

    def test_urls(self):
        for url in self.BAD_URLS:
            for platform in ("win32", "linux"):
                with self.subTest(url=url, platform=platform):
                    with self.assertRaises(ValueError):
                        shell.open_url(url, platform=platform)

    def test_bats(self):
        for path in [r"C:\a\b.exe", r"relative\go.bat", r'C:\a"&calc&".bat',
                     r"C:\%TEMP%\go.bat", "C:\\a\\go.bat\n", r"C:\a&b\go.bat",
                     None]:
            with self.subTest(path=path):
                with self.assertRaises(ValueError):
                    shell.run_bat(path, platform="win32")

    def test_bat_off_windows(self):
        with self.assertRaises(OSError):
            shell.run_bat(r"C:\go.bat", platform="linux")

    def test_appid(self):
        for appid in (0, -1, "387990", 1.5, True, None):
            with self.subTest(appid=appid):
                with self.assertRaises(ValueError):
                    shell.launch_game(appid, platform="win32")

    def test_run_cmd_takes_only_commands(self):
        with self.assertRaises(TypeError):
            shell.run_cmd("cmd /c start calc")
        with self.assertRaises(TypeError):
            shell.run_cmd(["xdg-open", "http://x/"])


class PosixLines(unittest.TestCase):

    def test_open_url_linux(self):
        c = shell.open_url("http://127.0.0.1:8765/", platform="linux")
        self.assertEqual(c.line, ["xdg-open", "http://127.0.0.1:8765/"])
        self.assertEqual(c.shown, "xdg-open http://127.0.0.1:8765/")

    def test_open_url_mac(self):
        c = shell.open_url("http://127.0.0.1:8765/", platform="darwin")
        self.assertEqual(c.line, ["open", "http://127.0.0.1:8765/"])

    def test_launch_game_linux(self):
        c = shell.launch_game(platform="linux")
        self.assertEqual(c.line, ["steam", "steam://rungameid/387990"])


class Spawning(unittest.TestCase):
    """run_cmd hands the command over untouched, with the right flags."""

    def test_windows_string_reaches_popen_whole(self):
        c = shell.open_url("http://127.0.0.1:8765/", platform="win32")
        with mock.patch.object(shell.os, "name", "nt"), \
                mock.patch.object(shell.subprocess, "Popen") as popen:
            shell.run_cmd(c)
        args, kwargs = popen.call_args
        self.assertEqual(args, (c.line,))
        self.assertEqual(kwargs["creationflags"], shell.CREATE_NO_WINDOW)
        self.assertNotIn("shell", kwargs)

    def test_windows_line_refused_elsewhere(self):
        c = shell.open_url("http://127.0.0.1:8765/", platform="win32")
        with mock.patch.object(shell.os, "name", "posix"):
            with self.assertRaises(OSError):
                shell.run_cmd(c)

    @unittest.skipIf(os.name == "nt", "runs a POSIX program")
    def test_waits_and_captures(self):
        c = shell.Command([sys.executable, "-c", "print('ok')"], "python")
        result = shell.run_cmd(c, wait=True, timeout=30)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "ok")

    @unittest.skipIf(os.name == "nt", "runs a POSIX program")
    def test_detached_popen(self):
        c = shell.Command([sys.executable, "-c", "pass"], "python")
        proc = shell.run_cmd(c)
        self.assertIsInstance(proc, subprocess.Popen)
        self.assertEqual(proc.wait(timeout=30), 0)

    @unittest.skipIf(os.name == "nt", "runs a POSIX program")
    def test_missing_program(self):
        c = shell.Command(["scoutbot-no-such-program"], "missing")
        with self.assertRaises(FileNotFoundError):
            shell.run_cmd(c)


if __name__ == "__main__":
    unittest.main()
