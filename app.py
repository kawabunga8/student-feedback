#!/usr/bin/env python3
"""Local web UI for feedback.py. Run:  python3 app.py
Opens http://127.0.0.1:8765 - served only on this laptop, talks only to a local model (Ollama or LM Studio)."""
import base64
import csv
import html
import io
import json
import re
import secrets
import subprocess
import tempfile
import zipfile
import threading
from pathlib import Path
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import feedback as fb
import hashlib
import sys
import jobs

HOST, PORT = "127.0.0.1", 8765
STANDARDS_DIR = Path(__file__).parent / "standards"  # drop learning-standards PDFs here
_cache = {}
_std_lock = threading.Lock()


NAME_LINE = re.compile(r"^\s*(?:student(?:\s+name)?|name)\s*[:\-\u2013]\s*(.+?)\s*$", re.I | re.M)
ID_LINE = re.compile(r"^\s*([A-Za-z]{1,2}\d{2,4})\b(?![.)])", re.M)  # e.g. "R002 ..." student codes, not "Q10." / "Q10)"
RULE_LINE = re.compile(r"^\s*(?:-{3,}|={3,}|_{3,})\s*$", re.M)


def _split_text(text, stem):
    """One document -> [(name, work)]. Splits on 'Name: X' lines, else on --- rules, else one student."""
    marks = list(NAME_LINE.finditer(text))
    if len(marks) >= 2:
        out = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            out.append((m.group(1), text[m.end():end].strip()))
        return [(n, w) for n, w in out if w]
    ids = list(ID_LINE.finditer(text))
    lead = [l for l in text[:ids[0].start()].splitlines() if l.strip()] if ids else []
    if len(ids) >= 2 and len(lead) <= 1:  # more than a title line before the first code: numbered questions, not codes
        out = []
        for i, m in enumerate(ids):
            end = ids[i + 1].start() if i + 1 < len(ids) else len(text)
            out.append((m.group(1), text[m.end():end].strip()))
        return [(n, w) for n, w in out if w]
    blocks = [b.strip() for b in RULE_LINE.split(text) if b.strip()]
    if len(blocks) >= 2:
        return [(f"{stem} {i}", b) for i, b in enumerate(blocks, 1)]
    return [(stem, text.strip())] if text.strip() else []


