"""Read one assignment's OneNote page for every student of a class, in ONE browser session (read-only).

The collector first opens the named student's section and reads its real page list after navigation settles.
If that list cannot be verified, it falls back to likely assignment titles using a read-only page address:
  .../Doc.aspx?sourcedoc={notebook}&action=view&wd=target(<First Last>/<Section>.one|/<Page title>|/)
A missing title can silently open another page, so collection requires the resolved student, section and page
identity to match. Missing or ambiguous work is reported rather than guessed.
Protocol (like teams_batch.py): one JSON request line on stdin; JSON lines on stdout:
  {"item": {"key", "found", "title", "section", "tried", "page": {...as onenote_read.collect...}}}   one per student
  {"ok": true, "done": true} or {"ok": false, "kind", "error"}
Page text goes only to this stdout (the parent writes it to the job's sidecar); nothing is logged.
"""
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime

import teams_read as T
import onenote_read as O

MAX_TRIES = 20               # titles tried per student before reporting "not found"
SECTIONS = ("Homework",)     # the teacher can add Handouts


def norm_tokens(s):
    """Words of a title with & read as 'and', so 'Define & Ideate' equals 'define and ideate'."""
    return re.findall(r"[a-z0-9]+", (s or "").lower().replace("&", " and "))


def candidate_titles(assignment_title):
    """Likely page titles for an assignment such as 'Task 3: Prototype & Test', most likely first. The teacher can edit the list."""
    t = " ".join((assignment_title or "").split())
    m = re.match(r"^(task|stage|part|step|unit|lab)\s*(\d+)\s*[:\-–.]?\s*(.*)$", t, re.I)
    out = []
    def add(x):
        x = x.strip()
        if x and x.lower() not in {o.lower() for o in out}:
            out.append(x)
    if not m:
        add(t)
        return out
    num, phrase = m.group(2), m.group(3).strip()
    phrases = []
    if phrase:
        for p in (phrase, phrase.replace("&", "and"), re.sub(r"\band\b", "&", phrase, flags=re.I)):
            if p not in phrases:
                phrases.append(p)
    words = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}
    nums = [num] + ([words[num]] if num in words else [])
    add(t)
    for n in nums:                                   # students very often just write "Task 3" or "Task three"
        for pre in ("Task", "Stage", "Part"):
            add(pre + " " + n)
    for p in phrases:
        add(p)
    for pre in ("Stage", "Task", "Part"):
        for p in phrases:
            for j in (" - ", ": ", " "):
                add(pre + " " + num + j + p)
    for p in phrases:
        add(num + "." + p)
        add(num + ". " + p)
        add("ICT Part " + num + "- " + p)
    for n in nums:
        add("ICT Task " + n)
        add(n)
    return out


def page_url(base, student, section, title):
    """The notebook address for one student's page by title. base is any page address of the same notebook."""
    sp = urllib.parse.urlsplit(O.read_only(base))
    q = urllib.parse.parse_qs(sp.query)
    keep = {k: q[k][0] for k in ("sourcedoc",) if k in q}
    if "sourcedoc" not in keep:
        raise T.ReadError("differs", "The notebook address has no notebook id (sourcedoc). Paste an address copied from the notebook.")
    wd = "target(" + "/".join([urllib.parse.quote(student, safe=""), urllib.parse.quote(section, safe="") + ".one|"]) + \
         "/" + urllib.parse.quote(title, safe="") + "|/)"
    qs = urllib.parse.urlencode({**keep, "action": "view", "wdorigin": "NavigationUrl"}, safe="{}") + "&wd=" + wd
    return urllib.parse.urlunsplit((sp.scheme, sp.netloc, sp.path, qs, ""))


def resolved_identity(url):
    """Where OneNote actually opened, from the browser's own address once OneNote has rewritten it to ids:
    .../wd=target(<Student>/<Section>.one|<section id>/<Page>|<page id>/). Returns {student, section, page}, or None while the
    address still only holds what was asked for (no ids yet) or has another shape (e.g. Welcome.one|id/Page|id/ has no student).
    A title that is missing for a student does not fail: OneNote silently opens some other page, and this shows which."""
    wd = urllib.parse.parse_qs(urllib.parse.urlsplit(url or "").query).get("wd", [""])[0]
    m = re.match(r"target\((.*)\)$", wd)
    if not m:
        return None
    segs = [x for x in m.group(1).split("/") if x]
    if len(segs) != 3:
        return None
    parts = []
    for seg in segs:
        name, _, ident = seg.partition("|")
        parts.append((urllib.parse.unquote(name), ident))
    if not parts[1][0].endswith(".one") or not parts[1][1] or not parts[2][1]:
        return None
    return {"student": parts[0][0], "section": parts[1][0][:-4], "page": parts[2][0]}


