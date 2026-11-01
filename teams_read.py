#!/usr/bin/env python3
"""Read-only reader for Teams Assignments (PROPOSED design, first version; live behaviour checked only by
tools/spike_teams_assignments.py on 2026-11-01, one class and one assignment).

Two operations, run in the automated Chrome profile that the OneNote spike also uses:
  list                       the assignment list: title, class, due-date heading, the two (unlabelled) fractions
  read --class C --title T   one assignment, matched on class AND title (never the first partial match): its
                             Student view (instructions, reference-material names, points) and aggregate roster
                             status counts, with source references (class id, assignment id, address, read time)

Version 1 returns NO student names and no per-student statuses: only counts.

Read-only guardrails (a guardrail, not a guarantee): the only clicks are the left-rail Assignments icon, one list
row, the roster page's "..." menu button, and the menu item named exactly "Student view" (the same menu holds Edit,
Mark as inactive, Export and Delete, which are never clicked). Nothing is typed, no form is submitted, and after every
step the page is checked against what that step should show; if it differs the read stops with a plain message.

Chrome allows one process per profile, so a lock file is taken first: a second reader (or any other browser script
that takes the same lock) gets "browser profile in use" and does nothing.

Output: one JSON object on stdout. Exit codes: 0 ok; 1 other failure; 2 blocked by sign-in policy; 3 setup problem
(Playwright or Chrome missing); 5 needs sign-in (not finished in time); 6 browser profile in use; 7 page differs from
what was expected, or no single assignment matches.
"""
import argparse
import fcntl
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

APP_DATA = Path.home() / "Library" / "Application Support" / "student-feedback"
PROFILE = APP_DATA / "chrome-profile"
LOCK = APP_DATA / "browser.lock"
LOGIN_HOSTS = ("login.microsoftonline.com", "login.microsoft.com", "login.live.com")
TEAMS = "https://teams.cloud.microsoft/"
FRAME_HOST = "assignments.edu.cloud.microsoft"

EXIT = {"ok": 0, "error": 1, "blocked": 2, "setup": 3, "sign_in": 5, "busy": 6, "differs": 7}


class ReadError(Exception):
    def __init__(self, kind, message, extra=None):
        super().__init__(message)
        self.kind, self.extra = kind, extra or {}


# ---------------------------------------------------------------------------------------------------- parsing
# Pure functions on the frame's text, so they are tested without a browser.
DATE_HEAD = re.compile(r"^(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}(?:st|nd|rd|th)?(?:, \d{4})?)$")
WHEN_HEAD = re.compile(r"^(?:Today|Tomorrow|Yesterday|Next week|This week|Further out|Earlier|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|No due date)$", re.I)
FRACTION = re.compile(r"^\d+/\d+$")
INITIALS = re.compile(r"^[A-Z]{1,3}$")
TEAM = re.compile(r"^RCS\s*-\s*[A-Z0-9]+\s*-\s*.+?\[\d{4}-\d{2}\]$")


def parse_list(text):
    """Assignment rows from the list view's text. A row is: [initials] title / 'Due ...' / class / fraction(s).
    The initials line (one to three capitals, from an avatar) sits before the title and is ignored."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    out, heading = [], ""
    for i, l in enumerate(lines):
        if DATE_HEAD.match(l):
            heading = l
        if i >= 2 and l.lower().startswith("due") and i + 1 < len(lines) and TEAM.match(lines[i + 1]):
            title = lines[i - 1]
            fractions, j = [], i + 2
            while j < len(lines) and FRACTION.match(lines[j]):
                fractions.append(lines[j]); j += 1
            out.append({"title": title, "due_text": l, "due_heading": heading, "class_name": lines[i + 1], "fractions": fractions})
    return out


STATUS_KNOWN = ("Viewed", "Turned in", "Not turned in", "Returned", "Returned for revision", "Excused", "Not viewed")


def parse_roster(text):
    """Aggregate counts from the roster text, never names. Rows are read as groups of three lines after the
    'Feedback' header (initials, name, status), so a word in a name or in a tab label can't be counted as a status.
    `consistent` is False when the rows don't add up to the page's own 'N results found' line."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    tabs = {}
    for l in lines:
        m = re.match(r"^(To return|Returned) \((\d+)\)$", l)
        if m:
            tabs[m.group(1)] = int(m.group(2))
    found = next((int(m.group(1)) for l in lines for m in [re.match(r"^(\d+) results? found$", l)] if m), None)
    try:
        start = max(i for i, l in enumerate(lines) if l == "Feedback") + 1
    except ValueError:
        start = None
    end = next((i for i, l in enumerate(lines) if re.match(r"^\d+ results? found$", l)), len(lines))
    counts, rows = {}, 0
    ragged = True
    if start is not None and end > start:
        body = lines[start:end]
        ragged = len(body) % 3 != 0
        for k in range(0, len(body) - len(body) % 3, 3):
            counts[body[k + 2]] = counts.get(body[k + 2], 0) + 1
            rows += 1
    unknown = {s: n for s, n in counts.items() if s not in STATUS_KNOWN}
    consistent = (not ragged) and found is not None and rows == found and tabs.get("To return", rows) == rows
    return {"to_return": tabs.get("To return"), "returned": tabs.get("Returned"), "results_found": found,
            "rows_read": rows, "statuses": counts, "unknown_statuses": unknown, "consistent": consistent}