def read_xlsx(raw):
    """Minimal .xlsx reader (stdlib only): {sheet name: [[cell text, ...], ...]}. Values only, no formulas."""
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
          "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
    z = zipfile.ZipFile(io.BytesIO(raw))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall("pr:Relationship", ns)}
    def col(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group():
            n = n * 26 + ord(ch) - 64
        return n - 1
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", ns):
        target = rels[sh.get("{%s}id" % ns["r"])].lstrip("/")
        root = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
        rows = []
        for row in root.iter("{%s}row" % ns["m"]):
            cells = {}
            for c in row.findall("m:c", ns):
                t, v = c.get("t"), c.find("m:v", ns)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
                elif v is not None:
                    val = v.text or ""
                    if t is None and re.fullmatch(r"-?\d+\.0+", val):
                        val = val.split(".")[0]
                else:
                    val = ""
                cells[col(c.get("r"))] = val.strip()
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
        out[sh.get("name")] = rows
    return out


def rows_to_students(rows, stem):
    """Header row + one row per student -> [(name, work)]. Name column = a header with 'name'/'student'."""
    if len(rows) < 2:
        return []
    head = rows[0]
    name_i = next((i for i, h in enumerate(head) if re.search(r"name|student", h, re.I)), 0)
    # whole-heading match only, so questions like "Who is your target market?" are kept
    skip = re.compile(r"\s*(?:e-?mail(?: address)?|timestamp|id|(?:total )?(?:score|points?|marks?)|grade(?: level)?"
                      r"|submitted(?: at| on| date)?|date submitted)\s*", re.I)
    work_i = [i for i, h in enumerate(head) if i != name_i and not skip.fullmatch(h)]
    out = []
    for n, r in enumerate(rows[1:], 1):
        r = r + [""] * (len(head) - len(r))
        parts = [(head[i], r[i].strip()) for i in work_i if r[i].strip()]
        if not parts:
            continue
        work = parts[0][1] if len(parts) == 1 else "\n\n".join(f"{h}: {v}" for h, v in parts)
        out.append((r[name_i].strip() or f"{stem} {n}", work))
    return out


def teams_export(rows):
    """Recognise a Teams 'Assignment Data' export (Full Name / Assignments / Status columns).
    Returns only what the page needs: no emails, no feedback text."""
    for hi, row in enumerate(rows):
        low = [c.strip().lower() for c in row]
        if "full name" in low and "status" in low and "assignments" in low:
            ix = {h: low.index(h) for h in ("full name", "first name", "last name", "assignments", "due date", "status", "feedback") if h in low}
            title = next((c for r in rows[:hi] for c in r if c.strip()), "")
            studs, assigns, dues = [], {}, set()
            for r in rows[hi + 1:]:
                get = lambda k: r[ix[k]].strip() if k in ix and ix[k] < len(r) else ""
                name = get("full name") or (get("first name") + " " + get("last name")).strip()
                if not name:
                    continue
                first, last = get("first name"), get("last name")
                if not (first and last):
                    parts = name.split()
                    first, last = parts[0], " ".join(parts[1:])
                studs.append({"name": name, "first": first, "last": last, "status": get("status") or "Unknown",
                              "has_feedback": bool(get("feedback"))})
                assigns[get("assignments")] = assigns.get(get("assignments"), 0) + 1
                if get("due date"):
                    dues.add(get("due date"))
            due = ""
            for d in dues:
                due = (datetime(1899, 12, 30) + timedelta(days=int(float(d)))).strftime("%Y-%m-%d") if re.fullmatch(r"\d+(\.\d+)?", d) else d
            return {"title": title, "assignment": max(assigns, key=assigns.get) if assigns else "", "due": due, "students": studs}
    return None


def parse_upload(filename, raw, mode):
    ext = Path(filename).suffix.lower()
    stem = Path(filename).stem
    if ext == ".csv":
        return rows_to_students(list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace")))), stem)
    if ext == ".xlsx":
        sheets = read_xlsx(raw)
        for rows in sheets.values():
            teams = teams_export(rows)
            if teams:
                return {"teams": teams}
        first = next(iter(sheets.values()), [])
        first = [r for r in first if any(c.strip() for c in r)]
        return rows_to_students(first, stem)
    if ext == ".docx":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)
        text = html.unescape(re.sub(r"<[^>]+>", "", xml))
        return _split_text(text, stem) if mode != "whole" else [(stem, text.strip())]
    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
            t.write(raw)
            t.flush()
            text = subprocess.run(["pdftotext", t.name, "-"], capture_output=True, text=True).stdout
        if mode == "page":
            return [(f"{stem} p{i}", p.strip()) for i, p in enumerate(text.split("\f"), 1) if p.strip()]
        return _split_text(text, stem) if mode != "whole" else [(stem, text.strip())]
    text = raw.decode("utf-8-sig", "replace")
    return _split_text(text, stem) if mode != "whole" else [(stem, text.strip())]


# Saved assignment records and the Teams class -> Course Hub mapping. Outside this repo, next to the automation
# Chrome profile. They hold assignment details only, never student work.
APP_DATA = Path.home() / "Library" / "Application Support" / "student-feedback"
ASSIGNMENTS_DIR = APP_DATA / "assignments"
CLASS_MAP = APP_DATA / "class-map.json"
ASG_ID = re.compile(r"asg-[a-z0-9-]{6,48}")
RECORD_KEYS = ("id", "title", "course", "grade", "term", "teams", "instructions", "focus", "standards", "length", "design", "sources")


def _atomic_write_json(path, data):
    """Write JSON so an interrupted save can never leave a half-written file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _read_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def list_assignment_records():
    out = []
    for p in ASSIGNMENTS_DIR.glob("asg-*.json"):
        r = _read_json(p, None)
        if isinstance(r, dict) and r.get("id"):
            out.append({"id": r["id"], "title": r.get("title", ""), "course": (r.get("course") or {}).get("label", ""),
                        "version": r.get("version", 0), "updated": r.get("updated", "")})
    return sorted(out, key=lambda r: r["updated"], reverse=True)


def load_assignment_record(aid):
    if not ASG_ID.fullmatch(aid or ""):
        raise ValueError("bad assignment id")
    r = _read_json(ASSIGNMENTS_DIR / f"{aid}.json", None)
    if not isinstance(r, dict):
        raise FileNotFoundError(aid)
    return r


def _criteria_of(r):
    return [c.get("text", "") for c in ((r.get("design") or {}).get("criteria") or []) if isinstance(c, dict)]


class VersionConflict(Exception):
    """The record was saved somewhere else (another tab or window) after the page loaded it."""
    def __init__(self, current):
        super().__init__("saved elsewhere")
        self.current = current


_save_lock = threading.Lock()   # one save at a time, so two requests can't interleave a read and a write


def save_assignment_record(rec, base_version=None):
    """Save a new version of an assignment record. The history notes what changed, and whether the change can
    make existing drafts and review marks outdated (instructions, standards or success criteria).
    An update must name the version the page loaded (base_version). If the saved file has moved on since,
    nothing is written and VersionConflict carries the current record."""
    with _save_lock:
        return _save_assignment_record(rec, base_version)


def _save_assignment_record(rec, base_version):
    rec = {k: rec[k] for k in RECORD_KEYS if k in rec}
    aid = rec.get("id") or f"asg-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4)}"
    if not ASG_ID.fullmatch(aid):
        raise ValueError("bad assignment id")
    old = _read_json(ASSIGNMENTS_DIR / f"{aid}.json", None)
    old = old if isinstance(old, dict) else None
    if old and base_version != old.get("version"):
        raise VersionConflict(old)
    same = lambda k: json.dumps((old or {}).get(k), sort_keys=True) == json.dumps(rec.get(k), sort_keys=True)
    changed = [k for k in RECORD_KEYS if k not in ("id", "sources") and not same(k)] if old else ["created"]
    if old and not changed:
        return old
    content = bool(old) and (any(k in changed for k in ("instructions", "focus", "standards")) or _criteria_of(old) != _criteria_of(rec))
    kind = "created" if not old else "content" if content else "title" if changed == ["title"] else "details"
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    version = (old or {}).get("version", 0) + 1
    history = ((old or {}).get("history") or [])[-49:] + [{"version": version, "at": now, "changed": changed, "kind": kind}]
    rec.update(id=aid, version=version, created=(old or {}).get("created", now), updated=now, history=history)
    _atomic_write_json(ASSIGNMENTS_DIR / f"{aid}.json", rec)
    return rec


def save_class_mapping(p):
    """Shingo's confirmed link from a Teams class name to a Course Hub offering, per school year."""
    year, cls, course = str(p.get("schoolYear", "")).strip(), str(p.get("className", "")).strip(), p.get("course")
    if not year or not cls or not isinstance(course, dict) or not course.get("name"):
        raise ValueError("schoolYear, className and course are required")
    with _save_lock:
        m = _read_json(CLASS_MAP, {})
        m.setdefault(year, {})[cls] = {"name": course["name"], "label": course.get("label", ""),
                                       "sectionIds": course.get("sectionIds") or [],
                                       "confirmed": datetime.now().astimezone().isoformat(timespec="seconds")}
        _atomic_write_json(CLASS_MAP, m)
        return m


ASSESSMENT = Path.home() / "Desktop" / "Teaching" / "Assessment"   # Assessment/<year>/<quarter>/<course>/<assignment>/FirstName_LastName.txt
SESSION_INDEX = APP_DATA / "session-index.json"        # assignment id -> its folder under Assessment (bookkeeping only)
SESSION_TEXT = ("student_id", "name", "orig", "grade", "work", "notes", "level", "feedback", "myschool_comment", "basis")
_FS_BAD = re.compile(r'[\x00-\x1f/\\:*?"<>|]')


def _folder_part(value, fallback):
    s = re.sub(r"\s+", " ", _FS_BAD.sub(" ", str(value or ""))).strip(" .")[:80]
    return s or fallback


def session_folder(aid, rec):
    """The assignment's folder under Assessment, fixed the first time a session is saved (so renaming the assignment
    later never strands the work). Always inside Assessment."""
    index = _read_json(SESSION_INDEX, {})
    rel = index.get(aid)
    if not rel:
        course = rec.get("course") or {}
        rel = "/".join([_folder_part(course.get("schoolYear"), "unsorted"), _folder_part(rec.get("term"), "no term"),
                        _folder_part(course.get("label") or course.get("name"), "no course"), _folder_part(rec.get("title"), aid)])
        taken = {v.lower() for k, v in index.items() if k != aid}

        def other_owner(r):      # another assignment already uses this folder (by index, or by the manifest inside it)
            m = _read_json(ASSESSMENT / r / "manifest.json", None)
            return r.lower() in taken or (isinstance(m, dict) and (m.get("assignment") or {}).get("id") not in (None, aid))
        base, n = rel, 1
        while other_owner(rel):  # two assignments with the same name, course and term must never share a manifest
            n += 1
            rel = f"{base} ({n})"
    root = ASSESSMENT.resolve()
    d = (root / rel).resolve()
    if d == root or not d.is_relative_to(root):
        raise ValueError("bad session folder")
    return rel, d


def load_session(aid):
    """The saved assessment session for an assignment: {path, session} (session is None if there isn't one yet)."""
    rec = load_assignment_record(aid)
    rel, d = session_folder(aid, rec)
    s = _read_json(d / "manifest.json", None)
    s = s if isinstance(s, dict) else None
    return {"path": rel, "session": s, "status": session_status(s, rec) if s else None}


def _clean_snapshot(x):
    """An approval or posting tick: {bound, at}. `bound` is the exact reviewed values as JSON, kept so that
    whether the record is still approved is worked out from the stored fields every time it is opened."""
    if isinstance(x, dict) and isinstance(x.get("bound"), str) and len(x["bound"]) <= 400_000:
        return {"bound": x["bound"], "at": str(x.get("at") or x.get("reviewed_at") or "")[:40]}
    return None


def _clean_student(s):
    if not isinstance(s, dict):
        return None
    st = {k: str(s.get(k) or "")[:200_000] for k in SESSION_TEXT}
    if not (st["name"].strip() or st["work"].strip() or st["feedback"].strip()):
        return None
    st["approval"] = _clean_snapshot(s.get("approval"))
    post = s.get("posting") if isinstance(s.get("posting"), dict) else {}
    st["posting"] = {k: _clean_snapshot(post.get(k)) for k in ("teams", "myschool")}
    return st


AUTOMATED_POSTING = False   # No worker posts to Teams or MySchool. Any future worker must check this AND use approved_for_posting().
FOCUS_HEAD = "Teacher's feedback focus (not shown to students):"   # same text as ui/assignment.js


def compose_rubric(instructions, focus):
    """What Setup's instructions box holds for a saved assignment (mirrors composeRubric in ui/assignment.js)."""
    instructions = (instructions or "").strip()
    focus = [f.strip() for f in (focus or []) if isinstance(f, str) and f.strip()]
    if not focus:
        return instructions
    return (instructions + "\n\n" if instructions else "") + FOCUS_HEAD + "\nMust include:\n" + "\n".join("- " + f for f in focus)


def check_reviewed(bound, st, rec, stamp):
    """Is a review approval (or a posting tick) still valid? Judged by the server alone, from what is stored now:
    the student's saved values and the saved assignment record. `bound` is the exact reviewed values the page saved
    with it. `stamp` is {assignment_version, first_seen}, set by the server when it first saw this approval.
    Returns {current, reasons}; never stored as a yes/no."""
    try:
        b = json.loads(bound)
    except (TypeError, ValueError):
        b = None
    if not isinstance(b, dict):
        return {"current": False, "reasons": ["unreadable approval"]}
    course = rec.get("course") or {}
    want = {k: st.get(k, "") for k in ("student_id", "name", "work", "notes", "level", "feedback", "myschool_comment")}
    want.update(grade=st.get("grade") or rec.get("grade", ""), assignment=rec.get("title", ""),
                course=course.get("label", ""), school_year=course.get("schoolYear", ""), quarter=rec.get("term", ""))
    reasons = [k for k, v in want.items() if b.get(k) != v]
    if str(b.get("instructions", "")).strip() != compose_rubric(rec.get("instructions"), rec.get("focus")):
        reasons.append("instructions")
    labels = [x.get("label") for x in (b.get("standards") or []) if isinstance(x, dict)]
    if labels != list(rec.get("standards") or []):
        reasons.append("standards")
    since = int((stamp or {}).get("assignment_version") or 0)
    if any(h.get("version", 0) > since and h.get("kind") in ("content", "title") for h in (rec.get("history") or [])):
        reasons.append("assignment changed since approval")
    return {"current": not reasons, "reasons": reasons}


def session_status(session, rec):
    """Server-side validity of every approval and posting tick in a session, worked out fresh from the stored values."""
    out, approved = [], 0
    for st in session.get("students", []):
        one = {"student_id": st.get("student_id", ""), "approval": None, "posting": {}}
        ap = st.get("approval")
        if ap:
            one["approval"] = check_reviewed(ap["bound"], st, rec, ap.get("stamp"))
            approved += one["approval"]["current"]
        for k, t in (st.get("posting") or {}).items():
            if t:
                one["posting"][k] = check_reviewed(t["bound"], st, rec, t.get("stamp"))
        out.append(one)
    return {"students": out, "approved": approved, "assignment_version": rec.get("version", 0)}


def approved_for_posting(aid):
    """The only way a posting worker may read what to post: students whose approval the server finds current, with the
    approved values and which destinations are already ticked. Raises unless AUTOMATED_POSTING has been switched on."""
    if not AUTOMATED_POSTING:
        raise PermissionError("Automated posting is disabled.")
    rec = load_assignment_record(aid)
    _, d = session_folder(aid, rec)
    session = _read_json(d / "manifest.json", None)
    if not isinstance(session, dict):
        return []
    status = session_status(session, rec)["students"]
    return [{"student_id": st["student_id"], "name": st["name"], "level": st["level"], "feedback": st["feedback"],
             "myschool_comment": st["myschool_comment"],
             "ticked": {k: bool(t and status[i]["posting"].get(k, {}).get("current")) for k, t in st["posting"].items()}}
            for i, st in enumerate(session.get("students", [])) if status[i]["approval"] and status[i]["approval"]["current"]]


class SessionConflict(Exception):
    def __init__(self, current):
        super().__init__("session saved elsewhere")
        self.current = current


def save_session(aid, students, base_version):
    """Save the whole session (student work, drafts, levels, notes, comments, review approvals, posting ticks) to
    manifest.json in the assignment's Assessment folder. Atomic, and refused if it was saved elsewhere since this
    page loaded it (base_version)."""
    if not isinstance(students, list) or len(students) > 400:
        raise ValueError("students must be a list of at most 400")
    with _save_lock:
        rec = load_assignment_record(aid)
        rel, d = session_folder(aid, rec)
        old = _read_json(d / "manifest.json", None)
        old = old if isinstance(old, dict) else None
        if old and (old.get("assignment") or {}).get("id") not in (None, aid):
            raise ValueError("this folder holds another assignment's session")
        if base_version != (old or {}).get("version"):
            raise SessionConflict(old or {"version": 0})
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        before = {(o.get("student_id") or o.get("name")): o for o in (old or {}).get("students", [])}
        students = [c for c in map(_clean_student, students) if c]
        for st in students:     # stamp each approval and tick with the assignment version the server first saw it at
            was = before.get(st["student_id"] or st["name"]) or {}
            for holder, prior in ((st, was), (st["posting"], was.get("posting") or {})):
                for key in (("approval",) if holder is st else ("teams", "myschool")):
                    snap, old_snap = holder.get(key), (prior or {}).get(key)
                    if snap:
                        same = old_snap and old_snap.get("bound") == snap["bound"] and old_snap.get("at") == snap["at"]   # a fresh mark has a new time
                        snap["stamp"] = old_snap["stamp"] if same and old_snap.get("stamp") else {"assignment_version": rec.get("version", 0), "first_seen": now}
        session = {"format": 1, "assignment": {"id": aid, "title": rec.get("title", ""), "version": rec.get("version", 0)},
                   "students": students, "version": (old or {}).get("version", 0) + 1,
                   "created": (old or {}).get("created", now), "updated": now}
        _atomic_write_json(d / "manifest.json", session)
        idx = _read_json(SESSION_INDEX, {})
        if idx.get(aid) != rel:
            idx[aid] = rel
            _atomic_write_json(SESSION_INDEX, idx)
        return {"path": rel, "session": session, "status": session_status(session, rec)}


def draft_for(p):
    """One draft of feedback, from the same request the page sends to /api/generate. Used by that route and by the
    background drafting job, so both write feedback the same way."""
    rubric = p.get("rubric", "").strip()
    picked = [x["text"] for x in load_standards().get(p.get("doc"), []) if x["id"] in p.get("standards", [])]
    if picked:
        rubric = (rubric + "\n\n" if rubric else "") + "Learning standards (RCS 2026-27):\n\n" + "\n\n".join(picked)
    if not rubric:
        raise ValueError("Add an assignment description or choose learning standards.")
    return fb.generate(p["model"], rubric, p.get("grade", ""), p.get("label", "student"), p["work"], p.get("notes", ""), p.get("level", ""),
                       p.get("term", ""), p.get("length", fb.DEFAULT_LENGTH), p.get("title", ""))


JOB_ID = re.compile(r"job-\d{8}-\d{6}-[0-9a-f]{6}")
JOB_SETTINGS = ("model", "rubric", "doc", "standards", "grade", "term", "length", "title")
QUEUE = None


def _run_draft_job(queue, job):
    """Drafts feedback one student at a time. Finished drafts are saved as they complete (so a restart never loses one),
    and nothing here posts anywhere."""
    side = queue.request_of(job)
    req, items = side["request"], {i["idx"]: i for i in side["items"]}
    while not queue.cancel_requested(job["id"]):
        nxt = queue.next_item(job["id"])
        if not nxt:
            return
        it = items[nxt["idx"]]
        p = {**req["settings"], "work": it["work"], "notes": it.get("notes", ""), "level": it.get("level", ""),
             "grade": it.get("grade") or req["settings"].get("grade", ""), "label": it.get("label") or "student"}
        try:
            queue.item_finished(job, nxt["idx"], nxt["key"], "done", result={"feedback": draft_for(p)})
        except (urllib.error.URLError, ConnectionError):
            engine, _ = fb.split_model(p.get("model", ""))
            raise jobs.JobFailed(fb.unreachable(engine))
        except RuntimeError as e:        # the engine answered with its own error (e.g. couldn't load the model): stop, keep the rest queued
            raise jobs.JobFailed(str(e))
        except Exception as e:           # a problem with this student only: record it and carry on
            queue.item_finished(job, nxt["idx"], nxt["key"], "failed", error=f"{type(e).__name__}: {e}")


TEAMS_FOLDER = "@teams"      # pseudo-folder for Teams read jobs (kept under App Support, outside Assessment and git)
TEAMS_JOB_KEY = "teams"      # the job list key for these jobs (not an assignment id)
TOOLS_PYTHON = Path.home() / ".venvs" / "student-feedback-tools" / "bin" / "python"


def teams_runner(op, cls="", title=""):
    """Run teams_read.py in its own process (it needs Playwright, which lives in the tools venv, and a Chrome window)
    and return its JSON answer. Tests replace this function."""
    py = str(TOOLS_PYTHON) if TOOLS_PYTHON.exists() else sys.executable
    cmd = [py, str(HERE / "teams_read.py"), op] + (["--class", cls, "--title", title] if op == "read" else [])
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"ok": False, "kind": "error", "error": "Reading Teams took longer than 15 minutes and was stopped."}
    last = next((l for l in reversed((r.stdout or "").strip().splitlines()) if l.startswith("{")), "")
    try:
        return json.loads(last)
    except ValueError:
        return {"ok": False, "kind": "setup" if r.returncode == 3 else "error",
                "error": "The Teams reader gave no answer. " + ((r.stderr or "").strip()[-300:] or f"Exit code {r.returncode}.")}


