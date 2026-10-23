"""The one place Scoutbot starts another program.

On Windows every launch goes through cmd.exe, named by its full path, and
anything opened is opened by URL with `start ""`. Both are deliberate:

- A bare `cmd` is looked up on PATH, and PATH is the user's to change. The
  full path is the program we mean and nothing else.
- Opening a *file* asks Windows which program owns its extension, and an
  extension nobody owns brings up the "How do you want to open this file?"
  dialog in the middle of a launch. A URL always has an owner: the browser for
  http, Steam for steam://.
- The empty `""` after `start` is the window title. Without it `start` takes
  the first quoted argument as the title and opens nothing.

The command is built as one string rather than a list. Python joins a list for
CreateProcess with the C runtime's quoting rules, which escape a `"` with a
backslash; cmd.exe does not read backslashes that way, and `start ""` would
reach it as `start \"\"`. A string is passed through untouched, so what is
logged is exactly what ran.

Only a narrow set of characters is allowed inside the quotes. Inside double
quotes cmd.exe still expands `%NAME%` and can be broken out of with a `"`, and
neither has a reliable escape on a `cmd /c` line, so anything that could carry
them is refused rather than quoted.

Linux and macOS (the game under Proton, or the map opened elsewhere) have no
cmd.exe; there the same three requests go to the desktop's own opener with an
argument list, which no shell ever reads.
"""

import os
import re
import subprocess
import sys

CMD_EXE = r"C:\Windows\System32\cmd.exe"
STEAM_APPID = 387990

# http(s) and steam URLs made of the RFC 3986 unreserved and delimiter
# characters, minus the ones cmd.exe gives a meaning to: % " ^ & | < > and
# whitespace. `&` is lost from query strings, which nothing here uses.
_URL = re.compile(r"(?:https?|steam)://[A-Za-z0-9\-._~:/?#\[\]@!$'()*+,;=]+")

# A Windows path to a .bat or .cmd file: drive or UNC root, no characters that
# cmd.exe would expand or that could close the quotes around it.
_BAT = re.compile(r'(?:[A-Za-z]:\\|\\\\)[^"%^&|<>\r\n]+\.(?:bat|cmd)',
                  re.IGNORECASE)

CREATE_NO_WINDOW = 0x08000000


class Command:
    """What to run, in the form the platform takes it, and how to show it.

    `line` is a string on Windows (handed to CreateProcess as-is) and an
    argument list elsewhere. `shown` is the same command as one line of text,
    for the launcher's step log.
    """

    __slots__ = ("line", "shown")

    def __init__(self, line, shown):
        self.line = line
        self.shown = shown

    def __repr__(self):
        return "Command(%r)" % self.shown


def _windows(platform):
    return (platform or sys.platform) == "win32"


def _check_url(url):
    if not isinstance(url, str) or not _URL.fullmatch(url):
        raise ValueError("refusing to open %r: only plain http, https and "
                         "steam URLs are passed to the shell" % (url,))
    return url


def _posix_opener(platform):
    return ["open"] if (platform or sys.platform) == "darwin" else ["xdg-open"]


def open_url(url, platform=None):
    """The command that opens `url` in whatever the system hands URLs to."""
    _check_url(url)
    if _windows(platform):
        line = '%s /c start "" "%s"' % (CMD_EXE, url)
        return Command(line, line)
    argv = _posix_opener(platform) + [url]
    return Command(argv, " ".join(argv))


def launch_game(appid=STEAM_APPID, platform=None):
    """The command that asks Steam to start the game.

    Through Steam rather than the executable, so Steam's overlay, cloud saves
    and (on Linux) Proton all come with it.
    """
    if not isinstance(appid, int) or isinstance(appid, bool) or appid <= 0:
        raise ValueError("Steam app id must be a positive integer, not %r"
                         % (appid,))
    url = "steam://rungameid/%d" % appid
    if not _windows(platform):
        # `steam <url>` hands the URL to a running client or starts one; it is
        # what the desktop's steam:// handler does anyway, without needing the
        # handler to be registered.
        argv = ["steam", url]
        return Command(argv, " ".join(argv))
    return open_url(url, platform)


def run_bat(path, platform=None):
    """The command that runs a batch file, on Windows only."""
    if not _windows(platform):
        raise OSError("batch files only run on Windows")
    if not isinstance(path, str) or not _BAT.fullmatch(path):
        raise ValueError("refusing to run %r: expected an absolute .bat or "
                         ".cmd path with no quotes or %% signs" % (path,))
    line = '%s /c "%s"' % (CMD_EXE, path)
    return Command(line, line)


def run_cmd(command, wait=False, timeout=None):
    """Start `command`. The only function in Scoutbot that spawns a process.

    With wait=False (launching a browser or Steam, which outlive us) it
    returns the Popen and does not hold on to the child's output. With
    wait=True it returns a CompletedProcess with stdout and stderr captured as
    text, and raises subprocess.TimeoutExpired past `timeout` seconds.

    Raises FileNotFoundError when the program is missing (no cmd.exe at the
    full path, no xdg-open), so the launcher can say which step failed.
    """
    if not isinstance(command, Command):
        raise TypeError("run_cmd takes a Command from open_url, launch_game or "
                        "run_bat, not %r" % (command,))
    kwargs = {"stdin": subprocess.DEVNULL}
    if isinstance(command.line, str):
        # Only Windows commands are strings; CreateProcess takes them whole.
        if os.name != "nt":
            raise OSError("a Windows command cannot run on this system: %s"
                          % command.shown)
        kwargs["creationflags"] = CREATE_NO_WINDOW
    if wait:
        return subprocess.run(command.line, capture_output=True, text=True,
                              timeout=timeout, check=False, **kwargs)
    kwargs["stdout"] = subprocess.DEVNULL
    kwargs["stderr"] = subprocess.DEVNULL
    if os.name != "nt":
        # Detach from our process group, so stopping the server with Ctrl+C
        # does not also close the browser it opened.
        kwargs["start_new_session"] = True
    return subprocess.Popen(command.line, **kwargs)
