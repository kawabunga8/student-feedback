#!/usr/bin/env python3
"""Collect submitted student work from a class team's SharePoint "Student Work" library, synced to this Mac by OneDrive.

Read-only on the synced folder: it never writes, renames, deletes or "frees up space" there, never follows symlinks,
and refuses to write output inside it. No network except the student-feedback app's own /api/roster and /api/courses
on 127.0.0.1. No browser. Student work never leaves this Mac.

Layout read (Teams' Student Work library):
    <sync root = .../Student Work/Submitted files>/<Student Display Name>/<files>                 (flat)
    <sync root>/<Student Display Name>/<Assignment folder>/<files>                                (nested)

For one assignment it:
  1. finds each student's files for that assignment (by assignment folder, else by file name);
  2. matches the student folder to the live class list (stage_submissions.match_student);
  3. reads text from .txt/.md/.docx/.pdf; lists audio, video, images and other files without reading them;
  4. stages into the existing Assessment folder convention (stage_submissions.staged_path), one
     First_Last.txt per student, plus _NEEDS_ATTENTION_, _MISSING_SUBMISSIONS.txt and _NON_TEXT_SUBMISSIONS.txt.

Dry run is the default; --commit writes. Re-runs never overwrite: identical work is skipped, and work that differs
from what is already staged (which may have been reviewed) goes to _CHANGED_<First_Last>.txt for the teacher.

Files OneDrive keeps only in the cloud are not opened (opening one downloads it) unless you pass --hydrate.

The report shows student names, for the teacher on this Mac. Use --counts-only for output you will share
(with Claude, in a log or with anyone else).

Usage:
    python3 sharepoint_collect.py --root ".../Student Work/Submitted files" --list-assignments
    python3 sharepoint_collect.py --root "..." --course "Band 11" --quarter 1 --assignment "Scales Test"
    python3 sharepoint_collect.py --root "..." --course "Band 11" --quarter 1 --assignment "Scales Test" --commit
"""
import argparse
import json
import os
import re
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import stage_submissions as S

MAX_DEPTH = 3                      # student folder (1) / assignment folder (2) / file (3)
MAX_FILE_BYTES = 12 * 1024 * 1024  # same limit as attachment_collect
MAX_TEXT = 120000
DEFAULT_MAX_MB = 300               # total bytes read per run (each read of a cloud-only file is a download)
SF_DATALESS = 0x40000000           # macOS st_flags: the file's contents are only in the cloud
TEXT_TYPES = {".txt", ".md", ".docx", ".pdf"}
KINDS = {
    "audio": {".mp3", ".m4a", ".wav", ".aac", ".aif", ".aiff", ".ogg", ".flac", ".wma"},
    "video": {".mp4", ".mov", ".m4v", ".avi", ".webm", ".mkv", ".wmv"},
    "image": {".png", ".jpg", ".jpeg", ".heic", ".gif", ".bmp", ".tif", ".tiff", ".webp"},
    "slides": {".pptx", ".ppt", ".key"},
    "spreadsheet": {".xlsx", ".xls", ".csv", ".numbers"},
    "notation": {".mscz", ".mscx", ".musicxml", ".mxl", ".sib", ".mid", ".midi"},
}
SKIP_NAME = re.compile(r"^(?:\.|~\$|Icon\r$)|\.(?:tmp|lnk)$", re.I)   # hidden, Office lock files, Finder icons


def kind_of(name):
    ext = Path(name).suffix.lower()
    if ext in TEXT_TYPES:
        return "text"
    return next((k for k, exts in KINDS.items() if ext in exts), "other")


# ---------- reading the synced folder (the transport seam: a Graph source would provide the same two calls) ----------

