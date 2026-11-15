#!/usr/bin/env python3
"""Copy the SHAPE of a synced SharePoint "Submitted files" folder with every student name replaced, so the collector
can be checked against real folder layouts and real name quirks without anyone seeing who the students are.

What is kept: folder depth, assignment folder names, file names and types, original sizes and dates (in _shape.json),
cloud-only flags, symlinks (counted), and the quirks that break name matching: initials ("T Ashgrove"), accents,
hyphens, apostrophes, capitals, a student with two folders, two students with one name. Each name word is replaced
the same way everywhere, and an initial becomes the initial of its replacement.

What is not kept: file contents. Input files are never opened (opening a cloud-only file would download it); the copy
has small placeholder files. The replacement table is random each run and never saved or printed.

    python3 tools/deidentify_shape.py --root ".../Student Work/Submitted files" --out ~/Desktop/shape-check
    python3 tools/deidentify_shape.py --root "..." --out ~/Desktop/shape-check --course "Band 11" --quarter 1

The copy is written to <out>/Submitted files, with _shape.json (and _roster.json) beside it.

With --course/--quarter it also asks the running app for the class list and writes _roster.json with the same
replacements (use it with: sharepoint_collect.py --roster-file). Before sharing the copy, read the "words left in
names" list it prints: names the tool could not know about (a partner's name, a nickname, a teacher) may be there.
"""
import argparse
import io
import json
import os
import random
import re
import string
import sys
import unicodedata
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

SF_DATALESS = 0x40000000
MAX_DEPTH = 6
SYLLABLES = ["ba", "ce", "di", "fo", "ga", "hu", "ji", "ka", "le", "mo", "na", "pe", "ri", "sa", "to", "vu", "wi",
             "xe", "yo", "za", "bel", "dor", "fen", "gil", "hal", "kin", "lor", "mar", "nel", "pim", "quin", "rus",
             "sel", "tam", "vor", "wex"]
COMMON = {"task", "unit", "lesson", "test", "quiz", "project", "assignment", "final", "draft", "copy", "version",
          "submission", "submitted", "files", "working", "student", "work", "the", "and", "of", "for", "my", "a", "to",
          "in", "part", "week", "scales", "recording", "reflection", "q1", "q2", "q3", "q4", "v1", "v2"}
WORD = re.compile(r"[^\W\d_]+", re.UNICODE)       # runs of letters, accented ones included


def plain(w):
    return unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode("ascii").lower()


class Replacer:
    """Consistent, irreversible name-word replacement. First letters go through one random letter permutation, so
    an initial and the full name it abbreviates still agree after replacement."""

    def __init__(self):
        rnd = random.SystemRandom()
        letters = list(string.ascii_lowercase)
        shuffled = letters[:]
        rnd.shuffle(shuffled)
        self.letter = dict(zip(letters, shuffled))
        self.rnd, self.map, self.used = rnd, {}, set()

    def learn(self, name):
        for w in WORD.findall(name):
            key = plain(w)
            if len(key) > 1 and key not in self.map:
                while True:
                    fake = self.letter.get(key[0], key[0]) + "".join(self.rnd.choice(SYLLABLES) for _ in range(2))[1:]
                    fake = fake[:max(3, min(len(key) + 1, 9))]
                    if fake not in self.used and fake != key and fake not in self.map:
                        break
                self.map[key] = fake
                self.used.add(fake)

    def word(self, w):
        key = plain(w)
        if len(key) == 1:                                    # an initial: map through the letter permutation
            fake = self.letter.get(key, key) if self._initial_ok(key) else key
        elif key in self.map:
            fake = self.map[key]
        else:
            return w
        if w != plain(w) and any(ord(c) > 127 for c in w):  # keep "has an accent"
            fake = fake[:-1] + {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}.get(fake[-1], fake[-1] + "é")
        if w.isupper() and len(w) > 1:
            return fake.upper()
        return fake[:1].upper() + fake[1:] if w[:1].isupper() else fake

    def _initial_ok(self, letter):
        return any(k.startswith(letter) for k in self.map)

    def text(self, s, initials=True):
        """Replace name words (and, in student-name positions, initials) inside one folder or file name."""
        return WORD.sub(lambda m: self.word(m.group()) if (len(m.group()) > 1 or initials) else m.group(), s)