def _run_teams_job(queue, job):
    """One Teams read (the list, or one assignment). Read-only. A sign-in page leaves the job waiting for the teacher."""
    side = queue.request_of(job)
    req = side["request"]
    nxt = queue.next_item(job["id"])
    if not nxt:
        return
    out = TEAMS_RUNNER(req["op"], req.get("class", ""), req.get("title", ""))
    kind = out.get("kind", "")
    if out.get("ok"):
        queue.item_finished(job, nxt["idx"], nxt["key"], "done", result={"teams": out})
    elif kind == "sign_in":
        raise jobs.NeedsSignIn(out.get("error", "Sign in to Microsoft in the Chrome window, then resume."))
    elif kind in ("busy", "setup", "blocked"):
        raise jobs.JobFailed(out.get("error", "The Teams reader couldn't start."))
    else:                                  # the page differed, nothing matched, or something else: record why, keep the details
        queue.item_finished(job, nxt["idx"], nxt["key"], "failed", error=str(out.get("error", "Failed"))[:300], result={"teams": out})


def enqueue_teams_job(body):
    if QUEUE is None:
        raise RuntimeError("The job worker isn't running.")
    op, cls, title = str(body.get("op", "")), str(body.get("class", "")).strip()[:200], str(body.get("title", "")).strip()[:300]
    if op not in ("list", "read"):
        raise ValueError("op must be list or read")
    if op == "read" and not (cls and title):
        raise ValueError("read needs the Teams class and the assignment title")
    if any(j["state"] in ("queued", "running", "waiting_for_sign_in") for j in QUEUE.list_for(TEAMS_JOB_KEY, 20) if j["type"] == "teams_read"):
        raise ValueError("A Teams read is already queued, running or waiting for you to sign in.")
    return QUEUE.enqueue("teams_read", TEAMS_JOB_KEY, TEAMS_FOLDER, {"op": op, "class": cls, "title": title},
                         [{"key": op, "work_sha": ""}])


TEAMS_RUNNER = teams_runner


def start_worker():
    """Create the job queue (journal in App Support) and start its worker. Call once, when the app starts."""
    global QUEUE
    if QUEUE is None:
        def inside(rel):
            if rel == TEAMS_FOLDER:               # Teams reads aren't tied to an assignment folder: they have no student work
                return (APP_DATA / "teams-reads").resolve()
            root = ASSESSMENT.resolve()
            d = (root / rel).resolve()
            if d == root or not d.is_relative_to(root):
                raise ValueError("bad folder")
            return d
        QUEUE = jobs.JobQueue(APP_DATA / "jobs.sqlite", {"draft": _run_draft_job, "teams_read": _run_teams_job}, inside, _atomic_write_json, _read_json)
    QUEUE.start()
    return QUEUE


def enqueue_draft_job(body):
    aid = str(body.get("assignment", ""))
    rec = load_assignment_record(aid)
    rel, _ = session_folder(aid, rec)
    if QUEUE is None:
        raise RuntimeError("The job worker isn't running.")
    if any(j["state"] in ("queued", "running", "interrupted") for j in QUEUE.list_for(aid, 20) if j["type"] == "draft"):
        raise ValueError("A drafting job for this assignment is already queued, running or waiting to be resumed.")
    settings = {k: body.get("settings", {}).get(k, "") for k in JOB_SETTINGS if k != "standards"}
    settings["standards"] = [str(x) for x in (body.get("settings", {}).get("standards") or [])][:50]
    if not settings["model"]:
        raise ValueError("Choose a model first.")
    raw = body.get("items")
    if not isinstance(raw, list) or not raw or len(raw) > 400:
        raise ValueError("items must be a list of 1 to 400 students")
    items, seen = [], set()
    for it in raw:
        key, work = str(it.get("key", ""))[:64], str(it.get("work", ""))[:200_000]
        if not key or key in seen or not work.strip():
            raise ValueError("each item needs a unique key and some work")
        seen.add(key)
        items.append({"key": key, "work": work, "notes": str(it.get("notes", ""))[:20_000], "level": str(it.get("level", ""))[:30],
                      "grade": str(it.get("grade", ""))[:30], "label": str(it.get("label", ""))[:120],
                      "work_sha": hashlib.sha256(work.encode("utf-8")).hexdigest()})
    request = {"settings": settings, "basis": str(body.get("basis", ""))[:400_000], "overwrite": bool(body.get("overwrite"))}
    return QUEUE.enqueue("draft", aid, rel, request, items)


def _job_view(job):
    return {k: job[k] for k in ("id", "type", "assignment", "state", "created", "started", "finished", "error", "total", "counts", "items", "drafts", "basis", "overwrite") if k in job}


SECTION_SUFFIX = re.compile(r"_(?:homework|handouts)$", re.I)


def list_assessments():
    """Every folder under Assessment that holds .txt/.md work, newest first: [{path (relative to Assessment), label}]."""
    found = []
    if ASSESSMENT.is_dir():
        for d in [ASSESSMENT, *ASSESSMENT.rglob("*")]:
            rel = d.relative_to(ASSESSMENT)
            if not d.is_dir() or any(p.startswith(".") for p in rel.parts):  # skip hidden folders and their contents
                continue
            if any(f.suffix.lower() in {".txt", ".md"} and not f.name.startswith(".") for f in d.iterdir()):
                found.append((d.stat().st_mtime, {"path": rel.as_posix(), "label": " \u203a ".join(rel.parts) or "Assessment"}))
    return [x for _, x in sorted(found, key=lambda t: -t[0])]