SECTION = ("Instructions", "Reference materials", "My work", "Points")
NOISE_FROM = re.compile(r"^Turn this doc into flashcards", re.I)    # Teams' own AI widget: not part of the assignment


def parse_student_view(text):
    """Split the Student view text into title, due line, instructions, reference-material names and points.
    Reference materials are listed by name only: nothing here opens them, so `reference_materials_read` is False."""
    raw = [l.rstrip() for l in (text or "").replace("\r", "").split("\n")]
    t = [l.strip() for l in raw]
    cut = next((i for i, l in enumerate(t) if NOISE_FROM.match(l)), len(t))
    raw, t = raw[:cut], t[:cut]
    preview = any(re.search(r"preview of what this assignment", l, re.I) for l in t)
    due_at = next((i for i, l in enumerate(t) if re.match(r"^Due\b", l)), -1)
    head_end = next((i for i, l in enumerate(t) if i > max(due_at, 0) and l == "Instructions"), -1)
    title = ""
    if due_at > 0:
        for i in range(due_at - 1, -1, -1):
            if t[i] and t[i] != "Back" and not re.search(r"preview of what this assignment", t[i], re.I):
                title = t[i]; break
    due = re.sub(r"\s*[•·]\s*Multiple submissions allowed.*$", "", t[due_at]) if due_at >= 0 else ""
    multiple = any("Multiple submissions allowed" in l for l in t[:max(head_end, 0) + 1])
    idx = {s: next((i for i, l in enumerate(t) if i > due_at and l == s), -1) for s in SECTION}

    def block(name):
        a = idx[name]
        if a < 0:
            return None
        nxt = [idx[s] for s in SECTION if idx[s] > a]
        return raw[a + 1:(min(nxt) if nxt else len(raw))]
    ins = block("Instructions")
    instructions = re.sub(r"\n{3,}", "\n\n", "\n".join(ins).strip()) if ins is not None else ""
    ref = block("Reference materials")
    refs = [l.strip() for l in (ref or []) if l.strip()][:30]
    pts = block("Points")
    points = " ".join(l.strip() for l in (pts or []) if l.strip())[:120]
    return {"title": title, "due": due, "multiple_submissions": multiple, "instructions": instructions,
            "reference_materials": refs, "reference_materials_read": False,
            "points": points, "sections_found": [s for s in SECTION if idx[s] >= 0], "is_preview": preview,
            "found": due_at >= 0 and idx["Instructions"] >= 0}


def ids_from_url(url):
    """Class id and assignment id from an Assignments frame address."""
    m = re.search(r"/classes/([0-9a-f-]{36})/(?:assignment-review|assignments)/([0-9a-f-]{36})", url or "")
    return {"class_id": m.group(1), "assignment_id": m.group(2)} if m else {"class_id": "", "assignment_id": ""}


def match_assignment(items, cls, title):
    """Exactly one list item with this class and title, or a ReadError that names the candidates."""
    hits = [x for x in items if x["class_name"].strip() == cls.strip() and x["title"].strip() == title.strip()]
    if len(hits) == 1:
        return hits[0]
    near = [x for x in items if title.strip().lower() in x["title"].lower() or x["title"].strip().lower() in title.strip().lower()]
    raise ReadError("differs", f"{len(hits)} assignments match that class and title" if hits else "no assignment matches that class and title",
                    {"candidates": [{"title": x["title"], "class_name": x["class_name"], "due_text": x["due_text"]} for x in (hits or near)][:8]})


