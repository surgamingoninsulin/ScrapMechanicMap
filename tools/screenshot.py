"""Screenshot a page at the two sizes every Scoutbot phase is checked at.

    python tools/screenshot.py PAGE NAME --phase N [--wait-ms MS] [--ready JS]

PAGE is a URL or a path to a local .html file. Two pictures are written to
docs/phases/: phase-N-NAME-desktop.png at 1920x1080 and phase-N-NAME-phone.png
at 390x844, the phone one with touch and a mobile user agent so the page takes
its phone layout for the same reasons it would on a real one.

A page that throws is a failed check, not a picture: any uncaught error or
console error is printed and the exit status is 1, though the screenshots are
still written so there is something to look at.

This is a development tool and the only thing in the repo that needs
Playwright (pip install playwright; playwright install chromium). Nothing the
user runs imports it. WebGL is drawn by SwiftShader, Chromium's software GPU,
so it works on a machine or container with no graphics card; it is slow, which
is why --wait-ms exists.
"""

import argparse
import os
import pathlib
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, os.pardir, "docs", "phases")

VIEWS = [
    ("desktop", {"viewport": {"width": 1920, "height": 1080}}),
    ("phone", {"viewport": {"width": 390, "height": 844},
               "is_mobile": True, "has_touch": True,
               "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like "
                             "Mac OS X) AppleWebKit/605.1.15 (KHTML, like "
                             "Gecko) Version/17.0 Mobile/15E148 Safari/604.1"}),
]

CHROMIUM_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                 "--ignore-gpu-blocklist"]


def page_url(page):
    if "://" in page:
        return page
    path = pathlib.Path(page).resolve()
    if not path.is_file():
        raise SystemExit("no such page: %s" % page)
    return path.as_uri()


def shoot(url, name, phase, wait_ms, ready, chromium):
    from playwright.sync_api import sync_playwright

    os.makedirs(OUT, exist_ok=True)
    problems = []
    written = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=chromium,
                                    args=CHROMIUM_ARGS)
        try:
            for view, options in VIEWS:
                context = browser.new_context(**options)
                page = context.new_page()
                page.on("pageerror",
                        lambda e, v=view: problems.append("%s: %s" % (v, e)))
                page.on("console",
                        lambda m, v=view: problems.append(
                            "%s: console.%s %s" % (v, m.type, m.text))
                        if m.type == "error" else None)
                page.goto(url, wait_until="load", timeout=120000)
                if ready:
                    page.wait_for_function(ready, timeout=max(wait_ms, 120000))
                page.wait_for_timeout(wait_ms)
                path = os.path.join(OUT, "phase-%s-%s-%s.png"
                                    % (phase, name, view))
                page.screenshot(path=path)
                written.append(os.path.normpath(path))
                context.close()
        finally:
            browser.close()
    return written, problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("page", help="URL or local .html file")
    ap.add_argument("name", help="short name for the picture, e.g. baseline")
    ap.add_argument("--phase", required=True, help="phase number, e.g. 0")
    ap.add_argument("--wait-ms", type=int, default=1500,
                    help="settle time after load (and after --ready), "
                         "default 1500")
    ap.add_argument("--ready", help="JS expression to wait for before the "
                                    "settle time, e.g. 'window.sceneReady'")
    ap.add_argument("--chromium", default=os.environ.get("SCOUTBOT_CHROMIUM"),
                    help="Chromium executable to use instead of Playwright's "
                         "own (or set SCOUTBOT_CHROMIUM)")
    args = ap.parse_args(argv)

    try:
        written, problems = shoot(page_url(args.page), args.name, args.phase,
                                  args.wait_ms, args.ready, args.chromium)
    except ImportError:
        print("Playwright is not installed: pip install playwright && "
              "playwright install chromium", file=sys.stderr)
        return 2
    for path in written:
        print(path)
    for line in problems:
        print("ERROR " + line, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
