"""Microsoft Forms response export (.xlsx / .csv), read from a file the teacher chose. Everything is invented; nothing
contacts Forms or any network. The answers carry a marker so the tests can prove what reached the cards and what did not."""
import base64, io, json, os, sys, tempfile, threading, time, zipfile
from _common import APPDIR, LAUNCH, guard, guard_app, block_live_browser
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

class O(BaseHTTPRequestHandler):
    def _j(self, o):
        b = json.dumps(o).encode(); self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_GET(self): self._j({"/api/tags": {"models": [{"name": "qwen2.5:14b"}]}, "/api/ps": {"models": []}}.get(self.path, {}))
    def do_POST(self): self.rfile.read(int(self.headers.get("Content-Length", 0))); self._j({"message": {"content": "x"}})
    def log_message(self, *a): pass
threading.Thread(target=ThreadingHTTPServer(("127.0.0.1", 11434), O).serve_forever, daemon=True).start()

import app, forms_import as F, teams_read as T
guard_app(app, HOME); block_live_browser(T)
ok_all = []
def check(label, cond, extra=""):
    ok_all.append(bool(cond)); print(("PASS " if cond else "FAIL ") + label + (("  | " + str(extra)[:220]) if extra != "" else ""))

M = "ZQ-FORMS-MARK"
HEAD = ["Id", "Start time", "Completion time", "Email", "Name", "Total points", "Quiz feedback", "What is a prototype?", "Points - What is a prototype?", "Feedback - What is a prototype?", "Name two materials you could test."]
def row(i, name, a1, a2, pts="3", email="x@example.test"):
    return [str(i), "45000.5", "45000.6", email, name, pts, "", a1, "1", "", a2]
ROWS = [HEAD, row(1, "Ada Example", f"{M} A first model used to test an idea.", "Cardboard; foam"), row(2, "Ben Sampleton", "A drawing.", "Plastic", pts="1")]

r = F.forms_students(ROWS)
check("A1 a Forms export is recognised and gives one entry per named student", r and [s["name"] for s in r["students"]] == ["Ada Example", "Ben Sampleton"] and not r["anonymous"], r and r["notes"])
w = r["students"][0]["work"]
check("A2 the work holds each question with its answer and nothing from Forms' own columns", w == f"What is a prototype?: {M} A first model used to test an idea.\n\nName two materials you could test.: Cardboard; foam", w)
check("A3 auto-scores are reported on the side, never in the work", r["students"][0]["points"] == "3" and "3" not in w.replace("first", "") and "Points" not in w and "Feedback" not in w)
check("A4 rows that are not a Forms export are left to the generic reader", F.forms_students([["Name", "Essay"], ["Ada", "text"]]) is None and F.forms_students([]) is None)
check("A5 times, ids and emails never reach the work", all(x not in w for x in ("45000", "example.test")))
anon = F.forms_students([["Id", "Start time", "Completion time", "Email", "Name", "Q1"], ["1", "a", "b", "anonymous", "", "an answer"]])
check("A6 an anonymous form is flagged, with a reason", anon["anonymous"] and "no student names" in anon["notes"][0], anon)
dup = F.forms_students([HEAD, row(1, "Ada Example", "first try", "x"), row(2, "Ben Sampleton", "b", "y"), row(3, "ada example", "second try", "z")])
check("A7 a student who submitted twice: the last response is kept and the teacher is told", [s["name"] for s in dup["students"]] == ["Ben Sampleton", "ada example"] and "second try" in dup["students"][1]["work"] and "more than once" in " ".join(dup["notes"]), dup["notes"])
blank = F.forms_students([HEAD, row(1, "Ada Example", "", ""), row(2, "Ben Sampleton", "b", "c")])
check("A8 a response with no answers at all is skipped and counted", len(blank["students"]) == 1 and "blank response" in " ".join(blank["notes"]))
un = F.forms_students([HEAD, row(1, "", "an answer", "b")])
check("A9 a response with no name gets a neutral label and a note", un["students"][0]["name"] == "Response 1" and not un["students"][0]["has_name"] and "no name" in " ".join(un["notes"]), un["notes"])
big = F.forms_students([HEAD, row(1, "Ada Example", "x" * 9000, "b")])
check("A10 a very long answer is cut and the teacher is told", len(big["students"][0]["work"]) < 4200 and "cut at" in " ".join(big["notes"]))
many = F.forms_students([HEAD] + [row(i, f"S{i}", "a", "b") for i in range(400)])
check("A11 more than 300 responses: only 300 are read and it says so", len(many["students"]) == 300 and "Only the first 300" in many["notes"][0])
ctl = F.forms_students([HEAD, row(1, "Ada\x07 Example", "ans\x00wer", "b")])
check("A12 control characters are removed", ctl["students"][0]["name"] == "Ada Example" and "\x00" not in ctl["students"][0]["work"])
checkbox = F.forms_students([HEAD, row(1, "Ada Example", "plan; test; share", "b")])
check("A13 a multi-choice answer keeps its separators", "plan; test; share" in checkbox["students"][0]["work"])

