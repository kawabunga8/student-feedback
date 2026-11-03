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


RUBRIC_LEVELS = ("Emerging", "Developing", "Proficient", "Extending")


def validate_rubric(raw):
    """Check the structure pulled from the View rubric dialog. Returns (rubric, note): the rubric when every criterion has
    exactly the four expected levels, each with its own descriptor, otherwise (None, why). Nothing is repaired or guessed:
    a rubric that doesn't fit stays 'present, not read'. Descriptors are kept exactly as Teams showed them."""
    try:
        title = re.sub(r"\s+", " ", (raw.get("title") or "")).strip()
        crits = raw.get("criteria") or []
    except AttributeError:
        return None, "the rubric dialog gave no structure"
    if not title:
        return None, "the rubric dialog had no title"
    if not crits:
        return None, "the rubric dialog had no criteria lists"
    out, seen = [], set()
    for c in crits:
        name = re.sub(r"\s+", " ", c.get("name") or "").strip()
        if not name or name.lower() in seen:
            return None, "a criterion had no name or a repeated name"
        seen.add(name.lower())
        lead = re.sub(r"\s+", " ", c.get("heading") or "").strip()
        if lead and lead != name:
            return None, f"criterion '{name}' didn't match the heading above it ('{lead[:40]}')"
        levels = []
        for o in c.get("levels") or []:
            lv, d = re.sub(r"\s+", " ", o.get("level") or "").strip(), (o.get("descriptor") or "").strip()
            if not lv or not d:
                return None, f"criterion '{name}' had a level without a name or without a descriptor"
            levels.append({"level": lv, "descriptor": d})
        got = sorted(x["level"].lower() for x in levels)
        if got != sorted(l.lower() for l in RUBRIC_LEVELS):
            return None, f"criterion '{name}' has levels {[x['level'] for x in levels]}, not the expected four ({', '.join(RUBRIC_LEVELS)})"
        out.append({"name": name, "levels": levels})
    return {"title": title, "criteria": out, "source": "View rubric dialog"}, ""


def apply_rubric_probe(sv, probe):
    """Combine what the page TEXT showed with what the page's CONTROLS showed (a button's name may not be in the text, or may
    load a moment later). Controls named exactly "View rubric" / "Rubric" count as the marker; anything looser is only reported."""
    probe = probe or {}
    names = [n for n in probe.get("control_names", []) if n]
    exact = [n for n in names if re.match(r"^\s*(view\s+)?rubric\s*$", n, re.I)]
    sv = dict(sv)
    if exact and not sv.get("rubric_present"):
        sv["rubric_present"] = True
        sv["rubric_found_by"] = "page control"
    elif sv.get("rubric_present"):
        sv["rubric_found_by"] = "page text"
    if not sv.get("rubric_present") and (names or probe.get("text_lines")):
        sv["rubric_note"] = ("Teams' page had " + str(len(names)) + " control(s) and " + str(len(probe.get("text_lines", []))) +
                             " text line(s) mentioning \u201crubric\u201d, but none was exactly \u201cView rubric\u201d: " +
                             "; ".join((names + probe.get("text_lines", []))[:5]))
    return sv


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


def parse_roster_students(text):
    """Per-student status from the roster text: (name, status) read from the same three-line groups as parse_roster.
    Returned only when the rows add up to the page's own 'N results found' line, so a partly loaded list never passes as
    the whole class. These are names: the caller keeps them in the assignment's own Assessment folder, never in the journal."""
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    found = next((int(m.group(1)) for l in lines for m in [re.match(r"^(\d+) results? found$", l)] if m), None)
    try:
        start = max(i for i, l in enumerate(lines) if l == "Feedback") + 1
    except ValueError:
        return {"complete": False, "students": [], "why": "the roster's column headings weren't found"}
    end = next((i for i, l in enumerate(lines) if re.match(r"^\d+ results? found$", l)), len(lines))
    body = lines[start:end]
    if len(body) % 3:
        return {"complete": False, "students": [], "why": "the roster rows don't come in groups of three lines"}
    rows = [{"name": body[k + 1], "status": body[k + 2]} for k in range(0, len(body), 3)]
    if found is None or len(rows) != found:
        return {"complete": False, "students": [], "why": f"{len(rows)} rows were read but the page says {found} results"}
    names = [r["name"].lower() for r in rows]
    if len(set(names)) != len(names):
        return {"complete": False, "students": [], "why": "two students have the same name on the roster"}
    return {"complete": True, "students": rows, "why": ""}