def load_assessment(rel):
    """One folder under Assessment -> [(name, work)], one per .txt/.md file; name = filename with _ as spaces."""
    root = ASSESSMENT.resolve()
    d = (root / rel).resolve()
    if not (d.is_dir() and (d == root or d.is_relative_to(root))):
        raise ValueError("not inside the Assessment folder")
    out = []
    for f in sorted(d.iterdir()):
        if f.name.startswith(".") or f.suffix.lower() not in {".txt", ".md"}:
            continue
        work = f.read_text(encoding="utf-8-sig", errors="replace").strip()
        if work:
            out.append((SECTION_SUFFIX.sub("", f.stem).replace("_", " "), work))
    return out


HERE = Path(__file__).parent
CACHE = HERE / "courses.cache.json"


def hub_settings():
    """Course Hub URL + API key. Env vars win, then ./.env.local. The key stays server-side only."""
    env = {}
    p = HERE / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    get = lambda k, d="": os.environ.get(k) or env.get(k) or d
    return get("COURSE_HUB_URL", "http://localhost:3005").rstrip("/"), get("COURSE_HUB_API_KEY")


def _classify(name, grades, rules):
    for r in rules:
        if re.search(r["pattern"], name, re.I):
            out = {"department": r["department"]}
            if r.get("match_by_grade") and len(grades) == 1:
                out["match"] = f"{r['match_by_grade']} {grades[0]}"
            return out
    return {"department": ""}


def hub_get(path):
    base, key = hub_settings()
    if not key:
        raise RuntimeError("COURSE_HUB_API_KEY is not set (see README)")
    req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Course Hub answered {e.code} for {path.split('?')[0].rsplit('/', 1)[0] if 'roster' in path else path.split('?')[0]}")
    except (urllib.error.URLError, OSError):
        raise RuntimeError(f"Can't reach Course Hub at {base}")


def fetch_from_course_hub(rules):
    """Live course list + quarters from Course Hub's API, normalised for the page."""
    get = hub_get

    quarters = get("/api/quarters")
    school_year = quarters[0]["school_year"] if quarters else ""
    sy = f"school_year={school_year}&" if school_year else ""
    sections = get(f"/api/courses?{sy}quarter=all&type=academic")

    grouped = {}  # (name, quarters) -> sections: blocks of one course merge; "ICT 9" Q1 and Q2 stay apart
    for c in sections:
        qs = tuple(sorted({int(m) for q in (c.get("quarters") or []) for m in re.findall(r"\d", str(q))}))
        g = grouped.setdefault((c["name"].strip(), qs), {"grades": set(), "sections": []})
        g["grades"].update(int(x) for x in (c.get("grade_years") or []))
        g["sections"].append({"id": c["id"], "block": c.get("block") or "", "quarters": list(qs)})
    per_name = {}
    for name, qs in grouped:
        per_name[name] = per_name.get(name, 0) + 1
    courses = []
    for (name, qs), g in sorted(grouped.items(), key=lambda kv: (min(kv[1]["grades"] or {99}), kv[0][0], kv[0][1])):
        grades = sorted(g["grades"])
        label = name
        if per_name[name] > 1:  # same name, different quarters: tell the sections apart
            label = f"{name} ({'/'.join('Q' + str(n) for n in qs)})" if qs else f"{name} (full year)"
        entry = {"name": label, "grades": grades, "sections": g["sections"], **_classify(name, grades, rules)}
        if qs:
            entry["quarters"] = list(qs)
        courses.append(entry)
    return {
        "courses": courses,
        "quarters": [{"label": q["label"], "start": q["start_date"], "end": q["end_date"]} for q in quarters],
        "school_year": school_year,
        "fetched_at": datetime.now().isoformat(timespec="minutes"),
    }


_mem = {"at": 0, "data": None}


def course_data():
    """Live from Course Hub (60 s in-memory reuse); else the last live copy; else courses.json."""
    if _mem["data"] and time.time() - _mem["at"] < 60:
        return _mem["data"]
    data = _course_data()
    if data.get("source") == "live":
        _mem.update(at=time.time(), data=data)
    return data


def _course_data():
    cfg = json.loads((HERE / "courses.json").read_text(encoding="utf-8"))
    rules = cfg.get("department_rules", [])
    try:
        data = fetch_from_course_hub(rules)
        CACHE.write_text(json.dumps(data, indent=1), encoding="utf-8")
        data.update(source="live", note=f"Courses from Course Hub (live), {data['school_year']}.")
        return data
    except RuntimeError as why:
        if CACHE.exists():
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            data.update(source="cache", note=f"{why}. Using the copy fetched {data.get('fetched_at', 'earlier')}.")
            return data
        cfg.update(source="file", note=f"{why}. Using the built-in course list.")
        return cfg


def roster_for(course_name, quarter=""):
    """Students in a course from Course Hub. In memory only: never cached or written to disk.
    Returns only what the page needs (no email, no gender)."""
    course = next((c for c in course_data().get("courses", []) if c["name"] == course_name), None)
    if not course or not course.get("sections"):
        raise RuntimeError("Class list needs live course data from Course Hub.")
    qn = int(quarter) if str(quarter).isdigit() else None
    secs = [s for s in course["sections"] if qn is None or not s["quarters"] or qn in s["quarters"]] or course["sections"]
    seen, out = set(), []
    for sec in secs:
        for st in hub_get(f"/api/courses/{urllib.parse.quote(str(sec['id']))}/roster"):
            if st["id"] in seen:
                continue
            seen.add(st["id"])
            out.append({"id": st["id"], "first": st.get("first_name", ""), "last": st.get("last_name", ""),
                        "grade": st.get("grade_year"), "grade_year_reference": st.get("grade_year_reference") or "",
                        "block": sec.get("block", "")})
    return sorted(out, key=lambda s: (s["last"].lower(), s["first"].lower()))


def load_standards():
    """{doc name: [{id, label, text}]} parsed from every PDF in standards/ (needs pdftotext).
    Locked, and the cache is filled only when every PDF is parsed: the page asks for courses and standards at once."""
    with _std_lock:
        if not _cache:
            _cache.update(_parse_standards())
        return _cache


