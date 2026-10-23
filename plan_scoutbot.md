# plan_scoutbot.md — Scoutbot: live 3D map for Scrap Mechanic

**Scoutbot** is a live 3D map and minimap of your Scrap Mechanic survival world
for a second monitor, tablet or phone. It shows real terrain and real game
assets, a Scoutbot drone that follows you, and 3D waypoints. A local Python
server serves it, and one menu starts the server, patches the game and launches
Scrap Mechanic through Steam.

- **Source repo:** https://github.com/surgamingoninsulin/ScrapMechanicMap (v2.2)
- **Reference:** the1killer/sm_overview (flat Leaflet map built from `cells.json`)
- **Design reference:** `scoutbot-mockup.html`, the last approved mockup. Every
  UI decision below comes from it.

---

## 0. Name

**Scoutbot** fits the game's own naming: Craftbot, Cookbot, Dressbot,
Totebot, Haybot, Tapebot, Farmbot. My web searches found no existing Scrap
Mechanic mod or tool with this name, and none called Navbot or Mapbot either.
The Steam Workshop and GitHub couldn't be searched directly, so search
"Scoutbot" on both once before publishing. **Backup name:** Navbot.

---

## 1. Rule set (also in `CLAUDE.md` at the repo root)

### 1.1 How to work: Karpathy's four guidelines
1. **Think before coding.** State assumptions out loud. If a task can be read
   two ways, name both and ask, or pick one and say which.
2. **Simplicity first.** Write the least code that passes the check. No
   speculative features, and no abstractions with only one caller.
3. **Surgical changes.** Touch only what the task needs and match the existing
   style. The repo writes prose docstrings that explain *why*; keep doing that.
4. **Goal-driven execution.** Every task starts with a check that proves it's
   done: a test, a curl or a screenshot. Loop until it passes.

### 1.2 Hard rules
**Windows commands**
- Always run commands through `C:\Windows\System32\cmd.exe`, by full path.
  Never a bare `cmd`, and never PowerShell unless the user asks.
- Never trigger the "How do you want to open this file? / pick an app" dialog:
  - no `os.startfile()` on files;
  - open pages by URL: `C:\Windows\System32\cmd.exe /c start "" "http://127.0.0.1:8765/"`;
  - launch Steam: `C:\Windows\System32\cmd.exe /c start "" "steam://rungameid/387990"`;
  - run `.bat` files: `C:\Windows\System32\cmd.exe /c "path\to\file.bat"`.
- `smmap/live/shell.py:run_cmd()` is the only function allowed to spawn a
  Windows process.

**Game and saves**
- Saves are read-only. Open them with SQLite `file:...?mode=ro`, and copy the
  `.db` and `-wal` to a temp folder first while the game is running.
- Never edit game files without a backup and a working unpatch. Patches are
  idempotent and anchored on stable text. sm_overview code (CC BY-NC-SA) is
  never copied.
- No memory reading, DLL injection or process hooking. The only data sources
  are the save, the game's data files and the game log.

**Code**
- Python stdlib + `numpy` + `Pillow`. Any new package needs one line here
  saying why.
- Web libraries (Three.js, OrbitControls) are vendored in
  `smmap/web/vendor/`: no CDN, and it works offline.
- The server binds `127.0.0.1` by default. LAN and public are opt-in.
- Keep Linux/Proton working.
- No placeholders and no `TODO: implement`.

### 1.3 Phase protocol
1. One phase at a time, on a branch `phase-N-<slug>`.
2. Before coding, restate the goal and its checks in 3–5 lines.
3. Build, run the checks, fix, and repeat until every check passes.
4. Take screenshots with headless Chromium (Playwright) at **1920×1080** and
   **390×844**, save them to `docs/phases/phase-N-*.png` and send them to the user.
5. Write a short "what changed / how to try it" note and a `CHANGELOG.md` entry.
6. Only then start the next phase. If a check can't pass, stop and report why.

---

## 2. Starting point

**ScrapMechanicMap v2.2 already reads almost everything:** the save (SQLite +
LZ4 + bit-packed Lua), terrain `.tile` and `.tileson` files, prefab trees, the
asset, harvestable and kinematic catalogues, collision meshes (`.obj` + FBX),
art meshes with UVs (`fbx.py`), creations, beds, beacons, quest markers and
underground floors. Its output is one self-contained HTML file in raw WebGL 2,
about 50 MB for a full world.

| Need | Today | Gap |
|---|---|---|
| Player position | not read | no live data source |
| Look | collision meshes, flat colours | textured art meshes |
| Delivery | one 50 MB HTML | streamed chunks a phone can handle |
| Runs as | one-shot export | long-running server + launcher |
| Waypoints | save's beacons (read-only) | user waypoints synced across devices |