class LocalFolder:
    """Read-only view of a synced 'Submitted files' folder."""

    def __init__(self, root):
        self.root = Path(root)
        if not self.root.is_dir():
            raise SystemExit(f"Sync folder not found: {self.root}")
        self.real = Path(os.path.realpath(self.root))

    def entries(self):
        """Every file to depth MAX_DEPTH as dicts {parts, size, dataless, mtime}, plus what was skipped and why.
        lstat only: listing never downloads a cloud-only file."""
        files, skipped = [], {"symlinks": 0, "too_deep": 0, "unreadable": 0}

        def walk(d, parts):
            try:
                with os.scandir(d) as it:
                    items = sorted(it, key=lambda e: e.name)
            except OSError:
                skipped["unreadable"] += 1
                return
            for e in items:
                if SKIP_NAME.search(e.name):
                    continue
                if e.is_symlink():
                    skipped["symlinks"] += 1
                    continue
                if e.is_dir(follow_symlinks=False):
                    if len(parts) + 1 >= MAX_DEPTH:
                        skipped["too_deep"] += 1      # a folder at file depth: its contents are not read
                    else:
                        walk(e.path, parts + [e.name])
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    files.append({"parts": parts + [e.name], "size": st.st_size, "mtime": st.st_mtime,
                                  "dataless": bool(getattr(st, "st_flags", 0) & SF_DATALESS)})
        walk(self.root, [])
        return files, skipped

    def read(self, parts, limit):
        """Bytes of one file (refusing anything that resolves outside the sync folder)."""
        p = self.root.joinpath(*parts)
        real = Path(os.path.realpath(p))
        if real != self.real and self.real not in real.parents:
            raise ValueError("outside the sync folder")
        st = os.lstat(p)
        if not stat.S_ISREG(st.st_mode):
            raise ValueError("not a regular file")
        if st.st_size > limit:
            raise ValueError("too large to read")
        with open(p, "rb") as f:
            return f.read(limit + 1)[:limit]


# ---------- matching ----------

def _tokens(s):
    return S._norm(s.replace("_", " ")).split()


def name_matches(name, assignment):
    """Exact after normalising, or one name's words appearing in order inside the other's ("Task 2" ~ "Task 2: Define",
    but not "Task 20")."""
    a, b = _tokens(name), _tokens(assignment)
    if not a or not b:
        return False
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    return any(long_[i:i + len(short)] == short for i in range(len(long_) - len(short) + 1))


def list_assignments(files):
    """Assignment folder names (depth 2) -> number of students with that folder. Folder names are the teacher's
    assignment names, not student names."""
    seen = {}
    for f in files:
        if len(f["parts"]) == 3:
            seen.setdefault(f["parts"][1], set()).add(f["parts"][0])
    return {k: len(v) for k, v in sorted(seen.items(), key=lambda kv: (-len(kv[1]), kv[0]))}


def files_for(student_files, assignment):
    """One student's files for the assignment: (files, problem). Prefers one matching assignment folder; falls back to
    files at the student's top level whose names match. Never guesses between two candidates."""
    folders = sorted({f["parts"][1] for f in student_files if len(f["parts"]) == 3})
    exact = [d for d in folders if S._norm(d) == S._norm(assignment)]
    hits = exact or [d for d in folders if name_matches(d, assignment)]
    if len(hits) > 1:
        return [], "more than one folder could be this assignment: " + ", ".join(hits)
    if hits:
        return [f for f in student_files if len(f["parts"]) == 3 and f["parts"][1] == hits[0]], None
    flat = [f for f in student_files if len(f["parts"]) == 2 and name_matches(Path(f["parts"][1]).stem, assignment)]
    return flat, None


# ---------- reading text ----------

def extract(src, f):
    """(text, None) or (None, reason). Only for text types."""
    ext = Path(f["parts"][-1]).suffix.lower()
    raw = src.read(f["parts"], MAX_FILE_BYTES)
    if ext in (".txt", ".md"):
        return raw.decode("utf-8-sig", "replace").strip()[:MAX_TEXT], None
    if ext == ".docx":
        from attachment_collect import docx_text   # imported here: the rest of that module is browser code
        return docx_text(raw), None
    if ext == ".pdf":
        r = subprocess.run(["pdftotext", "-", "-"], input=raw, capture_output=True, timeout=60)
        text = r.stdout.decode("utf-8", "replace").strip()
        return (text[:MAX_TEXT], None) if text else (None, "no text in this PDF (a scan or image?)")
    return None, "not a text file"


