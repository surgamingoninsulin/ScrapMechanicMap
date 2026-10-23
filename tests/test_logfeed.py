"""smmap.live.logfeed reads [SMMAP] reports out of a game log as it grows."""

import os
import shutil
import tempfile
import threading
import time
import unittest

from smmap.live import logfeed

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "game-scoutbot-sample.log")


def fixture_lines():
    with open(FIXTURE, "rb") as f:
        return [l.rstrip(b"\r").decode() for l in f.read().split(b"\n") if l]


class ParseLine(unittest.TestCase):

    def test_fixture(self):
        parsed = [p for p in map(logfeed.parse_line, fixture_lines()) if p]
        players = [r for kind, r in parsed if kind == "player"]
        errors = [r for kind, r in parsed if kind == "error"]
        self.assertEqual([r["t"] for r in players], [8200, 8204, 8208, 8212,
                                                     8220])
        self.assertEqual(players[0], {"x": -1024.5, "y": 2048.25,
                                      "z": 31.125, "yaw": 1.5708,
                                      "world": 1, "t": 8200})
        self.assertEqual(players[-1]["world"], 3)
        self.assertEqual(len(errors), 1)
        self.assertIn("attempt to index a nil value", errors[0])

    def test_both_prefix_forms(self):
        body = '{"x":1,"y":2,"z":3,"yaw":0.5,"world":1,"t":40}'
        for prefix in ("17:12:30 (1/2) [Logic Task:1] [Lua] ",
                       "17:12:30 (1/2) [Main:1] ", ""):
            with self.subTest(prefix=prefix):
                kind, r = logfeed.parse_line(prefix + "[SMMAP]" + body)
                self.assertEqual(kind, "player")
                self.assertEqual(r["x"], 1)

    def test_rejects(self):
        for line in ['[SMMAP]{"x":1}',
                     '[SMMAP]{"x":true,"y":0,"z":0,"yaw":0,"world":1,"t":1}',
                     '[SMMAP]{"x":NaN,"y":0,"z":0,"yaw":0,"world":1,"t":1}',
                     '[SMMAP]{"x":1e999,"y":0,"z":0,"yaw":0,"world":1,"t":1}',
                     '[SMMAP]"x"', "[SMMAP]", "nothing here",
                     '[smmap]{"x":1,"y":0,"z":0,"yaw":0,"world":1,"t":1}']:
            with self.subTest(line=line):
                self.assertIsNone(logfeed.parse_line(line))


class TailerTest(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir)

    def log(self, name, data=b"", mtime=None):
        path = os.path.join(self.dir, name)
        with open(path, "ab") as f:
            f.write(data)
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def test_joins_at_the_end_and_holds_partial_lines(self):
        path = self.log("game-20261023-100000.log", b"old line\n")
        tail = logfeed.Tailer(self.dir)
        self.assertEqual(tail.poll(), [])
        self.log("game-20261023-100000.log", b"new one\r\nhalf a li")
        self.assertEqual(tail.poll(), ["new one"])
        self.assertEqual(tail.poll(), [])
        self.log("game-20261023-100000.log", b"ne\n")
        self.assertEqual(tail.poll(), ["half a line"])
        self.assertTrue(os.path.isfile(path))

    def test_from_start(self):
        self.log("game-20261023-100000.log", b"a\nb\n")
        self.assertEqual(logfeed.Tailer(self.dir, from_start=True).poll(),
                         ["a", "b"])

    def test_follows_a_relaunch_from_its_first_line(self):
        now = time.time()
        self.log("game-20261023-100000.log", b"first session\n", now - 60)
        tail = logfeed.Tailer(self.dir)
        tail.poll()
        self.log("game-20261023-101500.log", b"second session\n", now)
        self.assertEqual(tail.poll(), ["second session"])

    def test_truncated_log_is_reread(self):
        self.log("game-20261023-100000.log", b"x" * 100 + b"\n")
        tail = logfeed.Tailer(self.dir)
        tail.poll()
        with open(os.path.join(self.dir, "game-20261023-100000.log"),
                  "wb") as f:
            f.write(b"fresh\n")
        self.assertEqual(tail.poll(), ["fresh"])

    def test_no_logs(self):
        self.assertEqual(logfeed.Tailer(self.dir).poll(), [])

    def test_follow_replays_fixture_in_order_as_written(self):
        """A writer thread appends the fixture in uneven chunks while follow()
        reads, the way the game flushes; every report arrives once, in order."""
        game = self.dir
        os.mkdir(os.path.join(game, "Logs"))
        path = os.path.join(game, "Logs", "game-20261023-120000.log")
        open(path, "wb").close()
        with open(FIXTURE, "rb") as f:
            data = f.read()
        stop = threading.Event()
        got = []

        def write():
            time.sleep(0.1)
            with open(path, "ab") as f:
                for i in range(0, len(data), 37):
                    f.write(data[i:i + 37])
                    f.flush()
                    time.sleep(0.002)

        writer = threading.Thread(target=write)
        writer.start()
        deadline = time.time() + 10
        for kind, report in logfeed.follow(game, interval=0.01, stop=stop):
            if kind == "player":
                got.append(report["t"])
            if len(got) == 5 or time.time() > deadline:
                stop.set()
        writer.join()
        self.assertEqual(got, [8200, 8204, 8208, 8212, 8220])


if __name__ == "__main__":
    unittest.main()
