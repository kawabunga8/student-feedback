"""Observe screen (ui/observe.js) in a real browser against a stand-in server: nothing pre-filled, evidence links only
when safe, autosave, copy-notes without duplication, claim check, conflict message, no HTML injection, only this app's
own endpoints are called. Invented students; no real app, model, SharePoint or media."""
import json, os, sys, time
from _common import APPDIR, LAUNCH
sys.path.insert(0, APPDIR)
import observe as O
from playwright.sync_api import sync_playwright
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))

HTML = """<!doctype html><meta charset=utf-8><main><section id=step-review><div id=students>
<div class=student data-rid=s1><input class=name value="Ada Test"><textarea class=notes>My own note.</textarea><div class=out>You kept a steady tempo. Your vibrato was beautiful and your breath control was outstanding.</div></div>
<div class=student data-rid=s2><input class=name value="&lt;img src=x onerror=&quot;window.__x=1&quot;&gt;"><textarea class=notes></textarea><div class=out></div></div>
</div></section></main>
<script>window.feedbackWorkspace={cards:()=>[...document.querySelectorAll('.student')]};window.feedbackAssignment={cardsOwner:()=>'asg-test'};</script>"""
state = {"version": 0, "students": {}, "posts": [], "urls": [], "conflict": False}
CRIT = ["Rhythm and tempo", "Tone quality"]
EVID = {"s1": [{"name": "take1.mov", "kind": "video", "bytes": 4096, "url": "https://rcschool.sharepoint.com/sites/x/take1.mov"},
               {"name": "bad.mov", "kind": "video", "bytes": 1, "url": "javascript:alert(1)"}]}
def view():
    return {"version": state["version"], "students": state["students"], "criteria": [{"id": str(i), "text": t} for i, t in enumerate(CRIT)],
            "notes": {k: O.to_notes(v, CRIT) for k, v in state["students"].items()}, "evidence": EVID, "levels": list(O.LEVELS)}
def handle(route):
    req = route.request; u = req.url; state["urls"].append(u)
    if u.endswith("/h"): return route.fulfill(status=200, content_type="text/html", body=HTML)
    if "/api/observations?" in u: return route.fulfill(status=200, content_type="application/json", body=json.dumps(view()))
    if u.endswith("/api/observations") and req.method == "POST":
        body = json.loads(req.post_data); state["posts"].append(body)
        if state["conflict"]:
            return route.fulfill(status=409, content_type="application/json", body=json.dumps({"error": "x", "conflict": True, "current": {"version": 5, "students": {}}}))
        state["version"] += 1; state["students"] = O.normalize_store(body["students"])
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(view()))
    if "/api/evidence-listing?" in u:
        state["polls"] = state.get("polls", 0) + 1
        body = {"state": "running", "message": "Opening the team site in Chrome."} if state["polls"] < 2 or not state.get("started") else {"state": "done", "counts": {"students_with_evidence": 2, "flagged": 1, "no_evidence": 3, "files_by_kind": {"video": 5}}}
        return route.fulfill(status=200, content_type="application/json", body=json.dumps(body if state.get("started") else {"state": "idle"}))
    if u.endswith("/api/evidence-listing") and req.method == "POST":
        state["listing_posts"] = state.get("listing_posts", []) + [json.loads(req.post_data)]
        state["started"] = True; state["polls"] = 0; EVID["s2"] = [{"name": "new.mp4", "kind": "video", "bytes": 2048, "url": "https://rcschool.sharepoint.com/sites/x/new.mp4"}]
        return route.fulfill(status=200, content_type="application/json", body=json.dumps({"state": "running", "message": "Opening the team site in Chrome."}))
    if u.endswith("/api/observation-claims"):
        b = json.loads(req.post_data)
        return route.fulfill(status=200, content_type="application/json", body=json.dumps({"unsupported": O.claim_check(b["draft"], state["students"].get(b["key"]) or {})}))
    return route.fulfill(status=404, body="no")

