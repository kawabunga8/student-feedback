"""A small local job queue for work that takes a while and must survive a restart.

- One worker thread runs one job at a time, in the order they were queued.
- The journal is a SQLite file. It holds only progress and recovery information (ids, states, counts, times, short
  error text). It never holds student names, work or feedback. A job's inputs and results live in a sidecar file in
  the assignment's own Assessment folder (`.jobs/<job id>.json`), next to the session, outside git.
- A job's state is one of: queued, running, completed, failed, cancelled, interrupted (the app stopped while it was
  running), waiting_for_sign_in and needs_teacher_input (for later browser jobs). `waiting_for_sign_in` is used by Teams reads; `needs_teacher_input` isn't used yet.
- On start, a job that was running is marked `interrupted`; its unfinished items go back to queued. Nothing resumes by
  itself: the teacher chooses Resume. Finished items are never redone.
- A job that was queued but hadn't started simply runs.
- Cancelling takes effect between items: an item already being written finishes (a model call can't be interrupted).
"""
import json
import secrets
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

STATES = ("queued", "running", "completed", "failed", "cancelled", "interrupted", "waiting_for_sign_in", "needs_teacher_input")
RESUMABLE = ("interrupted", "failed", "waiting_for_sign_in")


def _now():
    return datetime.now().astimezone().isoformat(timespec="seconds")


class NeedsSignIn(Exception):
    """The job needs the teacher to sign in (in the browser window it opened). Unfinished items stay queued; Resume
    continues. State: waiting_for_sign_in."""


class JobFailed(Exception):
    """Stop the whole job (for example the model engine isn't running). Unfinished items stay queued, so Resume works."""


