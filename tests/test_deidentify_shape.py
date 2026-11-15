"""The name-free shape copy (tools/deidentify_shape.py). Invented students and a temporary folder tree only."""
import json, os, stat, sys, tempfile, unicodedata
from pathlib import Path
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); sys.path.insert(0, os.path.join(APPDIR, "tools"))
import deidentify_shape as D
import sharepoint_collect as C
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

ROSTER = [{"id": "r1", "first": "José", "last": "Núñez"}, {"id": "r2", "first": "Anne-Marie", "last": "O'Neil"},
          {"id": "r3", "first": "Tobin", "last": "Ashgrove"}, {"id": "r4", "first": "Orrin", "last": "Vale"},
          {"id": "r5", "first": "Pell", "last": "Dunmore"}, {"id": "r6", "first": "Pell", "last": "Dunmore"},
          {"id": "r7", "first": "Quinby", "last": "Marsh"}]
NAME_WORDS = ["José", "Jose", "Núñez", "Nunez", "Anne", "Marie", "O'Neil", "Neil", "Tobin", "Ashgrove", "Orrin", "Vale",
              "Pell", "Dunmore", "Quinby", "Marsh", "Unknown"]

root = Path(tempfile.mkdtemp(dir=HOME)) / "Submitted files"
def put(rel, data=b"x"):
    p = root / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
put("José Núñez/Task 2/José_Núñez_answer.txt", b"real work one")
put("Anne-Marie O'Neil/Task 2/answer.txt", b"real work two")
put("T Ashgrove/Task 2/notes.txt", b"real work three")
put("Orrin Vale/Task 2.txt", b"real work four")
put("O Vale/Task 2.txt", b"real work five")
put("Pell Dunmore/Task 2/work.txt", b"real work six")
put("Unknown Person/Task 2/work.txt", b"real work seven")
put("Orrin Vale/Scales/recording.m4a", b"audio" * 100)
put("Anne-Marie O'Neil/Task 2/Task 2 with Benedetta.docx", b"PK")       # a name the tool can't know
os.symlink(root / "Orrin Vale", root / "Linked")
old = 1_700_000_000
os.utime(root / "Orrin Vale" / "Task 2.txt", (old, old))
for p in root.rglob("*"):                         # the tool must never open input files: make every one unreadable
    if p.is_file() and not p.is_symlink():
        p.chmod(0)

out = Path(tempfile.mkdtemp(dir=HOME)) / "shape"
r = D.run(root, out, ROSTER)
tree = out / "Submitted files"
paths = [str(p.relative_to(tree)) for p in tree.rglob("*")]
blob = "\n".join(paths) + (out / "_shape.json").read_text() + (out / "_roster.json").read_text()
flat = unicodedata.normalize("NFKD", blob).encode("ascii", "ignore").decode().lower()

check("1 runs without opening any input file (all were unreadable)", r["files"] == 9, r)
check("2 no student name word is left in names, _shape.json or _roster.json", not [w for w in NAME_WORDS if w.lower() in blob.lower() or
      unicodedata.normalize("NFKD", w).encode("ascii", "ignore").decode().lower() in flat.split("benedetta")[0] + flat.split("benedetta")[-1] and len(w) > 4],
      [w for w in NAME_WORDS if w.lower() in blob.lower()])
check("3 file contents are placeholders, not the real work", "real work" not in "".join(p.read_bytes().decode("latin-1") for p in tree.rglob("*") if p.is_file()))
check("4 same depth and the same number of folders and files", sorted(len(Path(p).parts) for p in paths) ==
      sorted(len(p.relative_to(root).parts) for p in root.rglob("*") if not p.is_symlink() and "Linked" not in p.parts))
check("5 assignment folder names and file types are kept", any(p.endswith("Task 2") for p in paths) and any(p.endswith(".m4a") for p in paths))
tops = sorted(p.name for p in tree.iterdir())
pairs = [(v, f) for v in tops for f in tops if v != f and len(v.split()[0]) == 1 and v.split()[-1] == f.split()[-1]]
check("6 an initial still matches its replaced full name ('O Vale' and 'Orrin Vale' stay a pair)",
      len(pairs) == 1 and pairs[0][1][0] == pairs[0][0][0], tops)
check("7 accents, hyphens and apostrophes are kept", any(any(ord(c) > 127 for c in t) for t in tops) and any("-" in t and "'" in t for t in tops), tops)
check("8 a symlink is counted, not copied", r["symlinks"] == 1 and not any(p.is_symlink() for p in tree.rglob("*")))
shape = json.loads((out / "_shape.json").read_text())
check("9 original sizes are kept in _shape.json", any(f["size"] == 500 for f in shape["files"]))
moved = next(p for p in tree.rglob("Task 2.txt") if p.stat().st_mtime == old) if any(p.stat().st_mtime == old for p in tree.rglob("Task 2.txt")) else None
check("10 file dates are kept", moved is not None)
check("11 a name the tool couldn't know is listed for checking", "Benedetta" in r["left"], r["left"])
check("12 the shared roster name stays shared after replacement", len({(s["first"], s["last"]) for s in json.loads((out / "_roster.json").read_text())}) == 6)

for p in root.rglob("*"):
    if p.is_file() and not p.is_symlink():
        p.chmod(stat.S_IRUSR | stat.S_IWUSR)
real = C.collect(root, "Task 2", ROSTER)
copy = C.collect(tree, "Task 2", json.loads((out / "_roster.json").read_text()))
counts = lambda x: (len(x["matched"]), sorted(f["reason"].split(":")[0].split(" matches ")[0] for f in x["flagged"]), len(x["missing"]), len(x["non_text"]))
check("13 the collector gives the same results on the copy as on the original", counts(real) == counts(copy), (counts(real), counts(copy)))

r2 = D.run(root, Path(tempfile.mkdtemp(dir=HOME)) / "shape2")
check("14 each run uses new random replacements (nothing to reverse)", sorted(p.name for p in (Path(r2 and HOME)).rglob("shape2/Submitted files/*")) != tops)
for bad, why in [(root / "inside", "inside the synced folder"), (out, "already has files")]:
    try:
        D.run(root, bad); refused = False
    except SystemExit:
        refused = True
    check(f"15 refuses an output folder {why}", refused and not (root / "inside").exists())

print(f"\n{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
