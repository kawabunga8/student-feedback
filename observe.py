"""Teacher observations for performance evidence (video, audio) - see BAND-PERFORMANCE-EVIDENCE-DESIGN.md.

Pure functions plus a small sidecar store. No network, no browser, no model, no media is ever read here.
The teacher watches the evidence and records, per rubric criterion, a level and a short note. Nothing is ever
defaulted: a level exists only if the teacher chose it. Only the typed notes (never levels, names or media) go to the
local drafting model, via to_notes().
"""
import json
import os
import re
from pathlib import Path

LEVELS = ("Emerging", "Developing", "Proficient", "Extending")
LEVEL_RE = re.compile(r"(Emerging|Developing|Proficient|Extending)(\+?)", re.I)
STATUSES = ("unobserved", "observed", "revisit")
VIDEO = {".mov", ".mp4", ".m4v", ".webm", ".avi", ".mkv"}
AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".aiff", ".flac", ".ogg"}
DOCUMENT = {".docx", ".pdf", ".txt", ".md"}
MAX_STUDENTS, MAX_CRITERIA, MAX_NOTE, MAX_TEXT = 500, 40, 2000, 4000
STORE_NAME = "observations.json"
HEAD = "Teacher's observations (what the teacher saw and heard; the only source for what the student did):"


class ObservationConflict(Exception):
    def __init__(self, current):
        super().__init__("observations were saved somewhere else")
        self.current = current


def classify(filename):
    """video | audio | document | other, from the file extension only."""
    ext = Path(str(filename or "")).suffix.lower()
    return "video" if ext in VIDEO else "audio" if ext in AUDIO else "document" if ext in DOCUMENT else "other"


def clean_level(value):
    """A level the teacher chose, normalised ('proficient+' -> 'Proficient+'), or '' - never a default."""
    m = LEVEL_RE.fullmatch(str(value or "").strip())
    if not m:
        return ""
    base, plus = m.group(1).capitalize(), m.group(2)
    return base + ("+" if plus and base != "Extending" else "")


def _text(v, n):
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v or "")).strip()[:n]


def normalize_observation(raw):
    """One student's observation. Unknown status -> 'unobserved'. Levels only if valid. Never marks reviewed."""
    raw = raw if isinstance(raw, dict) else {}
    seen, crit = set(), []
    for c in (raw.get("criteria") or [])[:MAX_CRITERIA]:
        if not isinstance(c, dict):
            continue
        cid = _text(c.get("id"), 80)
        if not cid or cid in seen:
            continue
        seen.add(cid)
        crit.append({"id": cid, "level": clean_level(c.get("level")), "note": _text(c.get("note"), MAX_NOTE),
                     "ts": _text(c.get("ts"), 20)})
    status = raw.get("status") if raw.get("status") in STATUSES else "unobserved"
    return {"status": status, "criteria": crit, "strengths": _text(raw.get("strengths"), MAX_TEXT),
            "next_step": _text(raw.get("next_step"), MAX_TEXT)}


def normalize_store(raw):
    """{student key: observation}. Keys are the student id or, failing that, the name; at most MAX_STUDENTS."""
    out = {}
    for k, v in list((raw or {}).items())[:MAX_STUDENTS] if isinstance(raw, dict) else []:
        key = _text(k, 120)
        if key:
            out[key] = normalize_observation(v)
    return out


def has_content(obs):
    return bool(obs.get("strengths") or obs.get("next_step") or any(c["note"] or c["level"] for c in obs.get("criteria", [])))


def to_notes(obs, criteria=None):
    """The teacher's notes as plain text for the drafting model's private-notes input. Levels are deliberately left out
    (the drafting rules forbid naming levels); timestamps are kept as the teacher's own pointers. '' if no notes."""
    obs = normalize_observation(obs)
    names = {str(i): t for i, t in (criteria or {}).items()} if isinstance(criteria, dict) else \
        {str(i): t for i, t in enumerate(criteria or [])}
    lines = []
    for c in obs["criteria"]:
        if c["note"]:
            label = names.get(c["id"], c["id"])
            lines.append(f"- {label}: {c['note']}" + (f" (at {c['ts']})" if c["ts"] else ""))
    if obs["strengths"]:
        lines.append(f"Strengths: {obs['strengths']}")
    if obs["next_step"]:
        lines.append(f"Next step: {obs['next_step']}")
    return (HEAD + "\n" + "\n".join(lines)) if lines else ""


_STOP = set("a an and are as at be but by for from had has have he her his i in is it its of on or our she so that the "
            "their them they this to was we were with you your will can very more most also than then there these those "
            "student students work good well great nice really quite just keep continue next time "
            "thank thanks sharing share shared performance piece recording video submitting submission playing played".split())


def _words(text):
    return {w[:5] for w in re.findall(r"[a-z']{3,}", str(text or "").lower()) if w not in _STOP}


def claim_check(draft, obs):
    """Heuristic: sentences of a draft whose content words share nothing with the teacher's notes. It is a prompt for
    the teacher to look again, not a verdict. Sentences with no content words (greetings, closers) are not flagged."""
    obs = normalize_observation(obs)
    pool = set()
    for c in obs["criteria"]:
        pool |= _words(c["note"])
    pool |= _words(obs["strengths"]) | _words(obs["next_step"])
    flagged = []
    for s in re.split(r"(?<=[.!?])\s+|\n+", str(draft or "")):
        s = s.strip(" -*#")
        w = _words(s)
        if len(w) >= 3 and not (w & pool):
            flagged.append(s)
    return flagged


def summary(store, criteria_ids, roster_keys=None, floor=5):
    """Counts only: how many students are observed/revisit/unobserved and, per criterion, how many chose each level
    (hidden when fewer than `floor` students chose any level for that criterion). No names, no notes."""
    store = normalize_store(store)
    keys = list(roster_keys) if roster_keys is not None else list(store)
    st = {s: 0 for s in STATUSES}
    for k in keys:
        st[(store.get(k) or {}).get("status", "unobserved")] += 1
    per = {}
    for cid in criteria_ids:
        lv = [c["level"] for k in keys for c in (store.get(k) or {}).get("criteria", []) if c["id"] == cid and c["level"]]
        per[cid] = None if len(lv) < floor else {b: sum(1 for x in lv if x.rstrip("+") == b) for b in LEVELS}
    return {"students": len(keys), "status": st, "levels": per}


# ---- sidecar store (atomic, versioned) -------------------------------------------------------------------------
def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def load_store(folder):
    try:
        d = json.loads((Path(folder) / STORE_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        d = {}
    d = d if isinstance(d, dict) else {}
    return {"version": int(d.get("version") or 0), "students": normalize_store(d.get("students"))}


def save_store(folder, students, base_version):
    """Replace the saved observations. Refused (ObservationConflict) if saved elsewhere since base_version."""
    cur = load_store(folder)
    if int(base_version or 0) != cur["version"]:
        raise ObservationConflict(cur)
    new = {"version": cur["version"] + 1, "students": normalize_store(students)}
    _atomic_write(Path(folder) / STORE_NAME, new)
    return new