class JobQueue:
    def __init__(self, db_path, handlers, resolve_folder, write_json, read_json):
        self.db_path = Path(db_path)
        self.handlers = handlers                  # job type -> function(queue, job_row_dict)
        self.resolve_folder = resolve_folder      # relative folder -> absolute Path inside Assessment (raises if outside)
        self.write_json, self.read_json = write_json, read_json
        self._wake = threading.Event()
        self._stop = False
        self._thread = None
        self._file_lock = threading.Lock()        # sidecar read-modify-write
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._db() as c:
            c.executescript("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY, type TEXT NOT NULL, assignment TEXT NOT NULL, folder TEXT NOT NULL,
                    state TEXT NOT NULL, created TEXT, started TEXT, finished TEXT, error TEXT DEFAULT '',
                    cancel INTEGER DEFAULT 0, total INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS items (
                    job_id TEXT NOT NULL, idx INTEGER NOT NULL, key TEXT NOT NULL, state TEXT NOT NULL,
                    error TEXT DEFAULT '', work_sha TEXT DEFAULT '', delivered INTEGER DEFAULT 0,
                    PRIMARY KEY (job_id, idx));""")
            # The app stopped while these were running: they wait for the teacher.
            c.execute("UPDATE items SET state='queued' WHERE state='running'")
            c.execute("UPDATE jobs SET state='interrupted', cancel=0 WHERE state='running'")

    def _db(self):
        c = sqlite3.connect(self.db_path, timeout=15)
        c.row_factory = sqlite3.Row
        return _Ctx(c)

    # ------------------------------------------------------------------ requests from the app
    def enqueue(self, jtype, assignment, folder, request, items):
        """request: everything the job needs (kept in the sidecar). items: [{key, work_sha, ...request data}]."""
        if jtype not in self.handlers:
            raise ValueError("unknown job type")
        if not items:
            raise ValueError("nothing to do")
        jid = f"job-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"
        d = self.resolve_folder(folder) / ".jobs"
        self.write_json(d / f"{jid}.json", {"type": jtype, "assignment": assignment, "request": request,
                                              "items": [{**it, "idx": i} for i, it in enumerate(items)], "results": {}})
        with self._db() as c:
            c.execute("INSERT INTO jobs (id,type,assignment,folder,state,created,total) VALUES (?,?,?,?,?,?,?)",
                      (jid, jtype, assignment, folder, "queued", _now(), len(items)))
            c.executemany("INSERT INTO items (job_id,idx,key,state,work_sha) VALUES (?,?,?,?,?)",
                          [(jid, i, it["key"], "queued", it.get("work_sha", "")) for i, it in enumerate(items)])
        self._wake.set()
        return self.get(jid)

    def get(self, jid, with_results=False):
        with self._db() as c:
            row = c.execute("SELECT * FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row:
                raise FileNotFoundError(jid)
            items = [dict(r) for r in c.execute("SELECT idx,key,state,error,work_sha,delivered FROM items WHERE job_id=? ORDER BY idx", (jid,))]
        job = dict(row)
        job["items"] = items
        job["counts"] = {s: sum(1 for i in items if i["state"] == s) for s in ("queued", "running", "done", "failed", "cancelled")}
        if with_results:
            sidecar = self._sidecar(job)
            res = sidecar.get("results", {})
            job["drafts"] = [{"key": i["key"], "work_sha": i["work_sha"], **res[i["key"]]} for i in items
                             if i["state"] == "done" and not i["delivered"] and i["key"] in res]
            job["basis"] = (sidecar.get("request") or {}).get("basis", "")
            job["overwrite"] = bool((sidecar.get("request") or {}).get("overwrite"))
        return job

    def list_for(self, assignment, limit=10):
        with self._db() as c:
            ids = [r["id"] for r in c.execute("SELECT id FROM jobs WHERE assignment=? ORDER BY created DESC, id DESC LIMIT ?", (assignment, limit))]
        return [self.get(i) for i in ids]

    def cancel(self, jid):
        with self._db() as c:
            row = c.execute("SELECT state FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row:
                raise FileNotFoundError(jid)
            if row["state"] == "running":
                c.execute("UPDATE jobs SET cancel=1 WHERE id=?", (jid,))
            elif row["state"] in ("queued", "interrupted", "failed", "waiting_for_sign_in", "needs_teacher_input"):
                c.execute("UPDATE items SET state='cancelled' WHERE job_id=? AND state IN ('queued','failed','running')", (jid,))
                c.execute("UPDATE jobs SET state='cancelled', finished=? WHERE id=?", (_now(), jid))
        return self.get(jid)

    def resume(self, jid):
        with self._db() as c:
            row = c.execute("SELECT state FROM jobs WHERE id=?", (jid,)).fetchone()
            if not row:
                raise FileNotFoundError(jid)
            if row["state"] not in RESUMABLE:
                raise ValueError(f"a {row['state']} job can't be resumed")
            c.execute("UPDATE items SET state='queued', error='' WHERE job_id=? AND state IN ('failed','running')", (jid,))
            c.execute("UPDATE jobs SET state='queued', error='', cancel=0, finished=NULL WHERE id=?", (jid,))
        self._wake.set()
        return self.get(jid)

    def mark_delivered(self, jid, keys):
        with self._db() as c:
            c.executemany("UPDATE items SET delivered=1 WHERE job_id=? AND key=?", [(jid, k) for k in keys])
        return self.get(jid, with_results=True)

    # ------------------------------------------------------------------ for handlers
    def _sidecar_path(self, job):
        return self.resolve_folder(job["folder"]) / ".jobs" / f"{job['id']}.json"

    def _sidecar(self, job):
        return self.read_json(self._sidecar_path(job), {}) or {}

    def request_of(self, job):
        return self._sidecar(job)

    def next_item(self, jid):
        with self._db() as c:
            r = c.execute("SELECT idx,key FROM items WHERE job_id=? AND state='queued' ORDER BY idx LIMIT 1", (jid,)).fetchone()
            if r:
                c.execute("UPDATE items SET state='running' WHERE job_id=? AND idx=?", (jid, r["idx"]))
            return dict(r) if r else None

    def cancel_requested(self, jid):
        with self._db() as c:
            r = c.execute("SELECT cancel FROM jobs WHERE id=?", (jid,)).fetchone()
            return bool(r and r["cancel"])

    def item_finished(self, job, idx, key, state, error="", result=None):
        """Record one item. The result goes to the sidecar first, then the journal, so a crash between the two
        redoes at most that one item and never loses a finished one."""
        if result is not None:
            with self._file_lock:
                path = self._sidecar_path(job)
                data = self.read_json(path, {}) or {}
                data.setdefault("results", {})[key] = {**result, "at": _now()}
                self.write_json(path, data)
        with self._db() as c:
            c.execute("UPDATE items SET state=?, error=? WHERE job_id=? AND idx=?", (state, error[:300], job["id"], idx))

    def _finish(self, jid, state, error=""):
        with self._db() as c:
            if state == "cancelled":
                c.execute("UPDATE items SET state='cancelled' WHERE job_id=? AND state='queued'", (jid,))
            c.execute("UPDATE jobs SET state=?, error=?, finished=?, cancel=0 WHERE id=?", (state, error[:300], _now(), jid))

    # ------------------------------------------------------------------ the worker
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop = False
        self._thread = threading.Thread(target=self._loop, name="job-worker", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop = True
        self._wake.set()

    def _loop(self):
        while not self._stop:
            with self._db() as c:
                row = c.execute("SELECT id FROM jobs WHERE state='queued' ORDER BY created, id LIMIT 1").fetchone()
                if row:
                    c.execute("UPDATE jobs SET state='running', started=COALESCE(started, ?), error='' WHERE id=?", (_now(), row["id"]))
            if not row:
                self._wake.wait(1.0)
                self._wake.clear()
                continue
            job = self.get(row["id"])
            try:
                self.handlers[job["type"]](self, job)
                left = self.get(job["id"])["counts"]["queued"]
                self._finish(job["id"], "cancelled" if left and self.cancel_requested(job["id"]) else "completed")
            except NeedsSignIn as e:
                with self._db() as c:
                    c.execute("UPDATE items SET state='queued' WHERE job_id=? AND state='running'", (job["id"],))
                self._finish(job["id"], "waiting_for_sign_in", str(e))
            except JobFailed as e:
                with self._db() as c:      # unfinished items stay queued: Resume continues from here
                    c.execute("UPDATE items SET state='queued' WHERE job_id=? AND state='running'", (job["id"],))
                self._finish(job["id"], "failed", str(e))
            except Exception as e:
                with self._db() as c:
                    c.execute("UPDATE items SET state='queued' WHERE job_id=? AND state='running'", (job["id"],))
                self._finish(job["id"], "failed", f"{type(e).__name__}: {e}")


class _Ctx:
    """sqlite3 connection that commits and closes on exit."""
    def __init__(self, conn):
        self.c = conn

    def __enter__(self):
        return self.c

    def __exit__(self, *exc):
        try:
            self.c.commit() if exc[0] is None else self.c.rollback()
        finally:
            self.c.close()
