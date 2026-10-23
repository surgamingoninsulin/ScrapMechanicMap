"""Every vendored web file is present and is the exact copy VENDOR.md records.

The hashes live in one place, the table in smmap/web/vendor/VENDOR.md, and are
read from there, so updating a library is one edit and cannot drift from what
the test checks.
"""

import hashlib
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, os.pardir, "smmap", "web", "vendor")
ROW = re.compile(r"^\|\s*`([^`]+)`\s*\|.*\|\s*`([0-9a-f]{64})`\s*\|\s*$")


def recorded():
    with open(os.path.join(VENDOR, "VENDOR.md"), encoding="utf-8") as f:
        return [m.groups() for m in map(ROW.match, f) if m]


class Vendored(unittest.TestCase):

    def test_table_is_complete(self):
        names = {name for name, _ in recorded()}
        self.assertEqual(names, {
            "three.min.js", "OrbitControls.js",
            "fonts/russo-one-latin-400-normal.woff2",
            "fonts/nunito-latin-400-normal.woff2",
            "fonts/nunito-latin-700-normal.woff2",
            "fonts/nunito-latin-800-normal.woff2",
        })

    def test_hashes(self):
        for name, want in recorded():
            with self.subTest(file=name):
                with open(os.path.join(VENDOR, name), "rb") as f:
                    self.assertEqual(hashlib.sha256(f.read()).hexdigest(), want)

    def test_licenses_ship_with_them(self):
        for name in ("LICENSE-three.txt", "fonts/OFL-RussoOne.txt",
                     "fonts/OFL-Nunito.txt"):
            with self.subTest(file=name):
                self.assertTrue(os.path.isfile(os.path.join(VENDOR, name)))

    def test_three_is_r128(self):
        with open(os.path.join(VENDOR, "three.min.js"), encoding="utf-8") as f:
            # The minified build opens by binding REVISION to its first const.
            self.assertRegex(f.read(4096), r'"use strict";const \w+="128"')

    def test_fonts_css_points_at_files_that_exist(self):
        with open(os.path.join(VENDOR, "fonts", "fonts.css"),
                  encoding="utf-8") as f:
            urls = re.findall(r"url\(\./([^)]+)\)", f.read())
        self.assertEqual(len(urls), 4)
        for u in urls:
            with self.subTest(url=u):
                self.assertTrue(os.path.isfile(os.path.join(VENDOR, "fonts", u)))


if __name__ == "__main__":
    unittest.main()
