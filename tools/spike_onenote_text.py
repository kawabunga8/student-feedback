#!/usr/bin/env python3
"""Local-first spike: what can a script on this Mac actually collect from a Class Notebook page?

Status (2026-10-31): written, but NOT yet run against a real OneNote page. Its results are unproven.

Step 1 of the build order in WORKFLOW.md. It answers:
  1. Does RCS sign-in (Conditional Access, MFA) allow an automated Chrome that you sign in to once?
  2. Can a page's text be read straight from OneNote's frame, without screenshots?
  3. What else is on the page that the text doesn't capture (images, canvases, drawings, embedded files)?

It never proves the text is complete: handwriting (ink) may not show up as a separate element at all. So it
always reports completeness as unverified, says why, and keeps the page open so you can compare by eye.

It only reads. The page is opened with action=view (read-only), nothing is typed into it, and the text is
printed in this Terminal only. Nothing is sent anywhere.

Try it on several kinds of page: typed text only, a page with handwriting (ink), one with a pasted image,
and one with more than one text box.

Setup (once):
    python3 -m venv ~/.venvs/student-feedback-tools
    ~/.venvs/student-feedback-tools/bin/pip install playwright
  It drives your installed Google Chrome, so no separate browser download is needed.

Run:
  1. In Chrome, open a student's notebook page (Class Notebook > student > Homework > page) and copy the
     address. It looks like https://rcschool.sharepoint.com/sites/.../Doc.aspx?sourcedoc=...
  2. From the repo folder, with the address in single quotes:
       ~/.venvs/student-feedback-tools/bin/python tools/spike_onenote_text.py '<address>'
  The first run opens a separate Chrome window on the Microsoft sign-in page. Sign in there (including
  MFA), then come back to Terminal and press Return. The sign-in is kept in
  ~/Library/Application Support/student-feedback/chrome-profile, outside this repo, for next time.

Options: --full prints all the text instead of the first part; --wait N waits up to N seconds for the
page (default 60).

Exit codes: 0 text read, no large embedded items found; 4 text read, but the page has embedded items the
text doesn't capture; 1 no text found; 2 blocked by sign-in policy; 3 setup problem.
"""
import argparse
import re
import sys
import time
import urllib.parse
from pathlib import Path

PROFILE = Path.home() / "Library" / "Application Support" / "student-feedback" / "chrome-profile"
LOGIN_HOSTS = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com")
MIN_CHARS = 200  # less than this is probably just OneNote's own buttons and menus
MIN_SIDE = 48    # px: smaller images and drawings are toolbar icons, not student content

# Run inside OneNote's frame: count large embedded items whose content the page text can't include.
MEDIA_JS = """() => {
  const out = {images: 0, canvases: 0, drawings: 0, videos: 0, frames: 0, files: 0};
  const kind = {img: "images", canvas: "canvases", svg: "drawings", video: "videos", iframe: "frames",
                object: "files", embed: "files"};
  for (const el of document.querySelectorAll("img, canvas, svg, video, iframe, object, embed")) {
    const tag = el.tagName.toLowerCase();
    if (tag === "svg" && el.parentElement && el.parentElement.closest("svg")) continue;  // part of a larger drawing
    const r = el.getBoundingClientRect();
    if (r.width < %d || r.height < %d) continue;
    out[kind[tag]] += 1;
  }
  return out;
}""" % (MIN_SIDE, MIN_SIDE)


def read_only(url):
    """Doc.aspx accepts action=view, which opens the notebook read-only."""
    if re.search(r"[?&]action=", url):
        return re.sub(r"([?&]action=)[A-Za-z]+", r"\1view", url)
    return url + ("&" if "?" in url else "?") + "action=view"


def page_identity(url):
    """Which section and page the address points at, from its wd=target(...) part, if present."""
    wd = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("wd", [""])[0]
    m = re.match(r"target\((.*)\)$", wd)
    if not m:
        return None
    parts = [p.split("|")[0].removesuffix(".one") for p in m.group(1).split("/") if p]
    if len(parts) < 2:
        return None
    return {"section": " > ".join(parts[:-1]), "page": parts[-1]}  # e.g. "Student > Homework", "Stage 2"


def host_of(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else "(no address)"


def frame_texts(page):
    """[(frame, name, host, text)] for every frame that has readable text."""
    found = []
    for f in page.frames:
        try:
            text = f.locator("body").inner_text(timeout=2000)
        except Exception:
            continue
        found.append((f, f.name or "", host_of(f.url), text))
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
    who = page_identity(url)
    if who:
        print(f"Address points at section: {who['section']}  |  page: {who['page']}")
        print("Check the Chrome window shows that same student and page.\n")
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
                for _, _, host, text in texts:
                    if "AADSTS" in text:
                        code = re.search(r"AADSTS\d+", text).group(0)
                        print(f"\nRESULT: blocked by sign-in policy ({code}, on {host}).")
                        print("Conditional Access doesn't allow this automated Chrome. "
                              "Worth asking RCS IT, or collection stays browser-pane based.")
                        return 2
                onenote = [t for t in texts if t[1] == "WebApplicationFrame" or "officeapps" in t[2]]
                cand = max(onenote, key=lambda t: len(t[3].strip()), default=None)
                if cand and len(cand[3].strip()) >= MIN_CHARS:
                    best = cand
                    break
                time.sleep(2)

            print("\nFrames on the page (name, site, characters of text):")
            for _, name, host, text in texts:
                print(f"  {name or '-':22} {host:45} {len(text.strip()):>7}")

            if not best:
                print(f"\nRESULT: no page text found in OneNote's frame within {args.wait}s.")
                print("Either the page didn't finish loading (try --wait 120), the page is empty, or its text "
                      "isn't in the page's HTML, in which case collection needs the local vision model.")
                return 1

            frame, name, host, text = best
            text = text.strip()
            try:
                media = frame.evaluate(MEDIA_JS)
            except Exception as e:
                media = None
                print(f"(Couldn't count embedded items: {type(e).__name__})")
            embedded = sum(media.values()) if media else 0

            print(f"\nRESULT: text read from OneNote's frame ({name or host}): {len(text)} characters.")
            print("It includes OneNote's own menus as well as the page; collect.py will trim those.")
            if media:
                found = ", ".join(f"{k}: {v}" for k, v in media.items() if v) or "none"
                print(f"Large embedded items on the page (at least {MIN_SIDE}px): {found}")
            print("Completeness: UNVERIFIED. ", end="")
            if embedded:
                print(f"The page has {embedded} embedded item(s) whose content isn't in the text. "
                      "Those need the vision model or a visual check.")
            else:
                print("No large images or canvases were found, but handwriting (ink) may not show up as a "
                      "separate element, so compare the text with the page by eye.")
            print()
            print(text if args.full else text[:800] + ("\n… (use --full for the rest)" if len(text) > 800 else ""))
            if sys.stdin.isatty():
                input("\nCompare the text above with the page in the Chrome window, then press Return to close it… ")
            return 4 if embedded else 0
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