### Lessons from sm_overview
- **SM 1.0 can't write files, but it can print to the game log.** The
  `0.6.6_bugfix` branch (`e336eb4`, Dec 2023) moved the `cells.json` dump from
  `sm.json.save()` to `sm.log.info()`. That log is Scoutbot's live channel.
- **Avoid run-once guards.** Both the branch (`setTempData("STORAGE_CELLJSON")`)
  and `main` (`g_smOverviewDumped`) dump only once per game launch. Reloading a
  save prints nothing. Scoutbot's reporter prints continuously.
- **Script cache.** In `setup.ps1` the step that clears `core_data.cbo` and
  `Bundle` is commented out, so the patch may never load. Phase 1 tests this.
- **`-dev` launch flag.** sm_overview only passes it when it launches the game
  itself. Phase 1 tests with and without it.
- **Silent failure.** The launcher must say "no position received in 30 s"
  instead of quietly showing nothing.

---

## 3. Architecture

```
 ┌──────────── Scoutbot launcher (tkinter, extends gui.py) ────────────┐
 │ world · This PC / Home Wi-Fi / Public · port · Look · 3 toggles ·   │
 │ [START] (shows live step log) · URL + QR · [STOP]                   │
 └───┬───────────────┬────────────────────────┬────────────────────────┘
     │ build cache   │ start server           │ run_cmd → cmd.exe /c start "" steam://rungameid/387990
     ▼               ▼                        ▼
 cache/<world>/   Python server (stdlib)    Scrap Mechanic, patched survival script
  manifest.json    /            web client     prints [SMMAP]{x,y,z,yaw,world,t} ~10 Hz
  terrain/*.bin    /cache/...   chunks              │
  objects/*.bin    /api/*       manifest, waypoints  │
  meshes/ tex/     /live  (SSE) ◄── log tailer ◄────┘
  waypoints.json      │
                      ▼
   Browser on 2nd monitor / tablet / phone: Three.js client (Scoutbot UI)
```

**Key choices**
- **Server-Sent Events** for the live feed. It only needs server→client,
  needs only the stdlib, and works in every phone browser. Waypoint edits use
  plain `POST` and `DELETE`.
- **Three.js r128, vendored**, for the new client. Streaming, instancing and
  mobile level of detail take far less code than extending the 1,837-line
  `viewer3d.py`. The old single-file export stays as it is.
- **The game log as live channel.** If that fails, fall back to polling the
  save file, which only updates at autosave.

---

## 4. UI spec (from the approved mockup)

### 4.1 Visual style
- **Palette:** survival orange `#f5a00f`, navy panels `#1b2433` / `#253145`,
  outline `#0b1018`, red `#e8382f`, cyan `#9ee6ff`, hazard yellow `#f5c518`.
- **Fonts:** Russo One for headings and buttons, Nunito for body text, with a
  system-ui fallback. Bundle both fonts locally in the real build.
- **Shapes:** panels have a thick dark outline and an inner navy ring;
  buttons are chunky with a pressed-down shadow. The look is "game UI", not
  "web app".

### 4.2 Launcher (the start menu)
- Orange header with the Scoutbot robot-head logo, **SCOUTBOT** and the
  tagline "Live 3D map for your second screen".
- World picker (newest first, last-played selected).
- "Who can open the map": **This PC / Home Wi-Fi / Public**.
- Port (default `8765`) and Look: **Full assets / Balanced / Phone**.
- Toggles:
  - **Launch Scrap Mechanic** (through Steam, using cmd.exe)
  - **Live position** (patches the game, undone on Stop)
  - **Open map on this PC**
- **START** runs the steps and shows each one with a ✓ as it finishes,
  including the exact cmd.exe line it ran.

### 4.3 Map HUD
- **Top bar:** brand + LIVE pill; compass strip with N in red, a centre
  needle and waypoint markers on it; waypoint-list button (phone only);
  settings gear.
- **Waypoint panel (left):** colour diamond, name, a "· save" tag for waypoints
  read from the save, live distance, and ✕ to delete your own. Click a row to
  fly there.
- **Coordinates (bottom-left):** X / Y / Z in metres, cell, and heading.
- **Camera modes (bottom-centre):** **Follow** (chase cam), **Free**
  (orbit/fly, shows a "Follow me" button), **Top** (heading-up, from high
  above). Switching modes snaps the camera instead of drifting.
- **Minimap (bottom-right):** round and heading-up by default (north-up in
  settings), with waypoints clamped to the rim and the same chevron + hazard
  ring as the 3D marker.
