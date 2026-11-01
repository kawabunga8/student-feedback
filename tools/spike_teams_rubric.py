#!/usr/bin/env python3
"""READ-ONLY SPIKE: what does Teams show when "View rubric" is opened on a Student view?  (Not run yet.)

It uses the same automated Chrome profile and the same shared browser lock as the app's Teams reader, so it will say
"browser profile in use" if the app or another script has Chrome open (stop the app's Teams read first).

What it does, in order, stopping at the first thing that differs from what it expects:
  1. Open the Assignments list, open ONE assignment matched on class AND exact title, open its Student view
     (the same steps and checks as the reader).
  2. Find "View rubric" on that page. There must be exactly ONE control with that exact name; otherwise it stops.
  3. Click it ONCE. That is the only extra click this spike makes. Nothing is typed, nothing is submitted.
  4. Watch what happened: a dialog or panel in the same frame, a new browser tab (stop), or the address changing (reported).
  5. Print the rubric's text (line by line) and, if this Playwright can, its accessibility outline, plus a few structure counts.
     Rubric descriptors are the teacher's own wording, not student data, but nothing from the roster is printed.
  6. Close the whole browser WITHOUT clicking Close, so nothing in Teams is touched.

Usage (same Python as the other spikes):
  ~/.venvs/student-feedback-tools/bin/python tools/spike_teams_rubric.py --class "RCS - … [YYYY-YY]" --title "Exact title"
Add --out FILE to also save the printed report (it is written next to your other app data, not into the repo).
Exit codes follow teams_read.py (0 ok, 5 sign-in, 6 profile in use, 7 page differs).
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import teams_read as T          # noqa: E402


def say(s=""):
    print(s, flush=True)


def numbered(text):
    return "\n".join(f"{i + 1:3d} | {l}" for i, l in enumerate(text.splitlines()))


def snapshot_names(loc):
    try:
        return loc.aria_snapshot(timeout=5000)
    except Exception as e:
        return f"(accessibility outline not available: {type(e).__name__})"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--wait", type=int, default=120)
    ap.add_argument("--signin-wait", type=int, default=240)
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    report = []
    orig_say = say

    def out(s=""):
        report.append(s); orig_say(s)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        out("Playwright isn't installed for this Python."); return T.EXIT["setup"]
    try:
        T.PROFILE.mkdir(parents=True, exist_ok=True)
        with T.BrowserLock(), sync_playwright() as p:
            ctx = T._launch(p)
            try:
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                s = T.Session(page, a.wait); s.t0 = time.time()
                page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(4000)
                if T._host(page.url) in T.LOGIN_HOSTS:
                    out("Sign in in the Chrome window; waiting…")
                    end = time.time() + a.signin_wait
                    while T._host(page.url) in T.LOGIN_HOSTS and time.time() < end:
                        page.wait_for_timeout(2000)
                    if T._host(page.url) in T.LOGIN_HOSTS:
                        raise T.ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then run again.")
                    page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(3000)
                want, roster_text, ids = s.open_one(a.cls, a.title)
                s.student_view(want["title"])
                sv = T.parse_student_view(s.text())
                out(f"Opened Student view of one assignment (title matched exactly). Marker in text: {sv['rubric_present']}; "
                    f"found by controls: {s.rubric_probe}")
                f = s.frame()
                before_pages, before_url = len(ctx.pages), T.url_shape(f.url)

                # --- the one extra click -------------------------------------------------------------------
                btns = []
                for role in ("button", "link"):
                    btns += [(role, b) for b in f.get_by_role(role, name=re.compile(r"^\s*View rubric\s*$", re.I)).all()]
                if len(btns) != 1:
                    raise T.ReadError("differs", f"Expected exactly one 'View rubric' control, found {len(btns)} "
                                                 f"(roles: {[r for r, _ in btns]}). Nothing was clicked.")
                role, btn = btns[0]
                out(f"Found exactly one 'View rubric' {role}. Clicking it once.")
                btn.click(timeout=5000)

                # --- watch what happened -------------------------------------------------------------------
                end, seen = time.time() + 20, None
                dialog = None
                while time.time() < end:
                    page.wait_for_timeout(1000)
                    if len(ctx.pages) != before_pages:
                        raise T.ReadError("differs", "Clicking View rubric opened a new browser tab. Stopping; nothing else was clicked.")
                    f = s.frame()
                    for sel in ('[role="dialog"]', '[role="complementary"]', '[aria-modal="true"]'):
                        loc = f.locator(sel)
                        if loc.count():
                            dialog = loc.first; break
                    if dialog is not None:
                        break
                after_url = T.url_shape(f.url)
                out(f"Address shape before: {before_url}\nAddress shape after:  {after_url}"
                    + ("   (CHANGED)" if before_url != after_url else ""))
                if dialog is None:
                    body = s.text()
                    out("No dialog or side panel was found in the frame. Page text changed? "
                        + ("yes" if re.search("emerging|extending|proficient", body, re.I) else "no sign of rubric levels in the page text"))
                    out("Whole-page text now (for a look, nothing was clicked after the one click):")
                    out(numbered(body[:6000]))
                    raise T.ReadError("differs", "No rubric dialog or panel appeared where expected.")
                txt = dialog.inner_text(timeout=5000)
                out("\n=== RUBRIC TEXT (line by line) ===")
                out(numbered(txt))
                out("\n=== STRUCTURE ===")
                for role_ in ("table", "grid", "row", "gridcell", "cell", "columnheader", "rowheader", "heading", "tab", "button"):
                    try:
                        out(f"{role_:12s} {dialog.get_by_role(role_).count()}")
                    except Exception:
                        pass
                levels = [l for l in ("Emerging", "Developing", "Proficient", "Extending") if re.search(l, txt, re.I)]
                out(f"Level words seen: {levels}   characters: {len(txt)}   lines: {len(txt.splitlines())}")
                out("\n=== ACCESSIBILITY OUTLINE (top of dialog) ===")
                out(snapshot_names(dialog)[:6000])
                out("\nDone. Closing the browser without clicking anything else.")
            finally:
                ctx.close()
        if a.out:
            Path(a.out).expanduser().write_text("\n".join(report) + "\n")
            orig_say(f"(report saved to {a.out})")
        return T.EXIT["ok"]
    except T.ReadError as e:
        out(f"STOPPED ({e.kind}): {e}")
        for l in e.extra.get("log", [])[-12:]:
            out("  " + l)
        return T.EXIT.get(e.kind, 1)


if __name__ == "__main__":
    sys.exit(main())