# ---------------------------------------------------------------- B. the real upload path (xlsx and csv bytes)
def xlsx_bytes(rows):
    def col(n):
        s = ""
        n += 1
        while n: n, rem = divmod(n - 1, 26); s = chr(65 + rem) + s
        return s
    esc = lambda t: t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    sheet = "".join(f'<row r="{ri}">' + "".join(f'<c r="{col(ci)}{ri}" t="inlineStr"><is><t>{esc(v)}</t></is></c>' for ci, v in enumerate(r)) + "</row>" for ri, r in enumerate(rows, 1))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("xl/workbook.xml", '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Sheet1" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr("xl/_rels/workbook.xml.rels", '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>{sheet}</sheetData></worksheet>')
    return b.getvalue()
import csv
def csv_bytes(rows):
    s = io.StringIO(); csv.writer(s).writerows(rows); return ("﻿" + s.getvalue()).encode("utf-8")
px = app.parse_upload("Prototype quiz.xlsx", xlsx_bytes(ROWS), "auto")
pc = app.parse_upload("Prototype quiz.csv", csv_bytes(ROWS), "auto")
check("B1 an .xlsx export and a .csv export give the same students", isinstance(px, dict) and px["forms"]["students"] == pc["forms"]["students"] and len(px["forms"]["students"]) == 2)
g = app.parse_upload("essays.csv", csv_bytes([["Name", "Essay"], ["Ada", "some text"]]), "auto")
check("B2 an ordinary spreadsheet still goes through the generic reader", isinstance(g, list) and g[0][0] == "Ada")

# ---------------------------------------------------------------- C. the page
srv = app.ThreadingHTTPServer(("127.0.0.1", 8765), app.Handler)
threading.Thread(target=srv.serve_forever, daemon=True).start(); time.sleep(0.5)
from playwright.sync_api import sync_playwright
tmp = tempfile.mkdtemp()
def write(name, data): p = os.path.join(tmp, name); open(p, "wb").write(data); return p
good = write("Prototype quiz.xlsx", xlsx_bytes(ROWS))
anon_f = write("Anonymous.csv", csv_bytes([["Id", "Start time", "Completion time", "Email", "Name", "Q1"], ["1", "a", "b", "anonymous", "", "an answer"]]))
with sync_playwright() as p:
    b = p.chromium.launch(**LAUNCH); pg = b.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto("http://127.0.0.1:8765/"); time.sleep(1.5)
    pg.set_input_files("#filepick", good); time.sleep(1.5)
    cards = pg.locator(".student")
    names = [cards.nth(i).locator(".name").input_value() for i in range(cards.count())]
    check("C1 uploading the export makes one card per student", names == ["Ada Example", "Ben Sampleton"], names)
    check("  each card holds the answers", M in cards.nth(0).locator(".work").input_value() and "Cardboard" in cards.nth(0).locator(".work").input_value())
    check("  the auto-score is shown as information, and is not in the work", "Forms auto-score: 3" in cards.nth(0).inner_text() and "auto-score" not in cards.nth(0).locator(".work").input_value())
    check("  no level is chosen for anyone", all(cards.nth(i).locator(".level").input_value() == "" for i in range(2)))
    pg.evaluate("document.querySelectorAll('.student').forEach(c => c.remove()); addStudent()")
    pg.set_input_files("#filepick", anon_f); time.sleep(1.2)
    check("C2 an anonymous export adds no cards and says why", "no student names" in pg.locator("#status").inner_text() and pg.locator(".student .name").first.input_value() == "", pg.locator("#status").inner_text())
    check("C3 no page errors", not errs, errs)
    b.close()
print(f"\n{sum(ok_all)}/{len(ok_all)} checks passed"); sys.exit(0 if all(ok_all) else 1)
