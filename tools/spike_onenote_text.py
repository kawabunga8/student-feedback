#!/usr/bin/env python3
"""Local-first spike: can a script on this Mac read a Class Notebook page's text?

Step 1 of the migration path in ARCHITECTURE.md ("Target"). It answers two questions:
  1. Does RCS sign-in (Conditional Access, MFA) allow an automated Chrome that you sign in to once?
  2. Can a page's text be read straight from OneNote's frame, without screenshots?

It only reads. The page is opened with action=view (read-only), nothing is typed into it, and the
text is printed in this Terminal only. Nothing is sent anywhere.

Setup (once):
    python3 -m venv ~/.venvs/student-feedback-tools
    ~/.venvs/student-feedback-tools/bin/pip install playwright
  It drives your installed Google Chrome, so no separate browser download is needed.

Run:
  1. In Chrome, open a student's notebook page (Class Notebook > student > Homework > page) and
     copy the address. It looks like https://rcschool.sharepoint.com/sites/.../Doc.aspx?sourcedoc=...
  2. From the repo folder:
       ~/.venvs/student-feedback-tools/bin/python tools/spike_onenote_text.py "<address>"
  The first run opens a separate Chrome window on the Microsoft sign-in page. Sign in there
  (including MFA), then come back to Terminal and press Return. The sign-in is kept in
  ~/Library/Application Support/student-feedback/chrome-profile, outside this repo, for next time.

Options: --full prints all the text instead of the first part; --wait N waits up to N seconds
for the page (default 60).

Exit codes: 0 text readable, 1 no text found, 2 blocked by sign-in policy, 3 setup problem.
"""
import argparse
import re
import sys
import time
from pathlib import Path

PROFILE = Path.home() / "Library" / "Application Support" / "student-feedback" / "chrome-profile"
LOGIN_HOSTS = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com")
MIN_CHARS = 200  # less than this is probably just OneNote's own buttons and menus


def read_only(url):
    """Doc.aspx accepts action=view, which opens the notebook read-only."""
    if re.search(r"[?&]action=", url):
        return re.sub(r"([?&]action=)[A-Za-z]+", r"\1view", url)
    return url + ("&" if "?" in url else "?") + "action=view"


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else "(no address)"


def frame_texts(page):
    """[(frame name, host, text)] for every frame that has readable text."""
    found = []
    for f in page.frames:
        try:
            text = f.locator("body").inner_text(timeout=2000)
        except Exception:
            continue
        found.append((f.name or "", host_of(f.url), text))
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("url", help="address of a Class Notebook page (…sharepoint.com/…/Doc.aspx?…)")
    ap.add_argument("--full", action="store_true", help="print all the text, not just the first part")
    ap.add_argument("--wait", type=int, default=60, help="seconds to wait for the page text (default 60)")
    args = ap.parse_args()

    if "sharepoint.com" not in args.url or "Doc.aspx" not in args.url:
        print("Expected a Class Notebook page address (…sharepoint.com/…/Doc.aspx?…).")
        return 3
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright isn't installed for this Python. See the setup lines at the top of this file.")
        return 3

    url = read_only(args.url)
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
            page.goto(url, wait_until="domcontentloaded")
            time.sleep(3)
            if host_of(page.url) in LOGIN_HOSTS:
                input("Sign in in the Chrome window that just opened (including MFA), "
                      "then come back here and press Return… ")
                page.goto(url, wait_until="domcontentloaded")

            print(f"Waiting up to {args.wait}s for the page text…")
            deadline = time.time() + args.wait
            best, texts = None, []
            while time.time() < deadline:
                texts = frame_texts(page)
                for _, host, text in texts:
                    if "AADSTS" in text:
                        code = re.search(r"AADSTS\d+", text).group(0)
                        print(f"\nRESULT: blocked by sign-in policy ({code}, on {host}).")
                        print("Conditional Access doesn't allow this automated Chrome. "
                              "Worth asking RCS IT, or collection stays browser-pane based.")
                        return 2
                onenote = [t for t in texts if t[0] == "WebApplicationFrame" or "officeapps" in t[1]]
                cand = max(onenote, key=lambda t: len(t[2].strip()), default=None)
                if cand and len(cand[2].strip()) >= MIN_CHARS:
                    best = cand
                    break
                time.sleep(2)

            print("\nFrames on the page (name, site, characters of text):")
            for name, host, text in texts:
                print(f"  {name or '-':22} {host:45} {len(text.strip()):>7}")

            if not best:
                print(f"\nRESULT: no page text found in OneNote's frame within {args.wait}s.")
                print("Either the page didn't finish loading (try --wait 120) or the text isn't in the "
                      "page's HTML, in which case collection needs screenshots and the local vision model.")
                return 1

            name, host, text = best
            text = text.strip()
            print(f"\nRESULT: text is readable from OneNote's frame ({name or host}): {len(text)} characters.")
            print("It includes OneNote's own menus as well as the page; collect.py will trim those.\n")
            print(text if args.full else text[:800] + ("\n… (use --full for the rest)" if len(text) > 800 else ""))
            return 0
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
