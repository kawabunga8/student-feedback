"""SharePoint collection from a synced folder (sharepoint_collect.py). Invented students and a temporary folder tree;
never contacts the app, Course Hub, OneDrive or SharePoint."""
import contextlib, io, os, shutil, sys, tempfile, time, zipfile
from pathlib import Path
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR)
import sharepoint_collect as C
import stage_submissions as S
S.APP_BASE = "http://127.0.0.1:9"      # a closed port: nothing here may reach the real app or its class list
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))

ROSTER = [{"id": "s1", "first": "Juniper", "last": "Quill"}, {"id": "s2", "first": "Orrin", "last": "Vale"},
          {"id": "s3", "first": "Mira", "last": "Fenwick"}, {"id": "s4", "first": "Tobin", "last": "Ashgrove"},
          {"id": "s5", "first": "Wren", "last": "Halloway"}, {"id": "s6", "first": "Pell", "last": "Dunmore"},
          {"id": "s7", "first": "Pell", "last": "Dunmore"}]       # two students with one name

def docx(text):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>')
    return b.getvalue()

def pdf(text):
    content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode() if text else b""
    objs = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
            b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
            b"<</Length %d>>stream\n" % len(content) + content + b"\nendstream", b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out)); out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offs)
    return out + b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, x)

def build():
    """A synced 'Submitted files' tree: flat and nested layouts and the awkward cases."""
    root = Path(tempfile.mkdtemp(dir=HOME)) / "Student Work" / "Submitted files"
    def put(rel, data):
        p = root / rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    put("Juniper Quill/Task 2 Define and Ideate/answer.docx", docx("My idea is a reusable bottle."))
    put("Juniper Quill/Task 2 Define and Ideate/sketch.png", b"\x89PNG fake")
    put("Juniper Quill/Task 20 Prototype/answer.txt", "Not this assignment.")
    put("Orrin Vale/Task 2.txt", "Flat layout work about a lunch tray.")
    put("O Vale/Task 2.md", "Second folder for the same student.")                  # two folders -> one student
    put("Mira Fenwick/Task 2 draft/a.txt", "draft")
    put("Mira Fenwick/Task 2 final/a.txt", "final")                                    # two candidate folders
    put("T Ashgrove/Task 2/scan.pdf", pdf("Prototype notes from a PDF"))               # initial + last name
    put("T Ashgrove/Task 2/blank.pdf", pdf(""))                                        # PDF with no text
    put("Wren Halloway/Task 2/recording.m4a", b"fake audio")                           # non-text only
    put("Wren Halloway/Task 2/clip.mov", b"fake video")
    put("Pell Dunmore/Task 2/work.txt", "Shared-name student work.")                   # duplicate on the class list
    put("Unknown Person/Task 2/work.txt", "Not on the class list.")
    put("Juniper Quill/Task 2 Define and Ideate/.hidden.txt", "hidden")
    put("Juniper Quill/Task 2 Define and Ideate/~$answer.docx", b"lock")
    put("Juniper Quill/Task 2 Define and Ideate/deeper/extra.txt", "too deep")
    put("loose file.txt", "not in a student folder")
    outside = Path(tempfile.mkdtemp(dir=HOME)) / "secret.txt"; outside.write_text("outside the sync folder")
    os.symlink(outside, root / "Juniper Quill" / "Task 2 Define and Ideate" / "link.txt")
    os.symlink(outside.parent, root / "Linked Student")
    return root

def snapshot(root):
    return sorted((str(p.relative_to(root)), p.lstat().st_size, p.lstat().st_mtime_ns) for p in root.rglob("*"))

root = build()
before = snapshot(root)
res = C.collect(root, "Task 2", ROSTER)
by = {m["folder"]: m for m in res["matched"]}
fl = {f["folder"]: f["reason"] for f in res["flagged"]}

