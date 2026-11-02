#!/usr/bin/env python3
"""READ-ONLY spike: what does Teams' per-student grading panel look like? (Needed before any feedback-posting is built.)

    python tools/spike_teams_grading_panel.py --class "RCS - H - Q1 ICT 9 [2026-27]" --title "Task 4: ..." --student "Last, First"

It opens the assignment's roster, clicks the ONE row whose displayed name is exactly --student (a navigation click, the same
one you make by hand), waits for the grading panel, and describes its controls. That is all:
  - it never types, never touches the Feedback box, Points, Return or any menu or toggle, and never leaves the panel open
    (the browser is closed afterwards, which discards anything not saved: nothing was entered);
  - the report holds control NAMES, roles, counts and lengths only. It never contains student work, feedback text, or the
    student's name (the name you pass is masked wherever it appears in a control's name);
  - the shared browser lock is taken first ("browser profile in use"), like the other readers.

Use a low-stakes assignment. Choose a student whose Feedback box is empty if you can; if it holds text, the report says so
(its length), never what it says.

What the report answers: is there a Feedback editor (and what kind); is it empty; what are the buttons, including the
Return button and whatever is attached to it; are Points and the Copilot toggle present; how do you move to the next
student; what does the panel's address look like (ids masked). Output: one JSON object on stdout and, with --out, a file.
Exit codes are teams_read.py's.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime

import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import teams_read as T

PANEL_JS = """() => {
  const vis = el => { const s = getComputedStyle(el); return s.display !== "none" && s.visibility !== "hidden" && el.getClientRects().length > 0; };
  const name = el => (el.getAttribute("aria-label") || el.getAttribute("title") || el.innerText || el.value || "").replace(/\\s+/g, " ").trim().slice(0, 80);
  const fieldLabel = el => (el.getAttribute("aria-label") || el.getAttribute("title") || "").replace(/\\s+/g, " ").trim().slice(0, 60);
  const buttons = [...document.querySelectorAll('button, [role="button"], [role="menuitem"], [role="switch"], [role="checkbox"]')].filter(vis)
    .map(b => ({role: b.getAttribute("role") || "button", name: name(b), disabled: b.disabled || b.getAttribute("aria-disabled") === "true",
                popup: b.getAttribute("aria-haspopup") || "", expanded: b.getAttribute("aria-expanded") || "", pressed: b.getAttribute("aria-pressed") || b.getAttribute("aria-checked") || ""}));
  const editors = [...document.querySelectorAll('[contenteditable="true"], [role="textbox"], textarea')].filter(vis)
    .map(e => ({kind: e.tagName.toLowerCase() + (e.getAttribute("contenteditable") === "true" ? "[contenteditable]" : ""), role: e.getAttribute("role") || "",
                label: fieldLabel(e), text_length: ((e.innerText || e.value || "").trim()).length, placeholder: (e.getAttribute("placeholder") || e.getAttribute("data-placeholder") || "").slice(0, 60)}));
  const inputs = [...document.querySelectorAll("input")].filter(vis).map(i => ({type: i.type, label: fieldLabel(i), has_value: !!i.value}));
  const headings = [...document.querySelectorAll('h1, h2, h3, [role="heading"]')].filter(vis).map(h => name(h).slice(0, 60));
  return {buttons, editors, inputs, headings};
}"""


def mask_names(text, student):
    """Mask name tokens, including short surnames, without replacing parts of other words."""
    out = text or ""
    for part in re.split(r"[\s,]+", student or ""):
        if part:
            out = re.sub(r"(?<!\w)" + re.escape(part) + r"(?!\w)", "<student>", out, flags=re.I)
    return out


def safe_report(info, student, shape):
    """Control names, roles, counts and lengths only; the student's name is masked out of every name."""
    m = lambda s: mask_names(s, student)
    return {"buttons": [{**b, "name": m(b["name"])} for b in info.get("buttons", [])],
            "editors": [{**e, "label": m(e["label"]), "placeholder": m(e["placeholder"])} for e in info.get("editors", [])],
            "inputs": [{**i, "label": m(i["label"])} for i in info.get("inputs", [])],
            "headings": [m(h) for h in info.get("headings", [])],
            "address_shape": shape}


