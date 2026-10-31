#!/usr/bin/env python3
"""Local-first spike: what can a script on this Mac actually collect from a Class Notebook page?

Status (2026-10-31): passed on one real typed page (whole text read from OneNote's #PageContentContainer,
checked by eye). Handwriting, pasted images and multi-box pages not yet tested.

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

Exit codes: 0 text read, no potential non-text elements detected; 4 text read, potential non-text elements
detected (inspect them); 1 no text found; 2 blocked by sign-in policy; 3 setup problem.
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

# Run inside OneNote's frame. Lists each large embedded item (images, canvases, drawings, videos, frames,
# files) with its size, position and label, and, for each place the page title appears, the chain of
# containers around it with how much text and how many embedded items each holds. That shows which
# container is the page itself (versus OneNote's menus), so collect.py can read just that part.
INSPECT_JS = """(title) => {
  const MIN = %d;
  // Actually shown (not display:none, invisible or zero-sized) and big enough to be content. Position never
  // excludes anything inside the page area: work further down, or scrolled past inside OneNote's own scroll box,
  // still counts. "Parked" items (placed entirely above or left of the frame, like the images OneNote preloads
  // at y = -1000) are skipped only in the whole-frame list.
  const shown = el => { const s = getComputedStyle(el);
                        return s.display !== "none" && s.visibility !== "hidden" && el.getClientRects().length > 0; };
  const bigEnough = el => { const r = el.getBoundingClientRect(); return r.width >= MIN && r.height >= MIN; };
  const parked = el => { const r = el.getBoundingClientRect();
                         return r.bottom + window.scrollY <= 0 || r.right + window.scrollX <= 0; };
  const media = (root, skipParked) => [...root.querySelectorAll("img, canvas, svg, video, iframe, object, embed")]
    .filter(el => !(el.tagName.toLowerCase() === "svg" && el.parentElement && el.parentElement.closest("svg"))
                  && shown(el) && bigEnough(el) && !(skipParked && parked(el)));
  const kind = {img: "image", canvas: "canvas", svg: "drawing", video: "video", iframe: "frame", object: "file", embed: "file"};
  const host = el => { try { const s = el.currentSrc || el.src || el.getAttribute("src") || "";
                             return s ? new URL(s, location.href).host : ""; } catch (e) { return ""; } };
  const items = media(document, true).map(el => { const r = el.getBoundingClientRect(); return {
    kind: kind[el.tagName.toLowerCase()], w: Math.round(r.width), h: Math.round(r.height),
    x: Math.round(r.left), y: Math.round(r.top + window.scrollY),
    label: (el.getAttribute("alt") || el.getAttribute("aria-label") || el.getAttribute("title") || "").slice(0, 40),
    src: host(el) }; });
  const chains = [];
  if (title) {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode()) && chains.length < 3) {
      if (node.nodeValue.trim() !== title) continue;
      const chain = [];
      for (let el = node.parentElement, i = 0; el && el !== document.documentElement && i < 12; el = el.parentElement, i++)
        chain.push({tag: el.tagName.toLowerCase(), id: (el.id || "").slice(0, 40),
                    cls: (typeof el.className === "string" ? el.className : "").slice(0, 50),
                    role: el.getAttribute("role") || "", chars: (el.innerText || "").trim().length, media: media(el, false).length});
      chains.push(chain);
    }
  }
  // The submission area: start at the page title that isn't in OneNote's navigation, and widen to the
  // largest container that still holds no menus, toolbars or navigation and only one copy of the title.
  const UI = '[role="navigation"],[role="tree"],[role="treeitem"],[role="listbox"],[role="menubar"],' +
             '[role="toolbar"],[role="tablist"],[role="banner"],nav,header';
  // First choice: OneNote's own page container (seen on the real page on 2026-10-31: #PageContentContainer
  // inside #WACViewPanel, role "document"). Fallback: start at a copy of the title outside the navigation and
  // widen while the container holds no menus or navigation; keep the widest result. (OneNote keeps a hidden
  // second copy of the title next to the visible one, so "the title appears only once" is not a usable test.)
  let area = document.querySelector("#PageContentContainer")
          || document.querySelector('#WACViewPanel[role="document"]')
          || document.querySelector('[role="document"]');
  let best = area ? Infinity : -1;
  if (!area && title) {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = w.nextNode())) {
      if (node.nodeValue.trim() !== title || node.parentElement.closest(UI)) continue;
      let a = node.parentElement;
      for (let up = a.parentElement; up && up !== document.body; up = up.parentElement) {
        if (up.querySelector(UI) || up.closest(UI)) break;
        a = up;
      }
      const n = (a.innerText || "").trim().length;
      if (n > best) { best = n; area = a; }
    }
  }
  const areaInfo = area ? {tag: area.tagName.toLowerCase(), id: (area.id || "").slice(0, 40),
                           cls: (typeof area.className === "string" ? area.className : "").slice(0, 50),
                           text: (area.innerText || "").trim(),
                           items: media(area, false).map(el => { const r = el.getBoundingClientRect(); return {
                             kind: kind[el.tagName.toLowerCase()], w: Math.round(r.width), h: Math.round(r.height),
                             x: Math.round(r.left), y: Math.round(r.top + window.scrollY),
                             label: (el.getAttribute("alt") || el.getAttribute("aria-label") || el.getAttribute("title") || "").slice(0, 40),
                             src: host(el) }; })} : null;
  return {items, chains, area: areaInfo};
}""" % MIN_SIDE


# Run inside OneNote's frame before reading: scroll the page from top to bottom and back, so anything OneNote
# only loads when it scrolls into view is in place. Scrolling changes nothing on the page.
SCROLL_JS = """async () => {
  const page = document.querySelector("#PageContentContainer") || document.querySelector('[role="document"]');
  if (!page) return null;
  let box = page;
  while (box && !(box.scrollHeight > box.clientHeight + 10 && /(auto|scroll)/.test(getComputedStyle(box).overflowY)))
    box = box.parentElement;
  box = box || document.scrollingElement;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const start = box.scrollTop;
  const steps = Math.min(40, Math.max(1, Math.ceil(box.scrollHeight / Math.max(200, box.clientHeight * 0.8))));
  for (let i = 1; i <= steps; i++) { box.scrollTop = Math.round(box.scrollHeight * i / steps); await sleep(250); }
  await sleep(500);
  box.scrollTop = 0;
  await sleep(500);
  return {height: box.scrollHeight, view: box.clientHeight, steps, startedAt: start};
}"""


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
            try:
                scrolled = frame.evaluate(SCROLL_JS)
            except Exception as e:
                scrolled = None
                print(f"(Couldn't scroll the page: {type(e).__name__})")
            if scrolled:
                print(f"Scrolled the page top to bottom and back before reading ({scrolled['steps']} steps, "
                      f"page {scrolled['height']}px tall, window {scrolled['view']}px).")
                try:
                    text = frame.locator("body").inner_text(timeout=5000)
                except Exception:
                    pass
            text = text.strip()
            try:
                info = frame.evaluate(INSPECT_JS, who["page"] if who else "")
            except Exception as e:
                info = None
                print(f"(Couldn't inspect the page: {type(e).__name__})")
            items = info["items"] if info else []
            media = {}
            for it in items:
                media[it["kind"]] = media.get(it["kind"], 0) + 1
            embedded = len(items)

            area = info.get("area") if info else None
            print(f"\nRESULT: text read from OneNote's frame ({name or host}): {len(text)} characters in the whole frame.")
            if area:
                print(f"Submission area found: <{area['tag']}> {area['id'] or '-'} / {area['cls'] or '-'}: "
                      f"{len(area['text'])} characters (menus and navigation left out).")
            else:
                print("Submission area not found, so the text below is the whole frame, including OneNote's menus.")
            found = ", ".join(f"{k}: {v}" for k, v in media.items()) or "none"
            print(f"Non-text elements in the whole frame (at least {MIN_SIDE}px): {found}")
            if items:
                print("  kind      size        position (x, y)   label / source")
                for it in items:
                    print(f"  {it['kind']:9} {it['w']:>4}x{it['h']:<6} ({it['x']:>5}, {it['y']:>6})   "
                          f"{it['label'] or '-'} / {it['src'] or '-'}")
            if info and info["chains"]:
                for n, chain in enumerate(info["chains"], 1):
                    print(f"\nContainers around the page title (match {n}), innermost first:")
                    print("  level tag      chars  items  id / class / role")
                    for lvl, c in enumerate(chain):
                        print(f"  {lvl:>5} {c['tag']:8} {c['chars']:>6} {c['media']:>6}  "
                              f"{c['id'] or '-'} / {c['cls'] or '-'} / {c['role'] or '-'}")

            checked = area["items"] if area else items
            where = "in the submission area" if area else "in the frame (some may be OneNote's own)"
            print("\nCompleteness: UNVERIFIED. ", end="")
            if checked:
                kinds = {}
                for it in checked:
                    kinds[it["kind"]] = kinds.get(it["kind"], 0) + 1
                print(f"Potential non-text elements detected {where}: "
                      + ", ".join(f"{k}: {v}" for k, v in kinds.items())
                      + ". Inspect their location and purpose before assuming the text is all the work.")
            else:
                print(f"No potential non-text elements detected {where}, but handwriting (ink) may not show up "
                      "as a separate element, so compare the text with the page by eye, including below the "
                      "visible area.")
            body = area["text"] if area else text
            print()
            print(body if args.full else body[:800] + ("\n… (use --full for the rest)" if len(body) > 800 else ""))
            embedded = len(checked)
            if sys.stdin.isatty():
                input("\nCompare the text above with the page in the Chrome window, then press Return to close it… ")
            return 4 if embedded else 0
        finally:
            ctx.close()


if __name__ == "__main__":
    sys.exit(main())
