"""The "Load evidence list" runner: success path, error mapping, one run at a time, timeout, cleanup, no names in
status. A stand-in command replaces the browser listing; invented students; nothing contacts SharePoint or Chrome."""
import json, os, stat, sys, tempfile, time
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
os.environ.pop("SF_FORBID_BROWSER", None)          # the runner's own guard is tested separately below
import evidence_runner as ER
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))
R = [{"id": "1", "first": "Ada", "last": "Test"}, {"id": "2", "first": "Bo", "last": "Sample"}, {"id": "3", "first": "Cy", "last": "Demo"}]
ENTRIES = [{"path": "Ada Test/Scales 1/take1.mov", "bytes": 4096, "modified": "1", "url": "https://rcschool.sharepoint.com/sites/x/take1.mov"},
           {"path": "Zed Unknown/Scales 1/z.mov", "bytes": 1, "modified": "1", "url": ""}]
def fake(entries=None, code=0, out_json=None, sleep=0, sink=None):
    script = ("import sys,json,time\nout=sys.argv[sys.argv.index('--out')+1]\n" + (f"time.sleep({sleep})\n" if sleep else "") +
              (f"json.dump({entries!r},open(out,'w'))\n" if entries is not None else "") +
              f"print({json.dumps(json.dumps(out_json))})\nsys.exit({code})\n")
    def cmd(site, out):
        if sink is not None: sink.append(out)
        return [sys.executable, "-c", script, "--site", site, "--out", out]
    return cmd
def wait(r, aid, secs=20):
    end = time.time() + secs
    while time.time() < end:
        s = r.status(aid)
        if s["state"] != "running": return s
        time.sleep(0.05)
    return r.status(aid)

# success
folder = tempfile.mkdtemp(); outs = []
r = ER.Runner(command=fake(ENTRIES, 0, {"ok": True, "files": 2}, sink=outs))
s0 = r.start("a1", "https://rcschool.sharepoint.com/sites/x", folder, "Scales 1", lambda: R)
check("1 start returns running at once", s0["state"] == "running")
s = wait(r, "a1")
check("2 a successful run is done with counts only", s["state"] == "done" and s["counts"]["students_with_evidence"] == 1 and s["counts"]["flagged"] == 1 and s["counts"]["no_evidence"] == 2, s)
check("3 status contains no student or file names", not any(n in json.dumps(s) for n in ("Ada", "Zed", "take1", "Bo", "Cy")), s)
ev = json.load(open(os.path.join(folder, "evidence.json")))
check("4 evidence.json holds metadata for the matched student", ev["students"]["1"]["items"][0]["name"] == "take1.mov" and ev["students"]["1"]["items"][0]["kind"] == "video")
check("5 evidence.json is owner-only and no temp is left", stat.S_IMODE(os.stat(os.path.join(folder, "evidence.json")).st_mode) == 0o600 and not [f for f in os.listdir(folder) if f.endswith(".tmp")], os.listdir(folder))
check("6 the temporary entries file is deleted afterwards", outs and not os.path.exists(outs[0]), outs)
check("7 the runner is free again", r._running is None)

# errors map to plain messages and save nothing
for kind, text in (("sign_in", "Sign in to Microsoft"), ("blocked", "RCS sign-in policy"), ("setup", "isn't set up"), ("busy", "profile open"), ("differs", "different site")):
    fo = tempfile.mkdtemp(); rr = ER.Runner(command=fake(None, {"sign_in": 5, "blocked": 2, "setup": 3, "busy": 6, "differs": 7}[kind], {"ok": False, "kind": kind, "error": "x"}))
    rr.start("a", "https://rcschool.sharepoint.com/sites/x", fo, "Scales 1", lambda: R); s = wait(rr, "a")
    check(f"8 {kind}: plain message, error state, nothing saved", s["state"] == "error" and s["kind"] == kind and text in s["message"] and not os.path.exists(os.path.join(fo, "evidence.json")), s)
fo = tempfile.mkdtemp(); rr = ER.Runner(command=fake(None, 0, None))
rr.start("a", "https://rcschool.sharepoint.com/sites/x", fo, "Scales 1", lambda: R); s = wait(rr, "a")
check("9 garbled output from the listing is an error, nothing saved", s["state"] == "error" and not os.path.exists(os.path.join(fo, "evidence.json")), s)

# roster failure
fo = tempfile.mkdtemp(); rr = ER.Runner(command=fake(ENTRIES, 0, {"ok": True}))
def bad(): raise RuntimeError("Course Hub is down")
rr.start("a", "https://rcschool.sharepoint.com/sites/x", fo, "Scales 1", bad); s = wait(rr, "a")
check("10 a roster failure is reported and nothing is saved", s["state"] == "error" and s["kind"] == "roster" and "Course Hub is down" in s["message"] and not os.path.exists(os.path.join(fo, "evidence.json")), s)

# one at a time
fo = tempfile.mkdtemp(); rr = ER.Runner(command=fake(ENTRIES, 0, {"ok": True}, sleep=1.5))
rr.start("a", "https://rcschool.sharepoint.com/sites/x", fo, "Scales 1", lambda: R)
try: rr.start("b", "https://rcschool.sharepoint.com/sites/y", fo, "Scales 1", lambda: R); refused = False
except ValueError: refused = True
check("11 a second run is refused while one is running", refused)
check("12 the first run still finishes", wait(rr, "a")["state"] == "done")
check("13 a new run is allowed afterwards", rr.start("b", "https://rcschool.sharepoint.com/sites/y", fo, "Scales 1", lambda: R)["state"] == "running")
wait(rr, "b")

# timeout
fo = tempfile.mkdtemp(); rr = ER.Runner(command=fake(ENTRIES, 0, {"ok": True}, sleep=5), timeout=1)
rr.start("a", "https://rcschool.sharepoint.com/sites/x", fo, "Scales 1", lambda: R); s = wait(rr, "a")
check("14 a listing that hangs is stopped with a plain message", s["state"] == "error" and "too long" in s["message"] and rr._running is None, s)

# guard
os.environ["SF_FORBID_BROWSER"] = "1"
rr = ER.Runner(command=fake(ENTRIES, 0, {"ok": True}))
s = rr.start("a", "https://rcschool.sharepoint.com/sites/x", tempfile.mkdtemp(), "Scales 1", lambda: R)
check("15 under the test guard no process is started", s["state"] == "error" and s["kind"] == "setup" and rr._running is None, s)
check("16 an unknown assignment reports idle", ER.Runner().status("none") == {"state": "idle"})
sys.exit(0 if all(ok) else 1)
