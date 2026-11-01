"""teams_read.py: the shared-browser lock and argument checks. Never starts Chrome: both cases stop before it would."""
import json, os, subprocess, sys, tempfile
from _common import APPDIR, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import teams_read as T
block_live_browser(T)
ok = []
def check(label, cond, extra=""):
    ok.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:200]) if extra != "" else ""))
def run(*args):
    r = subprocess.run([sys.executable, "teams_read.py", *args], capture_output=True, text=True, env={**os.environ, "HOME": HOME}, timeout=60)
    return r.returncode, json.loads(r.stdout.strip().splitlines()[-1])
code, out = run("read")
check("1 read without --class and --title is refused", code == 1 and "needs --class and --title" in out["error"], out)
with T.BrowserLock():
    code, out = run("list")
    check("2 a second browser job is refused while the lock is held", code == 6 and out["kind"] == "busy" and "Browser profile in use" in out["error"], out)
try:
    with T.BrowserLock():
        with T.BrowserLock():
            check("  (the lock must not be re-entrant)", False)
except T.ReadError as e:
    check("3 taking the lock twice in one process is refused", e.kind == "busy")
with T.BrowserLock():
    pass
check("4 the lock is released afterwards", True)
try:
    T.Session(None, 1).click("grading-return", None)
    check("5 a click outside the allowlist is refused", False)
except T.ReadError as e:
    check("5 a click outside the allowlist is refused", e.kind == "differs" and "not allowed" in str(e), e)
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
