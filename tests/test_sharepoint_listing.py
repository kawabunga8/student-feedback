"""SharePoint listing export: address checks, conversion of list-API items to evidence entries, counts-only output,
local file permissions. Invented data; no browser, network or real SharePoint is touched."""
import io, json, os, stat, sys, tempfile, contextlib
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import teams_read as T
import sharepoint_listing as SL
import evidence_collect as E
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:220]) if x != "" else ""))
def refused(fn, *a):
    try: fn(*a); return False
    except T.ReadError: return True

# address checks
O, P = SL.check_site_url("https://rcschool.sharepoint.com/sites/TeamA-2026/Student%20Work/Forms/AllItems.aspx?x=1")
check("1 a team site address is reduced to origin and /sites/<name>", (O, P) == ("https://rcschool.sharepoint.com", "/sites/TeamA-2026"), (O, P))
check("2 http, other hosts, credentials and non-site paths are refused", all(refused(SL.check_site_url, u) for u in (
    "http://rcschool.sharepoint.com/sites/a", "https://evil.example.com/sites/a", "https://sharepoint.com.evil.com/sites/a",
    "https://user:pw@rcschool.sharepoint.com/sites/a", "https://rcschool.sharepoint.com/personal/x", "https://rcschool.sharepoint.com/", "", None)))
check("3 library names with quotes or slashes are refused", all(refused(SL.check_library, n) for n in ("a'b", "a/b", "", "x" * 80, "a;b")) and SL.check_library("Student Work") == "Student Work")
u = SL.api_url(O, P)
check("4 the request is one read-only list query on that site", u.startswith("https://rcschool.sharepoint.com/sites/TeamA-2026/_api/web/lists/getbytitle('Student%20Work')/items?") and "$top=5000" in u, u)

# conversion
base = "/sites/TeamA-2026/Student Work/"
items = [
    {"FileSystemObjectType": 1, "FileRef": base + "Submitted files/Ada Test"},
    {"FileSystemObjectType": 0, "FileRef": base + "Submitted files/Ada Test/Scales 1/take1.mov", "File_x0020_Size": "4096", "Modified": "2026-11-12T10:00:00Z"},
    {"FileSystemObjectType": 0, "FileRef": base + "Submitted files/Ada Test/Scales 1/Retake/take 2 (final).mp4", "File_x0020_Size": 99, "Modified": "2026-11-13T10:00:00Z"},
    {"FileSystemObjectType": 0, "FileRef": base + "Working files/Ada Test/draft.docx", "File_x0020_Size": 5},
    {"FileSystemObjectType": 0, "FileRef": "/sites/OtherSite/Student Work/Submitted files/Zed/Scales 1/z.mov"},
    {"FileSystemObjectType": 0, "FileRef": base + "Submitted files/../Secret/x.docx"},
    {"FileSystemObjectType": 0, "FileRef": base + "submitted files/Bo Sample/Scales 1/a.docx", "File_x0020_Size": "bad"},
    "junk", None]
es = SL.to_entries(items, O, P)
check("5 only files under Submitted files of this site are kept, as relative paths", [e["path"] for e in es] == ["Ada Test/Scales 1/take1.mov", "Ada Test/Scales 1/Retake/take 2 (final).mp4", "Bo Sample/Scales 1/a.docx"], [e["path"] for e in es])
check("6 folders, Working files, other sites, .. paths and junk are skipped", len(es) == 3)
check("7 sizes parse, a bad size becomes 0", [e["bytes"] for e in es] == [4096, 99, 0])
check("8 links are absolute https on the site's host and URL-encoded", es[1]["url"] == "https://rcschool.sharepoint.com/sites/TeamA-2026/Student%20Work/Submitted%20files/Ada%20Test/Scales%201/Retake/take%202%20%28final%29.mp4", es[1]["url"])
check("9 an empty or None listing is an empty list", SL.to_entries(None, O, P) == [] and SL.to_entries([], O, P) == [])

# the output feeds evidence_collect unchanged
R = [{"id": "1", "first": "Ada", "last": "Test", "grade": "10", "block": "D"}, {"id": "2", "first": "Bo", "last": "Sample", "grade": "11", "block": "D"}]
r = E.build(es, R, "Scales 1")
check("10 entries flow into evidence_collect with matching and kinds", set(r["students"]) == {"1", "2"} and [i["kind"] for i in r["students"]["1"]["items"]] == ["video", "video"], r["students"].keys())

# counts only
sm = SL.summary(es)
check("11 the summary is counts only", sm == {"files": 3, "student_folders_with_files": 2, "files_by_depth_below_student": {2: 2, 3: 1}, "files_by_kind": {"video": 2, "document": 1}} and "Ada" not in str(sm) and "take" not in str(sm), sm)

# the browser is never opened in tests, and main() prints counts only and writes a private file
check("12 the browser part refuses to start under the test guard", refused(lambda: SL.listing("https://rcschool.sharepoint.com/sites/TeamA-2026")))
SL.listing = lambda site, library="Student Work", wait=60, signin_wait=240: items
out = os.path.join(tempfile.mkdtemp(), "e.json"); buf = io.StringIO(); old = sys.argv
sys.argv = ["sharepoint_listing.py", "--site", "https://rcschool.sharepoint.com/sites/TeamA-2026", "--out", out]
try:
    with contextlib.redirect_stdout(buf): code = SL.main()
finally: sys.argv = old
printed = buf.getvalue()
check("13 main succeeds and its output names no students or files", code == 0 and '"ok": true' in printed and not any(n in printed for n in ("Ada", "Bo Sample", "take", "Zed", ".mov")), printed[:200])
saved = json.load(open(out))
check("14 the local file holds the entries", len(saved) == 3 and saved[0]["path"] == "Ada Test/Scales 1/take1.mov")
check("15 the file is private to the owner", stat.S_IMODE(os.stat(out).st_mode) == 0o600, oct(stat.S_IMODE(os.stat(out).st_mode)))
check("16 no temp file is left behind", not [f for f in os.listdir(os.path.dirname(out)) if f.endswith(".tmp")])
sys.argv = ["sharepoint_listing.py", "--site", "https://evil.example.com/sites/a", "--out", out + "2"]; buf = io.StringIO()
try:
    with contextlib.redirect_stdout(buf): code = SL.main()
finally: sys.argv = old
check("17 a bad site address fails cleanly and writes nothing", code != 0 and not os.path.exists(out + "2") and '"ok": false' in buf.getvalue(), buf.getvalue()[:160])
sys.exit(0 if all(ok) else 1)
