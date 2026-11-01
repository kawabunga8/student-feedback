#!/usr/bin/env python3
"""Local-first spike: what can a script on this Mac read from Teams Assignments? (read-only)

Status (2026-10-31): written, NOT yet run. The in-app browser showed that the Assignments app is an embedded frame
(assignments.edu.cloud.microsoft) inside Teams, and that it can't be opened as its own page, so this script opens
Teams, clicks the Assignments icon, and reads inside that frame. It answers:
  1. Does the automated Chrome profile (the same one the OneNote spike uses) stay signed in to Teams?
  2. Can the assignment list be read as text from the frame? What does a row look like (title, class, due date)?
  3. With --open "<part of a title>": does the roster text show each student's status (Viewed / Turned in /
     Not turned in / Returned)?

It only reads. The only clicks are the left-rail Assignments icon and, with --open, one assignment title. It never
touches Feedback, Return, Points, Student view or any edit control. Everything is printed in this Terminal only;
nothing is saved or sent anywhere. The roster contains student names, so run it where only you can see the screen.

Setup is the same as the OneNote spike (Playwright in ~/.venvs/student-feedback-tools, installed Google Chrome).
Run:
  ~/.venvs/student-feedback-tools/bin/python tools/spike_teams_assignments.py
  ~/.venvs/student-feedback-tools/bin/python tools/spike_teams_assignments.py --open "Task 4"
The first run may show a Microsoft sign-in page in the Chrome window: sign in (including MFA), come back here and
press Return. Add --full to print all the text instead of the first part.

Exit codes: 0 list read (and the roster read if --open was given); 1 nothing readable; 2 blocked by sign-in policy;
3 setup problem.
"""
import argparse
import re
import sys
import time
from pathlib import Path

PROFILE = Path.home() / "Library" / "Application Support" / "student-feedback" / "chrome-profile"
LOGIN_HOSTS = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com")
TEAMS = "https://teams.cloud.microsoft/"
FRAME_HOST = "assignments.edu.cloud.microsoft"
MIN_CHARS = 80

# Summarises the shape of the frame so selectors for the real picker can be written from facts: how many of each
# useful role/tag are present, and for the first few rows what element holds them.
SHAPE_JS = """() => {
  const count = sel => document.querySelectorAll(sel).length;
  const out = {counts: {
    link: count('a[href]'), button: count('button,[role=button]'), row: count('[role=row],tr'),
    listitem: count('[role=listitem],li'), gridcell: count('[role=gridcell],td'), heading: count('h1,h2,h3,[role=heading]')}};
  out.headings = [...document.querySelectorAll('h1,h2,h3,[role=heading]')].slice(0, 12).map(e => e.innerText.trim().slice(0, 60));
  out.links = [...document.querySelectorAll('a[href]')].slice(0, 8).map(a => ({text: a.innerText.trim().slice(0, 60),
    href: (a.getAttribute('href') || '').replace(/[?#].*/, '').slice(0, 80)}));
  return out;
}"""


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else "(no address)"


def assignments_frame(page):
    for f in page.frames:
        if FRAME_HOST in host_of(f.url):
            return f
    return None


def frame_text(frame):
    try:
        return frame.locator("body").inner_text(timeout=3000).strip()
    except Exception:
        return ""


def wait_text(page, secs, need=MIN_CHARS, label="frame", ready=None):
    """Poll until the Assignments frame has at least `need` characters, printing each change of state with the time
    it happened, so a slow or failed load shows where it stalled (no frame / frame empty / frame growing)."""
    start = time.time(); last = None
    while time.time() - start < secs:
        f = assignments_frame(page)
        t = frame_text(f) if f else ""
        state = ("no frame" if not f else f"frame, {len(t)} chars")
        if state != last:
            print(f"  [{time.time() - start:5.1f}s] {label}: {state}")
            last = state
        if f and "AADSTS" in t:
            return f, t
        if f and len(t) >= need and (ready is None or ready(t)):
            return f, t
        page.wait_for_timeout(1000)   # NOT time.sleep: Playwright only sees new frames while it is running
    f = assignments_frame(page)
    print(f"  [{secs:5.1f}s] {label}: gave up ({'frame present' if f else 'no frame'})")
    return f, (frame_text(f) if f else "")