def _parse_standards():
    docs = {}
    for pdf in sorted(STANDARDS_DIR.glob("*.pdf")):
        raw = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
        sections = []
        for page in raw.split("\f"):
            lines = [l.rstrip() for l in page.splitlines() if l.strip()]
            if not lines:
                continue
            page_label = re.sub(r"\s+", " ", lines[0]).strip()
            cur = None
            for l in lines[1:]:
                flat = re.sub(r" {3,}", " | ", l.strip())
                if flat.startswith("Richmond Christian School"):
                    continue
                if re.match(r"Learning Standard \d+:", flat):
                    cur = {"label": f"{page_label} - {flat}", "lines": []}
                    sections.append(cur)
                elif cur is not None:
                    cur["lines"].append(flat)
        name = re.sub(r"_RCS_Branded|\.pdf$", "", pdf.name).replace("_", " ")
        docs[name] = [
            {"id": f"{i}", "label": sec["label"], "text": sec["label"].split(" - ", 1)[1] + "\n" + "\n".join(sec["lines"])}
            for i, sec in enumerate(sections)
        ]
    return docs

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Student Feedback</title>
<style>
  :root{--bg:#f6f5f1;--card:#fff;--ink:#1f2328;--mute:#6b7280;--line:#e2e0d8;--accent:#2f6f5e}
  @media (prefers-color-scheme:dark){:root{--bg:#16181a;--card:#1f2225;--ink:#e8e8e6;--mute:#9aa0a6;--line:#33373b;--accent:#6fbfa8}}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
  main{max-width:860px;margin:0 auto;padding:24px 16px 80px}
  h1{font-size:1.4rem;margin:0 0 4px} .sub{color:var(--mute);margin:0 0 20px;font-size:.9rem}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
  label{display:block;font-weight:600;font-size:.85rem;margin-bottom:4px}
  textarea,input,select{width:100%;font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px}
  textarea{min-height:110px;resize:vertical}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
  @media(max-width:600px){.row{grid-template-columns:1fr}}
  button{font:inherit;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 14px;cursor:pointer}
  button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
  button:disabled{opacity:.5;cursor:default}
  .bar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  .out{white-space:pre-wrap;margin-top:12px;padding:12px;border-left:3px solid var(--accent);background:var(--bg);border-radius:0 6px 6px 0}
  .status{color:var(--mute);font-size:.85rem;margin-top:8px}
  .err{color:#b42318}
</style></head><body><main>
<h1>Student Feedback</h1>
<p class="sub">Runs on this laptop with a local model. Drafts only: review before sharing.</p>

<div class="card">
  <label for="atitle">Assignment name <span style="font-weight:400;color:var(--mute)">(optional; filled in from a Teams export)</span></label>
  <input id="atitle" placeholder="e.g. Task 2: Define &amp; Ideate" style="margin-bottom:12px">
  <label for="rubric">Assignment instructions</label>
  <textarea id="rubric" placeholder="Paste the assignment instructions here. (Optional if you tick learning standards below.)"></textarea>
  <div class="row">
    <div><label for="grade">Grade level</label><select id="grade"></select></div>
    <div><label for="model">Model <span style="font-weight:400;color:var(--mute)">(Ollama or LM Studio)</span></label><select id="model"></select>
      <div id="modelnote" class="status"></div></div>
  </div>
  <div class="row">
    <div><label for="length">Feedback length</label>
      <select id="length">
        <option value="sentence">One sentence</option>
        <option value="paragraph">One paragraph</option>
        <option value="detailed">Long (multi-part)</option>
      </select></div>
    <div></div>
  </div>
</div>

<div class="card">
  <label for="course">Course</label>
  <div class="row" style="margin-top:0">
    <div><label for="quarter">Term <span style="font-weight:400;color:var(--mute)">(chosen from today's date)</span></label>
      <select id="quarter"></select></div>
    <div></div>
  </div>
  <label for="course" style="margin-top:12px">Course</label>
  <select id="course"><option value="">Not listed / choose department below</option></select>
  <div class="status" id="coursenote"></div>
  <div class="status" id="coursesrc"></div>
  <div class="status" id="rosternote"></div>
  <label for="doc" style="margin-top:14px">Department <span style="font-weight:400;color:var(--mute)">(set automatically from the course)</span></label>
  <select id="doc"><option value="">None</option></select>
  <div id="stds" style="margin-top:10px"></div>
</div>

<div id="students"></div>

<div class="bar">
  <button id="add">+ Add student</button>
  <button id="addall" disabled>+ Add whole class</button>
  <button id="files">Upload files…</button>
  <input id="filepick" type="file" accept=".txt,.md,.csv,.pdf,.docx,.xlsx" multiple hidden>
  <select id="split" style="width:auto" title="How to split uploaded files into students">
    <option value="auto">Split: automatic (Name: lines or --- rules)</option>
    <option value="page">Split: one student per PDF page</option>
    <option value="whole">Don't split: one student per file</option>
  </select>
  <select id="assess" style="width:auto" title="Student files saved under Desktop/Teaching/Assessment">
    <option value="">Load from Assessment folder…</option>
  </select>
  <button class="primary" id="go">Generate feedback</button>
  <button id="dl" disabled>Download all (.csv)</button>
  <button id="dlteams" disabled title="Names in Teams order, ready to paste into each student's Feedback box">Download for Teams (.csv)</button>
</div>
<label style="font-weight:400;display:flex;gap:8px;align-items:center;margin-top:10px"><input type="checkbox" id="skipret" checked style="width:auto"> Skip students Teams already shows as Returned</label>
<div class="status" id="teamsnote"></div>
<div class="status" id="status"></div>

<script>
const $ = s => document.querySelector(s);
const store = {get:k=>{try{return localStorage.getItem(k)||""}catch(e){return ""}},
               set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
$("#rubric").value = store.get("rubric"); const GRADES = ["Grade 9","Grade 10","Grade 11","Grade 12"];
$("#grade").innerHTML = GRADES.map(g=>`<option>${g}</option>`).join("");
$("#grade").value = GRADES.includes(store.get("grade")) ? store.get("grade") : "Grade 9";
$("#rubric").oninput = e => store.set("rubric", e.target.value);
$("#grade").onchange = e => store.set("grade", e.target.value);

fetch("/api/models").then(r=>r.json()).then(d=>{
  if(d.error){ $("#status").innerHTML = '<span class="err">'+d.error+'</span>'; return; }
  const saved = store.get("model_choice") || d.default;
  const groups = {};                                   // one group per engine: Ollama, LM Studio
  d.models.forEach(m => (groups[m.engine] = groups[m.engine] || []).push(m));
  $("#model").replaceChildren(...Object.entries(groups).map(([engine, ms]) => {
    const g = document.createElement("optgroup"); g.label = engine;
    g.append(...ms.map(m => new Option(m.name, m.id, false, m.id === saved))); return g;
  }));
  if(![...$("#model").options].some(o => o.value === saved)) $("#model").value = d.default;
  // Stay quiet unless it matters: mention an engine that's off only if the saved choice needs it, and the
  // memory note only when there really are two engines to switch between.
  const savedEngine = (saved || "").startsWith("lmstudio::") ? "LM Studio" : "Ollama";
  const savedOff = saved && d.offline.includes(savedEngine);
  $("#modelnote").textContent = (savedOff ? savedEngine + " isn't running, so your last choice isn't available. " : "")
    + (Object.keys(groups).length > 1 ? "Switching engines unloads the other one's model to free memory." : "");
});
$("#length").value = ["sentence","paragraph","detailed"].includes(store.get("length")) ? store.get("length") : "paragraph";
$("#length").onchange = e => store.set("length", e.target.value);
$("#model").onchange = e => store.set("model_choice", e.target.value);

let STD = {}, COURSES = [], QUARTERS = [], SCHOOL_YEAR = "", ROSTER = [];
function rosterOptions(){
  return '<option value="">' + (ROSTER.length ? "Choose from class list…" : "Choose a course for a class list…") + '</option>' +
    ROSTER.map((s,i)=>`<option value="${i}">${s.last}, ${s.first}${s.block ? " (" + s.block + ")" : ""}</option>`).join("");
}
const norm = t => (t||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z\s'-]/g," ").replace(/\s+/g," ").trim();
function lev(a,b){
  const m = Array.from({length:a.length+1}, (_,i)=>[i]); for(let j=1;j<=b.length;j++) m[0][j]=j;
  for(let i=1;i<=a.length;i++) for(let j=1;j<=b.length;j++)
    m[i][j] = Math.min(m[i-1][j]+1, m[i][j-1]+1, m[i-1][j-1] + (a[i-1]===b[j-1] ? 0 : 1));
  return m[a.length][b.length];
}
// Match an uploaded name to the class list. Tiers, strictest first; a tier with 2+ hits is ambiguous, not guessed.
function findStudent(raw, list = ROSTER){
  const n = norm(raw);
  if(!n || !list.length) return {status:"none"};
  let first, last;
  if(raw.includes(",")){ const p = raw.split(","); last = norm(p[0]); first = norm(p.slice(1).join(" ")); }
  else { const p = n.split(" "); first = p[0]; last = p.slice(1).join(" "); }
  const R = list.map((s,i)=>({s, i, f:norm(s.first), l:norm(s.last)}));
  const toks = n.split(" ");
  const tiers = [
    () => last && R.filter(r => (r.f===first && r.l===last) || (r.f===last && r.l===first)),                       // exact, either order
    () => last && last.replace(/\./g,"").length===1 ? R.filter(r => r.f===first && r.l.startsWith(last[0])) : [],   // "Mia C."
    () => R.filter(r => r.f && r.l && toks.includes(r.f) && r.l.split(" ").every(t => toks.includes(t))),            // both names appear (file names)
    () => !last ? R.filter(r => r.f===first) : [],                                                                  // first name only
    () => !last ? R.filter(r => r.l===first) : [],                                                                  // last name only
    () => { const full = (first+" "+last).trim(), lim = full.length > 10 ? 2 : 1;                                   // close spelling
            const sc = R.map(r => ({r, d: Math.min(lev(full, r.f+" "+r.l), lev(full, r.l+" "+r.f))})).filter(x=>x.d<=lim);
            const best = Math.min(...sc.map(x=>x.d)); return sc.filter(x=>x.d===best).map(x=>x.r); },
  ];
  for(const t of tiers){
    const hits = t();
    if(hits && hits.length === 1) return {status:"match", s:hits[0].s, i:hits[0].i};
    if(hits && hits.length > 1) return {status:"ambiguous", options:hits.map(h=>h.s.first+" "+h.s.last)};
  }
  return {status:"none"};
}
let TEAMS = null;   // status export from Teams, held in this page only
const teamsLabel = t => "Teams: " + ({"Turned in":"turned in", "Viewed":"viewed, not turned in",
  "Returned":"returned" + (t.has_feedback ? " (feedback already given)" : "")}[t.status] || t.status);
function teamsFor(card){
  if(!TEAMS) return null;
  const raw = card.dataset.orig || card.querySelector(".name").value.trim();
  if(!raw) return null;
  const r = findStudent(raw, TEAMS.students);
  return r.status === "match" ? r.s : null;
}
function applyTeams(){
  document.querySelectorAll(".student").forEach(c => {
    const el = c.querySelector(".tstatus"), t = teamsFor(c);
    c.dataset.tstatus = t ? t.status : "";
    const cur = c.querySelector(".name").value.trim();           // tidy file-name style names ("Lin_Ava_Task2")
    if(t && norm(cur) !== norm(t.name)){ c.dataset.orig = c.dataset.orig || cur; c.querySelector(".name").value = t.name; }
    el.textContent = !TEAMS ? "" : t ? teamsLabel(t) : (c.querySelector(".name").value.trim() ? "Teams: not found in this export" : "");
    el.style.color = t && t.status === "Returned" ? "#b45309" : "";
  });
  const note = $("#teamsnote");
  if(!TEAMS){ note.textContent = ""; return; }
  const counts = {}; TEAMS.students.forEach(s => counts[s.status] = (counts[s.status] || 0) + 1);
  const have = new Set();
  document.querySelectorAll(".student").forEach(c => { const t = teamsFor(c); if(t && c.querySelector(".work").value.trim()) have.add(t.name); });
  const waiting = TEAMS.students.filter(s => s.status === "Turned in" && !have.has(s.name)).map(s => s.name);
  note.textContent = (TEAMS.assignment || "Assignment") + (TEAMS.due ? " (due " + TEAMS.due + ")" : "") + ": " +
    Object.entries(counts).map(([k, v]) => v + " " + k.toLowerCase()).join(", ") + "." +
    (waiting.length ? " Turned in, no work loaded yet: " + waiting.slice(0, 8).join(", ") + (waiting.length > 8 ? " +" + (waiting.length - 8) + " more" : "") + "." : "");
}
function setNote(card, text, warn){
  const el = card.querySelector(".matchnote"); el.textContent = text; el.style.color = warn ? "#b45309" : "";
}
function matchCard(card){
  const name = card.querySelector(".name").value.trim();
  if(!ROSTER.length || !name){ setNote(card, ""); return null; }
  const raw = card.dataset.orig || name;          // the name as uploaded/typed, before correction
  card.dataset.orig = raw;
  const r = findStudent(raw);
  const was = norm(raw) !== norm(r.s ? r.s.first + " " + r.s.last : "") ? "  (uploaded as \"" + raw + "\")" : "";
  const pick = card.querySelector(".pick");
  if(r.status === "match"){
    pick.value = String(r.i); pick.onchange();
    setNote(card, "✓ Matched to class list: " + r.s.last + ", " + r.s.first + was);
    card.dataset.rid = r.s.id;
  } else {
    pick.value = ""; delete card.dataset.rid;
    setNote(card, r.status === "ambiguous" ? "? Could be: " + r.options.join(" or ") + " - choose from the class list" : "? Not on this class list - check the name or the course", true);
  }
  return r;
}
function matchAll(announce){
  if(!ROSTER.length) return;
  const cards = [...document.querySelectorAll(".student")].filter(c => c.querySelector(".name").value.trim());
  let ok = 0; const seen = {};
  cards.forEach(c => { const r = matchCard(c); if(r && r.status === "match"){ ok++; (seen[r.s.id] = seen[r.s.id] || []).push(c); } });
  Object.values(seen).filter(a => a.length > 1).forEach(a => a.forEach(c => { ok--; setNote(c, "? Two uploads match the same student (" + c.querySelector(".name").value + ")" + (c.dataset.orig ? "  (uploaded as \"" + c.dataset.orig + "\")" : ""), true); }));
  if(announce){
    const present = new Set(Object.keys(seen));
    const missing = ROSTER.filter(s => !present.has(s.id)).map(s => s.first + " " + s.last);
    $("#status").textContent = cards.length + " loaded: " + ok + " matched to the class list" +
      (cards.length - ok ? ", " + (cards.length - ok) + " need checking" : "") + "." +
      (missing.length ? " No work found for: " + missing.slice(0, 8).join(", ") + (missing.length > 8 ? " +" + (missing.length - 8) + " more" : "") + "." : "");
  }
}
function wirePicker(card){
  const pick = card.querySelector(".pick");
  pick.innerHTML = rosterOptions();
  pick.onchange = () => {
    const s = ROSTER[pick.value]; if(!s) return;
    card.querySelector(".name").value = s.first + " " + s.last;
    card.dataset.rid = s.id; setNote(card, "✓ Matched to class list: " + s.last + ", " + s.first);
    // Course Hub stores one grade per student, true only for the year it was recorded in.
    const g = "Grade " + s.grade;
    if(s.grade && s.grade_year_reference === SCHOOL_YEAR && GRADES.includes(g) && g !== $("#grade").value) card.querySelector(".sgrade").value = g;
  };
}
async function loadRoster(){
  const c = COURSES[$("#course").value];
  ROSTER = []; $("#addall").disabled = true;
  if(c && c.sections){
    const qn = ($("#quarter").value||"").replace("Q","");
    try {
      const d = await (await fetch("/api/roster?name=" + encodeURIComponent(c.name) + "&quarter=" + qn)).json();
      if(d.error) $("#rosternote").textContent = d.error;
      else { ROSTER = d.students; $("#rosternote").textContent = ROSTER.length + (ROSTER.length === 1 ? " student" : " students") + " in " + c.name + " (class list held in memory only)."; }
    } catch(e){ $("#rosternote").textContent = "Couldn't load the class list."; }
  } else $("#rosternote").textContent = c ? "Class list unavailable (course list isn't live from Course Hub)." : "";
  document.querySelectorAll(".student").forEach(wirePicker);
  $("#addall").disabled = !ROSTER.length;
  if(ROSTER.length) matchAll(document.querySelectorAll(".student .name").length > 1);
}
function quarterForToday(){
  if(!QUARTERS.length) return "";
  const t = new Date(); const iso = t.getFullYear()+"-"+String(t.getMonth()+1).padStart(2,"0")+"-"+String(t.getDate()).padStart(2,"0");
  let pick = QUARTERS[0];                       // before the year starts -> Q1
  for(const q of QUARTERS) if(q.start <= iso) pick = q;   // latest quarter already started (covers gaps and breaks)
  return pick.label;
}
function runsIn(c, qn){ return !c.quarters || !c.quarters.length || c.quarters.includes(qn); }
function courseLabel(c){ return c.name + (c.quarters && !/\(Q\d/.test(c.name) ? " (" + c.quarters.map(n=>"Q"+n).join("/") + ")" : ""); }
function renderCourses(keepValue){
  const qn = parseInt($("#quarter").value.replace("Q","")) || 0;
  const cur = keepValue === undefined ? $("#course").value : keepValue;
  const opt = (c,i) => `<option value="${i}">${courseLabel(c)}</option>`;
  const items = COURSES.map((c,i)=>({c,i}));
  const now = items.filter(({c}) => runsIn(c, qn)), other = items.filter(({c}) => !runsIn(c, qn));
  $("#course").innerHTML = '<option value="">Not listed / choose department below</option>' +
    `<optgroup label="Running in ${$("#quarter").value || "this term"}">${now.map(({c,i})=>opt(c,i)).join("")}</optgroup>` +
    (other.length ? `<optgroup label="Other terms">${other.map(({c,i})=>opt(c,i)).join("")}</optgroup>` : "");
  if([...$("#course").options].some(o=>o.value===cur)) $("#course").value = cur; else $("#course").value = "";
}
const baseName = n => n.replace(/\s*\([^)]*\)\s*$/, "").trim();
$("#quarter").onchange = () => {
  store.set("quarter_choice", JSON.stringify({q:$("#quarter").value, on:new Date().toDateString()}));
  const qn = parseInt($("#quarter").value.replace("Q","")), cur = COURSES[$("#course").value];
  let keep;
  if(cur && !runsIn(cur, qn)){
    const sib = COURSES.findIndex(c => baseName(c.name) === baseName(cur.name) && runsIn(c, qn) && c.quarters);
    if(sib >= 0) keep = String(sib);
  }
  renderCourses(keep);
  applyCourse(true);
};

fetch("/api/courses").then(r=>r.json()).then(d=>{
  if(d.error){ $("#coursenote").textContent = d.error; return; }
  COURSES = d.courses; QUARTERS = d.quarters || []; SCHOOL_YEAR = d.school_year || "";
  $("#coursesrc").textContent = d.note || "";
  $("#coursesrc").style.color = d.source === "live" ? "" : "#b45309";
  $("#quarter").innerHTML = QUARTERS.map(q=>`<option value="${q.label}">${q.label} (${q.start} to ${q.end})</option>`).join("");
  let qv = quarterForToday();
  try { const o = JSON.parse(store.get("quarter_choice")||"null"); if(o && o.on === new Date().toDateString()) qv = o.q; } catch(e){}  // manual pick lasts for the day
  if(qv) $("#quarter").value = qv;
  const sv = String(COURSES.findIndex(c => c.name === store.get("course")));   // saved by name: list order can change
  renderCourses(sv);
  if(sv !== "-1") { $("#course").value = sv; if(Object.keys(STD).length) applyCourse(false); }
});
function applyCourse(save=true){
  const c = COURSES[$("#course").value];
  if(c && c.quarters && c.quarters.length){
    const qn = parseInt($("#quarter").value.replace("Q",""));
    if(!c.quarters.includes(qn)){
      $("#quarter").value = "Q" + c.quarters[0];
      store.set("quarter_choice", JSON.stringify({q:$("#quarter").value, on:new Date().toDateString()}));
      renderCourses($("#course").value);
    }
  }
  loadRoster();
  if(save) store.set("course", c ? c.name : "");
  if(!c){ $("#coursenote").textContent = ""; showStds(); return; }
  // Never carry the previous course's department (and its ticked standards) over: use this course's own
  // document, else what the teacher picked for this course before, else none.
  const hasDoc = !!(c.doc && STD[c.doc]), own = store.get("doc_for:" + c.name);
  $("#doc").value = hasDoc ? c.doc : (STD[own] ? own : ""); store.set("doc", $("#doc").value);
  if(c.grades && c.grades.length === 1) { $("#grade").value = "Grade " + c.grades[0]; store.set("grade", $("#grade").value); }
  $("#coursenote").textContent = (hasDoc ? "Department: " + c.department
      : "No standards document for " + (c.department ? "department '" + c.department + "'" : "this course") +
        ". Paste the instructions above, or choose a department below.") +
    (c.grades && c.grades.length > 1 ? " · taught in grades " + c.grades.join(", ") + " (set grade above or per student)" : "");
  showStds();
}
$("#course").onchange = () => applyCourse(true);
fetch("/api/standards").then(r=>r.json()).then(d=>{
  STD = d;
  $("#doc").innerHTML += Object.keys(d).map(k=>`<option>${k}</option>`).join("");
  const sv = store.get("doc"); if(sv && d[sv]) { $("#doc").value = sv; showStds(); }
  if(COURSES.length && $("#course").value !== "") applyCourse(false);
});
function showStds(){
  const c = COURSES[$("#course").value];
  let list = STD[$("#doc").value] || [];
  if(c && c.match && c.doc === $("#doc").value) list = list.filter(x => x.label.includes(c.match));
  const ticked = JSON.parse(store.get("ticked:" + $("#doc").value) || "[]");   // saved by label, not position in the PDF
  $("#stds").innerHTML = list.map(x=>`<label style="font-weight:400;display:flex;gap:8px;align-items:center">
    <input type="checkbox" class="std" value="${x.id}" style="width:auto" ${ticked.includes(x.label)?"checked":""}> ${x.label}</label>`).join("");
  document.querySelectorAll(".std").forEach(c => c.onchange = () =>
    store.set("ticked:" + $("#doc").value, JSON.stringify([...document.querySelectorAll(".std:checked")].map(x=>list.find(s => s.id === x.value).label))));
}
$("#doc").onchange = () => {
  store.set("doc", $("#doc").value);
  const c = COURSES[$("#course").value]; if(c) store.set("doc_for:" + c.name, $("#doc").value);
  showStds();
};

function addStudent(name="", work=""){
  const d = document.createElement("div"); d.className = "card student";
  d.innerHTML = `<div class="row" style="margin-top:0"><div><label>Student</label>
        <select class="pick" style="margin-bottom:6px"><option value="">Choose from class list…</option></select>
        <input class="name" placeholder="…or type a name">
        <div class="matchnote status"></div>
        <div class="tstatus status"></div></div>
      <div><label>Grade <span style="font-weight:400;color:var(--mute)">(only if different from class)</span></label>
        <select class="sgrade"><option value="">Same as class</option>
        ${GRADES.map(g=>`<option>${g}</option>`).join("")}</select>
        <label style="margin-top:8px">Level <span style="font-weight:400;color:var(--mute)">(optional, you decide)</span></label>
        <select class="level"><option value="">No level (feedback only)</option>
        ${["Emerging","Emerging+","Developing","Developing+","Proficient","Proficient+","Extending","Extending+"].map(l=>`<option>${l}</option>`).join("")}
        </select></div></div>
    <label style="margin-top:12px">Work</label><textarea class="work"></textarea>
    <label style="margin-top:12px">Teacher notes <span style="font-weight:400;color:var(--mute)">(private, optional: e.g. "ELL, working on sentence variety")</span></label>
    <input class="notes">
    <div class="result"></div>`;
  d.querySelector(".name").value = name; d.querySelector(".work").value = work; wirePicker(d); d.querySelector(".name").onchange = () => { delete d.dataset.orig; matchCard(d); applyTeams(); };
  $("#students").appendChild(d); return d;
}
addStudent();
$("#add").onclick = () => addStudent();
$("#addall").onclick = () => {
  const have = new Set([...document.querySelectorAll(".student .name")].map(i=>i.value.trim().toLowerCase()));
  const first = document.querySelector(".student");
  if(first && !first.querySelector(".name").value.trim() && !first.querySelector(".work").value.trim()) first.remove();
  ROSTER.forEach((s,i) => {
    const full = s.first + " " + s.last;
    if(have.has(full.toLowerCase())) return;
    const card = addStudent(full, ""); card.querySelector(".pick").value = String(i); card.querySelector(".pick").onchange();
  });
};
$("#files").onclick = () => $("#filepick").click();
function b64(file){ return new Promise(res => { const r = new FileReader();
  r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(file); }); }
$("#filepick").onchange = async e => {
  const first = document.querySelector(".student");
  if(first && !first.querySelector(".work").value.trim() && !first.querySelector(".name").value.trim()) first.remove();
  let n = 0, sawTeams = false; const errors = [];
  for (const f of e.target.files) {
    $("#status").textContent = "Reading " + f.name + " …";
    const r = await fetch("/api/parse", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({filename:f.name, data:await b64(f), mode:$("#split").value})});
    const d = await r.json();
    if(d.error){ errors.push(d.error); continue; }   // shown after the summary, so later files can't hide it
    if(d.teams){                                   // a Teams status export: names + status, not student work
      TEAMS = d.teams;
      if(TEAMS.assignment) $("#atitle").value = TEAMS.assignment;
      sawTeams = true; continue;
    }
    d.students.forEach(s => { addStudent(s.name, s.work); n++; });
  }
  if(n && ROSTER.length) matchAll(true);
  else if(sawTeams && !n) $("#status").textContent = "Teams status export loaded: " + TEAMS.students.length + " students. Now upload the students' work (or paste it), and each card will show its Teams status.";
  else if(n) $("#status").textContent = n + " student" + (n===1?"":"s") + " loaded. Choose a course to match them to the class list, then check the work and click Generate.";
  else $("#status").textContent = "";
  if(!document.querySelector(".student")) addStudent();   // nothing loaded: put back the blank card removed above
  errors.forEach(msg => { const s = document.createElement("div"); s.className = "err"; s.textContent = msg; $("#status").append(s); });
  applyTeams();
  e.target.value = "";
};
function showErr(msg){ $("#status").textContent = ""; const s = document.createElement("span"); s.className = "err"; s.textContent = msg; $("#status").append(s); }
function loadAssessList(){
  fetch("/api/assessments").then(r=>r.json()).then(d=>{
    if($("#assess") === document.activeElement) return;   // don't swap options under an open menu
    const sel = $("#assess"), folders = d.folders || [];
    sel.replaceChildren(new Option(d.error ? "Assessment folder unreadable" : folders.length ? "Load from Assessment folder…" : "No Assessment folders found", ""));
    folders.forEach(f => sel.add(new Option(f.label, f.path)));   // text, not HTML: folder names can contain < or &
    sel.title = d.error || "Student files saved under Desktop/Teaching/Assessment";
  }).catch(() => {});
}
loadAssessList();
window.addEventListener("focus", loadAssessList);   // pick up folders saved while you were in another app
$("#assess").onchange = async e => {
  const path = e.target.value; if(!path) return;
  e.target.value = "";
  $("#status").textContent = "Reading " + path + " …";
  let d;
  try { d = await (await fetch("/api/load", {method:"POST", headers:{"Content-Type":"application/json"}, body: JSON.stringify({path})})).json(); }
  catch(err){ return showErr("Couldn't reach the app to read " + path + "."); }
  if(d.error) return showErr(d.error);
  const have = new Set([...document.querySelectorAll(".student")].map(c => c.querySelector(".name").value.trim() + "\n" + c.querySelector(".work").value.trim()));
  const fresh = d.students.filter(s => !have.has(s.name + "\n" + s.work));   // loading the same folder twice adds nothing
  const first = document.querySelector(".student");
  if(fresh.length && first && !first.querySelector(".work").value.trim() && !first.querySelector(".name").value.trim()) first.remove();
  fresh.forEach(s => addStudent(s.name, s.work));
  const dup = d.students.length - fresh.length, again = dup ? " (" + dup + " already on the page, skipped)" : "";
  if(fresh.length && ROSTER.length) matchAll(true);   // its class-list summary is the more useful status
  else $("#status").textContent = fresh.length + " student" + (fresh.length===1?"":"s") + " loaded from " + path + again + "." +
    (fresh.length ? " Choose a course to match them to the class list, then check the work and click Generate." : "");
  if(fresh.length && ROSTER.length && dup) $("#status").textContent += again;
  applyTeams();
};
function csvCell(t){ return '"' + String(t).replace(/"/g,'""') + '"'; }
$("#dlteams").onclick = () => {
  const done = [...document.querySelectorAll(".student")].map(c => ({c, o: c.querySelector(".out"), t: teamsFor(c)}))
    .filter(x => x.o && !x.o.classList.contains("err"));
  const order = TEAMS ? TEAMS.students.map(s => s.name) : [];
  const pos = x => x.t ? order.indexOf(x.t.name) : -1;
  done.sort((a, b) => (pos(a) < 0 ? 1e9 : pos(a)) - (pos(b) < 0 ? 1e9 : pos(b)));   // Teams order; unmatched last
  const rows = [["Full Name", "Teams status", "Feedback"]].concat(done.map(x =>
    [x.t ? x.t.name : x.c.querySelector(".name").value, x.t ? x.t.status : "", x.o.innerText]));
  const title = ($("#atitle").value || "assignment").replace(/[^\w\- ]+/g, "").replace(/\s+/g, " ").trim() || "assignment";
  const blob = new Blob(["\ufeff" + rows.map(r => r.map(csvCell).join(",")).join("\n")], {type: "text/csv"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "feedback - " + title + ".csv"; a.click();
};
$("#dl").onclick = () => {
  const rows = [["Student","Feedback"]];
  document.querySelectorAll(".student").forEach(c => {
    const o = c.querySelector(".out"); if(o && !o.classList.contains("err")) rows.push([c.querySelector(".name").value, o.innerText]);
  });
  const blob = new Blob(["\ufeff" + rows.map(r=>r.map(csvCell).join(",")).join("\n")], {type:"text/csv"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "feedback.csv"; a.click();
};

$("#go").onclick = async () => {
  const rubric = $("#rubric").value.trim();
  const stds = [...document.querySelectorAll(".std:checked")].map(c=>c.value);
  if(!rubric && !stds.length){ $("#status").textContent = "Add an assignment description or tick a learning standard."; return; }
  let cards = [...document.querySelectorAll(".student")].filter(c => c.querySelector(".work").value.trim());
  applyTeams();
  const skipped = $("#skipret").checked ? cards.filter(c => c.dataset.tstatus === "Returned") : [];
  skipped.forEach(c => { c.querySelector(".result").innerHTML = '<div class="status">Skipped: already returned in Teams.</div>'; });
  cards = cards.filter(c => !skipped.includes(c));
  if(!cards.length){ $("#status").textContent = skipped.length ? "Everyone with work loaded is already Returned in Teams (untick the skip box to redo them)." : "Paste some student work first."; return; }
  $("#go").disabled = true;
  let i = 0, failed = 0;
  for (const c of cards) {
    if(window.feedbackStopRequested) break;
    i++;
    const name = c.querySelector(".name").value.trim() || "Student " + i;
    const res = c.querySelector(".result");
    $("#status").textContent = `Writing ${i} of ${cards.length}: ${name} …`;
    res.innerHTML = "";
    try {
      const r = await fetch("/api/generate", {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({model:$("#model").value, rubric, doc:$("#doc").value, standards:stds, grade:c.querySelector(".sgrade").value || $("#grade").value, term:$("#quarter").value ? SCHOOL_YEAR + " " + $("#quarter").value : "", length:$("#length").value, title:$("#atitle").value, label:name,
                              work:c.querySelector(".work").value, notes:c.querySelector(".notes").value, level:c.querySelector(".level").value})});
      const d = await r.json();
      if(d.error) throw new Error(d.error);
      const out = document.createElement("div"); out.className = "out"; out.contentEditable = "true"; out.textContent = d.feedback.replace(/\*\*/g, "");  // plain text on the page, so Copy and the .csv files carry no asterisks
      const copy = document.createElement("button"); copy.textContent = "Copy"; copy.style.marginTop = "8px";
      copy.onclick = () => { navigator.clipboard.writeText(out.innerText); copy.textContent = "Copied"; setTimeout(()=>copy.textContent="Copy",1500); };
      res.append(out, copy);
    } catch(err) {
      failed++; res.innerHTML = '<div class="out err"></div>'; res.firstChild.textContent = err.message;
    }
  }
  $("#status").textContent = (window.feedbackStopRequested ? "Stopped after " + i + " students. Existing drafts remain available." : failed ? failed + " of " + cards.length + " failed (see the red messages)." : "Done. Feedback is editable: tweak it, then copy.") + (skipped.length ? " Skipped " + skipped.length + " already returned in Teams." : "");
  $("#go").disabled = false; $("#dl").disabled = false; $("#dlteams").disabled = false;
};
</script><link rel="stylesheet" href="/ui/workspace.css"><script src="/ui/workspace.js"></script><script src="/ui/assignment.js"></script><script src="/ui/jobs.js"></script></main></body></html>"""


ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


class Handler(BaseHTTPRequestHandler):
    def _host_ok(self):
        """Refuse any other Host: stops a web page using DNS rebinding to read class lists from this server."""
        if (self.headers.get("Host") or "").lower() in ALLOWED_HOSTS:
            return True
        self._send(403, {"error": "forbidden"})
        return False

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return
        if self.path == "/":
            self._send(200, PAGE.encode(), "text/html")
        elif self.path in ("/ui/workspace.css", "/ui/workspace.js", "/ui/assignment.js", "/ui/jobs.js"):
            asset = HERE / self.path.lstrip("/")
            self._send(200, asset.read_bytes(), "text/css" if asset.suffix == ".css" else "text/javascript")
        elif self.path == "/api/courses":
            try:
                cfg = course_data()
            except (OSError, ValueError) as e:
                return self._send(200, {"error": f"courses: {e}"})
            docs = list(load_standards())
            for c in cfg.get("courses", []):  # resolve department -> standards document name
                c["doc"] = next((d for d in docs if c.get("department") and d.lower().startswith(c["department"].lower())), "")
            self._send(200, {"courses": cfg.get("courses", []), "quarters": cfg.get("quarters", []),
                             "school_year": cfg.get("school_year", ""), "source": cfg.get("source", ""),
                             "note": cfg.get("note", "")})
        elif self.path.startswith("/api/roster"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                students = roster_for(q.get("name", [""])[0], q.get("quarter", [""])[0])
                self._send(200, {"students": students})
            except RuntimeError as e:
                self._send(200, {"error": str(e)})
        elif self.path == "/api/assessments":
            try:
                self._send(200, {"folders": list_assessments()})
            except OSError as e:  # e.g. macOS hasn't allowed this app to read the Desktop
                self._send(200, {"folders": [], "error": f"Can't read {ASSESSMENT}: {e.strerror or e}. If macOS blocked it, allow "
                                                       "Terminal (or the launcher) under System Settings > Privacy & Security > Files and Folders."})
        elif self.path == "/api/assignments":
            self._send(200, {"assignments": list_assignment_records()})
        elif self.path.startswith("/api/assignments/"):
            try:
                self._send(200, {"assignment": load_assignment_record(urllib.parse.unquote(self.path.rsplit("/", 1)[1]))})
            except (ValueError, FileNotFoundError):
                self._send(200, {"error": "Assignment not found."})
        elif self.path == "/api/class-map":
            self._send(200, {"map": _read_json(CLASS_MAP, {})})
        elif self.path.startswith("/api/jobs"):
            try:
                if QUEUE is None:
                    raise RuntimeError("The job worker isn't running.")
                parts = urllib.parse.urlparse(self.path)
                if parts.path == "/api/jobs":
                    aid = urllib.parse.parse_qs(parts.query).get("assignment", [""])[0]
                    if aid != TEAMS_JOB_KEY:
                        load_assignment_record(aid)
                    return self._send(200, {"jobs": [_job_view(j) for j in QUEUE.list_for(aid)]})
                jid = parts.path.rsplit("/", 1)[1]
                if not JOB_ID.fullmatch(jid):
                    raise ValueError("bad job id")
                self._send(200, {"job": _job_view(QUEUE.get(jid, with_results=True))})
            except (ValueError, FileNotFoundError):
                self._send(200, {"error": "Job not found."})
            except Exception as e:
                self._send(200, {"error": f"{type(e).__name__}: {e}"})
        elif self.path.startswith("/api/session?"):
            try:
                aid = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query).get("assignment", [""])[0]
                self._send(200, load_session(aid))
            except (ValueError, FileNotFoundError):
                self._send(200, {"error": "Assignment not found."})
            except OSError as e:
                self._send(200, {"error": f"Can't read the saved session: {e.strerror or e}"})
        elif self.path == "/api/standards":
            docs = load_standards()
            self._send(200, {d: [{"id": x["id"], "label": x["label"]} for x in v] for d, v in docs.items()})
        elif self.path == "/api/models":
            models, offline = [], []
            for b, info in fb.BACKENDS.items():
                try:
                    names = fb.list_models(b)
                except Exception:  # not running, or answered with an error: leave it out and say so on the page
                    offline.append(info["label"])
                    continue
                models += [{"id": fb.model_id(b, n), "name": n, "engine": info["label"]} for n in names]
            if not models:
                self._send(200, {"error": "Can't reach Ollama or LM Studio. Start Ollama (`ollama serve` or the Ollama app) "
                                          "or LM Studio's server, then reload."})
            else:
                ids = [m["id"] for m in models]
                self._send(200, {"models": models, "offline": offline,
                                 "default": fb.DEFAULT_MODEL if fb.DEFAULT_MODEL in ids else ids[0]})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return
        if self.path == "/api/parse":
            p = {}
            try:
                n = int(self.headers.get("Content-Length", 0))
                p = json.loads(self.rfile.read(n))
                rows = parse_upload(p["filename"], base64.b64decode(p["data"]), p.get("mode", "auto"))
                if isinstance(rows, dict):                      # Teams status export
                    return self._send(200, rows)
                if not rows:                                    # say why, rather than silently loading nothing
                    why = ("no text found. It may be a scanned image: export it as a text PDF or .docx, or paste the work in"
                           if p["filename"].lower().endswith(".pdf") else "no student work found in this file")
                    return self._send(200, {"error": f"{p['filename']}: {why}."})
                return self._send(200, {"students": [{"name": a, "work": b} for a, b in rows]})
            except Exception as e:
                return self._send(200, {"error": f"{p.get('filename', 'file')}: {type(e).__name__}: {e}"})
        if self.path == "/api/load":
            try:
                n = int(self.headers.get("Content-Length", 0))
                rows = load_assessment(json.loads(self.rfile.read(n))["path"])
                if not rows:
                    return self._send(200, {"error": "No student work found in that folder."})
                return self._send(200, {"students": [{"name": a, "work": b} for a, b in rows]})
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})
        if self.path in ("/api/assignments", "/api/class-map", "/api/session") or self.path.startswith("/api/jobs"):
            # Saving needs a JSON request from this app's own page: another website can't send one without the
            # browser asking first (a preflight this server never approves), and a stated Origin must be this app.
            origin = self.headers.get("Origin")
            if not self.headers.get("Content-Type", "").startswith("application/json") or \
                    (origin and origin not in (f"http://127.0.0.1:{PORT}", f"http://localhost:{PORT}")):
                return self._send(403, {"error": "forbidden"})
            try:
                n = int(self.headers.get("Content-Length", 0))
                if n > (20_000_000 if self.path == "/api/session" or self.path.startswith("/api/jobs") else 500_000):
                    raise ValueError("too large")
                body = json.loads(self.rfile.read(n))
                if self.path == "/api/assignments":
                    try:
                        return self._send(200, {"assignment": save_assignment_record(body.get("assignment") or {}, body.get("baseVersion"))})
                    except VersionConflict as c:
                        return self._send(409, {"error": "This assignment was saved somewhere else after this page opened it.",
                                                "conflict": True, "current": c.current})
                if self.path.startswith("/api/jobs"):
                    if self.path == "/api/jobs":
                        enqueue = enqueue_teams_job if body.get("type") == "teams_read" else enqueue_draft_job
                        return self._send(200, {"job": _job_view(enqueue(body))})
                    _, _, _, jid, action = self.path.split("/")
                    if not JOB_ID.fullmatch(jid) or QUEUE is None:
                        raise ValueError("bad job id")
                    if action == "cancel":
                        job = QUEUE.cancel(jid)
                    elif action == "resume":
                        job = QUEUE.resume(jid)
                    elif action == "delivered":
                        job = QUEUE.mark_delivered(jid, [str(k) for k in body.get("keys", [])])
                    else:
                        raise ValueError("unknown action")
                    return self._send(200, {"job": _job_view(job)})
                if self.path == "/api/session":
                    try:
                        return self._send(200, save_session(str(body.get("assignment", "")), body.get("students"), body.get("baseVersion")))
                    except SessionConflict as c:
                        return self._send(409, {"error": "This session was saved somewhere else after this page opened it.",
                                                "conflict": True, "current": c.current})
                return self._send(200, {"map": save_class_mapping(body)})
            except FileNotFoundError:
                return self._send(200, {"error": "Not found: that assignment or job doesn't exist."})
            except Exception as e:
                return self._send(200, {"error": f"{type(e).__name__}: {e}"})
        if self.path != "/api/generate":
            return self._send(404, {"error": "not found"})
        p = {}
        try:
            n = int(self.headers.get("Content-Length", 0))
            p = json.loads(self.rfile.read(n))
            self._send(200, {"feedback": draft_for(p)})
        except (urllib.error.URLError, ConnectionError):
            engine, _ = fb.split_model(p.get("model", ""))
            self._send(200, {"error": fb.unreachable(engine) + ", then click Generate again."})
        except RuntimeError as e:  # the engine answered with its own error message (e.g. LM Studio couldn't load the model)
            self._send(200, {"error": str(e)})
        except Exception as e:  # surface any failure to the page
            self._send(200, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Student Feedback is already running at {url} - opening it in your browser.")
        webbrowser.open(url)
        raise SystemExit(0)
    start_worker()
    print(f"Student Feedback running at {url}  (Ctrl+C to stop)")
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
