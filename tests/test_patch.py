"""smmap.gamepatch.patch adds the reporter once and takes it out exactly."""

import os
import shutil
import tempfile
import unittest

from smmap.gamepatch import patch as gp

# The shape of the real SurvivalPlayer.lua around the function we wrap, LF
# endings and trailing blank lines included, as Steam ships it.
GAME_FILE = (b"dofile( \"$SURVIVAL_DATA/Scripts/game/BasePlayer.lua\" )\n\n"
             b"SurvivalPlayer = class( BasePlayer )\n\n"
             b"function SurvivalPlayer.client_onFixedUpdate( self, dt )\n"
             b"\tBasePlayer.client_onFixedUpdate( self, dt )\nend\n\n"
             b"function SurvivalPlayer.client_onCancel( self )\n"
             b"\tg_effectManager:cl_cancelAllCinematics()\nend\n\n\n\n\n\n")


class Patching(unittest.TestCase):

    def setUp(self):
        self.game = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.game)
        self.path = gp.target_path(self.game)
        os.makedirs(os.path.dirname(self.path))
        self.write(GAME_FILE)

    def write(self, data):
        with open(self.path, "wb") as f:
            f.write(data)

    def read(self, path=None):
        with open(path or self.path, "rb") as f:
            return f.read()

    def backup(self):
        return self.path + gp.BACKUP_SUFFIX

    def test_round_trip_is_byte_identical(self):
        self.assertEqual(gp.status(self.game), gp.NOT_PATCHED)
        self.assertIn("patched", gp.patch(self.game))
        patched = self.read()
        self.assertTrue(patched.startswith(GAME_FILE))
        self.assertEqual(patched.count(gp.BEGIN), 1)
        self.assertEqual(self.read(self.backup()), GAME_FILE)
        self.assertEqual(gp.status(self.game), gp.PATCHED)
        self.assertIn("unpatched", gp.unpatch(self.game))
        self.assertEqual(self.read(), GAME_FILE)
        self.assertFalse(os.path.exists(self.backup()))
        self.assertEqual(gp.status(self.game), gp.NOT_PATCHED)

    def test_idempotent(self):
        gp.patch(self.game)
        once = self.read()
        self.assertIn("already", gp.patch(self.game))
        self.assertEqual(self.read(), once)
        gp.unpatch(self.game)
        self.assertIn("not patched", gp.unpatch(self.game))
        self.assertEqual(self.read(), GAME_FILE)

    def test_crlf_file_keeps_its_newlines(self):
        crlf = GAME_FILE.replace(b"\n", b"\r\n")
        self.write(crlf)
        gp.patch(self.game)
        patched = self.read()
        self.assertNotIn(b"\n", patched.replace(b"\r\n", b""))
        gp.unpatch(self.game)
        self.assertEqual(self.read(), crlf)

    def test_older_reporter_is_replaced(self):
        old = GAME_FILE + b"\n" + gp.BEGIN + b" v0 >>>\nprint('old')\n" + \
            gp.END + b"\n"
        self.write(old)
        self.assertEqual(gp.status(self.game), gp.OUTDATED)
        self.assertIn("updated", gp.patch(self.game))
        self.assertEqual(gp.status(self.game), gp.PATCHED)
        self.assertEqual(self.read(self.backup()), GAME_FILE)
        gp.unpatch(self.game)
        self.assertEqual(self.read(), GAME_FILE)

    def test_steam_replacing_the_file_drops_the_stale_backup(self):
        gp.patch(self.game)
        updated = GAME_FILE.replace(b"Cinematics", b"Cutscenes")
        self.write(updated)                       # a game update or a verify
        self.assertEqual(gp.status(self.game), gp.NOT_PATCHED)
        self.assertIn("outdated backup", gp.unpatch(self.game))
        self.assertEqual(self.read(), updated)    # the new file is kept
        self.assertFalse(os.path.exists(self.backup()))

    def test_refuses_without_anchor(self):
        self.write(GAME_FILE.replace(b"client_onFixedUpdate", b"onTick"))
        with self.assertRaises(gp.PatchError):
            gp.patch(self.game)
        self.assertFalse(os.path.exists(self.backup()))

    def test_refuses_a_broken_block(self):
        for data in (GAME_FILE + b"\n" + gp.BEGIN + b" v1 >>>\n",
                     GAME_FILE + b"\n" + gp.END + b"\n",
                     GAME_FILE + b"\n" + gp.BEGIN + b" v1 >>>\n" + gp.END +
                     b"\nprint('after')\n"):
            with self.subTest(data=data[-40:]):
                self.write(data)
                for fn in (gp.patch, gp.unpatch, gp.status):
                    with self.assertRaises(gp.PatchError):
                        fn(self.game)
                self.assertEqual(self.read(), data)

    def test_backup_mismatch_is_reported_and_kept(self):
        gp.patch(self.game)
        with open(self.backup(), "wb") as f:
            f.write(b"something else")
        with self.assertRaises(gp.PatchError):
            gp.unpatch(self.game)
        self.assertEqual(self.read(), GAME_FILE)
        self.assertTrue(os.path.exists(self.backup()))

    def test_missing_game_file(self):
        os.remove(self.path)
        with self.assertRaises(gp.PatchError):
            gp.patch(self.game)

    def test_leaves_other_tools_backups_alone(self):
        other = self.path + ".scrapmappy-backup"
        with open(other, "wb") as f:
            f.write(b"old game code")
        gp.patch(self.game)
        gp.unpatch(self.game)
        self.assertEqual(self.read(other), b"old game code")


if __name__ == "__main__":
    unittest.main()