def show(label, text, full):
    print(f"\n--- {label} ({len(text)} characters) ---")
    print(text if full or len(text) <= 1500 else text[:1500] + "\n… (use --full for the rest)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open", metavar="TEXT", help="open the first assignment whose title contains TEXT and read its roster")
    ap.add_argument("--class", dest="cls", metavar="TEXT", help="with --open: the Teams class name must contain TEXT")
    ap.add_argument("--student-view", action="store_true", help="with --open: also open the ... menu > Student view and read the instructions")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--wait", type=int, default=60)
    args = ap.parse_args()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright isn't installed for this Python. See the setup line at the top of this file.")
        return 3
    PROFILE.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        try:
            ctx = p.chromium.launch_persistent_context(
                str(PROFILE), channel="chrome", headless=False, viewport={"width": 1440, "height": 900})
        except Exception as e:
            print(f"Couldn't start Google Chrome through Playwright:\n{e}")
            return 3
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(TEAMS, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            if host_of(page.url) in LOGIN_HOSTS:
                input("Sign in in the Chrome window (including MFA), then press Return here… ")
                page.goto(TEAMS, wait_until="domcontentloaded")
            # The left rail's Assignments icon (Teams hides the rail in narrow windows, hence the 1440 width).
            clicked = False
            end = time.time() + args.wait
            while time.time() < end and not clicked:
                for loc in (page.get_by_role("button", name=re.compile(r"^Assignments")),
                            page.get_by_role("tab", name=re.compile(r"^Assignments")),
                            page.locator('[aria-label^="Assignments"]')):
                    try:
                        if loc.first.is_visible(timeout=500):
                            loc.first.click(timeout=3000)
                            clicked = True
                            break
                    except Exception:
                        pass
                if not clicked:
                    page.wait_for_timeout(2000)
            if not clicked:
                print("RESULT: couldn't find the Assignments icon in Teams' left rail within the wait.")
                print("Check the Chrome window: is Teams loaded, and is Assignments pinned in the rail?")
                return 1
            print("Clicked the left-rail Assignments icon. Waiting for the embedded Assignments frame…")
            frame, text = wait_text(page, args.wait)
            print("\nFrames on the page (site, characters of text):")
            for f in page.frames:
                print(f"  {host_of(f.url):45} {len(frame_text(f)):>7}")
            late = assignments_frame(page)          # the frame can finish loading just after the wait ends
            if late and (not frame or len(text) < MIN_CHARS):
                frame, text = late, frame_text(late)
            if "AADSTS" in text:
                code = re.search(r"AADSTS\d+", text).group(0)
                print(f"\nRESULT: blocked by sign-in policy ({code}).")
                return 2
            if not frame or len(text) < MIN_CHARS:
                print(f"\nRESULT: no assignment text found in the Assignments frame within {args.wait}s "
                      f"(frame {'found' if frame else 'not found'}). Try --wait 120.")
                return 1
            print(f"\nRESULT: assignment list text read from the frame on {host_of(frame.url)}.")
            show("Assignment list", text, args.full)
            try:
                print("\nShape of the frame (for writing selectors):", frame.evaluate(SHAPE_JS))
            except Exception as e:
                print(f"(Couldn't summarise the frame: {type(e).__name__})")
            if not args.open:
                print("\nNext: run again with --open \"<part of an assignment title>\" to read one roster.")
                return 0
            rows = frame.get_by_role("listitem")
            cands = []
            for i in range(rows.count()):
                t = rows.nth(i).inner_text(timeout=2000)
                if re.search(re.escape(args.open), t, re.I) and (not args.cls or re.search(re.escape(args.cls), t, re.I)):
                    cands.append((i, [l.strip() for l in t.splitlines() if l.strip()][:4]))
            if len(cands) != 1:
                print(f"\nRESULT: {len(cands)} assignments match title '{args.open}'"
                      + (f" and class '{args.cls}'" if args.cls else "") + "; I won't guess.")
                for i, lines in cands:
                    print("  candidate:", " | ".join(lines))
                print("Add --class \"<part of the Teams class name>\" (or a longer title) so exactly one matches.")
                return 1
            print("Opening:", " | ".join(cands[0][1]))
            rows.nth(cands[0][0]).get_by_text(re.compile(re.escape(args.open), re.I)).first.click(timeout=5000)  # opens the roster; read-only
            frame, text2 = wait_text(page, 30, label="roster", ready=lambda t: bool(re.search(r"\d+ results? found|To return \(\d+\)", t)))
            show(f"After opening '{args.open}'", text2, args.full)
            lines = [l.strip() for l in text2.splitlines()]
            statuses = {s: sum(1 for l in lines if l.lower() == s.lower()) for s in ("Viewed", "Turned in", "Not turned in", "Returned", "Returned for revision", "Excused")}
            print("\nWhole-line status counts in the roster text:", statuses)
            print("Tab labels:", [l for l in lines if re.match(r"^(To return|Returned) \(\d+\)$", l)],
                  "|", [l for l in lines if re.match(r"^\d+ results? found$", l)])
            print("Frame address now (class and assignment ids):", re.sub(r"[?#].*", "", frame.url))
            try:
                print("Shape of the frame:", frame.evaluate(SHAPE_JS))
            except Exception as e:
                print(f"(Couldn't summarise the frame: {type(e).__name__})")
            if args.student_view:
                print("\nOpening the assignment's ... menu, then Student view (read-only)…")
                try:
                    frame.get_by_role("button", name=re.compile(r"more options|more actions|^\.\.\.$|^⋯$", re.I)).first.click(timeout=5000)
                    page.wait_for_timeout(1000)
                    items = [t.strip() for t in frame.get_by_role("menuitem").all_inner_texts()]
                    print("Menu items shown:", items)
                    frame.get_by_role("menuitem", name=re.compile(r"^Student view$", re.I)).first.click(timeout=5000)
                    page.wait_for_timeout(1000)
                    frame, text3 = wait_text(page, 30, label="student view", ready=lambda t: t != text2)
                    show("Student view", text3, args.full)
                    print("Pages open:", len(ctx.pages), "(more than 1 means Student view opened a new tab)")
                    labels = ("Instructions", "Reference materials", "Rubric", "Points", "My work", "Resources", "Attachments", "Add work", "Turn in")
                    outline = [l.strip() for l in text3.splitlines() if l.strip() and (l.strip() in labels or re.match(r"^(Rubric|Reference|Attach|Resource)", l.strip(), re.I))]
                    print("Section labels found in Student view text:", outline or "none of the expected ones")
                    print("Characters in Student view:", len(text3), "| lines:", len([l for l in text3.splitlines() if l.strip()]))
                    try:
                        print("Shape of Student view:", frame.evaluate(SHAPE_JS))
                    except Exception as e:
                        print(f"(Couldn't summarise: {type(e).__name__})")
                    print("Frame address now:", re.sub(r"[?#].*", "", frame.url if frame else ""))
                except Exception as e:
                    print(f"(Couldn't open Student view: {type(e).__name__}: {str(e)[:200]})")
            print("\nCompare the text above with the Chrome window. Nothing was changed in Teams.")
            if sys.stdin.isatty():
                input("Press Return to close Chrome… ")
            return 0
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
