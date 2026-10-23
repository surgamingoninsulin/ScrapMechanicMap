"""Add Scoutbot's position reporter to the game, and take it out again.

The game has one file Scoutbot changes: Survival/Scripts/game/SurvivalPlayer.lua.
The reporter is appended to the end of it as one marked block, and the block
wraps SurvivalPlayer.client_onFixedUpdate instead of editing it. That keeps
the patch independent of what is inside the game's function, so a game update
that changes the function body does not break it, and taking it out is a
matter of cutting the file back to the length it had.

Three rules make it safe to run at any time, in any order:

- Patching twice changes nothing. A file that already carries the current
  block is left alone; one carrying an older block has it replaced.
- Unpatching gives back the file byte for byte. The block is appended to the
  untouched original, so removing it is exact; the backup written before the
  first patch is compared against the result and only then deleted.
- A file that does not look the way the patch expects is not touched. The
  anchor (the function being wrapped) must be there exactly once, and markers
  must come in one complete pair at the end.

The backup lives next to the file as SurvivalPlayer.lua.scoutbot-backup and
exists only while the game is patched. A backup left lying around is a
liability: once Steam updates the game it holds old code, and restoring it
would undo the update. An earlier tool on this PC left exactly such files
(.scrapmappy-backup); this module never reads or writes those.
"""

import argparse
import hashlib
import os
import sys

TARGET = os.path.join("Survival", "Scripts", "game", "SurvivalPlayer.lua")
ANCHOR = b"function SurvivalPlayer.client_onFixedUpdate( self, dt )"
BEGIN = b"-- >>> SCOUTBOT REPORTER"
END = b"-- <<< SCOUTBOT REPORTER <<<"
BACKUP_SUFFIX = ".scoutbot-backup"
REPORTER = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "scoutbot_reporter.lua")

NOT_PATCHED = "not patched"
PATCHED = "patched"
OUTDATED = "patched with an older reporter"


class PatchError(Exception):
    """The file is not in a state this module knows how to change safely."""


def target_path(game):
    return os.path.join(game, TARGET)


def reporter_block(newline=b"\n"):
    """The block as it goes into the game file, in the file's own newlines."""
    with open(REPORTER, "rb") as f:
        text = f.read().replace(b"\r\n", b"\n")
    if not text.endswith(b"\n"):
        text += b"\n"
    return text.replace(b"\n", newline)


def _newline(data):
    return b"\r\n" if b"\r\n" in data else b"\n"


def _split(data):
    """(original, block) where block is the appended reporter, or None.

    The block is everything from the line before BEGIN (the separating
    newline the patch added) to the end of the file, and it must end with
    END. Anything else (one marker without the other, a block followed by
    more code, two blocks) means someone or something edited the file after
    us, and it is refused rather than guessed at.
    """
    begins = data.count(BEGIN)
    ends = data.count(END)
    if begins == 0 and ends == 0:
        return data, None
    if begins != 1 or ends != 1:
        raise PatchError("the Scoutbot markers in %s are not one complete "
                         "pair; restore the file with Steam's 'Verify "
                         "integrity of game files'" % TARGET)
    nl = _newline(data)
    start = data.index(BEGIN)
    if not data[:start].endswith(nl):
        raise PatchError("the Scoutbot block in %s does not start on its own "
                         "line" % TARGET)
    start -= len(nl)                     # the separator the patch added
    tail = data[data.index(END) + len(END):]
    if tail not in (b"", nl):
        raise PatchError("there is code after the Scoutbot block in %s, so "
                         "removing it would remove that too" % TARGET)
    return data[:start], data[start:]


def _read(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise PatchError("%s was not found; is this the Scrap Mechanic folder?"
                         % path)


def _write(path, data):
    """Replace the file in one step, so the game never sees half of it."""
    tmp = path + ".scoutbot-tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def status(game):
    data = _read(target_path(game))
    original, block = _split(data)
    if block is None:
        return NOT_PATCHED
    nl = _newline(original)
    return PATCHED if block == nl + reporter_block(nl) else OUTDATED


def patch(game):
    """Add the reporter. Returns what was done, as one line for the log."""
    path = target_path(game)
    data = _read(path)
    original, block = _split(data)
    if original.count(ANCHOR) != 1:
        raise PatchError("expected `%s` exactly once in %s, found it %d "
                         "times; the game has changed and the patch needs "
                         "updating" % (ANCHOR.decode(), TARGET,
                                       original.count(ANCHOR)))
    nl = _newline(original)
    wanted = original + nl + reporter_block(nl)
    if data == wanted:
        return "already patched: %s" % path
    backup = path + BACKUP_SUFFIX
    if block is None:
        # First patch: keep the original before anything else is written.
        _write(backup, original)
    elif not os.path.isfile(backup):
        # Upgrading an older block whose backup went missing: the original is
        # still recoverable exactly, so recreate it.
        _write(backup, original)
    _write(path, wanted)
    return ("patched: %s" if block is None else "updated the reporter: %s") \
        % path


def unpatch(game):
    """Remove the reporter, leaving the file as it was before patch()."""
    path = target_path(game)
    backup = path + BACKUP_SUFFIX
    data = _read(path)
    original, block = _split(data)
    if block is None:
        if os.path.isfile(backup):
            # Steam replaced the file (an update or a verify) while patched.
            # Its new file is the one to keep; the backup is now old code.
            os.remove(backup)
            return "not patched (removed an outdated backup): %s" % path
        return "not patched: %s" % path
    _write(path, original)
    if os.path.isfile(backup):
        with open(backup, "rb") as f:
            saved = f.read()
        if saved != original:
            raise PatchError("removed the reporter, but the result (%s) does "
                             "not match the backup (%s); both are left in "
                             "place, see %s" % (_sha(original)[:12],
                                                _sha(saved)[:12], backup))
        os.remove(backup)
    return "unpatched: %s" % path


def main(argv=None):
    from .. import discover

    ap = argparse.ArgumentParser(
        prog="python -m smmap.gamepatch",
        description="Add or remove Scoutbot's position reporter.")
    ap.add_argument("--game", help="path to the Scrap Mechanic folder")
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--unpatch", action="store_true",
                       help="remove the reporter")
    group.add_argument("--status", action="store_true",
                       help="say whether the game is patched")
    args = ap.parse_args(argv)

    game = args.game or discover.find_game()
    if not game:
        print("Could not find Scrap Mechanic; pass --game.", file=sys.stderr)
        return 2
    try:
        if args.status:
            print("%s: %s" % (status(game), target_path(game)))
        elif args.unpatch:
            print(unpatch(game))
        else:
            print(patch(game))
    except PatchError as e:
        print("error: %s" % e, file=sys.stderr)
        return 1
    return 0