# ---------------------------------------------------------------------------------------------------- the browser
class BrowserLock:
    """One browser script at a time on the shared Chrome profile."""
    def __enter__(self):
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        self.f = open(LOCK, "a+")
        try:
            fcntl.flock(self.f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.f.close()
            raise ReadError("busy", "Browser profile in use: another browser job (or a script you started) is using Chrome. "
                                    "Close its Chrome window or wait for it to finish, then try again.")
        self.f.seek(0); self.f.truncate(); self.f.write(f"{os.getpid()} teams_read {datetime.now().isoformat(timespec='seconds')}\n"); self.f.flush()
        return self

    def __exit__(self, *a):
        try:
            fcntl.flock(self.f, fcntl.LOCK_UN)
        finally:
            self.f.close()


def _host(url):
    m = re.match(r"https?://([^/]+)", url or "")
    return m.group(1) if m else ""


class Session:
    def __init__(self, page, wait):
        self.page, self.wait, self.log = page, wait, []

    def note(self, s):
        self.log.append(f"[{time.time() - self.t0:5.1f}s] {s}")

    def frame(self):
        for f in self.page.frames:
            if FRAME_HOST in _host(f.url):
                return f
        return None

    def text(self):
        f = self.frame()
        try:
            return f.locator("body").inner_text(timeout=3000).strip() if f else ""
        except Exception:
            return ""

    def wait_for(self, label, ready, secs=None):
        """Poll (with the page's own wait, so Playwright keeps seeing new frames) until ready(text) is true."""
        secs = secs or self.wait
        end, last = time.time() + secs, None
        while time.time() < end:
            f = self.frame(); t = self.text() if f else ""
            state = "no frame" if not f else f"frame, {len(t)} chars"
            if state != last:
                self.note(f"{label}: {state}"); last = state
            if "AADSTS" in t:
                raise ReadError("blocked", "Sign-in is blocked by RCS's policy for this automated Chrome (" +
                                re.search(r"AADSTS\d+", t).group(0) + "). Ask RCS IT, or use the paste route.")
            if f and ready(t):
                return t
            self.page.wait_for_timeout(1000)
        raise ReadError("differs", f"Teams didn't show the expected page for '{label}' within {int(secs)} s.", {"log": self.log})

    # ---- the only clicks this reader makes
    def click(self, kind, locator):
        if kind not in ("rail-assignments", "list-row", "menu-button", "menu-student-view"):
            raise ReadError("differs", f"internal: click kind '{kind}' is not allowed")
        locator.click(timeout=5000)

    def open_assignments(self):
        for loc in (self.page.get_by_role("button", name=re.compile(r"^Assignments")),
                    self.page.get_by_role("tab", name=re.compile(r"^Assignments")),
                    self.page.locator('[aria-label^="Assignments"]')):
            try:
                if loc.first.is_visible(timeout=800):
                    self.click("rail-assignments", loc.first)
                    break
            except Exception:
                continue
        else:
            raise ReadError("differs", "Couldn't find the Assignments icon in Teams' left rail (is the window wide enough, and is Assignments pinned?).")
        t = self.wait_for("assignment list", lambda t: bool(re.search(r"^Assignments\s*$", t, re.M)) and bool(parse_list(t)))
        return t

    def list_items(self):
        return parse_list(self.open_assignments())

    def open_one(self, cls, title):
        """Open the assignment whose class and title match exactly, and read its roster counts."""
        items = self.list_items()
        want = match_assignment(items, cls, title)
        f = self.frame()
        rows = f.get_by_role("listitem")
        hit = None
        for i in range(rows.count()):
            try:
                t = rows.nth(i).inner_text(timeout=2000)
            except Exception:
                continue
            lines = [l.strip() for l in t.splitlines() if l.strip()]
            if want["title"] in lines and want["class_name"] in lines:
                hit = rows.nth(i); break
        if hit is None:
            raise ReadError("differs", "The assignment was in the list text but its row couldn't be found to open.")
        self.click("list-row", hit.get_by_text(want["title"], exact=True).first)
        t = self.wait_for("roster", lambda t: want["title"] in t and bool(re.search(r"\d+ results? found", t)))
        ids = ids_from_url(self.frame().url)
        if not ids["assignment_id"] or "assignment-review" not in self.frame().url:
            raise ReadError("differs", "The roster page's address isn't the expected assignment-review address.")
        return want, t, ids

    def student_view(self, title):
        f = self.frame()
        self.click("menu-button", f.get_by_role("button", name=re.compile(r"more options|more actions|^\.\.\.$|^⋯$", re.I)).first)
        self.page.wait_for_timeout(800)
        names = [s.strip() for s in f.get_by_role("menuitem").all_inner_texts()]
        if "Student view" not in names:
            raise ReadError("differs", "The assignment's menu doesn't contain 'Student view'; menu items seen: " + "; ".join(names))
        before = len(self.page.context.pages)
        self.click("menu-student-view", f.get_by_role("menuitem", name=re.compile(r"^Student view$")).first)
        t = self.wait_for("student view", lambda t: "preview of what this assignment" in t.lower() or ("Instructions" in t and "Points" in t))
        if len(self.page.context.pages) != before:
            raise ReadError("differs", "Student view opened in a new tab, which this reader doesn't expect.")
        if not self.frame().url.rstrip("/").endswith("/preview"):
            raise ReadError("differs", "Student view's address doesn't end in /preview.")
        return t


def _launch(p, headless=False):
    try:
        return p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=headless,
                                                   viewport={"width": 1440, "height": 900})
    except Exception as e:
        msg = str(e)
        if "ProcessSingleton" in msg or "profile" in msg.lower() and "in use" in msg.lower():
            raise ReadError("busy", "Browser profile in use: Chrome already has this profile open. Close that Chrome window and try again.")
        raise ReadError("setup", f"Couldn't start Google Chrome through Playwright: {msg[:300]}")


