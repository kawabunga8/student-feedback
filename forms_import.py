"""Read a Microsoft Forms response export (the .xlsx or .csv a teacher downloads) into one entry per student.

Local and read-only: it works on the rows of a file the teacher chose, never contacts Forms, and returns the answers
only to the page that uploaded them. Forms' own bookkeeping columns (times, ids, auto-scores, quiz feedback) are kept
out of the work text, so the drafting model sees only what the student answered. Auto-scores are reported on the
side as information for the teacher; they are not a level and are never sent to the model.

Returns None when the rows are not a Forms export, so the generic spreadsheet reader can handle them.
"""
import re

MAX_ROWS, MAX_COLS, MAX_ANSWER = 300, 80, 4000
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
_META = {"id", "start time", "completion time", "last modified time", "email", "name", "total points", "quiz feedback"}
_ANON = {"anonymous", "anonymous user", ""}


def _norm(h):
    return re.sub(r"\s+", " ", (h or "").strip()).lower()


def is_forms_header(head):
    low = {_norm(h) for h in head}
    return "start time" in low and "completion time" in low and "id" in low


def _clean(v):
    return _CTRL.sub("", v or "").strip()


def forms_students(rows):
    """rows: header row + response rows (lists of str). Returns None, or
    {"anonymous": bool, "students": [{"name", "work", "points", "has_name"}], "notes": [str]}."""
    rows = [r for r in rows if any((c or "").strip() for c in r)]
    if not rows or not is_forms_header(rows[0]):
        return None
    head = rows[0][:MAX_COLS]
    low = [_norm(h) for h in head]
    notes = []
    if len(rows[0]) > MAX_COLS:
        notes.append(f"Only the first {MAX_COLS} columns were read.")
    body = rows[1:]
    if len(body) > MAX_ROWS:
        notes.append(f"Only the first {MAX_ROWS} responses were read ({len(body) - MAX_ROWS} left out).")
        body = body[:MAX_ROWS]
    name_i = low.index("name") if "name" in low else None
    mail_i = low.index("email") if "email" in low else None
    pts_i = low.index("total points") if "total points" in low else None
    q_idx = [i for i, h in enumerate(low) if h not in _META and not h.startswith(("points - ", "feedback - ")) and head[i].strip()]
    if not q_idx:
        notes.append("No question columns were found in this export.")
    cell = lambda r, i: _clean(r[i]) if i is not None and i < len(r) else ""
    anonymous = name_i is None and (mail_i is None or all(cell(r, mail_i).lower() in _ANON for r in body))
    if name_i is not None and all(not cell(r, name_i) for r in body):
        anonymous = all(mail_i is None or cell(r, mail_i).lower() in _ANON for r in body)
    if anonymous:
        notes.append("This export has no student names (the form was anonymous), so responses cannot be matched to students.")
    latest, order, empty, truncated, repeats, unnamed = {}, [], 0, 0, 0, 0
    for n, r in enumerate(body, 1):
        parts = []
        for i in q_idx:
            v = cell(r, i)
            if len(v) > MAX_ANSWER:
                v, truncated = v[:MAX_ANSWER] + " […cut]", truncated + 1
            parts.append((head[i].strip(), v or "(no answer)"))
        if not any(v != "(no answer)" for _, v in parts):
            empty += 1
            continue
        name = cell(r, name_i)
        has_name = bool(name)
        if not has_name:
            unnamed += 1
            name = f"Response {n}"
        work = "\n\n".join(f"{q}: {a}" for q, a in parts)
        entry = {"name": name, "work": work, "points": cell(r, pts_i), "has_name": has_name}
        key = name.casefold() if has_name else f"#{n}"
        if key in latest:
            repeats += 1
            order.remove(key)
        latest[key] = entry
        order.append(key)
    if repeats:
        notes.append(f"{repeats} student{'s' if repeats != 1 else ''} submitted more than once. The last response in the file was loaded; check it is the one that counts.")
    if empty:
        notes.append(f"{empty} blank response{'s were' if empty != 1 else ' was'} skipped.")
    if unnamed and not anonymous:
        notes.append(f"{unnamed} response{'s have' if unnamed != 1 else ' has'} no name. Type the name on the card.")
    if truncated:
        notes.append(f"{truncated} very long answer{'s were' if truncated != 1 else ' was'} cut at {MAX_ANSWER} characters.")
    return {"anonymous": anonymous, "students": [latest[k] for k in order], "notes": notes}