SECTION = ("Instructions", "Reference materials", "My work", "Points")
RUBRIC_BUTTON = re.compile(r"^View rubric$", re.I)   # Teams' button saying a rubric is attached (the rubric text is NOT on this page)
RUBRIC_HEAD = re.compile(r"^Rubric$", re.I)          # on its own this could be the teacher's own word, so it only counts next to the button
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
    def strip_marker(lines):
        """Remove Teams' marker (a 'View rubric' button, with a 'Rubric' heading just before it) from the END of a block.
        Returns (lines, found). A teacher's own word 'Rubric', or 'rubric' inside a sentence, is never touched."""
        lines = list(lines)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines and RUBRIC_BUTTON.match(lines[-1].strip()):
            lines.pop()
            while lines and not lines[-1].strip():
                lines.pop()
            if lines and RUBRIC_HEAD.match(lines[-1].strip()):
                lines.pop()
            return lines, True
        return lines, False

    def clean(lines):
        """For the short blocks after the instructions: drop the marker wherever it sits in them."""
        lines = [l for l in (lines or [])]
        has = any(RUBRIC_BUTTON.match(l.strip()) for l in lines)
        if not has:
            return lines, False
        out = [l for k, l in enumerate(lines) if not RUBRIC_BUTTON.match(l.strip()) and
               not (RUBRIC_HEAD.match(l.strip()) and k + 1 < len(lines) and RUBRIC_BUTTON.match(lines[k + 1].strip()))]
        return out, True
    ins = block("Instructions")
    rubric = False
    if ins is not None:
        ins, rubric = strip_marker(ins)
    instructions = re.sub(r"\n{3,}", "\n\n", "\n".join(ins).strip()) if ins is not None else ""
    ref, r1 = clean(block("Reference materials"))
    refs = [l.strip() for l in ref if l.strip()][:30]
    pts, r2 = clean(block("Points"))
    points = " ".join(l.strip() for l in pts if l.strip())[:120]
    _, r3 = clean(block("My work"))
    rubric = rubric or r1 or r2 or r3
    return {"title": title, "due": due, "multiple_submissions": multiple, "instructions": instructions,
            "reference_materials": refs, "reference_materials_read": False,
            "rubric_present": rubric, "rubric_read": False,       # presence only: the descriptors are behind "View rubric" and are not read yet
            "points": points, "sections_found": [s for s in SECTION if idx[s] >= 0], "is_preview": preview,
            "found": due_at >= 0 and idx["Instructions"] >= 0}


def url_path(url):
    """The path of an address without its ?query or #fragment, and without a trailing slash."""
    return re.split(r"[?#]", url or "", 1)[0].rstrip("/")


def is_preview_url(url):
    return url_path(url).endswith("/preview")


def is_review_url(url):
    return "/assignment-review/" in url_path(url) + "/"