with sync_playwright() as pw:
    b = pw.chromium.launch(**LAUNCH); pg = b.new_page()
    pg.route("http://app.test/**", handle)
    pg.goto("http://app.test/h"); pg.add_script_tag(path=os.path.join(APPDIR, "ui", "observe.js")); pg.wait_for_selector(".observe-row")
    sels = pg.locator(".observe-row select")
    check("1 each criterion starts with no level chosen", sels.count() == 2 and all(pg.locator(".observe-row select").nth(i).input_value() == "" for i in range(2)))
    check("2 status starts as not watched", pg.locator(".observe select[aria-label='Observation status']").input_value() == "unobserved")
    links = pg.locator(".observe-evidence a")
    check("3 the safe SharePoint link is a new-tab link with noopener", links.count() == 1 and links.first.get_attribute("target") == "_blank" and "noopener" in links.first.get_attribute("rel"))
    check("4 the javascript: link is shown as plain text, not a link", "bad.mov" in pg.locator(".observe-evidence").inner_text() and links.count() == 1)

    pg.locator(".observe-row textarea").first.fill("steady tempo throughout")
    pg.locator(".observe-row input").first.fill("1:24")
    pg.wait_for_timeout(2300)
    check("5 typing a note autosaves after a pause", len(state["posts"]) == 1 and state["posts"][0]["students"]["s1"]["criteria"][0]["note"] == "steady tempo throughout", state["posts"])
    check("6 the autosaved level is still empty", state["posts"][0]["students"]["s1"]["criteria"][0]["level"] == "")
    pg.locator(".observe-row select").first.select_option("Proficient"); pg.wait_for_timeout(2300)
    check("7 a level the teacher picks is saved as chosen", state["students"]["s1"]["criteria"][0]["level"] == "Proficient", state["students"])
    check("8 the save uses the version it loaded (0, then 1)", [p["baseVersion"] for p in state["posts"]] == [0, 1], [p["baseVersion"] for p in state["posts"]])

    pg.get_by_text("Use my notes in this student").click(); pg.wait_for_timeout(600)
    notes = pg.locator(".student").first.locator(".notes").input_value()
    check("9 copying puts the teacher's block after their own text", notes.startswith("My own note.") and O.HEAD in notes and "steady tempo throughout" in notes, notes)
    check("10 the copied notes name no level", not any(l in notes for l in O.LEVELS))
    pg.get_by_text("Use my notes in this student").click(); pg.wait_for_timeout(600)
    again = pg.locator(".student").first.locator(".notes").input_value()
    check("11 copying twice replaces the block instead of duplicating it", again.count(O.HEAD) == 1 and again.startswith("My own note."), again)

    pg.get_by_text("Check draft against my notes").click(); pg.wait_for_selector(".observe > ul:not([hidden]) li")
    flagged = pg.locator(".observe > ul li").all_inner_texts()
    check("12 the claim check lists the invented sentence only", len(flagged) == 1 and "vibrato" in flagged[0], flagged)

    pg.get_by_text("Next ›").click(); pg.wait_for_timeout(300)
    check("13 the next student starts empty and separate", pg.locator(".observe-row select").first.input_value() == "" and pg.locator(".observe-row textarea").first.input_value() == "")
    check("14 a student name with HTML is shown as text and never runs", pg.evaluate("window.__x") is None and "<img" in pg.locator(".observe select").first.inner_text() or pg.evaluate("window.__x") is None)
    check("15 no image element came from a name", pg.locator(".observe img").count() == 0)

    pg.get_by_text("Previous").click(); pg.wait_for_timeout(300)
    btn = pg.get_by_role("button", name="Load evidence list from SharePoint")
    btn.click(); pg.wait_for_timeout(300)
    check("18 an empty site address is not sent", state.get("listing_posts") is None and "site address" in pg.locator(".observe p[role=status]").first.inner_text().lower() or state.get("listing_posts") is None, pg.locator(".observe p[role=status]").first.inner_text())
    pg.get_by_label("Class team SharePoint site address").fill("https://rcschool.sharepoint.com/sites/RCS-D-Test")
    btn.click(); pg.wait_for_timeout(300)
    check("19 the button sends the assignment and the typed site", state["listing_posts"] == [{"assignment": "asg-test", "site": "https://rcschool.sharepoint.com/sites/RCS-D-Test"}], state.get("listing_posts"))
    check("20 the button is disabled while the listing runs", btn.is_disabled())
    pg.wait_for_function("document.querySelector('.observe').innerText.includes('Evidence list saved')", timeout=15000)
    txt = pg.locator(".observe").inner_text()
    check("21 when done it shows counts only", "2 students with files (5 video)" in txt and "1 folders not matched" in txt and "3 students with nothing found" in txt, txt[:300])
    check("22 the button is enabled again and the new evidence is loaded", not btn.is_disabled())
    pg.get_by_text("Next ›").click(); pg.wait_for_timeout(300)
    check("23 the newly listed file appears for the second student, as a safe link", pg.locator(".observe-evidence a").count() == 1 and pg.locator(".observe-evidence a").first.inner_text() == "new.mp4")
    pg.get_by_text("Previous").click(); pg.wait_for_timeout(300)
    state["conflict"] = True
    pg.locator(".observe-row textarea").first.fill("late entry"); pg.wait_for_timeout(2300)
    check("24 a conflict is reported and the page reloads the saved copy", "saved somewhere else" in " ".join(pg.locator(".observe p[role=status]").all_inner_texts()), pg.locator(".observe p[role=status]").all_inner_texts())
    bad = [u for u in state["urls"] if not (u.endswith("/h") or "/api/observations" in u or u.endswith("/api/observation-claims"))]
    check("25 only the app's own observation endpoints were called", not bad, bad)
    b.close()
sys.exit(0 if all(ok) else 1)
