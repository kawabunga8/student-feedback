"""Group projects: the pieces that let the existing feedback drafter write ONE comment for a team from a transcript of the
team's video. The drafting itself (criteria checks, retries, level and rubric guards) is feedback.generate, unchanged; this
module only prepares its inputs.

What the model gets is words only: a transcript made by speech recognition, with timestamps removed. It never sees video,
audio or any student's name, and it runs on this computer. The result is a draft for the teacher to read and edit in the
Team assessment box; nothing is applied, marked reviewed or posted from here."""
import re
from pathlib import Path

MAX_CHARS = 12000          # a transcript longer than this is cut (a 3-minute skit is about 2,500 characters)
_TIMED = re.compile(r"^\s*\[\s*[\d.]+\s*-\s*[\d.]+\s*\]\s*")
_DURATION = re.compile(r"^\s*duration_s=[\d.]+\s*$")


def clean_transcript(text):
    """The spoken words only: drops the duration line and the [start-end] stamps that tools/transcribe_scales.py writes."""
    lines = []
    for raw in str(text or "").splitlines():
        s = raw.strip()
        if not s or _DURATION.match(s):
            continue
        s = _TIMED.sub("", s).strip()
        if s:
            lines.append(s)
    return "\n".join(lines)


def team_work(transcript):
    """The 'student work' the drafter assesses: the cleaned transcript under a plain label of what it is."""
    words = clean_transcript(transcript)[:MAX_CHARS].strip()
    if not words:
        raise ValueError("Add the transcript of the team's video first.")
    return ("Transcript of the words spoken in one group's video. It has no picture or sound, it was made by speech recognition "
            "so it can contain mistakes, and some lines may be missing.\n\n" + words)


# Passed to the drafter as the teacher's private notes (which it is told to follow but never quote).
TEAM_NOTE = (
    "This feedback is for a GROUP of students who made one video together. Write to the whole group: say \"your team\" and "
    "\"you\" (plural). Never write a person's name, the placeholder [NAME], or the word \"student\"; never say who did what. "
    "The only evidence is the transcript of the spoken words. Do not judge or mention acting, costumes, filming, editing, music, "
    "sound or picture quality, and never say anything was unclear, missing or cut off in the video. Use only what the transcript "
    "shows: do not credit the team with a study, a Bible passage, a source or any skill unless words in the transcript show it, even when "
    "the assignment asks for it. If the spoken words show nothing about a criterion, say in one short clause that the spoken words do not show it; "
    "do not guess. Do not name anyone who appears in the transcript.")


def team_request(p):
    """p is the page's /api/generate request plus 'transcript'. Returns the same request for feedback.generate, as a team."""
    q = dict(p)
    q["work"] = team_work(p.get("transcript", ""))
    q["notes"] = (TEAM_NOTE + " " + str(p.get("notes", ""))).strip()
    q["label"] = "student"          # feedback.generate swaps a stray [NAME] for the first name; never a real name here
    q["level"] = ""                 # the teacher's level is chosen in the box and never given to the model for a team
    return q


def tidy(text):
    """A stray 'the student' (from an unfilled [NAME]) becomes 'your team'."""
    return re.sub(r"\bthe student\b", lambda m: "Your team" if m.group(0)[0] == "T" else "your team", str(text), flags=re.I)


VIDEO_EXT = (".mov", ".mp4", ".m4v", ".webm", ".avi", ".mkv")


def video_files(roots=None):
    """Videos already downloaded for group projects. Looks in ~/Desktop/Teaching/<anything>-videos*/ and, when an external drive is
    plugged in, /Volumes/*/Work/RCS/Teaching Archive/<course>/*videos*/ (the T7 archive). Under each such folder any depth is
    searched; the student is the file's own folder. Returns [{'folder', 'student', 'file'}] without duplicates, never opening a
    file. `roots` (a list of folders that are themselves video folders) is for tests."""
    if roots is None:
        roots = sorted(Path.home().glob("Desktop/Teaching/*-videos*")) + sorted(Path("/Volumes").glob("*/Work/RCS/Teaching Archive/*/*videos*"))
    out, seen = [], set()
    for d in map(Path, roots if isinstance(roots, (list, tuple)) else [roots]):
        if not d.is_dir():
            continue
        for f in sorted(d.rglob("*")):
            if f.is_file() and f.suffix.lower() in VIDEO_EXT and not f.name.startswith((".", "._")) and (f.parent.name, f.name) not in seen:
                seen.add((f.parent.name, f.name)); out.append({"folder": d.name, "student": f.parent.name, "file": f.name})
    return out