# ---------- the run ----------

def collect(root, assignment, roster, hydrate=False, since=None, max_bytes=DEFAULT_MAX_MB * 1024 * 1024):
    """Read and match; writes nothing. Returns a result dict for report() and write()."""
    src = LocalFolder(root)
    files, skipped = src.entries()
    by_student = {}
    loose = 0
    for f in files:
        if len(f["parts"]) == 1:
            loose += 1                       # a file directly in Submitted files: not inside any student folder
        else:
            by_student.setdefault(f["parts"][0], []).append(f)

    res = {"assignment": assignment, "skipped": dict(skipped, loose_files=loose), "matched": [], "flagged": [],
           "non_text": [], "no_work": [], "cloud_only": [], "unreadable": [], "missing": [], "roster_size": len(roster),
           "bytes_read": 0, "byte_cap_hit": False}
    covered = set()
    for folder, sfiles in sorted(by_student.items()):
        mine, problem = files_for(sfiles, assignment)
        if problem:
            res["flagged"].append({"folder": folder, "reason": problem, "text": ""})
            student, _ = S.match_student(folder, roster)
            if student:
                covered.add(student["id"])           # submitted something; the teacher picks which folder
            continue
        if since is not None:
            mine = [f for f in mine if f["mtime"] >= since]
        if not mine:
            res["no_work"].append(folder)          # has a folder, but nothing for this assignment
            continue
        student, why = S.match_student(folder, roster)
        texts, other, cloud, bad = [], [], [], []
        for f in mine:
            name = f["parts"][-1]
            k = kind_of(name)
            if k != "text":
                other.append({"name": name, "kind": k, "size": f["size"]})
                continue
            if f["dataless"] and not hydrate:
                cloud.append(name)
                continue
            if res["bytes_read"] + f["size"] > max_bytes:
                res["byte_cap_hit"] = True
                bad.append((name, "run size limit reached"))
                continue
            try:
                text, err = extract(src, f)
                res["bytes_read"] += f["size"]
            except Exception as e:                  # a damaged file stops only itself
                text, err = None, str(e) or type(e).__name__
            if text:
                texts.append((name, text))
            else:
                bad.append((name, err or "no text"))
        if cloud:
            res["cloud_only"].append({"folder": folder, "files": cloud})
        if bad:
            res["unreadable"].append({"folder": folder, "files": bad})
        if other:
            res["non_text"].append({"folder": folder, "student": student, "files": other})
        if student:
            covered.add(student["id"])               # submitted something, even if nothing readable as text
        if not texts:
            continue
        body = texts[0][1] if len(texts) == 1 else "\n\n".join(f"[file: {n}]\n{t}" for n, t in texts)
        if student:
            res["matched"].append({"folder": folder, "student": student, "text": body})
        else:
            res["flagged"].append({"folder": folder, "reason": why, "text": body})
    ids = [m["student"]["id"] for m in res["matched"]]
    for m in [m for m in res["matched"] if ids.count(m["student"]["id"]) > 1]:   # two folders, one student: don't pick
        res["matched"].remove(m)
        res["flagged"].append({"folder": m["folder"], "reason": "more than one SharePoint folder matches "
                               f"{m['student']['first']} {m['student']['last']}", "text": m["text"]})
    res["missing"] = [s for s in roster if s["id"] not in covered]
    return res


def _safe(s):
    return re.sub(r"[\\/:*?\"<>|]", "-", s).strip()


