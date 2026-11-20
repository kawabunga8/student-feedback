"""Observation routes against the real app in a throwaway HOME: save/load, versions, notes for drafting, claim check,
evidence links, guards. Invented students only; no model, browser, SharePoint or media is touched."""
import json, os, subprocess, sys, tempfile, time, urllib.request, urllib.error
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
env = {**os.environ, "HOME": HOME, "NO_BROWSER": "1"}
p = subprocess.Popen([sys.executable, "app.py"], cwd=APPDIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))
def call(method, path, body=None, headers=None):
    h = {"Content-Type": "application/json", **(headers or {})}
    req = urllib.request.Request("http://127.0.0.1:8765" + path, data=None if body is None else json.dumps(body).encode(), headers=h if method == "POST" else {}, method=method)
    try:
        with urllib.request.urlopen(req) as r: return r.status, r.read()
    except urllib.error.HTTPError as e: return e.code, e.read()
def J(method, path, body=None, headers=None):
    s, b = call(method, path, body, headers)
    try: return s, json.loads(b or b"{}")
    except ValueError: return s, {}
try:
    for _ in range(60):
        try: urllib.request.urlopen("http://127.0.0.1:8765/api/assignments", timeout=1); break
        except Exception: time.sleep(0.25)
    else: raise SystemExit("app did not start")

    s, page = call("GET", "/")
    check("1 the page loads the Observe script", b'/ui/observe.js' in page)
    s, js = call("GET", "/ui/observe.js")
    check("2 the script is served", s == 200 and b"Performance observations" in js)

    s, d = J("POST", "/api/assignments", {"assignment": {"title": "Scales 1", "term": "Q1", "course": {"name": "Band 10 (Q1)", "label": "Band 10 (Q1)", "schoolYear": "2026-27"},
        "design": {"criteria": [{"text": "Rhythm and tempo"}, {"text": "Tone quality"}]}}})
    aid = d["assignment"]["id"]
    s, d = J("GET", f"/api/observations?assignment={aid}")
    check("3 before a session exists, observations ask the teacher to save the session first", "Save the assessment session" in d.get("error", ""), d)

    s, d = J("POST", "/api/session", {"assignment": aid, "baseVersion": None, "students": [{"student_id": "s1", "name": "Ada Test", "work": "w"}, {"student_id": "s2", "name": "Bo Sample", "work": "w"}]})
    check("4 a session saves", "error" not in d, d)
    man = None
    for dp, dn, fn in os.walk(HOME):
        if "manifest.json" in fn: man = os.path.join(dp, "manifest.json")
    before = open(man, "rb").read()
    s, d = J("GET", f"/api/observations?assignment={aid}")
    check("5 empty observations: version 0, criteria from the assignment, four levels", d.get("version") == 0 and [c["text"] for c in d["criteria"]] == ["Rhythm and tempo", "Tone quality"] and d["levels"] == ["Emerging", "Developing", "Proficient", "Extending"] and d["students"] == {}, d)

    obs = {"s1": {"status": "observed", "criteria": [{"id": "0", "level": "Proficient", "note": "steady tempo throughout", "ts": "1:24"}, {"id": "1", "level": "", "note": ""}], "strengths": "confident tone", "next_step": "watch the last four bars"}}
    s, d = J("POST", "/api/observations", {"assignment": aid, "baseVersion": 0, "students": obs})
    check("6 saving returns version 1 and the saved observation", s == 200 and d["version"] == 1 and d["students"]["s1"]["criteria"][0]["note"] == "steady tempo throughout", d)
    check("7 an unchosen level stays unchosen (nothing pre-filled)", d["students"]["s1"]["criteria"][1]["level"] == "")
    n = d["notes"]["s1"]
    check("8 notes for drafting carry the teacher's words with criterion labels and no levels", "Rhythm and tempo: steady tempo throughout (at 1:24)" in n and not any(l in n for l in ("Emerging", "Developing", "Proficient", "Extending")), n)
    s, d2 = J("POST", "/api/observations", {"assignment": aid, "baseVersion": 0, "students": {}})
    check("9 a stale save is refused with 409 and the current copy", s == 409 and d2.get("conflict") and d2["current"]["version"] == 1, (s, d2))
    s, d3 = J("GET", f"/api/observations?assignment={aid}")
    check("10 the refused save changed nothing", d3["students"]["s1"]["status"] == "observed" and d3["version"] == 1)
    check("11 saving observations does not touch the session manifest", open(man, "rb").read() == before)

    s, d = J("POST", "/api/observation-claims", {"assignment": aid, "key": "s1", "draft": "You kept a steady tempo throughout. Your vibrato was beautiful and your breath control was outstanding."})
    check("12 claim check flags the invented sentence only", len(d["unsupported"]) == 1 and "vibrato" in d["unsupported"][0], d)

    ev = {"students": {"s1": {"name": "Ada Test", "items": [
        {"name": "take1.mov", "kind": "video", "bytes": 2048, "url": "https://rcschool.sharepoint.com/sites/x/take1.mov"},
        {"name": "bad1.mov", "kind": "video", "bytes": 1, "url": "http://rcschool.sharepoint.com/x"},
        {"name": "bad2.mov", "kind": "video", "bytes": 1, "url": "https://evil.example.com/x"},
        {"name": "bad3.mov", "kind": "video", "bytes": 1, "url": "javascript:alert(1)"},
        {"name": "bad4.mov", "kind": "video", "bytes": 1, "url": "https://user:pw@rcschool.sharepoint.com/x"}]}}}
    json.dump(ev, open(os.path.join(os.path.dirname(man), "evidence.json"), "w"))
    s, d = J("GET", f"/api/observations?assignment={aid}")
    urls = {i["name"]: i["url"] for i in d["evidence"]["s1"]}
    check("13 only https SharePoint links without credentials are kept", urls["take1.mov"].startswith("https://rcschool.sharepoint.com/") and all(urls[k] == "" for k in ("bad1.mov", "bad2.mov", "bad3.mov", "bad4.mov")), urls)

    s, d = J("POST", "/api/observations", {"assignment": aid, "baseVersion": 1, "students": obs}, {"Origin": "https://evil.example.com"})
    check("14 a POST from another website's origin is refused", s == 403)
    s, d = J("GET", "/api/observations?assignment=../../etc")
    check("15 a bad assignment id is an error, not a crash or a file read", "error" in d, d)
    s, d = J("POST", "/api/observations", {"assignment": aid, "baseVersion": 1, "students": {"s1": {"status": "observed", "reviewed": True, "approval": {"bound": "x"}}}})
    check("16 review or approval flags in the input are ignored", "reviewed" not in d["students"]["s1"] and "approval" not in d["students"]["s1"], d["students"]["s1"])
    s, d = J("GET", f"/api/evidence-listing?assignment={aid}")
    check("17 before any run the listing status is idle", d == {"state": "idle"}, d)
    for bad in ("http://rcschool.sharepoint.com/sites/x", "https://evil.example.com/sites/x", "https://sharepoint.com.evil.com/sites/x", "", "https://user:pw@rcschool.sharepoint.com/sites/x"):
        s, d = J("POST", "/api/evidence-listing", {"assignment": aid, "site": bad})
        if "error" not in d: check("18 a bad site address is refused: " + bad, False, d); break
    else: check("18 non-SharePoint, http and credentialed site addresses are refused", True)
    s, d = J("POST", "/api/evidence-listing", {"assignment": aid, "site": "https://rcschool.sharepoint.com/sites/RCS-D-Test"})
    check("19 under the test guard the listing refuses to start a browser", d.get("state") == "error" and d.get("kind") == "setup", d)
    s, d = J("GET", f"/api/evidence-listing?assignment={aid}")
    check("20 the status then reports that error with no names", d.get("state") == "error" and "Ada" not in json.dumps(d), d)
    s, d = J("POST", "/api/evidence-listing", {"assignment": aid, "site": "https://rcschool.sharepoint.com/sites/x"}, {"Origin": "https://evil.example.com"})
    check("21 the button's route refuses another website's origin", s == 403)
    s, d = J("GET", "/api/evidence-listing?assignment=../../etc")
    check("22 a bad assignment id is an error on the status route too", "error" in d, d)
finally:
    p.terminate()
    try: p.wait(5)
    except Exception: p.kill()
sys.exit(0 if all(ok) else 1)
