"""Read one assignment's OneNote page for every student of a class, in ONE browser session (read-only).

Why guessing: OneNote Online shows the automated browser no page list, but it opens a page by its title:
  .../Doc.aspx?sourcedoc={notebook}&action=view&wd=target(<First Last>/<Section>.one|/<Page title>|/)
Titles are exact (case doesn't matter, punctuation does), and a title that doesn't exist silently opens some other page.
So for each student this tries the likely titles for the assignment, and counts a page as found only when the title that
actually loaded equals the title asked for. A student with no match is reported with how many titles were tried, never
guessed at. Titles that worked for earlier students are tried first for the next ones.

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


def run_class(req, emit, wait=14, signin_wait=240):
    from playwright.sync_api import sync_playwright
    base, students = req["base"], req["students"]
    titles = [t for t in (req.get("titles") or []) if str(t).strip()]
    sections = [s for s in (req.get("sections") or SECTIONS) if str(s).strip()] or list(SECTIONS)
    if not titles:
        raise T.ReadError("differs", "No page titles to try.")
    O.check_url(base)
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    hits = {}                                            # (section, title) -> students it worked for
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            signed_in = False
            for st in students:
                order = sorted(((s, t) for s in sections for t in titles), key=lambda k: -hits.get(k, 0))[:max(MAX_TRIES, 1)]
                found, tried = None, 0
                for sec, title in order:
                    tried += 1
                    url = page_url(base, st["name"], sec, title)
                    page.goto(url, wait_until="domcontentloaded")
                    page.wait_for_timeout(1500)
                    if not signed_in:
                        if T._host(page.url) in T.LOGIN_HOSTS:
                            end = time.time() + signin_wait
                            while T._host(page.url) in T.LOGIN_HOSTS and time.time() < end:
                                page.wait_for_timeout(2000)
                            if T._host(page.url) in T.LOGIN_HOSTS:
                                raise T.ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then resume the job.")
                            page.goto(url, wait_until="domcontentloaded")
                            page.wait_for_timeout(1500)
                        signed_in = True
                    if not O.ONENOTE_HOST.search(T._host(page.url)):
                        raise T.ReadError("differs", "The browser ended up on a different site than the notebook; nothing was read.")
                    try:
                        out = O.read_loaded(page, url, {"section": sec, "page": title, "student_hint": st["name"]}, lambda s: None, wait)
                    except T.ReadError as e:
                        if e.kind == "blocked":
                            raise
                        continue                         # blank page, or nothing loaded: try the next title
                    ident = None
                    for _ in range(10):                  # OneNote rewrites the address to the page it really opened
                        ident = resolved_identity(page.url)
                        if ident:
                            break
                        page.wait_for_timeout(500)
                    if not ident:
                        continue                         # can't prove whose page this is: not accepted
                    if not same_name(ident["student"], st["name"]):
                        break                            # opened someone else's page (this student has no such section): stop guessing
                    if same_name(ident["section"], sec) and norm_tokens(ident["page"]) == norm_tokens(title) and \
                            norm_tokens(first_line(out["page"]["text"])) == norm_tokens(title):
                        out["source"]["student_hint"] = ident["student"]
                        found = (sec, title, out)
                        hits[(sec, title)] = hits.get((sec, title), 0) + 1
                        break
                if found:
                    emit({"item": {"key": st["key"], "found": True, "section": found[0], "title": found[1], "tried": tried, "page": found[2]}})
                else:
                    emit({"item": {"key": st["key"], "found": False, "tried": tried}})
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