def write(res, dest, root):
    """Stage into dest. Never overwrites a student's work: identical -> skipped, different -> _CHANGED_ file."""
    dest = Path(dest)
    real_dest, real_root = Path(os.path.realpath(dest)), Path(os.path.realpath(root))
    if real_dest == real_root or real_root in real_dest.parents:
        raise SystemExit("Refusing to write inside the synced SharePoint folder.")
    dest.mkdir(parents=True, exist_ok=True)

    def put(path, text):
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    out = {"written": 0, "unchanged": 0, "changed": 0, "flag_files": 0}
    for m in res["matched"]:
        stem = _safe(f"{m['student']['first']}_{m['student']['last']}")
        path = dest / f"{stem}.txt"
        if path.exists():
            if path.read_text(encoding="utf-8", errors="replace").strip() == m["text"].strip():
                out["unchanged"] += 1
                continue
            put(dest / f"_CHANGED_{stem}.txt", "[This student's SharePoint work differs from the file already staged, "
                "which may have been reviewed. Compare, then replace the staged file yourself if this is newer.]\n\n" + m["text"])
            out["changed"] += 1
            continue
        put(path, m["text"])
        out["written"] += 1
    for fl in res["flagged"]:
        put(dest / f"_NEEDS_ATTENTION_{_safe(fl['folder'])}.txt",
            f"[Could not auto-match to roster: {fl['reason']}]\n[SharePoint folder: {fl['folder']}]\n\n{fl['text']}")
        out["flag_files"] += 1
    if res["missing"]:
        put(dest / "_MISSING_SUBMISSIONS.txt", "On the class list, but nothing for this assignment in SharePoint:\n\n"
            + "\n".join(f"- {s['first']} {s['last']}" for s in res["missing"]) + "\n")
    if res["non_text"]:
        lines = [f"- {n['folder']}: " + ", ".join(f"{f['name']} ({f['kind']})" for f in n["files"]) for n in res["non_text"]]
        put(dest / "_NON_TEXT_SUBMISSIONS.txt", "Submitted in SharePoint but not readable as text (listen, watch or open "
            "these yourself):\n\n" + "\n".join(lines) + "\n")
    return out


def report(res, counts_only=False, dest=None, written=None):
    """Plain-text summary. counts_only leaves out every student name, folder name and file name."""
    def names(items, fmt):
        return [] if counts_only else ["   " + fmt(i) for i in items]
    kinds = {}
    for n in res["non_text"]:
        for f in n["files"]:
            kinds[f["kind"]] = kinds.get(f["kind"], 0) + 1
    sk = res["skipped"]
    L = [f"Assignment:  {res['assignment']}", f"Class list:  {res['roster_size']} students"]
    if dest and not counts_only:
        L.append(f"Destination: {dest}")
    L += ["-" * 60, f"Matched with readable text:        {len(res['matched'])}"]
    L += names(res["matched"], lambda m: f"{m['folder']}  ->  {m['student']['first']} {m['student']['last']}")
    L.append(f"Need attention (not matched):      {len(res['flagged'])}")
    L += names(res["flagged"], lambda f: f"{f['folder']}  -  {f['reason']}")
    L.append(f"Non-text submissions (not read):   {len(res['non_text'])} students, "
             + (", ".join(f"{v} {k}" for k, v in sorted(kinds.items())) or "no files"))
    L += names(res["non_text"], lambda n: f"{n['folder']}: " + ", ".join(f["name"] for f in n["files"]))
    L.append(f"Cloud-only, not opened:            {sum(len(c['files']) for c in res['cloud_only'])} files"
             + (" (run again with --hydrate to download and read them)" if res["cloud_only"] else ""))
    L += names(res["cloud_only"], lambda c: f"{c['folder']}: " + ", ".join(c["files"]))
    L.append(f"Text files that could not be read: {sum(len(u['files']) for u in res['unreadable'])}")
    L += names(res["unreadable"], lambda u: f"{u['folder']}: " + "; ".join(f"{n} ({why})" for n, why in u["files"]))
    L.append(f"Student folders with nothing for this assignment: {len(res['no_work'])}")
    L.append(f"On the class list, nothing found:  {len(res['missing'])}")
    L += names(res["missing"], lambda s: f"{s['first']} {s['last']}")
    extra = [f"{v} {k.replace('_', ' ')}" for k, v in sk.items() if v]
    if extra:
        L.append("Skipped (not read): " + ", ".join(extra))
    if res["byte_cap_hit"]:
        L.append("Stopped reading at the run size limit; raise --max-mb to read the rest.")
    L.append("-" * 60)
    if written:
        L.append(f"Written: {written['written']} new, {written['unchanged']} unchanged, {written['changed']} changed "
                 f"(saved as _CHANGED_ files, nothing overwritten), {written['flag_files']} need-attention files.")
    else:
        L.append("DRY RUN: nothing written. Run again with --commit to stage these files.")
    return "\n".join(L)


