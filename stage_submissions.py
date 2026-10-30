#!/usr/bin/env python3
"""Folder-staging script for the assessment workflow (Phase A, step 1).

Given an assignment's collected student work (one text file per student,
already produced by whatever collection step pulled it from OneNote/Teams/
Canva/etc.), this script:

  1. Writes each student's work into the exact folder convention app.py and
     feedback.py already expect:
       ~/Desktop/Teaching/Assessment/<year>/<quarter>/<course>/<assignment>/FirstName_LastName.txt
  2. Checks the folder against the live class roster (via the student-feedback
     app's own running /api/roster endpoint) to find who's missing.
  3. Flags anything that couldn't be matched to a roster name, by writing a
     clearly-named placeholder file instead of silently dropping it.
  4. Prints an end-of-run summary: how many matched cleanly, how many are
     flagged, and where the folder is.

This script does NOT talk to OneNote, Teams, Canva, SharePoint, or any other
external submission source — that collection step (done separately, via
browser automation) is expected to have already produced one text blob per
student, handed to this script as a simple list of (student_name, work_text)
pairs, or as a folder of loosely-named .txt files to be matched against the
roster.

Run directly for a quick check of what the roster/collected-file matching
would produce (the --dry-run default); nothing is written to the Assessment
folder until you pass --commit.

Usage (dry run, see what would happen):
    python3 stage_submissions.py \
        --course "Computer Studies 10" \
        --assignment "Unit3-Lesson2" \
        --quarter 2 \
        --input ./collected/

Usage (actually write the Assessment folder):
    python3 stage_submissions.py \
        --course "Computer Studies 10" \
        --assignment "Unit3-Lesson2" \
        --quarter 2 \
        --input ./collected/ \
        --commit

--input is a folder of .txt/.md files, one per student. The filename (minus
extension, with underscores read as spaces) is matched against the roster by
fuzzy name match. A file that can't be confidently matched is still staged,
but as a "_NEEDS_ATTENTION_<original name>.txt" file, with a note inside
explaining why (no roster match, or an ambiguous match), so Phase A's
drafting step and Shingo's review both see it clearly rather than it being
silently skipped or silently mis-matched to the wrong student.
"""
import argparse
import datetime as dt
import json
import re
import shutil
import sys
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ASSESSMENT = Path.home() / "Desktop" / "Teaching" / "Assessment"
APP_BASE = "http://127.0.0.1:8765"  # the student-feedback app's own local server


