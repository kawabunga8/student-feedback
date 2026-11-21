"""Background runner for the "Load evidence list from SharePoint" button.

Starts sharepoint_listing.py in its own process (it owns the browser and the profile lock), then matches the listing to the
roster and saves evidence.json (metadata only) beside the assignment's session. One run at a time. Status is counts and
plain messages only: no student or file names are ever put in it. The entries file the listing writes is deleted once
evidence.json is saved. See docs/BAND-PERFORMANCE-EVIDENCE-DESIGN.md.
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

import evidence_collect as E

MESSAGES = {
    "sign_in": "Sign in to Microsoft in the Chrome window that opened, then press the button again.",
    "blocked": "RCS sign-in policy blocked the browser. Ask RCS IT, or use a downloaded folder with evidence_collect.py.",
    "setup": "The browser reader isn't set up on this computer (see the setup lines in tools/spike_onenote_text.py).",
    "busy": "Chrome already has the app's browser profile open. Close that Chrome window and try again.",
    "differs": "The browser ended up on a different site than the team site; nothing was read.",
}


def _clean_status(**kw):
    return {k: v for k, v in kw.items()}


class Runner:
    def __init__(self, command=None, timeout=900):
        self.command = command or self._default_command
        self.timeout = timeout
        self._lock = threading.Lock()
        self._status = {}          # assignment id -> status dict
        self._running = None       # assignment id currently running

    @staticmethod
    def _default_command(site, out):
        py = Path.home() / ".venvs" / "student-feedback-tools" / "bin" / "python"
        here = Path(__file__).resolve().parent
        return [str(py if py.exists() else sys.executable), str(here / "sharepoint_listing.py"), "--site", site, "--out", out]

    def status(self, aid):
        with self._lock:
            return dict(self._status.get(aid) or {"state": "idle"})

    def start(self, aid, site, folder, title, roster_fn):
        """Begin a run. `roster_fn()` returns the roster (called on the worker thread); `folder` is the session folder."""
        with self._lock:
            if self._running:
                raise ValueError("An evidence listing is already running. Wait for it to finish.")
            if os.environ.get("SF_FORBID_BROWSER"):
                self._status[aid] = {"state": "error", "kind": "setup", "message": "Browser use is switched off (SF_FORBID_BROWSER is set)."}
                return dict(self._status[aid])
            self._running = aid
            self._status[aid] = {"state": "running", "message": "Opening the team site in Chrome. If it asks you to sign in, do that in the Chrome window."}
        threading.Thread(target=self._work, args=(aid, site, Path(folder), title, roster_fn), daemon=True).start()
        return self.status(aid)

    def _set(self, aid, **kw):
        with self._lock:
            self._status[aid] = _clean_status(**kw)

    def _work(self, aid, site, folder, title, roster_fn):
        entries_path = None
        try:
            fd, entries_path = tempfile.mkstemp(prefix="sf-entries-", suffix=".json")
            os.close(fd)
            os.chmod(entries_path, 0o600)
            try:
                proc = subprocess.run(self.command(site, entries_path), capture_output=True, text=True, timeout=self.timeout)
            except subprocess.TimeoutExpired:
                return self._set(aid, state="error", kind="error", message="The listing took too long and was stopped.")
            line = next((l for l in reversed((proc.stdout or "").splitlines()) if l.strip().startswith("{")), "")
            try:
                out = json.loads(line)
            except ValueError:
                out = {}
            if proc.returncode != 0 or not out.get("ok"):
                kind = str(out.get("kind") or "error")
                return self._set(aid, state="error", kind=kind, message=MESSAGES.get(kind) or "The listing didn't finish. Nothing was saved.")
            entries = json.loads(Path(entries_path).read_text(encoding="utf-8"))
            try:
                roster = roster_fn()
            except Exception as e:
                return self._set(aid, state="error", kind="roster", message=f"Couldn't get the class list from Course Hub: {str(e)[:120]}")
            res = E.build(entries, roster, title)
            tmp = folder / "evidence.json.tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump({"students": res["students"]}, f, indent=1, ensure_ascii=False)
            os.replace(tmp, folder / "evidence.json")
            self._set(aid, state="done", counts=E.counts(res),
                      message="Evidence list saved. File names and links are shown only to you, on this computer.")
        except Exception as e:
            self._set(aid, state="error", kind="error", message=f"The listing failed ({type(e).__name__}). Nothing was saved.")
        finally:
            if entries_path:
                try: os.unlink(entries_path)
                except OSError: pass
            with self._lock:
                self._running = None
