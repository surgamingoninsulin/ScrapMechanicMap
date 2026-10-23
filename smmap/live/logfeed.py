"""Read the player's position out of the game log while the game writes it.

Scrap Mechanic 1.0 gives scripts no way to write a file, but sm.log.info()
lands in Logs/game-<date>-<time>.log in the game folder, flushed as it goes.
The patched SurvivalPlayer prints a line there about ten times a second:

    17:12:12 (1/8162) [Logic Task:18492] [Lua] [SMMAP]{"x":..,"y":..,...}

What comes before [SMMAP] is the game's own prefix, and it is not one shape:
a time, a frame/tick pair, a thread in brackets and usually a category in
brackets, though warnings drop the category. So nothing here parses the
prefix. A report is whatever follows the first "[SMMAP]" on a line, and it
has to be a JSON object with every field a finite number, or it is ignored.

The game starts a new log every launch, so the tailer follows the newest
game-*.log and moves to a newer one when it appears, which is how a game
restarted while the map stays open keeps working.
"""

import argparse
import glob
import json
import math
import os
import sys
import time

TAG = "[SMMAP]"
ERROR_TAG = "[SMMAP-ERROR]"
FIELDS = ("x", "y", "z", "yaw", "world", "t")
LOG_GLOB = "game-*.log"


def log_dir(game):
    return os.path.join(game, "Logs")


def newest_log(folder):
    """The game log written most recently, or None."""
    logs = glob.glob(os.path.join(folder, LOG_GLOB))
    if not logs:
        return None
    # Names carry the launch time, which breaks ties when two logs share an
    # mtime to the second (a crash and an immediate relaunch).
    return max(logs, key=lambda p: (os.path.getmtime(p), os.path.basename(p)))


def parse_line(line):
    """("player", {x, y, z, yaw, world, t}), ("error", text), or None."""
    at = line.find(ERROR_TAG)
    if at >= 0:
        return "error", line[at + len(ERROR_TAG):].strip()
    at = line.find(TAG)
    if at < 0:
        return None
    try:
        report = json.loads(line[at + len(TAG):].strip())
    except ValueError:
        return None
    if not isinstance(report, dict):
        return None
    out = {}
    for key in FIELDS:
        value = report.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not math.isfinite(value):
            return None
        out[key] = value
    out["world"] = int(out["world"])
    out["t"] = int(out["t"])
    return "player", out


class Tailer(object):
    """Follows the newest game log, returning complete new lines.

    Call poll() as often as you like; each call reads what was added since
    the last one. A line the game is still in the middle of writing is held
    back until its newline arrives, so a report is never parsed in halves.
    """

    def __init__(self, folder, from_start=False):
        self.folder = folder
        self.path = None
        self.offset = 0
        self.partial = b""
        self.from_start = from_start

    def _switch(self, path, from_start):
        self.path = path
        self.partial = b""
        self.offset = 0 if from_start else os.path.getsize(path)

    def poll(self):
        newest = newest_log(self.folder)
        if newest is None:
            return []
        if newest != self.path:
            # The first log is joined at its end, so a map opened mid-session
            # starts from now rather than replaying the session. A log that
            # appears later is a new launch and is read from its start.
            self._switch(newest, self.from_start or self.path is not None)
        try:
            size = os.path.getsize(self.path)
            if size < self.offset:      # truncated or replaced in place
                self.offset = 0
                self.partial = b""
            if size == self.offset:
                return []
            with open(self.path, "rb") as f:
                f.seek(self.offset)
                chunk = f.read(size - self.offset)
        except OSError:
            return []                   # mid-rotation; try again next poll
        self.offset += len(chunk)
        data = self.partial + chunk
        lines = data.split(b"\n")
        self.partial = lines.pop()
        return [l.rstrip(b"\r").decode("utf-8", "replace") for l in lines]


def follow(game, interval=0.05, from_start=False, stop=None):
    """Yield ("player", report) and ("error", text) as the game writes them.

    `stop` is a threading.Event (or anything with is_set) that ends the loop.
    """
    tail = Tailer(log_dir(game), from_start=from_start)
    while stop is None or not stop.is_set():
        for line in tail.poll():
            parsed = parse_line(line)
            if parsed:
                yield parsed
        time.sleep(interval)


def main(argv=None):
    from .. import discover

    ap = argparse.ArgumentParser(
        prog="python -m smmap.live.logfeed",
        description="Print the positions the patched game writes to its log.")
    ap.add_argument("--game", help="path to the Scrap Mechanic folder")
    ap.add_argument("--from-start", action="store_true",
                    help="replay the newest log from its first line")
    args = ap.parse_args(argv)
    game = args.game or discover.find_game()
    if not game:
        print("Could not find Scrap Mechanic; pass --game.", file=sys.stderr)
        return 2
    print("following %s" % log_dir(game), flush=True)
    last = None
    try:
        for kind, payload in follow(game, from_start=args.from_start):
            now = time.time()
            if kind == "error":
                print("reporter error: %s" % payload, flush=True)
                continue
            gap = "" if last is None else "  +%3d ms" % ((now - last) * 1000)
            last = now
            print("%s  x %9.2f  y %9.2f  z %7.2f  yaw %6.1f deg  world %d  "
                  "tick %d%s" % (time.strftime("%H:%M:%S"), payload["x"],
                                 payload["y"], payload["z"],
                                 math.degrees(payload["yaw"]),
                                 payload["world"], payload["t"], gap),
                  flush=True)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