def school_year():
    """The current school year folder name (e.g. 2026-27) from the running app, or ''."""
    try:
        with urllib.request.urlopen(f"{S.APP_BASE}/api/courses", timeout=10) as r:
            return json.load(r).get("school_year", "") or ""
    except (urllib.error.URLError, OSError, ValueError):
        return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help='The synced ".../Student Work/Submitted files" folder')
    ap.add_argument("--list-assignments", action="store_true", help="List assignment folders found, then stop")
    ap.add_argument("--course", help="Course name exactly as the app shows it")
    ap.add_argument("--quarter", help="Quarter number, e.g. 1")
    ap.add_argument("--assignment", help="Assignment name (matched against assignment folder or file names)")
    ap.add_argument("--year", help="School year folder, e.g. 2026-27 (default: from the running app)")
    ap.add_argument("--roster-file", help="Class list as JSON (e.g. _roster.json from tools/deidentify_shape.py) instead of the app's")
    ap.add_argument("--since", help="Only files changed on or after this date (YYYY-MM-DD). Sync time can differ from submit time.")
    ap.add_argument("--hydrate", action="store_true", help="Download and read cloud-only files")
    ap.add_argument("--max-mb", type=int, default=DEFAULT_MAX_MB, help=f"Most data to read in one run (default {DEFAULT_MAX_MB})")
    ap.add_argument("--counts-only", action="store_true", help="Leave every name out of the report (for sharing)")
    ap.add_argument("--commit", action="store_true", help="Write the Assessment folder (default: dry run)")
    a = ap.parse_args()

    if a.list_assignments:
        files, _ = LocalFolder(a.root).entries()
        found = list_assignments(files)
        flat = len({f["parts"][0] for f in files if len(f["parts"]) == 2})
        print(f"{len(found)} assignment folders" + (":" if found else "."))
        for name, n in found.items():
            print(f"   {n:3d} students  {name}")
        print(f"{flat} student folders also have files directly inside them (flat layout).")
        return
    if not (a.course and a.quarter and a.assignment):
        ap.error("--course, --quarter and --assignment are needed (or use --list-assignments)")
    since = None
    if a.since:
        import datetime as dt
        since = dt.datetime.strptime(a.since, "%Y-%m-%d").timestamp()
    if a.roster_file:
        roster = json.loads(Path(a.roster_file).read_text(encoding="utf-8"))
    else:
        try:
            roster = S.fetch_roster(a.course, a.quarter)
        except RuntimeError as e:
            print(f"WARNING: {e} Everything will be flagged for manual review.", file=sys.stderr)
            roster = []
    year = a.year or school_year()
    if not year:
        sys.exit("Couldn't get the school year from the app. Pass --year, e.g. --year 2026-27.")
    dest = S.staged_path(year, a.quarter, a.course, a.assignment)
    res = collect(a.root, a.assignment, roster, a.hydrate, since, a.max_mb * 1024 * 1024)
    written = write(res, dest, a.root) if a.commit else None
    print(report(res, a.counts_only, dest, written))


if __name__ == "__main__":
    main()
