"""The reporter Lua runs under LuaJIT (the game's runtime) against a stand-in
for the parts of the sm API it touches, and prints what logfeed can parse.

Needs lupa (pip install lupa), a development-only dependency like Playwright;
without it the tests are skipped, not failed.
"""

import os
import unittest

from smmap.gamepatch import patch as gp
from smmap.live import logfeed

try:
    from lupa.luajit21 import LuaRuntime
except ImportError:               # pragma: no cover - depends on the machine
    LuaRuntime = None

# Just enough of the game for the reporter: a class table holding the
# function it wraps, a local player whose character can come and go, the
# tick counter, and a log that the test reads back.
STUB = """
logged = {}
calls = 0
tick = 0
SurvivalPlayer = {}
function SurvivalPlayer.client_onFixedUpdate( self, dt ) calls = calls + 1 end
local world = { id = 1 }
local character = {
  worldPosition = { x = -1024.5, y = 2048.25, z = 31.125 },
  direction = { x = 0, y = 1, z = 0 },
  getWorld = function( self ) return world end,
}
localPlayer = { character = character }
otherPlayer = { character = character }
sm = {
  localPlayer = { getPlayer = function() return localPlayer end },
  game = { getCurrentTick = function() return tick end },
  exists = function( obj ) return obj ~= nil end,
  log = {
    info = function( s ) logged[#logged + 1] = s end,
    warning = function( s ) logged[#logged + 1] = s end,
  },
}
"""


@unittest.skipIf(LuaRuntime is None, "lupa is not installed")
class Reporter(unittest.TestCase):

    def setUp(self):
        self.lua = LuaRuntime()
        self.lua.execute(STUB)
        with open(gp.REPORTER, encoding="utf-8") as f:
            self.lua.execute(f.read())
        self.g = self.lua.globals()

    def step(self, player, ticks):
        me = self.lua.table_from({"player": player})
        for _ in range(ticks):
            self.g.SurvivalPlayer.client_onFixedUpdate(me, 0.025)
            self.g.tick += 1

    def logged(self):
        return list(self.g.logged.values())

    def test_ten_reports_a_second_that_logfeed_reads(self):
        self.step(self.g.localPlayer, 40)
        lines = self.logged()
        self.assertEqual(len(lines), 10)
        self.assertEqual(self.g.calls, 40)        # the game's update still runs
        kind, r = logfeed.parse_line("17:00:00 (1/1) [Main:1] [Lua] " +
                                     lines[0])
        self.assertEqual(kind, "player")
        self.assertEqual((r["x"], r["y"], r["z"], r["world"], r["t"]),
                         (-1024.5, 2048.25, 31.125, 1, 0))
        self.assertAlmostEqual(r["yaw"], 1.5708, places=4)

    def test_keeps_reporting_with_no_run_once_guard(self):
        self.step(self.g.localPlayer, 400)
        self.assertEqual(len(self.logged()), 100)

    def test_only_the_local_player(self):
        self.step(self.g.otherPlayer, 40)
        self.assertEqual(self.logged(), [])
        self.assertEqual(self.g.calls, 40)

    def test_no_character_while_loading(self):
        self.g.localPlayer.character = None
        self.step(self.g.localPlayer, 40)
        self.assertEqual(self.logged(), [])

    def test_an_error_is_logged_once_and_the_game_carries_on(self):
        self.g.sm.game.getCurrentTick = None      # API missing on this build
        self.step(self.g.localPlayer, 40)
        lines = self.logged()
        self.assertEqual(len(lines), 1)
        kind, text = logfeed.parse_line(lines[0])
        self.assertEqual(kind, "error")
        self.assertEqual(self.g.calls, 40)


if __name__ == "__main__":
    unittest.main()