check("1 nested layout: the matching assignment folder's .docx text is read", "reusable bottle" in by.get("Juniper Quill", {}).get("text", ""), list(by))
check("2 'Task 2' does not match the 'Task 20' folder", "Not this assignment" not in by.get("Juniper Quill", {}).get("text", ""))
check("3 flat layout: a file named for the assignment is read", "lunch tray" in str(fl.get("Orrin Vale", "")) + by.get("Orrin Vale", {}).get("text", "") or "Orrin Vale" in fl)
check("4 two folders matching one student are both flagged, neither picked", "Orrin Vale" in fl and "O Vale" in fl and "Orrin Vale" not in by, fl)
check("5 two candidate assignment folders are flagged, not guessed", "more than one folder" in fl.get("Mira Fenwick", ""), fl)
check("6 initial + last name folder matches the class list", by.get("T Ashgrove", {}).get("student", {}).get("id") == "s4")
check("7 PDF text is extracted", "Prototype notes from a PDF" in by.get("T Ashgrove", {}).get("text", ""))
unread = {u["folder"]: u["files"] for u in res["unreadable"]}
check("8 a PDF with no text is reported unreadable, not staged as empty work", any(n == "blank.pdf" for n, _ in unread.get("T Ashgrove", [])), unread)
nt = {n["folder"]: n for n in res["non_text"]}
check("9 audio and video are listed by kind, not read", sorted(f["kind"] for f in nt.get("Wren Halloway", {}).get("files", [])) == ["audio", "video"])
check("10 a student with only non-text work is not reported missing", "s5" not in [s["id"] for s in res["missing"]])
check("11 images beside text work are listed as non-text", [f["kind"] for f in nt.get("Juniper Quill", {}).get("files", [])] == ["image"])
check("12 a name shared by two class-list students is flagged", "Pell Dunmore" in fl, fl)
check("13 a folder not on the class list is flagged with its text kept", "Unknown Person" in fl and any(f["text"] for f in res["flagged"] if f["folder"] == "Unknown Person"))
check("14 only students with nothing found are missing (flagged ones submitted; the shared name can't be resolved)",
      sorted(s["id"] for s in res["missing"]) == ["s6", "s7"], [s["id"] for s in res["missing"]])
check("15 hidden files and Office lock files are ignored", ".hidden" not in by.get("Juniper Quill", {}).get("text", "") and "lock" not in by.get("Juniper Quill", {}).get("text", ""))
check("16 symlinks (file and folder) are skipped, never followed", res["skipped"]["symlinks"] == 2 and "outside the sync folder" not in str(res))
check("17 folders deeper than the layout are counted, not read", res["skipped"]["too_deep"] == 1 and "too deep" not in str(res))
check("18 a loose file outside any student folder is counted", res["skipped"]["loose_files"] == 1)
check("19 reading never changes the synced folder", snapshot(root) == before)

src = C.LocalFolder(root)
try:
    src.read(["..", "..", "x"], 100); escaped = True
except (ValueError, OSError):
    escaped = False
check("20 the reader refuses paths that leave the sync folder", not escaped)

# Cloud-only (dataless) files: simulated, since a test can't create real OneDrive placeholders.
real_entries, reads = C.LocalFolder.entries, []
def cloudy(self):
    files, skipped = real_entries(self)
    for f in files:
        if f["parts"][0] == "T Ashgrove": f["dataless"] = True
    return files, skipped
real_read = C.LocalFolder.read
def counting_read(self, parts, limit):
    reads.append(parts[0]); return real_read(self, parts, limit)
C.LocalFolder.entries, C.LocalFolder.read = cloudy, counting_read
cl = C.collect(root, "Task 2", ROSTER)
check("21 cloud-only files are not opened without --hydrate", "T Ashgrove" not in reads and sum(len(c["files"]) for c in cl["cloud_only"]) == 2)
check("22 a student with only cloud-only files still counts as submitted", "s4" not in [s["id"] for s in cl["missing"]])
reads.clear(); hy = C.collect(root, "Task 2", ROSTER, hydrate=True)
check("23 --hydrate reads them", "T Ashgrove" in reads and any(m["folder"] == "T Ashgrove" for m in hy["matched"]))
C.LocalFolder.entries, C.LocalFolder.read = real_entries, real_read

