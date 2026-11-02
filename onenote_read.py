#!/usr/bin/env python3
"""Read-only collector for ONE typed Class Notebook page (PROTOTYPE, version 1).

What it does: opens the page you give it (read-only: Doc.aspx with action=view) in the automated Chrome profile,
reads the text of OneNote's own page area, and reports what it could not read. That is all.

  collect --url 'https://….sharepoint.com/…/Doc.aspx?…'

Scope of version 1 (it grows from here, one verified step at a time):
  - ONE page per run, addressed by its URL. Typed text only. No clicks, no typing: the only things it does to the page
    are open it and scroll it top to bottom and back, so text that loads lazily is in place.
  - If OneNote's page area (#PageContentContainer / role "document") is not found it STOPS and returns nothing: the
    whole-frame fallback of the spike would include OneNote's menus, which must never become "student work".
  - Completeness is always reported as UNVERIFIED. Handwriting (ink) may not appear in the text at all, and pasted
    images, drawings, embedded files and frames are listed (kind, size, label) but are not read. Compare with the page.
  - The text it returns is student work: it goes to the assignment's own Assessment folder through the app's job queue
    and is never printed in logs or error messages.

How the page text is read was proved on one real typed page by tools/spike_onenote_text.py (2026-10-31); the page area
logic and scrolling below are that spike's, copied here. Handwriting, images and multi-box pages are not yet tested.

Chrome allows one process per profile, so the same lock as teams_read.py is taken first ("browser profile in use").

Output: one JSON object on stdout. Exit codes are teams_read.py's: 0 ok; 1 other failure; 2 blocked by sign-in policy;
3 setup problem; 5 needs sign-in; 6 browser profile in use; 7 page differs from what was expected.
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime

import teams_read as T

MIN_CHARS = 200          # less than this is probably just OneNote's own buttons and menus
MIN_SIDE = 48            # px: smaller images and drawings are toolbar icons, not student content
ONENOTE_HOST = re.compile(r"(^|\.)sharepoint\.com$", re.I)


# ---------------------------------------------------------------------------------------------------- pure functions
def read_only(url):
    """Doc.aspx accepts action=view, which opens the notebook read-only."""
    if re.search(r"[?&]action=", url):
        return re.sub(r"([?&]action=)[A-Za-z]+", r"\1view", url)
    return url + ("&" if "?" in url else "?") + "action=view"


def check_url(url):
    """Only a Class Notebook page address is accepted: https, a sharepoint.com host, Doc.aspx. Raises ReadError otherwise,
    so nothing else is ever opened by this reader."""
    p = urllib.parse.urlsplit((url or "").strip())
    if p.scheme != "https" or not ONENOTE_HOST.search(p.hostname or "") or not p.path.lower().endswith("/doc.aspx"):
        raise T.ReadError("error", "That doesn't look like a Class Notebook page address (https://….sharepoint.com/…/Doc.aspx?…).")
    return url.strip()


def page_identity(url):
    """Which student section and page the address points at, from its wd=target(...) part, if present."""
    wd = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query).get("wd", [""])[0]
    m = re.match(r"target\((.*)\)$", wd)
    if not m:
        return None
    parts = [urllib.parse.unquote(p.split("|")[0]).removesuffix(".one") for p in m.group(1).split("/") if p]
    if len(parts) < 2:
        return None
    return {"section": " > ".join(parts[:-1]), "page": parts[-1], "student_hint": parts[0] if len(parts) >= 3 else ""}


def clean_text(text):
    """Trailing spaces off each line, runs of blank lines collapsed to one blank line; wording is not touched."""
    lines = [l.rstrip() for l in (text or "").replace("\r", "").split("\n")]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def summarise_items(items):
    """{kind: count} for the non-text elements found."""
    out = {}
    for it in items or []:
        out[it["kind"]] = out.get(it["kind"], 0) + 1
    return out


def completeness_note(items, area_found):
    """The honest statement about what was and was not read. Never says 'complete'."""
    kinds = summarise_items(items)
    base = "Completeness is UNVERIFIED: compare the text with the page, including below the visible area. "
    if kinds:
        return (base + "Not read (images, drawings, files or frames on the page): " +
                ", ".join(f"{k}: {n}" for k, n in kinds.items()) + ".")
    return (base + "No images or drawings were detected, but handwriting (ink) may not show up as a separate element or as text, "
            "so a page with handwriting needs the screenshot route.")


# ---------------------------------------------------------------------------------------------------- in the page
# Copied from tools/spike_onenote_text.py (verified on one real page, 2026-10-31).
INSPECT_JS = """() => {
  const MIN = %d;
  const shown = el => { const s = getComputedStyle(el);
                        return s.display !== "none" && s.visibility !== "hidden" && el.getClientRects().length > 0; };
  const bigEnough = el => { const r = el.getBoundingClientRect(); return r.width >= MIN && r.height >= MIN; };
  const media = root => [...root.querySelectorAll("img, canvas, svg, video, iframe, object, embed")]
    .filter(el => !(el.tagName.toLowerCase() === "svg" && el.parentElement && el.parentElement.closest("svg")) && shown(el) && bigEnough(el));
  const kind = {img: "image", canvas: "canvas", svg: "drawing", video: "video", iframe: "frame", object: "file", embed: "file"};
  const area = document.querySelector("#PageContentContainer")
            || document.querySelector('#WACViewPanel[role="document"]')
            || document.querySelector('[role="document"]');
  if (!area) return {area: null};
  return {area: {id: (area.id || "").slice(0, 40), text: (area.innerText || "").trim(),
                 items: media(area).map(el => { const r = el.getBoundingClientRect(); return {
                   kind: kind[el.tagName.toLowerCase()], w: Math.round(r.width), h: Math.round(r.height),
                   label: (el.getAttribute("alt") || el.getAttribute("aria-label") || el.getAttribute("title") || "").slice(0, 40)}; })}};
}""" % MIN_SIDE

SCROLL_JS = """async () => {
  const page = document.querySelector("#PageContentContainer") || document.querySelector('[role="document"]');
  if (!page) return null;
  let box = page;
  while (box && !(box.scrollHeight > box.clientHeight + 10 && /(auto|scroll)/.test(getComputedStyle(box).overflowY)))
    box = box.parentElement;
  box = box || document.scrollingElement;
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const steps = Math.min(40, Math.max(1, Math.ceil(box.scrollHeight / Math.max(200, box.clientHeight * 0.8))));
  for (let i = 1; i <= steps; i++) { box.scrollTop = Math.round(box.scrollHeight * i / steps); await sleep(250); }
  await sleep(500);
  box.scrollTop = 0;
  await sleep(500);
  return {steps};
}"""


def _frame_text(f):
    try:
        return f.locator("body").inner_text(timeout=2000)
    except Exception:
        return ""


def _onenote_frame(page):
    """The frame OneNote draws the page in (named WebApplicationFrame, or served from an officeapps host) with the most text."""
    best, size = None, 0
    for f in page.frames:
        host = T._host(f.url)
        if f.name == "WebApplicationFrame" or "officeapps" in host:
            n = len(_frame_text(f).strip())
            if n > size:
                best, size = f, n
    return best, size


def run(url, wait=60, signin_wait=240):
    check_url(url)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise T.ReadError("setup", "Playwright isn't installed for this Python (see the setup lines in tools/spike_onenote_text.py).")
    target = read_only(url.strip())
    who = page_identity(target)
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    log, t0 = [], time.time()
    note = lambda s: log.append(f"[{time.time() - t0:5.1f}s] {s}")
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            page.goto(target, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            if T._host(page.url) in T.LOGIN_HOSTS:
                note("Microsoft sign-in page shown; waiting for the teacher to sign in")
                end = time.time() + signin_wait
                while T._host(page.url) in T.LOGIN_HOSTS and time.time() < end:
                    page.wait_for_timeout(2000)
                if T._host(page.url) in T.LOGIN_HOSTS:
                    raise T.ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then resume the job.")
                page.goto(target, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
            if not ONENOTE_HOST.search(T._host(page.url)):
                raise T.ReadError("differs", "The browser ended up on a different site than the notebook page; nothing was read.")
            frame, end = None, time.time() + wait
            while time.time() < end:
                for f in page.frames:
                    txt = _frame_text(f)
                    if "AADSTS" in txt:
                        raise T.ReadError("blocked", "Sign-in is blocked by RCS's policy for this automated Chrome (" +
                                          re.search(r"AADSTS\d+", txt).group(0) + "). Ask RCS IT, or use the screenshot route.")
                f, n = _onenote_frame(page)
                if f is not None and n >= MIN_CHARS:
                    frame = f
                    break
                page.wait_for_timeout(2000)
            if frame is None:
                raise T.ReadError("differs", f"No page text appeared in OneNote's frame within {wait} s (still loading, an empty page, "
                                             "or text that isn't in the page's HTML, which needs the screenshot route). Nothing was collected.",
                                  {"log": log})
            note("OneNote frame found")
            try:
                frame.evaluate(SCROLL_JS)
            except Exception as e:
                note("couldn't scroll: " + type(e).__name__)
            info = frame.evaluate(INSPECT_JS)
            area = (info or {}).get("area")
            if not area or not area.get("text"):
                raise T.ReadError("differs", "OneNote's page area wasn't found (the frame text would include menus), so nothing was "
                                             "collected. Use the screenshot route for this page.", {"log": log})
            text = clean_text(area["text"])
            items = area.get("items", [])
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            note(f"read {len(text)} characters; {len(items)} non-text element(s)")
            return {"op": "collect", "read_at": now,
                    "source": {"url": target, "section": (who or {}).get("section", ""), "page": (who or {}).get("page", ""),
                               "student_hint": (who or {}).get("student_hint", ""), "read_at": now},
                    "page": {"text": text, "chars": len(text), "area": area.get("id") or "page area"},
                    "non_text": items, "non_text_counts": summarise_items(items),
                    "completeness": "unverified", "completeness_note": completeness_note(items, True),
                    "log": log}
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("op", choices=["collect"])
    ap.add_argument("--url", required=True)
    ap.add_argument("--wait", type=int, default=60)
    ap.add_argument("--signin-wait", type=int, default=240)
    a = ap.parse_args()
    try:
        out = run(a.url, a.wait, a.signin_wait)
        out["ok"] = True
        print(json.dumps(out, ensure_ascii=False))
        return T.EXIT["ok"]
    except T.ReadError as e:
        print(json.dumps({"ok": False, "kind": e.kind, "error": str(e), **e.extra}, ensure_ascii=False))
        return T.EXIT.get(e.kind, 1)
    except Exception as e:
        print(json.dumps({"ok": False, "kind": "error", "error": f"{type(e).__name__}: {str(e)[:300]}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