def summarise(rep):
    """Plain-language findings the posting design depends on."""
    names = [b["name"] for b in rep["buttons"]]
    has = lambda pat: [n for n in names if re.search(pat, n, re.I)]
    ed = rep["editors"]
    return {"feedback_editors": len(ed), "feedback_editor_empty": (ed[0]["text_length"] == 0) if ed else None,
            "return_buttons": has(r"^return"), "other_return_controls": has(r"return|revision|excus"),
            "copilot_controls": has(r"copilot|enhance"), "points_controls": has(r"point") + [i["label"] for i in rep["inputs"] if re.search(r"point", i["label"], re.I)],
            "move_between_students": has(r"previous|next"), "total_buttons": len(names)}


def run(cls, title, student, wait=120, signin_wait=240):
    if T.os.environ.get("SF_FORBID_BROWSER"):
        raise T.ReadError("setup", "Browser use is switched off (SF_FORBID_BROWSER is set).")
    from playwright.sync_api import sync_playwright
    T.PROFILE.mkdir(parents=True, exist_ok=True)
    with T.BrowserLock(), sync_playwright() as p:
        ctx = T._launch(p)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            s = T.Session(page, wait); s.t0 = time.time()
            page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(4000)
            if T._host(page.url) in T.LOGIN_HOSTS:
                end = time.time() + signin_wait
                while T._host(page.url) in T.LOGIN_HOSTS and time.time() < end:
                    page.wait_for_timeout(2000)
                if T._host(page.url) in T.LOGIN_HOSTS:
                    raise T.ReadError("sign_in", "Sign in to Microsoft in the Chrome window that opened, then run again.")
                page.goto(T.TEAMS, wait_until="domcontentloaded"); page.wait_for_timeout(3000)
            want, roster_text, ids = s.open_one(cls, title)
            f = s.frame()
            hits = f.get_by_text(student, exact=True)
            n = hits.count()
            if n != 1:
                raise T.ReadError("differs", f"The roster showed that exact student name {n} times (expected once). Nothing was clicked.")
            before = len(ctx.pages)
            hits.first.click(timeout=5000)             # the one navigation click: it opens that student's grading panel
            end = time.time() + wait
            while time.time() < end:
                t = s.text()
                if "Feedback" in t and re.search(r"\bReturn\b", t) and student.split(",")[0].strip() in t:
                    break
                page.wait_for_timeout(1000)
            else:
                raise T.ReadError("differs", "The student's grading panel (Feedback and Return) didn't appear.")
            if len(ctx.pages) != before:
                raise T.ReadError("differs", "Opening the student opened a new tab, which this spike doesn't expect.")
            page.wait_for_timeout(2500)
            info = s.frame().evaluate(PANEL_JS)
            shape = T.url_shape(s.frame().url)
            rep = safe_report(info, student, shape)
            return {"op": "grading-panel-spike", "read_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                    "report": rep, "findings": summarise(rep), "log": s.log}
        finally:
            ctx.close()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--class", dest="cls", required=True); ap.add_argument("--title", required=True)
    ap.add_argument("--student", required=True, help="the name exactly as the roster shows it")
    ap.add_argument("--out", default=""); ap.add_argument("--wait", type=int, default=120)
    a = ap.parse_args()
    try:
        if T.os.environ.get("SF_FORBID_BROWSER"):
            raise T.ReadError("setup", "Browser use is switched off (SF_FORBID_BROWSER is set).")
        out = run(a.cls, a.title, a.student, a.wait); out["ok"] = True
        text = json.dumps(out, ensure_ascii=False, indent=2)
        if a.out:
            open(a.out, "w", encoding="utf-8").write(text + "\n")
        print(text)
        return T.EXIT["ok"]
    except T.ReadError as e:
        print(json.dumps({"ok": False, "kind": e.kind, "error": mask_names(str(e), a.student), **{k: v for k, v in e.extra.items() if k != "candidates"}}, ensure_ascii=False))
        return T.EXIT.get(e.kind, 1)
    except Exception as e:
        print(json.dumps({"ok": False, "kind": "error", "error": f"{type(e).__name__}: The panel inspection stopped. No page content was included in this error."}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
