"""List a class's submitted files per student as METADATA ONLY (name, kind, size, modified, link).

Works on `entries`: [{"path": "<student>/<assignment folder>/[<subfolder>/]<file>", "bytes": int, "modified": str,
"url": str}] with paths relative to the library's `Submitted files` folder. Entries come from either a local folder
(entries_from_folder, e.g. a synced or downloaded copy) or a read-only SharePoint listing made in the signed-in page.
No file is ever opened, downloaded, transcribed or thumbnailed here. See docs/BAND-PERFORMANCE-EVIDENCE-DESIGN.md.

Matching is conservative, like the Teams reader: a student folder that does not match the roster exactly once, or an
assignment folder that does not match the title exactly once, is flagged, never guessed.
"""
import os
from pathlib import Path

import observe
from stage_submissions import _norm, match_student

MAX_ENTRIES, MAX_DEPTH = 20000, 6
SF_DATALESS = 0x40000000          # macOS: a OneDrive/iCloud placeholder whose bytes are not on this computer yet


def entries_from_folder(root):
    """Walk a local folder (never following symlinks) and return metadata entries. Never opens a file."""
    root = Path(root)
    out = []
    for dp, dn, fn in os.walk(root, followlinks=False):
        rel = Path(dp).relative_to(root)
        if len(rel.parts) >= MAX_DEPTH:
            dn[:] = []
            continue
        dn[:] = [d for d in dn if not d.startswith(".") and not os.path.islink(os.path.join(dp, d))]
        for f in fn:
            fp = Path(dp) / f
            if f.startswith(".") or fp.is_symlink():
                continue
            st = fp.stat()
            out.append({"path": "/".join((*rel.parts, f)), "bytes": st.st_size, "modified": str(int(st.st_mtime)),
                        "url": "", "cloud_only": bool(getattr(st, "st_flags", 0) & SF_DATALESS)})
            if len(out) >= MAX_ENTRIES:
                return out
    return out


def assignment_folder(names, title):
    """Exactly one of `names` that matches `title` (exact after normalising, else one unique containment), or None."""
    t = _norm(title)
    if not t:
        return None
    exact = [n for n in names if _norm(n) == t]
    if len(exact) == 1:
        return exact[0]
    if exact:
        return None
    part = [n for n in names if _norm(n) and (t in _norm(n) or _norm(n) in t)]
    return part[0] if len(part) == 1 else None


def build(entries, roster, title):
    """Group entries by roster student for the assignment `title`.

    Returns {"students": {student_id: {"name", "items": [{name, kind, bytes, modified, url, cloud_only}]}},
             "flagged": [{"folder": <student folder name as found>, "reason"}],
             "no_evidence": [student_id, ...]        # on the roster, nothing found for this assignment
             "other_assignment_files": int}           # files under folders that matched a different assignment
    """
    by_student = {}
    for e in (entries or [])[:MAX_ENTRIES]:
        parts = [p for p in str(e.get("path", "")).split("/") if p]
        if len(parts) < 3:                      # student/assignment/file at least; files straight in a student folder are flagged
            if len(parts) == 2:
                by_student.setdefault(parts[0], {}).setdefault("", []).append((parts[1:], e))
            continue
        by_student.setdefault(parts[0], {}).setdefault(parts[1], []).append((parts[2:], e))

    students, flagged, covered, other = {}, [], set(), 0
    for folder, groups in sorted(by_student.items()):
        stu, reason = match_student(folder, roster)
        if not stu:
            flagged.append({"folder": folder, "reason": reason or "no roster match"})
            continue
        named = [g for g in groups if g]
        chosen = assignment_folder(named, title)
        other += sum(len(v) for g, v in groups.items() if g and g != chosen)    # files under other assignments
        if chosen is None:
            if "" in groups:
                flagged.append({"folder": folder, "reason": "files sit directly in the student folder (no assignment folder)"})
            elif len(named) > 1 and any(_norm(title) in _norm(n) or _norm(n) in _norm(title) for n in named):
                flagged.append({"folder": folder, "reason": "more than one assignment folder could match the title"})
            continue
        items = []
        for rest, e in groups[chosen]:
            name = rest[-1]
            items.append({"name": name, "kind": observe.classify(name), "bytes": int(e.get("bytes") or 0),
                          "modified": str(e.get("modified") or ""), "url": str(e.get("url") or ""),
                          "cloud_only": bool(e.get("cloud_only"))})
        if items:
            covered.add(stu["id"])
            students[stu["id"]] = {"name": f"{stu['first']} {stu['last']}", "items": sorted(items, key=lambda i: i["name"])}
    return {"students": students, "flagged": flagged,
            "no_evidence": [s["id"] for s in roster if s["id"] not in covered], "other_assignment_files": other}


def counts(result):
    """Counts only (no names): safe to print or share."""
    kinds, cloud = {}, 0
    for s in result["students"].values():
        for i in s["items"]:
            kinds[i["kind"]] = kinds.get(i["kind"], 0) + 1
            cloud += 1 if i.get("cloud_only") else 0
    return {"students_with_evidence": len(result["students"]), "flagged": len(result["flagged"]),
            "no_evidence": len(result["no_evidence"]), "files_by_kind": kinds, "cloud_only_files": cloud,
            "files_under_other_assignments": result["other_assignment_files"]}


def main():
    """CLI. Dry run by default; prints counts only (add --verbose to see names). --commit writes evidence.json."""
    import argparse, json, sys
    import stage_submissions as S
    ap = argparse.ArgumentParser(description="List submitted files per student as metadata only (nothing is opened or downloaded).")
    ap.add_argument("--root", help="local folder shaped like Submitted files/<student>/<assignment>/... (a synced or downloaded copy)")
    ap.add_argument("--entries", help="JSON file of entries [{path, bytes, modified, url}] from a read-only SharePoint listing")
    ap.add_argument("--course", required=True, help="exact course name as the app shows it")
    ap.add_argument("--quarter", required=True)
    ap.add_argument("--title", required=True, help="assignment title (matched to the assignment folder)")
    ap.add_argument("--out", help="the assignment's session folder; evidence.json is written there with --commit")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--verbose", action="store_true", help="also print student names (default prints counts only)")
    a = ap.parse_args()
    if bool(a.root) == bool(a.entries):
        sys.exit("Give exactly one of --root or --entries.")
    entries = entries_from_folder(a.root) if a.root else json.load(open(a.entries, encoding="utf-8"))
    try:
        roster = S.fetch_roster(a.course, a.quarter)
    except RuntimeError as e:
        sys.exit(str(e))
    res = build(entries, roster, a.title)
    print(json.dumps(counts(res), indent=1))
    if a.verbose:
        for sid, v in res["students"].items():
            print(" ", v["name"], len(v["items"]), "file(s)")
        for f in res["flagged"]:
            print("  flagged:", f["folder"], "-", f["reason"])
    if not a.commit:
        print("Dry run: nothing written. Add --commit with --out to save evidence.json.")
        return
    if not a.out:
        sys.exit("--commit needs --out (the assignment's session folder).")
    out = Path(a.out)
    if not out.is_dir():
        sys.exit("The session folder does not exist yet. Save the assessment session in the app first.")
    (out / "evidence.json").write_text(json.dumps({"students": res["students"]}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("Wrote evidence.json (metadata only).")


if __name__ == "__main__":
    main()