def url_shape(url):
    """An address with ids masked and the query dropped, safe to show in an error or log."""
    path = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<id>", url_path(url))
    path = re.sub(r"^https?://[^/]+", "", path)
    return path + (" (+query)" if "?" in (url or "") else "") + (" (+fragment)" if "#" in (url or "") else "")


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
        self.t0 = time.time()         # callers that time a whole run reset it; note() needs it either way
        self.rubric_wait = 15          # seconds to wait for the rubric dialog after the one click

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
        if kind not in ("rail-assignments", "list-row", "menu-button", "menu-student-view", "view-rubric"):
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
        # The text can appear before the frame's address settles (the list page's text may still be on screen), so
        # wait on the address too, then re-read the text so counts come from the settled page.
        end = time.time() + 20
        while time.time() < end and not is_review_url(self.frame().url):
            self.page.wait_for_timeout(500)
        url = self.frame().url
        self.note("roster address shape: " + url_shape(url))
        ids = ids_from_url(url)
        if not ids["assignment_id"] or not is_review_url(url):
            raise ReadError("differs", "The roster page's address isn't the expected assignment-review address (shape seen: " +
                            url_shape(url) + ").", {"log": self.log})
        t2 = self.text()
        return want, (t2 if want["title"] in t2 and re.search(r"\d+ results? found", t2) else t), ids

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
        # The page text can look right a moment before the address settles, and the address may carry a query or
        # fragment, so wait on the path itself (ignoring ?query and #fragment) before giving up.
        end = time.time() + 20
        while time.time() < end and not is_preview_url(self.frame().url):
            self.page.wait_for_timeout(500)
        url = self.frame().url
        self.note("student view address shape: " + url_shape(url))
        if not is_preview_url(url):
            raise ReadError("differs", "Student view's address doesn't end in /preview (shape seen: " + url_shape(url) + ").",
                            {"log": self.log})
        # Parts of this page (the rubric button among them) can appear after the instructions do: wait until the text has
        # stopped changing for two reads in a row (at most ~8 s) before capturing it.
        last, stable, end = None, 0, time.time() + 8
        while time.time() < end and stable < 2:
            cur = self.text()
            stable = stable + 1 if cur == last else 0
            last = cur
            self.page.wait_for_timeout(1000)
        self.rubric_probe = self.probe_rubric()
        self.note("rubric probe: " + json.dumps(self.rubric_probe)[:300])
        return last or t

    def read_rubric(self):
        """Open the rubric ('View rubric', exactly one such button, one click) and read its criteria. Never raises for a
        rubric that doesn't look as expected: returns (rubric or None, note) so the instructions and counts already read are
        kept and the rubric simply stays 'present, not read'. A new browser tab or a changed assignment address is the
        exception: that is a real surprise, so it raises and the read stops. The dialog is not closed by clicking: the
        browser is closed when the read ends."""
        f = self.frame()
        btns = f.get_by_role("button", name=re.compile(r"^\s*View rubric\s*$", re.I)).all()
        if len(btns) != 1:
            return None, f"expected exactly one 'View rubric' button, found {len(btns)}; nothing was clicked"
        before_pages, before = len(self.page.context.pages), url_path(f.url)
        self.click("view-rubric", btns[0])
        dialog, end = None, time.time() + self.rubric_wait
        while time.time() < end and dialog is None:
            self.page.wait_for_timeout(1000)
            if len(self.page.context.pages) != before_pages:
                raise ReadError("differs", "View rubric opened a new browser tab, which this reader doesn't expect.")
            fr = self.frame()
            if fr is not None and url_path(fr.url) != before:
                raise ReadError("differs", "Opening the rubric changed the page address, which this reader doesn't expect.")
            loc = fr.locator('[role="dialog"]') if fr is not None else None
            if loc is not None and loc.count() and loc.first.locator('[role="listbox"]').count():
                dialog = loc.first
        if dialog is None:
            return None, f"no rubric dialog with criteria lists appeared within {self.rubric_wait} s"
        raw = dialog.evaluate("""d => {
            const txt = e => (e && e.textContent || '').trim();
            const h = d.querySelector('h1,h2,h3,[role=heading]');
            return {title: txt(h), criteria: [...d.querySelectorAll('[role=listbox]')].map(lb => {
                const label = lb.getAttribute('aria-label') || '', prev = lb.previousElementSibling;
                return {name: label.replace(/^Criteria for\\s*/i, ''), heading: prev && prev.tagName !== 'H2' ? txt(prev) : '',
                        levels: [...lb.querySelectorAll('[role=option]')].map(o => {
                            const k = [...o.children];
                            return {level: txt(k[0]), descriptor: k.slice(1).map(txt).filter(Boolean).join('\\n')};
                        })};
            })};
        }""")
        self.note("rubric dialog read: " + str(len((raw or {}).get("criteria") or [])) + " criteria")
        return validate_rubric(raw)

    def probe_rubric(self):
        """Read-only: which buttons/links on the page have 'rubric' in their name, and which text lines mention it."""
        f = self.frame(); names = []
        try:
            for role in ("button", "link", "menuitem"):
                for el in f.get_by_role(role, name=re.compile("rubric", re.I)).all():
                    try:
                        n = (el.get_attribute("aria-label", timeout=1000) or el.inner_text(timeout=1000) or "").strip()
                    except Exception:
                        n = ""
                    names.append(re.sub(r"\s+", " ", n)[:60])
        except Exception as e:
            names.append("(control probe failed: " + type(e).__name__ + ")")
        lines = [re.sub(r"\s+", " ", l.strip())[:80] for l in self.text().splitlines() if re.search("rubric", l, re.I)][:6]
        return {"control_names": names[:8], "text_lines": lines}