def _norm(s):
    """Lowercase, strip accents/punctuation, collapse whitespace - for fuzzy name matching."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    return re.sub(r"\s+", " ", s).strip()


def fetch_roster(course_name, quarter):
    """Ask the running student-feedback app for the live roster of a course/quarter.

    Returns a list of {"id", "first", "last", "grade", "block"} dicts, or
    raises RuntimeError with a clear message if the app isn't running or
    Course Hub can't be reached - the caller should treat that as "no roster
    available, flag everything for manual review" rather than a hard stop.
    """
    url = f"{APP_BASE}/api/roster?name={urllib.parse.quote(course_name)}&quarter={quarter or ''}"
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.load(r)
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError(
            f"Can't reach the student-feedback app at {APP_BASE}. "
            f"Make sure it's running (`python3 app.py`) before staging. ({e})"
        )
    if "error" in data:
        raise RuntimeError(f"Roster lookup failed: {data['error']}")
    return data["students"]


def match_student(filename_stem, roster):
    """Match a collected file's name to one roster entry.

    Returns (student_dict_or_None, reason_if_unmatched).
    A roster entry's display name is "First Last"; matching is exact after
    normalization first, then "last name + first initial" as a fallback for
    files named loosely (e.g. a nickname, or "FirstName_L").
    """
    target = _norm(filename_stem.replace("_", " "))
    if not roster:
        return None, "no roster available"

    exact = [s for s in roster if _norm(f"{s['first']} {s['last']}") == target]
    if len(exact) == 1:
        return exact[0], None
    if len(exact) > 1:
        return None, "matched more than one roster entry (duplicate name?)"

    # fallback: last name present, and first name's first letter matches
    loose = [
        s for s in roster
        if _norm(s["last"]) and _norm(s["last"]) in target
        and target.strip() and s["first"][:1].lower() == target.strip()[:1]
    ]
    if len(loose) == 1:
        return loose[0], None

    return None, "no confident roster match"


def staged_path(year, quarter, course, assignment):
    safe = lambda s: re.sub(r"[\/:*?\"<>|]", "-", s.strip())
    return (
        ASSESSMENT
        / safe(str(year))
        / f"Q{quarter}"
        / safe(course)
        / safe(assignment)
    )


def stage(course, assignment, quarter, input_dir, year, commit):
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        sys.exit(f"Input folder not found: {input_dir}")

    files = sorted(
        f for f in input_dir.iterdir()
        if f.suffix.lower() in {".txt", ".md"} and not f.name.startswith(".")
    )
    if not files:
        sys.exit(f"No .txt/.md files found in {input_dir}")

    try:
        roster = fetch_roster(course, quarter)
        roster_note = f"{len(roster)} students in {course} (live roster)."
    except RuntimeError as e:
        roster = []
        roster_note = f"WARNING: {e} Everything will be flagged for manual review."

    dest = staged_path(year, quarter, course, assignment)
    matched, flagged = [], []
    covered_ids = set()

    for f in files:
        text = f.read_text(encoding="utf-8-sig", errors="replace").strip()
        if not text:
            flagged.append((f.name, "file is empty"))
            continue
        student, reason = match_student(f.stem, roster)
        if student:
            covered_ids.add(student["id"])
            out_name = f"{student['first']}_{student['last']}.txt"
            matched.append((f.name, out_name, text))
        else:
            flagged.append((f.name, reason, text))

    missing = [
        s for s in roster
        if s["id"] not in covered_ids
    ]

    # --- report ---
    print(f"\nCourse:      {course}")
    print(f"Assignment:  {assignment}")
    print(f"Quarter:     {quarter}")
    print(f"Roster:      {roster_note}")
    print(f"Destination: {dest}")
    print(f"\n{'DRY RUN - nothing written yet' if not commit else 'WRITING FILES'}")
    print("-" * 60)
    print(f"Matched cleanly:    {len(matched)}")
    for orig, out_name, _ in matched:
        print(f"   {orig}  ->  {out_name}")
    print(f"\nFlagged (need attention): {len(flagged)}")
    for item in flagged:
        name, reason = item[0], item[1]
        print(f"   {name}  -  {reason}")
    print(f"\nOn roster but no submission found: {len(missing)}")
    for s in missing:
        print(f"   {s['first']} {s['last']}")
    print("-" * 60)

    if not commit:
        print("\nRun again with --commit to actually write these files.")
        return

    dest.mkdir(parents=True, exist_ok=True)
    for orig, out_name, text in matched:
        (dest / out_name).write_text(text, encoding="utf-8")
    for item in flagged:
        name = item[0]
        reason = item[1]
        text = item[2] if len(item) > 2 else ""
        safe_stem = re.sub(r"[\/:*?\"<>|]", "-", Path(name).stem)
        flag_path = dest / f"_NEEDS_ATTENTION_{safe_stem}.txt"
        note = f"[Could not auto-match to roster: {reason}]\n[Original file: {name}]\n\n{text}"
        flag_path.write_text(note, encoding="utf-8")
    if missing:
        missing_note = "\n".join(f"- {s['first']} {s['last']}" for s in missing)
        (dest / "_MISSING_SUBMISSIONS.txt").write_text(
            f"On the roster for {course} but no submission found when this batch was staged "
            f"({dt.date.today().isoformat()}):\n\n{missing_note}\n",
            encoding="utf-8",
        )

    print(f"\nDone. Folder ready for Phase A drafting:\n  {dest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", required=True, help='Exact course name as Course Hub/the app shows it, e.g. "Computer Studies 10"')
    ap.add_argument("--assignment", required=True, help="Short assignment name/slug, used as the folder name")
    ap.add_argument("--quarter", required=True, help="Quarter number, e.g. 2")
    ap.add_argument("--input", required=True, help="Folder of collected .txt/.md files, one per student")
    ap.add_argument("--year", default=None, help="School year folder name, e.g. 2026-27 (default: current Course Hub school year, falls back to this calendar year)")
    ap.add_argument("--commit", action="store_true", help="Actually write the Assessment folder (default is dry-run)")
    args = ap.parse_args()

    year = args.year or str(dt.date.today().year)
    stage(args.course, args.assignment, args.quarter, args.input, year, args.commit)


if __name__ == "__main__":
    main()
