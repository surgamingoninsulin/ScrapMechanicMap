# Vendored web files

Copied in rather than loaded from a CDN, so the map works on a LAN with no
internet and a phone never waits on a third party. `tests/test_vendor.py`
checks every file below against its hash, so a changed copy fails the tests
instead of shipping by accident.

| File | From | License | sha256 |
|---|---|---|---|
| `three.min.js` | npm `three@0.128.0`, `build/three.min.js` | MIT, `LICENSE-three.txt` | `9274bbcec8d96168626c732b5d31c775aa8cfb7eaa0599bec0c175908a2c1ce2` |
| `OrbitControls.js` | npm `three@0.128.0`, `examples/js/controls/OrbitControls.js` | MIT, `LICENSE-three.txt` | `02bb4ade710f3e607329e37a21f098bc3ac70eb6e33daf8a65e79f4db785e7b2` |
| `fonts/russo-one-latin-400-normal.woff2` | npm `@fontsource/russo-one@5.3.0` | OFL 1.1, `fonts/OFL-RussoOne.txt` | `8a6b754cd3bc5ad2bf0d0308bbd9c1b7f6b4ecdd915982ffedf50ed18fed4a46` |
| `fonts/nunito-latin-400-normal.woff2` | npm `@fontsource/nunito@5.3.0` | OFL 1.1, `fonts/OFL-Nunito.txt` | `a5906e15ceb68f73d3b2c2076b4057c3f6ed401186d56283b45ce12944ca0735` |
| `fonts/nunito-latin-700-normal.woff2` | npm `@fontsource/nunito@5.3.0` | OFL 1.1, `fonts/OFL-Nunito.txt` | `fa89300b9bbb3bd0f60d6991aa055965d98e2ccca27bf8688fe0c39cdc796846` |
| `fonts/nunito-latin-800-normal.woff2` | npm `@fontsource/nunito@5.3.0` | OFL 1.1, `fonts/OFL-Nunito.txt` | `2363d3ed037283ebb961e8c4b4917e40a8bc8853cf9965cf1ea7b4daa1df630a` |

r128 is the last release that still ships `examples/js/`, the plain-script
builds that attach to the global `THREE`. Later releases are ES modules only,
which would need an import map or a bundler for no gain here.

To update one: replace the file, put its new hash in this table and in
`tests/test_vendor.py`, and say why in `CHANGELOG.md`.