def _launch(p, headless=False):
    if os.environ.get("SF_FORBID_BROWSER"):      # set by the tests: they must never open a browser profile
        raise ReadError("setup", "Browser use is switched off (SF_FORBID_BROWSER is set).")
    try:
        return p.chromium.launch_persistent_context(str(PROFILE), channel="chrome", headless=headless,
                                                   viewport={"width": 1440, "height": 900})
    except Exception as e:
        msg = str(e)
        if "ProcessSingleton" in msg or "profile" in msg.lower() and "in use" in msg.lower():
            raise ReadError("busy", "Browser profile in use: Chrome already has this profile open. Close that Chrome window and try again.")
        raise ReadError("setup", f"Couldn't start Google Chrome through Playwright: {msg[:300]}")


def run(op, cls="", title="", wait=120, signin_wait=240, students=False):
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
            sv = apply_rubric_probe(parse_student_view(sv_text), getattr(s, "rubric_probe", None))
            ids2 = ids_from_url(s.frame().url)
            if ids2 != ids:
                raise ReadError("differs", "The roster and Student view addresses name different assignments; nothing was returned.")
            if not sv["found"] or sv["title"] != want["title"]:
                raise ReadError("differs", "Student view didn't show the expected title and an Instructions section.")
            if sv.get("rubric_present"):          # last, so a surprise here can't lose the instructions or counts
                rubric, why = s.read_rubric()
                if rubric:
                    sv["rubric"], sv["rubric_read"] = rubric, True
                else:
                    sv["rubric_note"] = (sv.get("rubric_note", "") + " Rubric not read: " + why + ".").strip()
                    s.note("rubric not read: " + why)
            return {"op": "read", "read_at": now,
                    "source": {**ids, "url": roster_url, "student_view_url": re.sub(r"[?#].*", "", s.frame().url),
                               "teams_class": want["class_name"], "list_title": want["title"], "read_at": now},
                    "list_row": want, "student_view": sv, "roster_counts": roster, "log": s.log,
                    **({"roster_students": parse_roster_students(roster_text)} if students else {})}
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("op", choices=["list", "read"])
    ap.add_argument("--class", dest="cls", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--students", action="store_true", help="also return each student's status (names), for the app's per-card status")
    ap.add_argument("--wait", type=int, default=120)
    ap.add_argument("--signin-wait", type=int, default=240)
    a = ap.parse_args()
    try:
        if a.op == "read" and not (a.cls and a.title):
            raise ReadError("error", "read needs --class and --title")
        out = run(a.op, a.cls, a.title, a.wait, a.signin_wait, students=a.students and a.op == "read")
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