- **Tap or click the ground** to drop a waypoint. A toast confirms it with its
  distance.
- **Settings drawer:** QR code + URL, minimap heading-up or north-up, toggles
  for the trail, waypoint beams and place names (off means no spoilers), and
  a red **STOP** button ("Stop shuts the server and removes the game patch").

### 4.4 Player marker: the Scoutbot drone
- **Drone:** rounded orange body with dark outlines. **Front:** navy visor
  with cyan eyes. **Back:** vent panel with three orange slats and a red tail
  light. **Top:** antenna with a blinking red tip. **Bottom:** thruster with
  a flickering cyan glow.
- **Motion:** it bobs gently, leans forward and banks into turns.
- **Ground marker:** dark disc, yellow-and-black hazard ring and a red
  chevron pointing in your facing direction.
- **No clipping (approved behaviour):**
  - Heights come from the actual terrain *triangles*, not the smooth function.
  - The disc stays flat. It tilts to the best-fit (least-squares) slope,
    capped at about 14° so it never turns edge-on, then lifts by the most any
    ground point sticks up through it.
  - Water counts as ground, so the disc floats on lakes.
  - The drone hovers above the highest ground within its footprint.
  - The road surface sits on the same terrain triangles, below the disc.
- In Top view the drone and disc scale ×2.6 so they stay readable.

### 4.5 Waypoints
- 3D marker: dark base, spinning bobbing gem, additive light beam and a name
  label that stays the same size on screen.
- Six colours, cycled. Waypoints read from the save (beacons, quest markers)
  are tagged "save" and can't be deleted.
- Synced to every open device through `/live`.

### 4.6 Phone layout (≤ 760 px)
The waypoint list moves behind a pin button. The mode bar is full width at the
bottom, the minimap is 128 px, and the follow camera pulls back and up for
portrait screens.

---

## 5. Directory layout

```
ScrapMechanicMap/
├── CLAUDE.md
├── plan_scoutbot.md
├── smmap/                    existing renderer; readers changed only surgically
├── smmap/live/
│   ├── shell.py              run_cmd(): the only process spawner (cmd.exe rule)
│   ├── logfeed.py            find + tail game log, parse [SMMAP] lines
│   ├── cache.py              chunked world export (terrain, objects, meshes, textures)
│   ├── server.py             ThreadingHTTPServer: static, /api/*, /live SSE
│   ├── waypoints.py          per-world waypoints.json, validation
│   ├── settings.py           settings.json load/save
│   ├── qr.py                 QR encoder in pure Python
│   └── launcher.py           Scoutbot tab / window
├── smmap/gamepatch/
│   ├── scoutbot_reporter.lua position reporter snippet
│   └── patch.py              patch / unpatch / status, with backups
├── smmap/web/
│   ├── index.html  style.css  app.js
│   ├── js/ terrain.js objects.js marker.js waypoints.js hud.js minimap.js live.js
│   └── vendor/ three.min.js OrbitControls.js fonts/
├── tests/                    unit tests + fixtures (recorded logs, tiny world)
└── docs/phases/              phase screenshots
```

---

## 6. Phases

Every phase ends with passing checks and desktop + phone screenshots sent
before the next one starts.

### Phase 0: Groundwork
- Add `CLAUDE.md`, this plan, `tests/`, `docs/phases/` and a Playwright
  screenshot script.
- Add `shell.py` with `run_cmd()`.
- Vendor Three.js r128, OrbitControls and the two fonts.
- Render your world with today's `--3d` as a baseline.
- **Checks:** the existing CLI output is unchanged; `run_cmd` builds the
  exact cmd.exe command line (unit test); the baseline screenshot exists.

### Phase 1: Live-position spike (riskiest part first)
- `scoutbot_reporter.lua`: about every 10 ticks, print
  `[SMMAP]{"x":..,"y":..,"z":..,"yaw":..,"world":..,"t":..}` for the local
  player's character. **No run-once guard.**
- `patch.py`: anchored, idempotent injection with a backup, `--unpatch` and
  `--status`.
- `logfeed.py`: find the newest `game-*.log`, tail it while it grows, and
  strip the log prefix (both the one-field and two-field forms).
- **Answer:** which survival hook works; whether `-dev` is needed; whether the
  script cache must be cleared; log latency; and whether multiplayer only
  reports the host.
- **Checks:** walking in game moves the parsed coordinate within 1 s;
  reloading the save keeps reporting; unpatch restores byte-identical files;
  the parser passes on a recorded log fixture.
- **If it fails:** fall back to polling the save, and tell the user before
  continuing.