def run(op, cls="", title="", wait=120, signin_wait=240):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise ReadError("setup", "Playwright isn't installed for this Python (see the setup lines in tools/spike_onenote_text.py).")
    PROFILE.mkdir(parents=True, exist_ok=True)
    with BrowserLock(), sync_playwright() as p:
        ctx = _launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            s = Session(page, wait); s.t0 = time.time()
            page.goto(TEAMS, wait_until="domcontentloaded")
            page.wait_for_timeout(4000)
            if _host(page.url) in LOGIN_HOSTS:
                s.note("Microsoft sign-in page shown; waiting for the teacher to sign in in the Chrome window")
                end = time.time() + signin_wait
                while _host(page.url) in LOGIN_HOSTS and time.time() < end:
                    page.wait_for_timeout(2000)
                if _host(page.url) in LOGIN_HOSTS:
                    raise ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then resume the job.")
                page.goto(TEAMS, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
            now = datetime.now().astimezone().isoformat(timespec="seconds")
            if op == "list":
                items = s.list_items()
                return {"op": "list", "read_at": now, "source": {"url": FRAME_HOST, "app": "Teams Assignments"},
                        "assignments": items, "log": s.log}
            want, roster_text, ids = s.open_one(cls, title)
            roster = parse_roster(roster_text)
            roster_url = re.sub(r"[?#].*", "", s.frame().url)
            sv_text = s.student_view(want["title"])
            sv = parse_student_view(sv_text)
            ids2 = ids_from_url(s.frame().url)
            if ids2 != ids:
                raise ReadError("differs", "The roster and Student view addresses name different assignments; nothing was returned.")
            if not sv["found"] or sv["title"] != want["title"]:
                raise ReadError("differs", "Student view didn't show the expected title and an Instructions section.")
            return {"op": "read", "read_at": now,
                    "source": {**ids, "url": roster_url, "student_view_url": re.sub(r"[?#].*", "", s.frame().url),
                               "teams_class": want["class_name"], "list_title": want["title"], "read_at": now},
                    "list_row": want, "student_view": sv, "roster_counts": roster, "log": s.log}
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("op", choices=["list", "read"])
    ap.add_argument("--class", dest="cls", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--wait", type=int, default=120)
    ap.add_argument("--signin-wait", type=int, default=240)
    a = ap.parse_args()
    try:
        if a.op == "read" and not (a.cls and a.title):
            raise ReadError("error", "read needs --class and --title")
        out = run(a.op, a.cls, a.title, a.wait, a.signin_wait)
        out["ok"] = True
        print(json.dumps(out, ensure_ascii=False))
        return EXIT["ok"]
    except ReadError as e:
        print(json.dumps({"ok": False, "kind": e.kind, "error": str(e), **e.extra}, ensure_ascii=False))
        return EXIT.get(e.kind, 1)
    except Exception as e:
        print(json.dumps({"ok": False, "kind": "error", "error": f"{type(e).__name__}: {str(e)[:300]}"}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
