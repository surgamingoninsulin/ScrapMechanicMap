# CLAUDE.md

Rules for working on this repo. The full Scoutbot plan, phases and UI spec are
in `plan_scoutbot.md`; read it before starting a phase.

## How to work

1. **Think before coding.** State assumptions out loud. If a task can be read
   two ways, name both and ask, or pick one and say which.
2. **Simplicity first.** Write the least code that passes the check. No
   speculative features, and no abstractions with only one caller.
3. **Surgical changes.** Touch only what the task needs and match the existing
   style. Docstrings here are prose that explain *why*; keep writing them that
   way.
4. **Goal-driven execution.** Every task starts with a check that proves it is
   done: a test, a curl or a screenshot. Loop until it passes.

## Hard rules

### Windows commands
- Always run commands through `C:\Windows\System32\cmd.exe`, by full path.
  Never a bare `cmd`, and never PowerShell unless the user asks.
- Never trigger the "How do you want to open this file?" dialog:
  - no `os.startfile()` on files;
  - open pages by URL: `C:\Windows\System32\cmd.exe /c start "" "http://127.0.0.1:8765/"`;
  - launch Steam: `C:\Windows\System32\cmd.exe /c start "" "steam://rungameid/387990"`;
  - run `.bat` files: `C:\Windows\System32\cmd.exe /c "path\to\file.bat"`.
- `smmap/live/shell.py:run_cmd()` is the only function allowed to spawn a
  process for Scoutbot. Build the command with `open_url`, `launch_game` or
  `run_bat`; they refuse anything cmd.exe could misread.
- The 2.x window (`smmap/gui.py`) still opens results its own way. It moves to
  `run_cmd` when the Scoutbot launcher replaces it (Phase 7), not before.

### Game and saves
- Saves are read-only. Open them with SQLite `file:...?mode=ro`, and copy the
  `.db` and `-wal` to a temp folder first while the game is running.
- Never edit game files without a backup and a working unpatch. Patches are
  idempotent and anchored on stable text. sm_overview code (CC BY-NC-SA) is
  never copied.
- No memory reading, DLL injection or process hooking. The only data sources
  are the save, the game's data files and the game log.

### Code
- Python stdlib + `numpy` + `Pillow` at run time. Any new package needs one
  line here saying why:
  - `playwright` (development only, `tools/screenshot.py`): phase screenshots
    of WebGL pages need a real browser. Nothing the user runs imports it.
  - `lupa` (development only, `tests/test_reporter.py`): runs the game patch's
    Lua under LuaJIT, the game's own runtime. Skipped when missing.
- Web libraries are vendored in `smmap/web/vendor/` (see `VENDOR.md` there):
  no CDN, and it works offline.
- The server binds `127.0.0.1` by default. LAN and public are opt-in.
- Keep Linux/Proton working.
- No placeholders and no `TODO: implement`.

## Phase protocol

1. One phase at a time, on a branch `phase-N-<slug>`.
2. Before coding, restate the goal and its checks in 3-5 lines.
3. Build, run the checks, fix, and repeat until every check passes.
4. Screenshot at 1920x1080 and 390x844 with
   `python tools/screenshot.py PAGE NAME --phase N` into `docs/phases/`, and
   send them to the user.
5. Write a short "what changed / how to try it" note and a `CHANGELOG.md`
   entry.
6. Only then start the next phase. If a check cannot pass, stop and say why.

## Checks

    python -m unittest discover -s tests -t .