### Phase 2: World cache export
- `cache.py` reuses the existing readers but writes chunked binary:
  - terrain per 256 m chunk (heights on the 2 m grid, plus colour);
  - object instances per chunk;
  - a shared mesh library;
  - `manifest.json` with bounds, water level, places, beacons and quest markers.
- The cache is keyed by save mtime + game version and rebuilds only when stale.
- **Checks:** a full world builds; object count and terrain bounds match the
  old export; a second run skips the rebuild.

### Phase 3: Local server
- `server.py` serves these routes:
  - `/` (client)
  - `/cache/...` (static, with a path-traversal guard)
  - `/api/manifest`
  - `/api/waypoints` (GET / POST / DELETE)
  - `/live` (SSE: `player`, `waypoint_added`, `waypoint_removed`, `status`)
- **Checks:** curl tests for every route; a traversal attempt returns 403;
  SSE replays a recorded log in order.

### Phase 4: 3D client (terrain, objects, HUD shell)
- Port the mockup into `smmap/web/` as modules. Replace the fake world with
  streamed chunks.
- Add instanced objects, water, sun and shadows, distance-based level of
  detail, and performance mode.
- Add the full HUD from §4.3: compass, coordinates, the three camera modes
  with snapping, the minimap, the settings drawer and the phone layout from §4.6.
- **Checks:** screenshots match the mockup; ≥ 60 fps on desktop and ≥ 30 fps
  at the phone viewport (measured); first view in under 3 s on LAN.

### Phase 5: Scoutbot marker + waypoints
- `marker.js`: the drone and ground disc exactly as in §4.4, including the
  no-clipping rules, the ×2.6 Top-view scale and the breadcrumb trail.
- Driven by `/live` with smoothing between the ~10 Hz updates.
- `waypoints.js`: tap to place (raycast against terrain), list, delete, fly
  to, and edge markers on the compass and minimap.
- Save beacons and quest markers are imported as read-only waypoints.
- **Checks:**
  - the marker never sits below the terrain on a replayed walk (an automated
    test samples 1,000 positions and asserts every disc vertex is ≥ the
    ground height);
  - a waypoint placed on the phone appears on the PC within 1 s;
  - waypoints survive a restart.

### Phase 6: Full Scrap Mechanic asset look
- Export art meshes (already parsed by `fbx.py`) with UVs at 2–3 levels of
  detail. The collision mesh stays as the far level.
- Read the game's `.dds` textures. Check that Pillow handles the BC formats SM
  uses; if not, add a small numpy BC decoder.
- Write resized PNG/WebP per quality tier. The terrain gets the real ground
  textures, blended by material weights.
- Wire up Look: **Full assets / Balanced / Phone**.
- **Checks:** side-by-side with an in-game screenshot from you; the Phone tier
  stays ≥ 30 fps; cache size per tier is reported.

### Phase 7: Launcher menu
- The Scoutbot window, laid out as in §4.2.
- **START does, in order:**
  1. refresh the cache;
  2. start the server;
  3. patch the game (if Live position is on);
  4. `run_cmd` Steam launch (if on);
  5. wait for the first `[SMMAP]` line, or warn after 30 s;
  6. `run_cmd` to open the page (if on).
- **STOP** stops the server and unpatches the game.
- Show the URL and a real, scannable QR code (`qr.py`, no new dependency).
- Save settings to `settings.json`.
- **Checks:** one click from a cold start to the drone moving; after Stop the
  game files are byte-identical to before; the QR code scans on a real phone.

### Phase 8: LAN / Public hardening
- LAN binds `0.0.0.0`. Public requires a token, with viewer and editor tokens
  (only editors can change waypoints).
- Rate-limit `POST`, keep CORS off and cap request sizes.
- Public is reached through your own port-forward or a tunnel you choose; the
  app never opens ports itself.
- **Note:** Full assets serves Axolot's art to anyone who connects. Keep
  Public for friends with a token, not open links.
- **Checks:** no token → 401; a viewer can't edit; fuzzed requests don't
  crash the server.

### Phase 9: Package & document
- `build_exe.py` bundles `smmap/web` and the vendor files.
- README "Scoutbot" section and a 3.0 entry in `CHANGELOG.md`.
- **Checks:** a fresh `ScrapMap.exe` in a clean folder runs the whole flow.

---

## 7. Open questions

1. **Phase 1:** single-player only, or do you host multiplayer? This decides
   whether other players get their own drones later.
2. **Phase 4:** keep heading-up as the default minimap? (The mockup does.)
3. **Phase 8:** does "Public" mean friends over the internet, or just your
   own phone on mobile data?
4. **Before Phase 1:** link this chat to your PC through the Claude desktop
   app. Phases 1, 2 and 6 need your real game install and save, which this
   cloud workspace doesn't have.
