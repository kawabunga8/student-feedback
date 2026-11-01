"""Reading the rubric from the 'View rubric' dialog: structure validation (no browser) and the one-click read against a
synthetic page served from memory (no network, no Teams). Everything is invented."""
import sys
from _common import APPDIR, LAUNCH, guard, block_live_browser
import tempfile, os
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR)
import teams_read as T
block_live_browser(T)
from teams_fixtures import rubric_dialog_html, student_view_page
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

def raw(crit=None, title="Sample"):
    crit = crit if crit is not None else {"A": ["Extending", "Proficient", "Developing", "Emerging"], "B": ["Extending", "Proficient", "Developing", "Emerging"]}
    return {"title": title, "criteria": [{"name": n, "heading": n, "levels": [{"level": l, "descriptor": f"{n} {l} text."} for l in ls]} for n, ls in crit.items()]}

# ---- validate_rubric (pure)
r, why = T.validate_rubric(raw())
check("1 a complete rubric validates; levels keep Teams' order and exact descriptors", r and [c["name"] for c in r["criteria"]] == ["A", "B"] and [l["level"] for l in r["criteria"][0]["levels"]] == ["Extending", "Proficient", "Developing", "Emerging"] and r["criteria"][1]["levels"][3]["descriptor"] == "B Emerging text.", why)
check("  source is labelled", r["source"] == "View rubric dialog")
for label, bad in [("a missing level", raw({"A": ["Extending", "Proficient", "Emerging"]})),
                   ("a repeated level", raw({"A": ["Extending", "Extending", "Developing", "Emerging"]})),
                   ("an unexpected level word", raw({"A": ["Extending", "Proficient", "Developing", "Beginning"]})),
                   ("no criteria", {"title": "Sample", "criteria": []}), ("no title", raw(title="")), ("garbage", None)]:
    rr, why = T.validate_rubric(bad)
    check(f"2 {label}: not accepted, with a reason", rr is None and why, why)
b = raw(); b["criteria"][0]["levels"][1]["descriptor"] = " "
check("  an empty descriptor is not accepted", T.validate_rubric(b)[0] is None)
b = raw(); b["criteria"][1]["heading"] = "Something else"
check("  a criterion whose heading disagrees with its list name is not accepted", T.validate_rubric(b)[0] is None)
b = raw({"A": ["Extending", "Proficient", "Developing", "Emerging"], "a": ["Extending", "Proficient", "Developing", "Emerging"]})
check("  repeated criterion names are not accepted", T.validate_rubric(b)[0] is None)
check("  the descriptor wording is not altered (internal newlines kept)", T.validate_rubric({**raw(), "criteria": [{"name": "A", "heading": "A", "levels": [{"level": l, "descriptor": "one\ntwo"} for l in T.RUBRIC_LEVELS]}]})[0]["criteria"][0]["levels"][0]["descriptor"] == "one\ntwo")

# ---- the one-click read against synthetic pages
from playwright.sync_api import sync_playwright
T.FRAME_HOST = "assignments.example.test"
def session(p, html, **kw):
    b = p.chromium.launch(**LAUNCH); ctx = b.new_context()
    ctx.route("**/*", lambda route: route.fulfill(status=200, content_type="text/html", body=html if "other" not in route.request.url else "<p>other</p>"))
    pg = ctx.new_page(); pg.goto("https://assignments.example.test/classes/x/assignments/y/preview")
    s = T.Session(pg, 20); s.t0 = 0; s.rubric_wait = 3
    return b, ctx, pg, s
with sync_playwright() as p:
    b, ctx, pg, s = session(p, student_view_page(rubric_dialog_html()))
    rub, why = s.read_rubric()
    check("3 one click reads the synthetic dialog into validated criteria", rub and [c["name"] for c in rub["criteria"]] == ["Planning", "Building"] and rub["title"].startswith("Sample Design Rubric") and rub["criteria"][0]["levels"][0] == {"level": "Extending", "descriptor": "Plans ahead and adapts the plan with reasons."}, why)
    check("  the read kept the dialog open and clicked nothing else (still one tab)", len(ctx.pages) == 1)
    b.close()
    b, ctx, pg, s = session(p, student_view_page(rubric_dialog_html({"Planning": {"Extending": "x", "Proficient": "y", "Developing": "z"}})))
    rub, why = s.read_rubric()
    check("4 a rubric missing a level stays unread, with a reason (nothing imported)", rub is None and "expected four" in why, why)
    b.close()
    b, ctx, pg, s = session(p, student_view_page(rubric_dialog_html(), buttons=2))
    rub, why = s.read_rubric()
    check("5 two 'View rubric' buttons: nothing is clicked", rub is None and "found 2" in why and "nothing was clicked" in why and pg.locator("#slot").inner_html() == "", why)
    b.close()
    b, ctx, pg, s = session(p, student_view_page(rubric_dialog_html(), behaviour="nothing"))
    rub, why = s.read_rubric()
    check("6 a click that opens no dialog: unread, with a reason", rub is None and "no rubric dialog" in why, why)
    b.close()
    b, ctx, pg, s = session(p, student_view_page(rubric_dialog_html(), behaviour="newtab"))
    try:
        s.read_rubric(); raised = ""
    except T.ReadError as e: raised = str(e)
    check("7 a click that opens a new tab stops the read", "new browser tab" in raised, raised)
    b.close()
    # the allowlist: the rubric click is allowed, anything else still is not
    b, ctx, pg, s = session(p, student_view_page(rubric_dialog_html()))
    try: s.click("close-dialog", pg.get_by_role("button", name="Close")); err = ""
    except T.ReadError as e: err = str(e)
    check("8 clicking anything not on the allowlist (e.g. Close) is refused", "not allowed" in err, err)
    b.close()
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