def same_name(a, b):
    return " ".join((a or "").split()).casefold() == " ".join((b or "").split()).casefold()


def first_line(text):
    return next((l.strip() for l in (text or "").splitlines() if l.strip()), "")


KINDS = {"task", "stage", "part", "step", "unit", "lab"}
WORDS = {"1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def step_number(titles):
    """The 'N' of 'Task N: ...' from the first title, or ''."""
    m = re.match(r"^\s*(?:%s)\s*(\d+)" % "|".join(sorted(KINDS)), titles[0] if titles else "", re.I)
    return m.group(1) if m else ""


def pick_page(pages, titles):
    """Which of a student's listed pages is this assignment's. Returns (title, why_not).
    First an exact match (words only, & = and) with any title in the list, in order; then, only if exactly one page fits, a page that
    starts 'Task/Stage/Part N' or 'N.' (optionally after 'ICT'), as students name them differently. Two candidates are never
    guessed between."""
    for t in titles:
        hits = [p for p in pages if norm_tokens(p) == norm_tokens(t)]
        if len(hits) == 1:
            return hits[0], ""
        if len(hits) > 1:
            return None, "more than one page has that title"
    num = step_number(titles)
    if num:
        ok = {num, WORDS.get(num, "\0")}
        def loose(p):
            tk = norm_tokens(p)
            if tk[:1] == ["ict"]:
                tk = tk[1:]
            return bool(tk) and ((tk[0] in KINDS and len(tk) > 1 and tk[1] in ok) or tk[0] in ok)
        hits = [p for p in pages if loose(p)]
        if len(hits) == 1:
            return hits[0], ""
        if len(hits) > 1:
            return None, "more than one page could be it"
    return None, "no page matches"


def notebook_url(base):
    """The notebook with no page chosen (opens at its first section), so no student's section starts expanded."""
    sp = urllib.parse.urlsplit(O.read_only(base))
    q = urllib.parse.parse_qs(sp.query)
    if "sourcedoc" not in q:
        raise T.ReadError("differs", "The notebook address has no notebook id (sourcedoc). Paste an address copied from the notebook.")
    qs = urllib.parse.urlencode({"sourcedoc": q["sourcedoc"][0], "action": "view", "wdorigin": "NavigationUrl"}, safe="{}")
    return urllib.parse.urlunsplit((sp.scheme, sp.netloc, sp.path, qs, ""))


def _until(page, fn, secs):
    end = time.monotonic() + secs
    while True:
        v = fn()
        if v:
            return v
        if time.monotonic() >= end:
            return None
        page.wait_for_timeout(500)


def _frame(page):
    f, _ = O._onenote_frame(page)
    return f


def _name_re(name, suffix):
    return re.compile(r"^" + r"\s+".join(re.escape(w) for w in name.split()) + suffix, re.I)


def same_notebook(url, base):
    def key(value):
        parsed = urllib.parse.urlsplit(value)
        ident = urllib.parse.parse_qs(parsed.query).get('sourcedoc', [''])[0].strip('{}').casefold()
        return parsed.scheme, parsed.netloc.casefold(), parsed.path.casefold(), ident
    first, second = key(url), key(base)
    return bool(first[3]) and first == second


def open_section(page, base, student, section, signin):
    """Reuse the open notebook tree; navigate only when it is unavailable or belongs to another notebook.
    Opening a section still requires the resolved student and section address to match.
    """
    f = _frame(page) if same_notebook(page.url, base) else None
    if f is None or f.get_by_role('treeitem').count() <= 3:
        page.goto(notebook_url(base), wait_until="domcontentloaded")
        signin(page, notebook_url(base))
        f = _until(page, lambda: (lambda fr: fr if fr is not None and fr.get_by_role("treeitem").count() > 3 else None)(_frame(page)), 40)
    if f is None:
        return None
    items = lambda: _frame(page).locator("[role=treeitem]")
    labels = lambda: _frame(page).evaluate("() => [...document.querySelectorAll('[role=treeitem]')].map(e => e.getAttribute('aria-label') || '')")
    is_group = lambda l: bool(re.search(r",\s*Section Group\b", l))
    def group_at():
        hits = [i for i, l in enumerate(labels()) if is_group(l) and _name_re(student, r",\s*Section Group").match(l)]
        return hits[0] if len(hits) == 1 else None
    def section_under(gi):
        """Index of the section called `section` listed directly under the group at gi (other students' open groups don't count)."""
        ls = labels()
        for k in range(gi + 1, len(ls)):
            if is_group(ls[k]):
                return None
            if _name_re(section, r",\s*Section\b").match(ls[k]):
                return k
        return None
    gi = _until(page, lambda: (group_at(),) if group_at() is not None else None, 8)
    gi = gi[0] if gi is not None else None
    if gi is None:
        return None
    if section_under(gi) is None and not (gi + 1 < len(labels()) and not is_group(labels()[gi + 1])):
        items().nth(gi).click()                          # closed: open it (an open one would be shut by a click)
    si = _until(page, lambda: section_under(group_at()) if group_at() is not None else None, 15)
    if si is None:
        return "nosection" if group_at() is not None else None      # the student is there but has no such section: nothing to guess
    items().nth(si).click()
    def opened():
        ident = resolved_identity(page.url)
        return ident and same_name(ident["student"], student) and same_name(ident["section"], section)
    return _frame(page) if _until(page, opened, 20) else None


PAGE_TITLES_JS = """() => [...document.querySelectorAll('#PageList .pageListItem')].map(e => ((e.innerText || '').trim().split('\\n')[0] || '').trim())"""


def identity_matches(ident, student, section, title=None):
    """Require resolved navigation, never the requested URL alone."""
    if not ident or not same_name(ident["student"], student) or not same_name(ident["section"], section):
        return False
    core = lambda x: [w for w in norm_tokens(x) if w != "and"]
    return title is None or core(ident["page"]) == core(title)


def list_pages(page, f, student, section):
    """Return a stable list only while the requested student's section is resolved.
    The current page must appear in the list too; an old list is not evidence of missing work.
    None means navigation/list readiness could not be established: use the title fallback.
    """
    previous = None
    def settled():
        nonlocal previous
        before = resolved_identity(page.url)
        if not identity_matches(before, student, section):
            previous = None
            return None
        frame = _frame(page)
        titles = [t for t in frame.evaluate(PAGE_TITLES_JS) if t] if frame is not None else []
        after = resolved_identity(page.url)
        if before != after or not any(identity_matches(after, student, section, t) for t in titles):
            previous = None
            return None
        sample = (after, titles)
        ready = sample == previous
        previous = sample
        return titles if ready else None
    return _until(page, settled, 15)


def open_listed_page(page, title, wait, student, section):
    """Click once, then wait for the exact student/section/page before reading content."""
    if not identity_matches(resolved_identity(page.url), student, section):
        return None
    items = _frame(page).locator("#PageList .pageListItem")
    n = items.count()
    hit = [i for i, t in enumerate(_frame(page).evaluate(PAGE_TITLES_JS)) if t == title]
    if n == 0 or len(hit) != 1:
        return None
    items.nth(hit[0]).click()
    if not _until(page, lambda: identity_matches(resolved_identity(page.url), student, section, title), min(wait, 20)):
        return None
    return O.read_loaded(page, page.url, {"section": section, "page": title, "student_hint": student}, lambda s: None, wait)


def run_class(req, emit, wait=14, signin_wait=240):
    from playwright.sync_api import sync_playwright
    base, students = req["base"], req["students"]
    titles = [t for t in (req.get("titles") or []) if str(t).strip()]
    sections = [s for s in (req.get("sections") or SECTIONS) if str(s).strip()] or list(SECTIONS)
    if not titles:
        raise T.ReadError("differs", "No page titles to try.")
    O.check_url(base)
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    hits = {}                                            # (section, title) -> students it worked for (guessing fallback)
    state = {"signed_in": False}
    def signin(page, url):
        if state["signed_in"]:
            return
        if T._host(page.url) in T.LOGIN_HOSTS:
            end = time.time() + signin_wait
            while T._host(page.url) in T.LOGIN_HOSTS and time.time() < end:
                page.wait_for_timeout(2000)
            if T._host(page.url) in T.LOGIN_HOSTS:
                raise T.ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then resume the job.")
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
        state["signed_in"] = True
    def host_ok(page):
        if not O.ONENOTE_HOST.search(T._host(page.url)):
            raise T.ReadError("differs", "The browser ended up on a different site than the notebook; nothing was read.")
    def accept(page, st, sec, title, out, first_line_must_match=True):
        """Only a page whose opened address names this student, this section and this title, and whose first line is that title."""
        ident = None
        for _ in range(10):                              # OneNote rewrites the address to the page it really opened
            ident = resolved_identity(page.url)
            if ident:
                break
            page.wait_for_timeout(500)
        if not ident or not same_name(ident["student"], st["name"]):
            return "other"
        core = lambda x: [w for w in norm_tokens(x) if w != "and"]     # OneNote drops '&' (and escapes brackets) in the address
        if same_name(ident["section"], sec) and core(ident["page"]) == core(title) and \
                (not first_line_must_match or norm_tokens(first_line(out["page"]["text"])) == norm_tokens(title)):
            out["source"]["student_hint"] = ident["student"]
            return "ok"
        return "no"
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            for st in students:
                found, tried, listed, seen, unread = None, 0, False, [], ""
                for sec in sections:
                    # 1. the student's real page list (fast, and says what is there when nothing matches)
                    try:
                        f = open_section(page, base, st["name"], sec, signin)
                        host_ok(page)
                        if f == "nosection":
                            listed = True
                            continue
                        pages = list_pages(page, f, st["name"], sec) if f is not None else None
                    except T.ReadError as e:
                        if e.kind in ("sign_in", "differs", "blocked"):
                            raise
                        f, pages = None, None
                    except Exception:
                        f, pages = None, None
                    if pages is not None:
                        listed = True
                        seen += pages
                        title, _why = pick_page(pages, titles)
                        if title:
                            try:
                                out = open_listed_page(page, title, wait, st["name"], sec)
                            except T.ReadError as e:
                                if e.kind == "blocked":
                                    raise
                                out = None
                            if out and accept(page, st, sec, title, out, False) == "ok":
                                found = (sec, title, out)
                                break
                            unread = "unreadable" if not out else "mismatch"      # the page is listed but nothing trustworthy came out of it
                        continue
                    # 2. the list couldn't be read for this student: fall back to opening likely titles directly
                    order = sorted(((sec, t) for t in titles), key=lambda k: -hits.get(k, 0))[:max(MAX_TRIES, 1)]
                    for _s, title in order:
                        tried += 1
                        url = page_url(base, st["name"], sec, title)
                        page.goto(url, wait_until="domcontentloaded")
                        page.wait_for_timeout(1500)
                        signin(page, url)
                        host_ok(page)
                        try:
                            out = O.read_loaded(page, url, {"section": sec, "page": title, "student_hint": st["name"]}, lambda s: None, wait)
                        except T.ReadError as e:
                            if e.kind == "blocked":
                                raise
                            continue                     # blank page, or nothing loaded: try the next title
                        verdict = accept(page, st, sec, title, out)
                        if verdict == "other":
                            break                        # opened someone else's page (this student has no such section): stop guessing
                        if verdict == "ok":
                            found = (sec, title, out)
                            hits[(sec, title)] = hits.get((sec, title), 0) + 1
                            break
                    if found:
                        break
                if found:
                    emit({"item": {"key": st["key"], "found": True, "section": found[0], "title": found[1], "tried": tried, "page": found[2]}})
                else:
                    emit({"item": {"key": st["key"], "found": False, "tried": tried, "listed": listed, "unread": unread, "pages": [x[:80] for x in seen[:40]]}})
        finally:
            ctx.close()


def main():
    def emit(msg):
        print(json.dumps(msg, ensure_ascii=False), flush=True)
    try:
        req = json.loads(sys.stdin.readline())
        run_class(req, emit)
        emit({"ok": True, "done": True})
    except T.ReadError as e:
        emit({"ok": False, "kind": e.kind, "error": str(e)})
    except Exception as e:
        emit({"ok": False, "kind": "error", "error": "The class reader stopped (" + type(e).__name__ + ")."})


if __name__ == "__main__":
    main()
