"""Checks that this app can save a session into your real Assessment folder (macOS can block Terminal from the
Desktop). Writes, reads back and deletes one small hidden test file; leaves nothing behind.
Run from this folder:  python3 check_session_folder.py"""
import json
import os
import secrets
import sys

import app

root = app.ASSESSMENT
probe = root / f".session-probe-{secrets.token_hex(4)}"
print("Assessment folder:", root)
try:
    app._atomic_write_json(probe / "manifest.json", {"probe": True})
    ok = json.loads((probe / "manifest.json").read_text(encoding="utf-8")) == {"probe": True}
    (probe / "manifest.json").unlink()
    probe.rmdir()
    print("OK: saved, read back and removed a test file." if ok else "PROBLEM: the file read back differently.")
    sys.exit(0 if ok else 1)
except OSError as e:
    print(f"CANNOT SAVE HERE: {e.strerror or e}")
    print("If macOS blocked it: System Settings > Privacy & Security > Files and Folders (or Full Disk Access),")
    print("allow Terminal (or the app launcher you start this from) to use the Desktop folder, then run this again.")
    for leftover in (probe,):
        try:
            os.remove(leftover / "manifest.json")
            leftover.rmdir()
        except OSError:
            pass
    sys.exit(1)
