#!/usr/bin/env python3
"""Run every test in this folder, one after another, and print a one-line result for each.

    python3 tests/run_all.py            (or: ~/.venvs/student-feedback-tools/bin/python tests/run_all.py)

Needs Playwright with a browser (see tests/README.md). The tests start their own copy of the app on 127.0.0.1:8765 and
a stand-in model server on 127.0.0.1:11434, so STOP the real app and Ollama first: this script checks both ports and
refuses to run if either is busy. Tests use a throwaway HOME, so your Assessment folder, Application Support folder and
Chrome profile are never touched."""
import glob
import os
import socket
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def port_free(port):
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)     # a port in TIME_WAIT after a previous run is free; a listener still is not
    try:
        s.bind(("127.0.0.1", port))
        return True
    except OSError:
        return False
    finally:
        s.close()


def main():
    busy = [p for p in (8765, 11434) if not port_free(p)]
    if busy:
        print(f"Port {', '.join(map(str, busy))} is in use. Quit the feedback app (8765) and Ollama (11434), then run again.")
        return 2
    results, failed = [], 0
    for path in sorted(glob.glob(os.path.join(HERE, "test_*.py"))):
        name = os.path.basename(path)
        r = subprocess.run([sys.executable, path], capture_output=True, text=True, cwd=HERE)
        lines = r.stdout.splitlines()
        passed = sum(1 for l in lines if l.startswith("PASS"))
        failures = [l for l in lines if l.startswith("FAIL")]
        ok = r.returncode == 0 and not failures
        failed += 0 if ok else 1
        results.append((name, ok, passed, failures, r))
        print(f"{'ok  ' if ok else 'FAIL'} {name}: {passed} checks passed" + ("" if ok else f", {len(failures)} failed (exit {r.returncode})"))
        if not ok:
            for l in failures[:10]:
                print("     " + l[:200])
            if not failures:
                print("     " + (r.stderr.strip().splitlines() or ["(no output)"])[-1][:200])
    print(f"\n{sum(r[2] for r in results)} checks passed in {len(results)} files; {failed} file(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