capped = C.collect(root, "Task 2", ROSTER, max_bytes=40)
check("24 the run size limit stops reading and says so", capped["byte_cap_hit"] and len(capped["matched"]) < len(res["matched"]))
later = C.collect(root, "Task 2", ROSTER, since=time.time() + 3600)
check("25 --since leaves out older files", not later["matched"] and len(later["no_work"]) > 0)
big = root / "Juniper Quill" / "Task 2 Define and Ideate" / "huge.docx"
big.write_bytes(b"PK" + b"0" * (C.MAX_FILE_BYTES + 10))
r2 = C.collect(root, "Task 2", ROSTER)
check("26 an oversized file is reported unreadable, others still read", any(n == "huge.docx" for u in r2["unreadable"] for n, _ in u["files"]) and any(m["folder"] == "Juniper Quill" for m in r2["matched"]))
big.unlink(); before = snapshot(root)

check("27 assignment folders are listed with student counts", C.list_assignments(src.entries()[0]).get("Task 2") == 4, C.list_assignments(src.entries()[0]))

# Writing
dest = Path(HOME) / "Desktop" / "Teaching" / "Assessment" / "2026-27" / "Q1" / "ICT 9" / "Task 2"
try:
    C.write(res, root / "Juniper Quill" / "out", root); inside = True
except SystemExit:
    inside = False
check("28 writing inside the synced folder is refused", not inside and snapshot(root) == before)
w1 = C.write(res, dest, root)
files = sorted(p.name for p in dest.iterdir())
check("29 matched students are staged as First_Last.txt", "Juniper_Quill.txt" in files and "Tobin_Ashgrove.txt" in files, files)
check("30 flagged, missing and non-text lists are written", any(f.startswith("_NEEDS_ATTENTION_") for f in files) and "_MISSING_SUBMISSIONS.txt" in files and "_NON_TEXT_SUBMISSIONS.txt" in files)
w2 = C.write(res, dest, root)
check("31 a second run with the same work writes nothing new", w2["written"] == 0 and w2["unchanged"] == w1["written"] and w2["changed"] == 0, w2)
staged = (dest / "Juniper_Quill.txt").read_text()
(root / "Juniper Quill" / "Task 2 Define and Ideate" / "answer.docx").write_bytes(docx("A changed idea after review."))
w3 = C.write(C.collect(root, "Task 2", ROSTER), dest, root)
check("32 changed work goes to a _CHANGED_ file; the staged (maybe reviewed) file is untouched",
      w3["changed"] == 1 and (dest / "Juniper_Quill.txt").read_text() == staged and "changed idea" in (dest / "_CHANGED_Juniper_Quill.txt").read_text())
check("33 no temporary files are left behind", not any(p.name.endswith(".tmp") for p in dest.iterdir()))

# Reports
everyone = [f"{s['first']} {s['last']}" for s in ROSTER] + ["Juniper", "Quill", "Orrin", "Ashgrove", "Halloway", "Unknown Person",
            "answer.docx", "recording.m4a", "scan.pdf", "blank.pdf", "Juniper_Quill"]
full = C.report(res, False, dest)
quiet = C.report(res, True, dest)
check("34 the normal report names students for the teacher", "Juniper Quill" in full and "Orrin" in full)
check("35 the --counts-only report contains no student, folder or file names", not [n for n in everyone if n in quiet], [n for n in everyone if n in quiet])
check("36 the counts-only report still has the counts", "Matched with readable text:        2" in quiet and "1 audio" in quiet, quiet)

# Command line, end to end, with no app running (closed port): dry run writes nothing
out = io.StringIO(); err = io.StringIO()
sys.argv = ["sharepoint_collect.py", "--root", str(root), "--course", "ICT 9", "--quarter", "1", "--assignment", "Task 9",
            "--year", "2026-27", "--counts-only"]
with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
    C.main()
check("37 command line without the app: warns, flags everything, writes nothing", "WARNING" in err.getvalue()
      and "DRY RUN" in out.getvalue() and not (dest.parent / "Task 9").exists(), out.getvalue()[-200:])
sys.argv = ["sharepoint_collect.py", "--root", str(root), "--list-assignments"]
out = io.StringIO()
with contextlib.redirect_stdout(out):
    C.main()
check("38 --list-assignments shows assignment folders without student names", "Task 2" in out.getvalue() and "Juniper" not in out.getvalue(), out.getvalue())

shutil.rmtree(HOME, ignore_errors=True)
print(f"\n{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