def docx(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return b.getvalue()


def pdf(text):
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length %d>>stream\n" % len(content) + content + b"\nendstream", b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)


def placeholder(name):
    ext = Path(name).suffix.lower()
    if ext in (".txt", ".md"):
        return b"Placeholder work."
    if ext == ".docx":
        return docx("Placeholder work.")
    if ext == ".pdf":
        return pdf("Placeholder work.")
    return b""


def fetch_roster(base, course, quarter):
    url = f"{base}/api/roster?name={urllib.parse.quote(course)}&quarter={quarter}"
    with urllib.request.urlopen(url, timeout=10) as r:
        data = json.load(r)
    if "error" in data:
        raise SystemExit(f"Class list: {data['error']}")
    return data["students"]


def run(root, out, roster=None):
    root, out = Path(root), Path(out)
    if not root.is_dir():
        raise SystemExit(f"Not a folder: {root}")
    r_root, r_out = Path(os.path.realpath(root)), Path(os.path.realpath(out))
    if r_out == r_root or r_root in r_out.parents or r_out in r_root.parents:
        raise SystemExit("The output folder must be outside the synced folder (and not contain it).")
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"{out} already has files in it. Choose a new or empty folder.")

    rep = Replacer()
    students = sorted(e.name for e in os.scandir(root) if e.is_dir(follow_symlinks=False))
    for s in students:
        rep.learn(s)
    for s in roster or []:
        rep.learn(f"{s.get('first', '')} {s.get('last', '')}")

    shape = {"files": [], "symlinks": 0, "unreadable_folders": 0}
    left = {}

    def walk(src, dst, depth):
        try:
            items = sorted(os.scandir(src), key=lambda e: e.name)
        except OSError:
            shape["unreadable_folders"] += 1
            return
        for e in items:
            name = rep.text(e.name, initials=(depth == 0))   # initials only stand for names at student-folder level
            for w in WORD.findall(Path(name).stem if e.is_file(follow_symlinks=False) else name):
                if plain(w) not in COMMON and len(w) > 1 and plain(w) not in rep.used:
                    left[w] = left.get(w, 0) + 1
            if e.is_symlink():
                shape["symlinks"] += 1
                continue
            st = e.stat(follow_symlinks=False)
            if e.is_dir(follow_symlinks=False):
                if depth + 1 < MAX_DEPTH:
                    (dst / name).mkdir(exist_ok=True)
                    walk(e.path, dst / name, depth + 1)
                    os.utime(dst / name, ns=(st.st_atime_ns, st.st_mtime_ns))
            elif e.is_file(follow_symlinks=False):
                target = dst / name
                target.write_bytes(placeholder(name))
                os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns))
                shape["files"].append({"path": str(target.relative_to(tree)), "size": st.st_size,
                                       "cloud_only": bool(getattr(st, "st_flags", 0) & SF_DATALESS)})

    tree = out / "Submitted files"          # the copy; _shape.json and _roster.json sit beside it, not in it
    tree.mkdir(parents=True, exist_ok=True)
    walk(root, tree, 0)
    (out / "_shape.json").write_text(json.dumps(shape, indent=1, ensure_ascii=False), encoding="utf-8")
    if roster is not None:
        fake = [{"id": f"s{i}", "first": rep.text(s.get("first", "")), "last": rep.text(s.get("last", ""))}
                for i, s in enumerate(roster, 1)]
        (out / "_roster.json").write_text(json.dumps(fake, indent=1, ensure_ascii=False), encoding="utf-8")
    return {"students": len(students), "files": len(shape["files"]), "symlinks": shape["symlinks"],
            "cloud_only": sum(f["cloud_only"] for f in shape["files"]), "left": left}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True, help='The synced ".../Student Work/Submitted files" folder')
    ap.add_argument("--out", required=True, help="A new folder for the name-free copy (outside the synced folder)")
    ap.add_argument("--course", help="Also copy this course's class list, with names replaced")
    ap.add_argument("--quarter", help="Quarter for the class list")
    ap.add_argument("--app", default="http://127.0.0.1:8765", help=argparse.SUPPRESS)
    a = ap.parse_args()
    roster = fetch_roster(a.app, a.course, a.quarter or "") if a.course else None
    r = run(a.root, a.out, roster)
    print(f"Copied the shape of {r['students']} student folders: {r['files']} placeholder files, "
          f"{r['cloud_only']} cloud-only (not downloaded), {r['symlinks']} symlinks (not copied)."
          + (" Class list copied to _roster.json." if roster is not None else ""))
    print(f"Name-free copy: {Path(a.out) / 'Submitted files'}  (sizes and cloud-only flags in _shape.json beside it)")
    if r["left"]:
        print("\nWords left in folder and file names. Check these for names the tool couldn't know "
              "(a partner, a nickname, a teacher) before sharing:")
        for w, n in sorted(r["left"].items(), key=lambda kv: (-kv[1], kv[0].lower())):
            print(f"   {n:3d}  {w}")
    else:
        print("\nNo other words are left in folder or file names.")


if __name__ == "__main__":
    sys.exit(main())
