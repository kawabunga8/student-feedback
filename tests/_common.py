"""Shared setup for the tests: where the app is, where screenshots go, which browser to use.

Every test builds its own temporary HOME before importing the app, so nothing here touches your real
Assessment folder, Application Support folder or Chrome profile. Optional: pass an app folder as argv[1] and a
screenshot folder as argv[2]."""
import os
import sys
import tempfile

REAL_HOME = os.path.realpath(os.path.expanduser("~"))
os.environ["SF_FORBID_BROWSER"] = "1"      # inherited by any process a test starts: no browser profile, no live Teams
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APPDIR = sys.argv[1] if len(sys.argv) > 1 else ROOT
SHOTS = sys.argv[2] if len(sys.argv) > 2 else tempfile.mkdtemp(prefix="sf-test-shots-")
# Playwright's own Chromium by default; TEST_BROWSER_CHANNEL=chrome uses the Google Chrome installed on this computer.
LAUNCH = {"channel": os.environ["TEST_BROWSER_CHANNEL"]} if os.environ.get("TEST_BROWSER_CHANNEL") else {}


def guard(home):
    """Refuse to run unless HOME is a fresh temporary folder, so the real Assessment folder, Application Support folder
    and Chrome profile can't be touched."""
    h = os.path.realpath(home)
    if h == REAL_HOME or not h.startswith(os.path.realpath(tempfile.gettempdir())):
        raise SystemExit(f"Refusing to run: HOME ({home}) is not a temporary folder.")
    if os.path.realpath(os.path.expanduser("~")) != h:
        raise SystemExit("Refusing to run: the process's HOME doesn't point at the temporary folder.")


def guard_app(app, home):
    """After importing app / teams_read, check that every data path they computed is inside the temporary HOME."""
    for name in ("APP_DATA", "ASSESSMENT", "ASSIGNMENTS_DIR"):
        v = getattr(app, name, None)
        if v is not None and not os.path.realpath(str(v)).startswith(os.path.realpath(home)):
            raise SystemExit(f"Refusing to run: app.{name} ({v}) is outside the temporary HOME.")


def block_live_browser(T):
    """Make any attempt to start a browser from teams_read raise, whatever else goes wrong."""
    def _no(*a, **k):
        raise AssertionError("A test tried to open a browser profile. Tests must use a stand-in reader.")
    T._launch = _no
    if not str(T.PROFILE).startswith(os.path.realpath(os.environ["HOME"])) and not str(T.PROFILE).startswith(os.environ["HOME"]):
        raise SystemExit(f"Refusing to run: Chrome profile path {T.PROFILE} is outside the temporary HOME.")
