#!/usr/bin/env python3
"""Local web UI for feedback.py. Run:  python3 app.py
Opens http://127.0.0.1:8765 - served only on this laptop, talks only to local Ollama."""
import base64
import csv
import html
import io
import json
import re
import subprocess
import tempfile
import zipfile
import threading
from pathlib import Path
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import feedback as fb

HOST, PORT = "127.0.0.1", 8765
STANDARDS_DIR = Path(__file__).parent / "standards"  # drop learning-standards PDFs here
_cache = {}
_std_lock = threading.Lock()


NAME_LINE = re.compile(r"^\s*(?:student(?:\s+name)?|name)\s*[:\-\u2013]\s*(.+?)\s*$", re.I | re.M)
ID_LINE = re.compile(r"^\s*([A-Za-z]{1,2}\d{2,4})\b(?![.)])", re.M)  # e.g. "R002 ..." student codes, not "Q10." / "Q10)"
RULE_LINE = re.compile(r"^\s*(?:-{3,}|={3,}|_{3,})\s*$", re.M)


def _split_text(text, stem):
    """One document -> [(name, work)]. Splits on 'Name: X' lines, else on --- rules, else one student."""
    marks = list(NAME_LINE.finditer(text))
    if len(marks) >= 2:
        out = []
        for i, m in enumerate(marks):
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            out.append((m.group(1), text[m.end():end].strip()))
        return [(n, w) for n, w in out if w]
    ids = list(ID_LINE.finditer(text))
    lead = [l for l in text[:ids[0].start()].splitlines() if l.strip()] if ids else []
    if len(ids) >= 2 and len(lead) <= 1:  # more than a title line before the first code: numbered questions, not codes
        out = []
        for i, m in enumerate(ids):
            end = ids[i + 1].start() if i + 1 < len(ids) else len(text)
            out.append((m.group(1), text[m.end():end].strip()))
        return [(n, w) for n, w in out if w]
    blocks = [b.strip() for b in RULE_LINE.split(text) if b.strip()]
    if len(blocks) >= 2:
        return [(f"{stem} {i}", b) for i, b in enumerate(blocks, 1)]
    return [(stem, text.strip())] if text.strip() else []


def read_xlsx(raw):
    """Minimal .xlsx reader (stdlib only): {sheet name: [[cell text, ...], ...]}. Values only, no formulas."""
    import xml.etree.ElementTree as ET
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
          "pr": "http://schemas.openxmlformats.org/package/2006/relationships"}
    z = zipfile.ZipFile(io.BytesIO(raw))
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", ns):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % ns["m"])))
    rels = {r.get("Id"): r.get("Target") for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels")).findall("pr:Relationship", ns)}
    def col(ref):
        n = 0
        for ch in re.match(r"[A-Z]+", ref).group():
            n = n * 26 + ord(ch) - 64
        return n - 1
    out = {}
    for sh in ET.fromstring(z.read("xl/workbook.xml")).find("m:sheets", ns):
        target = rels[sh.get("{%s}id" % ns["r"])].lstrip("/")
        root = ET.fromstring(z.read(target if target.startswith("xl/") else "xl/" + target))
        rows = []
        for row in root.iter("{%s}row" % ns["m"]):
            cells = {}
            for c in row.findall("m:c", ns):
                t, v = c.get("t"), c.find("m:v", ns)
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter("{%s}t" % ns["m"]))
                elif v is not None:
                    val = v.text or ""
                    if t is None and re.fullmatch(r"-?\d+\.0+", val):
                        val = val.split(".")[0]
                else:
                    val = ""
                cells[col(c.get("r"))] = val.strip()
            if cells:
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
        out[sh.get("name")] = rows
    return out


def rows_to_students(rows, stem):
    """Header row + one row per student -> [(name, work)]. Name column = a header with 'name'/'student'."""
    if len(rows) < 2:
        return []
    head = rows[0]
    name_i = next((i for i, h in enumerate(head) if re.search(r"name|student", h, re.I)), 0)
    # whole-heading match only, so questions like "Who is your target market?" are kept
    skip = re.compile(r"\s*(?:e-?mail(?: address)?|timestamp|id|(?:total )?(?:score|points?|marks?)|grade(?: level)?"
                      r"|submitted(?: at| on| date)?|date submitted)\s*", re.I)
    work_i = [i for i, h in enumerate(head) if i != name_i and not skip.fullmatch(h)]
    out = []
    for n, r in enumerate(rows[1:], 1):
        r = r + [""] * (len(head) - len(r))
        parts = [(head[i], r[i].strip()) for i in work_i if r[i].strip()]
        if not parts:
            continue
        work = parts[0][1] if len(parts) == 1 else "\n\n".join(f"{h}: {v}" for h, v in parts)
        out.append((r[name_i].strip() or f"{stem} {n}", work))
    return out


def teams_export(rows):
    """Recognise a Teams 'Assignment Data' export (Full Name / Assignments / Status columns).
    Returns only what the page needs: no emails, no feedback text."""
    for hi, row in enumerate(rows):
        low = [c.strip().lower() for c in row]
        if "full name" in low and "status" in low and "assignments" in low:
            ix = {h: low.index(h) for h in ("full name", "first name", "last name", "assignments", "due date", "status", "feedback") if h in low}
            title = next((c for r in rows[:hi] for c in r if c.strip()), "")
            studs, assigns, dues = [], {}, set()
            for r in rows[hi + 1:]:
                get = lambda k: r[ix[k]].strip() if k in ix and ix[k] < len(r) else ""
                name = get("full name") or (get("first name") + " " + get("last name")).strip()
                if not name:
                    continue
                first, last = get("first name"), get("last name")
                if not (first and last):
                    parts = name.split()
                    first, last = parts[0], " ".join(parts[1:])
                studs.append({"name": name, "first": first, "last": last, "status": get("status") or "Unknown",
                              "has_feedback": bool(get("feedback"))})
                assigns[get("assignments")] = assigns.get(get("assignments"), 0) + 1
                if get("due date"):
                    dues.add(get("due date"))
            due = ""
            for d in dues:
                due = (datetime(1899, 12, 30) + timedelta(days=int(float(d)))).strftime("%Y-%m-%d") if re.fullmatch(r"\d+(\.\d+)?", d) else d
            return {"title": title, "assignment": max(assigns, key=assigns.get) if assigns else "", "due": due, "students": studs}
    return None


def parse_upload(filename, raw, mode):
    ext = Path(filename).suffix.lower()
    stem = Path(filename).stem
    if ext == ".csv":
        return rows_to_students(list(csv.reader(io.StringIO(raw.decode("utf-8-sig", "replace")))), stem)
    if ext == ".xlsx":
        sheets = read_xlsx(raw)
        for rows in sheets.values():
            teams = teams_export(rows)
            if teams:
                return {"teams": teams}
        first = next(iter(sheets.values()), [])
        first = [r for r in first if any(c.strip() for c in r)]
        return rows_to_students(first, stem)
    if ext == ".docx":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
        xml = re.sub(r"</w:p>", "\n", xml)
        text = html.unescape(re.sub(r"<[^>]+>", "", xml))
        return _split_text(text, stem) if mode != "whole" else [(stem, text.strip())]
    if ext == ".pdf":
        with tempfile.NamedTemporaryFile(suffix=".pdf") as t:
            t.write(raw)
            t.flush()
            text = subprocess.run(["pdftotext", t.name, "-"], capture_output=True, text=True).stdout
        if mode == "page":
            return [(f"{stem} p{i}", p.strip()) for i, p in enumerate(text.split("\f"), 1) if p.strip()]
        return _split_text(text, stem) if mode != "whole" else [(stem, text.strip())]
    text = raw.decode("utf-8-sig", "replace")
    return _split_text(text, stem) if mode != "whole" else [(stem, text.strip())]


HERE = Path(__file__).parent
CACHE = HERE / "courses.cache.json"


def hub_settings():
    """Course Hub URL + API key. Env vars win, then ./.env.local. The key stays server-side only."""
    env = {}
    p = HERE / ".env.local"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip("'\"")
    get = lambda k, d="": os.environ.get(k) or env.get(k) or d
    return get("COURSE_HUB_URL", "http://localhost:3005").rstrip("/"), get("COURSE_HUB_API_KEY")


def _classify(name, grades, rules):
    for r in rules:
        if re.search(r["pattern"], name, re.I):
            out = {"department": r["department"]}
            if r.get("match_by_grade") and len(grades) == 1:
                out["match"] = f"{r['match_by_grade']} {grades[0]}"
            return out
    return {"department": ""}


def hub_get(path):
    base, key = hub_settings()
    if not key:
        raise RuntimeError("COURSE_HUB_API_KEY is not set (see README)")
    req = urllib.request.Request(base + path, headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Course Hub answered {e.code} for {path.split('?')[0].rsplit('/', 1)[0] if 'roster' in path else path.split('?')[0]}")
    except (urllib.error.URLError, OSError):
        raise RuntimeError(f"Can't reach Course Hub at {base}")


def fetch_from_course_hub(rules):
    """Live course list + quarters from Course Hub's API, normalised for the page."""
    get = hub_get

    quarters = get("/api/quarters")
    school_year = quarters[0]["school_year"] if quarters else ""
    sy = f"school_year={school_year}&" if school_year else ""
    sections = get(f"/api/courses?{sy}quarter=all&type=academic")

    grouped = {}  # (name, quarters) -> sections: blocks of one course merge; "ICT 9" Q1 and Q2 stay apart
    for c in sections:
        qs = tuple(sorted({int(m) for q in (c.get("quarters") or []) for m in re.findall(r"\d", str(q))}))
        g = grouped.setdefault((c["name"].strip(), qs), {"grades": set(), "sections": []})
        g["grades"].update(int(x) for x in (c.get("grade_years") or []))
        g["sections"].append({"id": c["id"], "block": c.get("block") or "", "quarters": list(qs)})
    per_name = {}
    for name, qs in grouped:
        per_name[name] = per_name.get(name, 0) + 1
    courses = []
    for (name, qs), g in sorted(grouped.items(), key=lambda kv: (min(kv[1]["grades"] or {99}), kv[0][0], kv[0][1])):
        grades = sorted(g["grades"])
        label = name
        if per_name[name] > 1:  # same name, different quarters: tell the sections apart
            label = f"{name} ({'/'.join('Q' + str(n) for n in qs)})" if qs else f"{name} (full year)"
        entry = {"name": label, "grades": grades, "sections": g["sections"], **_classify(name, grades, rules)}
        if qs:
            entry["quarters"] = list(qs)
        courses.append(entry)
    return {
        "courses": courses,
        "quarters": [{"label": q["label"], "start": q["start_date"], "end": q["end_date"]} for q in quarters],
        "school_year": school_year,
        "fetched_at": datetime.now().isoformat(timespec="minutes"),
    }


_mem = {"at": 0, "data": None}


def course_data():
    """Live from Course Hub (60 s in-memory reuse); else the last live copy; else courses.json."""
    if _mem["data"] and time.time() - _mem["at"] < 60:
        return _mem["data"]
    data = _course_data()
    if data.get("source") == "live":
        _mem.update(at=time.time(), data=data)
    return data


def _course_data():
    cfg = json.loads((HERE / "courses.json").read_text(encoding="utf-8"))
    rules = cfg.get("department_rules", [])
    try:
        data = fetch_from_course_hub(rules)
        CACHE.write_text(json.dumps(data, indent=1), encoding="utf-8")
        data.update(source="live", note=f"Courses from Course Hub (live), {data['school_year']}.")
        return data
    except RuntimeError as why:
        if CACHE.exists():
            data = json.loads(CACHE.read_text(encoding="utf-8"))
            data.update(source="cache", note=f"{why}. Using the copy fetched {data.get('fetched_at', 'earlier')}.")
            return data
        cfg.update(source="file", note=f"{why}. Using the built-in course list.")
        return cfg


def roster_for(course_name, quarter=""):
    """Students in a course from Course Hub. In memory only: never cached or written to disk.
    Returns only what the page needs (no email, no gender)."""
    course = next((c for c in course_data().get("courses", []) if c["name"] == course_name), None)
    if not course or not course.get("sections"):
        raise RuntimeError("Class list needs live course data from Course Hub.")
    qn = int(quarter) if str(quarter).isdigit() else None
    secs = [s for s in course["sections"] if qn is None or not s["quarters"] or qn in s["quarters"]] or course["sections"]
    seen, out = set(), []
    for sec in secs:
        for st in hub_get(f"/api/courses/{urllib.parse.quote(str(sec['id']))}/roster"):
            if st["id"] in seen:
                continue
            seen.add(st["id"])
            out.append({"id": st["id"], "first": st.get("first_name", ""), "last": st.get("last_name", ""),
                        "grade": st.get("grade_year"), "grade_year_reference": st.get("grade_year_reference") or "",
                        "block": sec.get("block", "")})
    return sorted(out, key=lambda s: (s["last"].lower(), s["first"].lower()))


def load_standards():
    """{doc name: [{id, label, text}]} parsed from every PDF in standards/ (needs pdftotext).
    Locked, and the cache is filled only when every PDF is parsed: the page asks for courses and standards at once."""
    with _std_lock:
        if not _cache:
            _cache.update(_parse_standards())
        return _cache


def _parse_standards():
    docs = {}
    for pdf in sorted(STANDARDS_DIR.glob("*.pdf")):
        raw = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
        sections = []
        for page in raw.split("\f"):
            lines = [l.rstrip() for l in page.splitlines() if l.strip()]
            if not lines:
                continue
            page_label = re.sub(r"\s+", " ", lines[0]).strip()
            cur = None
            for l in lines[1:]:
                flat = re.sub(r" {3,}", " | ", l.strip())
                if flat.startswith("Richmond Christian School"):
                    continue
                if re.match(r"Learning Standard \d+:", flat):
                    cur = {"label": f"{page_label} - {flat}", "lines": []}
                    sections.append(cur)
                elif cur is not None:
                    cur["lines"].append(flat)
        name = re.sub(r"_RCS_Branded|\.pdf$", "", pdf.name).replace("_", " ")
        docs[name] = [
            {"id": f"{i}", "label": sec["label"], "text": sec["label"].split(" - ", 1)[1] + "\n" + "\n".join(sec["lines"])}
            for i, sec in enumerate(sections)
        ]
    return docs

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Student Feedback</title>
<style>
  :root{--bg:#f6f5f1;--card:#fff;--ink:#1f2328;--mute:#6b7280;--line:#e2e0d8;--accent:#2f6f5e}
  @media (prefers-color-scheme:dark){:root{--bg:#16181a;--card:#1f2225;--ink:#e8e8e6;--mute:#9aa0a6;--line:#33373b;--accent:#6fbfa8}}
  *{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
  main{max-width:860px;margin:0 auto;padding:24px 16px 80px}
  h1{font-size:1.4rem;margin:0 0 4px} .sub{color:var(--mute);margin:0 0 20px;font-size:.9rem}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px}
  label{display:block;font-weight:600;font-size:.85rem;margin-bottom:4px}
  textarea,input,select{width:100%;font:inherit;color:var(--ink);background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:8px}
  textarea{min-height:110px;resize:vertical}
  .row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
  @media(max-width:600px){.row{grid-template-columns:1fr}}
  button{font:inherit;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--ink);padding:8px 14px;cursor:pointer}
  button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
  button:disabled{opacity:.5;cursor:default}
  .bar{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}
  .out{white-space:pre-wrap;margin-top:12px;padding:12px;border-left:3px solid var(--accent);background:var(--bg);border-radius:0 6px 6px 0}
  .status{color:var(--mute);font-size:.85rem;margin-top:8px}
  .err{color:#b42318}
</style></head><body><main>
<h1>Student Feedback</h1>
<p class="sub">Runs on this laptop with a local model. Drafts only: review before sharing.</p>

<div class="card">
  <label for="atitle">Assignment name <span style="font-weight:400;color:var(--mute)">(optional; filled in from a Teams export)</span></label>
  <input id="atitle" placeholder="e.g. Task 2: Define &amp; Ideate" style="margin-bottom:12px">
  <label for="rubric">Assignment instructions</label>
  <textarea id="rubric" placeholder="Paste the assignment instructions here. (Optional if you tick learning standards below.)"></textarea>
  <div class="row">
    <div><label for="grade">Grade level</label><select id="grade"></select></div>
    <div><label for="model">Model</label><select id="model"></select></div>
  </div>
  <div class="row">
    <div><label for="length">Feedback length</label>
      <select id="length">
        <option value="sentence">One sentence</option>
        <option value="paragraph">One paragraph</option>
        <option value="detailed">Long (multi-part)</option>
      </select></div>
    <div></div>
  </div>
</div>

<div class="card">
  <label for="course">Course</label>
  <div class="row" style="margin-top:0">
    <div><label for="quarter">Term <span style="font-weight:400;color:var(--mute)">(chosen from today's date)</span></label>
      <select id="quarter"></select></div>
    <div></div>
  </div>
  <label for="course" style="margin-top:12px">Course</label>
  <select id="course"><option value="">Not listed / choose department below</option></select>
  <div class="status" id="coursenote"></div>
  <div class="status" id="coursesrc"></div>
  <div class="status" id="rosternote"></div>
  <label for="doc" style="margin-top:14px">Department <span style="font-weight:400;color:var(--mute)">(set automatically from the course)</span></label>
  <select id="doc"><option value="">None</option></select>
  <div id="stds" style="margin-top:10px"></div>
</div>

<div id="students"></div>

<div class="bar">
  <button id="add">+ Add student</button>
  <button id="addall" disabled>+ Add whole class</button>
  <button id="files">Upload files…</button>
  <input id="filepick" type="file" accept=".txt,.md,.csv,.pdf,.docx,.xlsx" multiple hidden>
  <select id="split" style="width:auto" title="How to split uploaded files into students">
    <option value="auto">Split: automatic (Name: lines or --- rules)</option>
    <option value="page">Split: one student per PDF page</option>
    <option value="whole">Don't split: one student per file</option>
  </select>
  <button class="primary" id="go">Generate feedback</button>
  <button id="dl" disabled>Download all (.csv)</button>
  <button id="dlteams" disabled title="Names in Teams order, ready to paste into each student's Feedback box">Download for Teams (.csv)</button>
</div>
<label style="font-weight:400;display:flex;gap:8px;align-items:center;margin-top:10px"><input type="checkbox" id="skipret" checked style="width:auto"> Skip students Teams already shows as Returned</label>
<div class="status" id="teamsnote"></div>
<div class="status" id="status"></div>

<script>
const $ = s => document.querySelector(s);
const store = {get:k=>{try{return localStorage.getItem(k)||""}catch(e){return ""}},
               set:(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}}};
$("#rubric").value = store.get("rubric"); const GRADES = ["Grade 9","Grade 10","Grade 11","Grade 12"];
$("#grade").innerHTML = GRADES.map(g=>`<option>${g}</option>`).join("");
$("#grade").value = GRADES.includes(store.get("grade")) ? store.get("grade") : "Grade 9";
$("#rubric").oninput = e => store.set("rubric", e.target.value);
$("#grade").onchange = e => store.set("grade", e.target.value);

fetch("/api/models").then(r=>r.json()).then(d=>{
  if(d.error){ $("#status").innerHTML = '<span class="err">'+d.error+'</span>'; return; }
  const saved = store.get("model_choice") || d.default;
  $("#model").innerHTML = d.models.map(m=>`<option ${m===saved?"selected":""}>${m}</option>`).join("");
});
$("#length").value = ["sentence","paragraph","detailed"].includes(store.get("length")) ? store.get("length") : "paragraph";
$("#length").onchange = e => store.set("length", e.target.value);
$("#model").onchange = e => store.set("model_choice", e.target.value);

let STD = {}, COURSES = [], QUARTERS = [], SCHOOL_YEAR = "", ROSTER = [];
function rosterOptions(){
  return '<option value="">' + (ROSTER.length ? "Choose from class list…" : "Choose a course for a class list…") + '</option>' +
    ROSTER.map((s,i)=>`<option value="${i}">${s.last}, ${s.first}${s.block ? " (" + s.block + ")" : ""}</option>`).join("");
}
const norm = t => (t||"").normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z\s'-]/g," ").replace(/\s+/g," ").trim();
function lev(a,b){
  const m = Array.from({length:a.length+1}, (_,i)=>[i]); for(let j=1;j<=b.length;j++) m[0][j]=j;
  for(let i=1;i<=a.length;i++) for(let j=1;j<=b.length;j++)
    m[i][j] = Math.min(m[i-1][j]+1, m[i][j-1]+1, m[i-1][j-1] + (a[i-1]===b[j-1] ? 0 : 1));
  return m[a.length][b.length];
}
// Match an uploaded name to the class list. Tiers, strictest first; a tier with 2+ hits is ambiguous, not guessed.
function findStudent(raw, list = ROSTER){
  const n = norm(raw);
  if(!n || !list.length) return {status:"none"};
  let first, last;
  if(raw.includes(",")){ const p = raw.split(","); last = norm(p[0]); first = norm(p.slice(1).join(" ")); }
  else { const p = n.split(" "); first = p[0]; last = p.slice(1).join(" "); }
  const R = list.map((s,i)=>({s, i, f:norm(s.first), l:norm(s.last)}));
  const toks = n.split(" ");
  const tiers = [
    () => last && R.filter(r => (r.f===first && r.l===last) || (r.f===last && r.l===first)),                       // exact, either order
    () => last && last.replace(/\./g,"").length===1 ? R.filter(r => r.f===first && r.l.startsWith(last[0])) : [],   // "Mia C."
    () => R.filter(r => r.f && r.l && toks.includes(r.f) && r.l.split(" ").every(t => toks.includes(t))),            // both names appear (file names)
    () => !last ? R.filter(r => r.f===first) : [],                                                                  // first name only
    () => !last ? R.filter(r => r.l===first) : [],                                                                  // last name only
    () => { const full = (first+" "+last).trim(), lim = full.length > 10 ? 2 : 1;                                   // close spelling
            const sc = R.map(r => ({r, d: Math.min(lev(full, r.f+" "+r.l), lev(full, r.l+" "+r.f))})).filter(x=>x.d<=lim);
            const best = Math.min(...sc.map(x=>x.d)); return sc.filter(x=>x.d===best).map(x=>x.r); },
  ];
  for(const t of tiers){
    const hits = t();
    if(hits && hits.length === 1) return {status:"match", s:hits[0].s, i:hits[0].i};
    if(hits && hits.length > 1) return {status:"ambiguous", options:hits.map(h=>h.s.first+" "+h.s.last)};
  }
  return {status:"none"};
}
let TEAMS = null;   // status export from Teams, held in this page only
const teamsLabel = t => "Teams: " + ({"Turned in":"turned in", "Viewed":"viewed, not turned in",
  "Returned":"returned" + (t.has_feedback ? " (feedback already given)" : "")}[t.status] || t.status);
function teamsFor(card){
  if(!TEAMS) return null;
  const raw = card.dataset.orig || card.querySelector(".name").value.trim();
  if(!raw) return null;
  const r = findStudent(raw, TEAMS.students);
  return r.status === "match" ? r.s : null;
}
function applyTeams(){
  document.querySelectorAll(".student").forEach(c => {
    const el = c.querySelector(".tstatus"), t = teamsFor(c);
    c.dataset.tstatus = t ? t.status : "";
    const cur = c.querySelector(".name").value.trim();           // tidy file-name style names ("Lin_Ava_Task2")
    if(t && norm(cur) !== norm(t.name)){ c.dataset.orig = c.dataset.orig || cur; c.querySelector(".name").value = t.name; }
    el.textContent = !TEAMS ? "" : t ? teamsLabel(t) : (c.querySelector(".name").value.trim() ? "Teams: not found in this export" : "");
    el.style.color = t && t.status === "Returned" ? "#b45309" : "";
  });
  const note = $("#teamsnote");
  if(!TEAMS){ note.textContent = ""; return; }
  const counts = {}; TEAMS.students.forEach(s => counts[s.status] = (counts[s.status] || 0) + 1);
  const have = new Set();
  document.querySelectorAll(".student").forEach(c => { const t = teamsFor(c); if(t && c.querySelector(".work").value.trim()) have.add(t.name); });
  const waiting = TEAMS.students.filter(s => s.status === "Turned in" && !have.has(s.name)).map(s => s.name);
  note.textContent = (TEAMS.assignment || "Assignment") + (TEAMS.due ? " (due " + TEAMS.due + ")" : "") + ": " +
    Object.entries(counts).map(([k, v]) => v + " " + k.toLowerCase()).join(", ") + "." +
    (waiting.length ? " Turned in, no work loaded yet: " + waiting.slice(0, 8).join(", ") + (waiting.length > 8 ? " +" + (waiting.length - 8) + " more" : "") + "." : "");
}
function setNote(card, text, warn){
  const el = card.querySelector(".matchnote"); el.textContent = text; el.style.color = warn ? "#b45309" : "";
}
function matchCard(card){
  const name = card.querySelector(".name").value.trim();
  if(!ROSTER.length || !name){ setNote(card, ""); return null; }
  const raw = card.dataset.orig || name;          // the name as uploaded/typed, before correction
  card.dataset.orig = raw;
  const r = findStudent(raw);
  const was = norm(raw) !== norm(r.s ? r.s.first + " " + r.s.last : "") ? "  (uploaded as \"" + raw + "\")" : "";
  const pick = card.querySelector(".pick");
  if(r.status === "match"){
    pick.value = String(r.i); pick.onchange();
    setNote(card, "✓ Matched to class list: " + r.s.last + ", " + r.s.first + was);
    card.dataset.rid = r.s.id;
  } else {
    pick.value = ""; delete card.dataset.rid;
    setNote(card, r.status === "ambiguous" ? "? Could be: " + r.options.join(" or ") + " - choose from the class list" : "? Not on this class list - check the name or the course", true);
  }
  return r;
}
function matchAll(announce){
  if(!ROSTER.length) return;
  const cards = [...document.querySelectorAll(".student")].filter(c => c.querySelector(".name").value.trim());
  let ok = 0; const seen = {};
  cards.forEach(c => { const r = matchCard(c); if(r && r.status === "match"){ ok++; (seen[r.s.id] = seen[r.s.id] || []).push(c); } });
  Object.values(seen).filter(a => a.length > 1).forEach(a => a.forEach(c => { ok--; setNote(c, "? Two uploads match the same student (" + c.querySelector(".name").value + ")" + (c.dataset.orig ? "  (uploaded as \"" + c.dataset.orig + "\")" : ""), true); }));
  if(announce){
    const present = new Set(Object.keys(seen));
    const missing = ROSTER.filter(s => !present.has(s.id)).map(s => s.first + " " + s.last);
    $("#status").textContent = cards.length + " loaded: " + ok + " matched to the class list" +
      (cards.length - ok ? ", " + (cards.length - ok) + " need checking" : "") + "." +
      (missing.length ? " No work found for: " + missing.slice(0, 8).join(", ") + (missing.length > 8 ? " +" + (missing.length - 8) + " more" : "") + "." : "");
  }
}
function wirePicker(card){
  const pick = card.querySelector(".pick");
  pick.innerHTML = rosterOptions();
  pick.onchange = () => {
    const s = ROSTER[pick.value]; if(!s) return;
    card.querySelector(".name").value = s.first + " " + s.last;
    card.dataset.rid = s.id; setNote(card, "✓ Matched to class list: " + s.last + ", " + s.first);
    // Course Hub stores one grade per student, true only for the year it was recorded in.
    const g = "Grade " + s.grade;
    if(s.grade && s.grade_year_reference === SCHOOL_YEAR && GRADES.includes(g) && g !== $("#grade").value) card.querySelector(".sgrade").value = g;
  };
}
async function loadRoster(){
  const c = COURSES[$("#course").value];
  ROSTER = []; $("#addall").disabled = true;
  if(c && c.sections){
    const qn = ($("#quarter").value||"").replace("Q","");
    try {
      const d = await (await fetch("/api/roster?name=" + encodeURIComponent(c.name) + "&quarter=" + qn)).json();
      if(d.error) $("#rosternote").textContent = d.error;
      else { ROSTER = d.students; $("#rosternote").textContent = ROSTER.length + (ROSTER.length === 1 ? " student" : " students") + " in " + c.name + " (class list held in memory only)."; }
    } catch(e){ $("#rosternote").textContent = "Couldn't load the class list."; }
  } else $("#rosternote").textContent = c ? "Class list unavailable (course list isn't live from Course Hub)." : "";
  document.querySelectorAll(".student").forEach(wirePicker);
  $("#addall").disabled = !ROSTER.length;
  if(ROSTER.length) matchAll(document.querySelectorAll(".student .name").length > 1);
}
function quarterForToday(){
  if(!QUARTERS.length) return "";
  const t = new Date(); const iso = t.getFullYear()+"-"+String(t.getMonth()+1).padStart(2,"0")+"-"+String(t.getDate()).padStart(2,"0");
  let pick = QUARTERS[0];                       // before the year starts -> Q1
  for(const q of QUARTERS) if(q.start <= iso) pick = q;   // latest quarter already started (covers gaps and breaks)
  return pick.label;
}
function runsIn(c, qn){ return !c.quarters || !c.quarters.length || c.quarters.includes(qn); }
function courseLabel(c){ return c.name + (c.quarters && !/\(Q\d/.test(c.name) ? " (" + c.quarters.map(n=>"Q"+n).join("/") + ")" : ""); }
function renderCourses(keepValue){
  const qn = parseInt($("#quarter").value.replace("Q","")) || 0;
  const cur = keepValue === undefined ? $("#course").value : keepValue;
  const opt = (c,i) => `<option value="${i}">${courseLabel(c)}</option>`;
  const items = COURSES.map((c,i)=>({c,i}));
  const now = items.filter(({c}) => runsIn(c, qn)), other = items.filter(({c}) => !runsIn(c, qn));
  $("#course").innerHTML = '<option value="">Not listed / choose department below</option>' +
    `<optgroup label="Running in ${$("#quarter").value || "this term"}">${now.map(({c,i})=>opt(c,i)).join("")}</optgroup>` +
    (other.length ? `<optgroup label="Other terms">${other.map(({c,i})=>opt(c,i)).join("")}</optgroup>` : "");
  if([...$("#course").options].some(o=>o.value===cur)) $("#course").value = cur; else $("#course").value = "";
}
const baseName = n => n.replace(/\s*\([^)]*\)\s*$/, "").trim();
$("#quarter").onchange = () => {
  store.set("quarter_choice", JSON.stringify({q:$("#quarter").value, on:new Date().toDateString()}));
  const qn = parseInt($("#quarter").value.replace("Q","")), cur = COURSES[$("#course").value];
  let keep;
  if(cur && !runsIn(cur, qn)){
    const sib = COURSES.findIndex(c => baseName(c.name) === baseName(cur.name) && runsIn(c, qn) && c.quarters);
    if(sib >= 0) keep = String(sib);
  }
  renderCourses(keep);
  applyCourse(true);
};

fetch("/api/courses").then(r=>r.json()).then(d=>{
  if(d.error){ $("#coursenote").textContent = d.error; return; }
  COURSES = d.courses; QUARTERS = d.quarters || []; SCHOOL_YEAR = d.school_year || "";
  $("#coursesrc").textContent = d.note || "";
  $("#coursesrc").style.color = d.source === "live" ? "" : "#b45309";
  $("#quarter").innerHTML = QUARTERS.map(q=>`<option value="${q.label}">${q.label} (${q.start} to ${q.end})</option>`).join("");
  let qv = quarterForToday();
  try { const o = JSON.parse(store.get("quarter_choice")||"null"); if(o && o.on === new Date().toDateString()) qv = o.q; } catch(e){}  // manual pick lasts for the day
  if(qv) $("#quarter").value = qv;
  const sv = String(COURSES.findIndex(c => c.name === store.get("course")));   // saved by name: list order can change
  renderCourses(sv);
  if(sv !== "-1") { $("#course").value = sv; if(Object.keys(STD).length) applyCourse(false); }
});
function applyCourse(save=true){
  const c = COURSES[$("#course").value];
  if(c && c.quarters && c.quarters.length){
    const qn = parseInt($("#quarter").value.replace("Q",""));
    if(!c.quarters.includes(qn)){
      $("#quarter").value = "Q" + c.quarters[0];
      store.set("quarter_choice", JSON.stringify({q:$("#quarter").value, on:new Date().toDateString()}));
      renderCourses($("#course").value);
    }
  }
  loadRoster();
  if(save) store.set("course", c ? c.name : "");
  if(!c){ $("#coursenote").textContent = ""; showStds(); return; }
  // Never carry the previous course's department (and its ticked standards) over: use this course's own
  // document, else what the teacher picked for this course before, else none.
  const hasDoc = !!(c.doc && STD[c.doc]), own = store.get("doc_for:" + c.name);
  $("#doc").value = hasDoc ? c.doc : (STD[own] ? own : ""); store.set("doc", $("#doc").value);
  if(c.grades && c.grades.length === 1) { $("#grade").value = "Grade " + c.grades[0]; store.set("grade", $("#grade").value); }
  $("#coursenote").textContent = (hasDoc ? "Department: " + c.department
      : "No standards document for " + (c.department ? "department '" + c.department + "'" : "this course") +
        ". Paste the instructions above, or choose a department below.") +
    (c.grades && c.grades.length > 1 ? " · taught in grades " + c.grades.join(", ") + " (set grade above or per student)" : "");
  showStds();
}
$("#course").onchange = () => applyCourse(true);
fetch("/api/standards").then(r=>r.json()).then(d=>{
  STD = d;
  $("#doc").innerHTML += Object.keys(d).map(k=>`<option>${k}</option>`).join("");
  const sv = store.get("doc"); if(sv && d[sv]) { $("#doc").value = sv; showStds(); }
  if(COURSES.length && $("#course").value !== "") applyCourse(false);
});
function showStds(){
  const c = COURSES[$("#course").value];
  let list = STD[$("#doc").value] || [];
  if(c && c.match && c.doc === $("#doc").value) list = list.filter(x => x.label.includes(c.match));
  const ticked = JSON.parse(store.get("ticked:" + $("#doc").value) || "[]");   // saved by label, not position in the PDF
  $("#stds").innerHTML = list.map(x=>`<label style="font-weight:400;display:flex;gap:8px;align-items:center">
    <input type="checkbox" class="std" value="${x.id}" style="width:auto" ${ticked.includes(x.label)?"checked":""}> ${x.label}</label>`).join("");
  document.querySelectorAll(".std").forEach(c => c.onchange = () =>
    store.set("ticked:" + $("#doc").value, JSON.stringify([...document.querySelectorAll(".std:checked")].map(x=>list.find(s => s.id === x.value).label))));
}
$("#doc").onchange = () => {
  store.set("doc", $("#doc").value);
  const c = COURSES[$("#course").value]; if(c) store.set("doc_for:" + c.name, $("#doc").value);
  showStds();
};

function addStudent(name="", work=""){
  const d = document.createElement("div"); d.className = "card student";
  d.innerHTML = `<div class="row" style="margin-top:0"><div><label>Student</label>
        <select class="pick" style="margin-bottom:6px"><option value="">Choose from class list…</option></select>
        <input class="name" placeholder="…or type a name">
        <div class="matchnote status"></div>
        <div class="tstatus status"></div></div>
      <div><label>Grade <span style="font-weight:400;color:var(--mute)">(only if different from class)</span></label>
        <select class="sgrade"><option value="">Same as class</option>
        ${GRADES.map(g=>`<option>${g}</option>`).join("")}</select>
        <label style="margin-top:8px">Level <span style="font-weight:400;color:var(--mute)">(optional, you decide)</span></label>
        <select class="level"><option value="">No level (feedback only)</option>
        ${["Emerging","Emerging+","Developing","Developing+","Proficient","Proficient+","Extending","Extending+"].map(l=>`<option>${l}</option>`).join("")}
        </select></div></div>
    <label style="margin-top:12px">Work</label><textarea class="work"></textarea>
    <label style="margin-top:12px">Teacher notes <span style="font-weight:400;color:var(--mute)">(private, optional: e.g. "ELL, working on sentence variety")</span></label>
    <input class="notes">
    <div class="result"></div>`;
  d.querySelector(".name").value = name; d.querySelector(".work").value = work; wirePicker(d); d.querySelector(".name").onchange = () => { delete d.dataset.orig; matchCard(d); applyTeams(); };
  $("#students").appendChild(d); return d;
}
addStudent();
$("#add").onclick = () => addStudent();
$("#addall").onclick = () => {
  const have = new Set([...document.querySelectorAll(".student .name")].map(i=>i.value.trim().toLowerCase()));
  const first = document.querySelector(".student");
  if(first && !first.querySelector(".name").value.trim() && !first.querySelector(".work").value.trim()) first.remove();
  ROSTER.forEach((s,i) => {
    const full = s.first + " " + s.last;
    if(have.has(full.toLowerCase())) return;
    const card = addStudent(full, ""); card.querySelector(".pick").value = String(i); card.querySelector(".pick").onchange();
  });
};
$("#files").onclick = () => $("#filepick").click();
function b64(file){ return new Promise(res => { const r = new FileReader();
  r.onload = () => res(r.result.split(",")[1]); r.readAsDataURL(file); }); }
$("#filepick").onchange = async e => {
  const first = document.querySelector(".student");
  if(first && !first.querySelector(".work").value.trim() && !first.querySelector(".name").value.trim()) first.remove();
  let n = 0, sawTeams = false; const errors = [];
  for (const f of e.target.files) {
    $("#status").textContent = "Reading " + f.name + " …";
    const r = await fetch("/api/parse", {method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({filename:f.name, data:await b64(f), mode:$("#split").value})});
    const d = await r.json();
    if(d.error){ errors.push(d.error); continue; }   // shown after the summary, so later files can't hide it
    if(d.teams){                                   // a Teams status export: names + status, not student work
      TEAMS = d.teams;
      if(TEAMS.assignment) $("#atitle").value = TEAMS.assignment;
      sawTeams = true; continue;
    }
    d.students.forEach(s => { addStudent(s.name, s.work); n++; });
  }
  if(n && ROSTER.length) matchAll(true);
  else if(sawTeams && !n) $("#status").textContent = "Teams status export loaded: " + TEAMS.students.length + " students. Now upload the students' work (or paste it), and each card will show its Teams status.";
  else if(n) $("#status").textContent = n + " student" + (n===1?"":"s") + " loaded. Choose a course to match them to the class list, then check the work and click Generate.";
  else $("#status").textContent = "";
  if(!document.querySelector(".student")) addStudent();   // nothing loaded: put back the blank card removed above
  errors.forEach(msg => { const s = document.createElement("div"); s.className = "err"; s.textContent = msg; $("#status").append(s); });
  applyTeams();
  e.target.value = "";
};
function csvCell(t){ return '"' + String(t).replace(/"/g,'""') + '"'; }
$("#dlteams").onclick = () => {
  const done = [...document.querySelectorAll(".student")].map(c => ({c, o: c.querySelector(".out"), t: teamsFor(c)}))
    .filter(x => x.o && !x.o.classList.contains("err"));
  const order = TEAMS ? TEAMS.students.map(s => s.name) : [];
  const pos = x => x.t ? order.indexOf(x.t.name) : -1;
  done.sort((a, b) => (pos(a) < 0 ? 1e9 : pos(a)) - (pos(b) < 0 ? 1e9 : pos(b)));   // Teams order; unmatched last
  const rows = [["Full Name", "Teams status", "Feedback"]].concat(done.map(x =>
    [x.t ? x.t.name : x.c.querySelector(".name").value, x.t ? x.t.status : "", x.o.innerText]));
  const title = ($("#atitle").value || "assignment").replace(/[^\w\- ]+/g, "").replace(/\s+/g, " ").trim() || "assignment";
  const blob = new Blob(["\ufeff" + rows.map(r => r.map(csvCell).join(",")).join("\n")], {type: "text/csv"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "feedback - " + title + ".csv"; a.click();
};
$("#dl").onclick = () => {
  const rows = [["Student","Feedback"]];
  document.querySelectorAll(".student").forEach(c => {
    const o = c.querySelector(".out"); if(o && !o.classList.contains("err")) rows.push([c.querySelector(".name").value, o.innerText]);
  });
  const blob = new Blob(["\ufeff" + rows.map(r=>r.map(csvCell).join(",")).join("\n")], {type:"text/csv"});
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "feedback.csv"; a.click();
};

$("#go").onclick = async () => {
  const rubric = $("#rubric").value.trim();
  const stds = [...document.querySelectorAll(".std:checked")].map(c=>c.value);
  if(!rubric && !stds.length){ $("#status").textContent = "Add an assignment description or tick a learning standard."; return; }
  let cards = [...document.querySelectorAll(".student")].filter(c => c.querySelector(".work").value.trim());
  applyTeams();
  const skipped = $("#skipret").checked ? cards.filter(c => c.dataset.tstatus === "Returned") : [];
  skipped.forEach(c => { c.querySelector(".result").innerHTML = '<div class="status">Skipped: already returned in Teams.</div>'; });
  cards = cards.filter(c => !skipped.includes(c));
  if(!cards.length){ $("#status").textContent = skipped.length ? "Everyone with work loaded is already Returned in Teams (untick the skip box to redo them)." : "Paste some student work first."; return; }
  $("#go").disabled = true;
  let i = 0, failed = 0;
  for (const c of cards) {
    i++;
    const name = c.querySelector(".name").value.trim() || "Student " + i;
    const res = c.querySelector(".result");
    $("#status").textContent = `Writing ${i} of ${cards.length}: ${name} …`;
    res.innerHTML = "";
    try {
      const r = await fetch("/api/generate", {method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({model:$("#model").value, rubric, doc:$("#doc").value, standards:stds, grade:c.querySelector(".sgrade").value || $("#grade").value, term:$("#quarter").value ? SCHOOL_YEAR + " " + $("#quarter").value : "", length:$("#length").value, title:$("#atitle").value, label:name,
                              work:c.querySelector(".work").value, notes:c.querySelector(".notes").value, level:c.querySelector(".level").value})});
      const d = await r.json();
      if(d.error) throw new Error(d.error);
      const out = document.createElement("div"); out.className = "out"; out.contentEditable = "true"; out.textContent = d.feedback.replace(/\*\*/g, "");  // plain text on the page, so Copy and the .csv files carry no asterisks
      const copy = document.createElement("button"); copy.textContent = "Copy"; copy.style.marginTop = "8px";
      copy.onclick = () => { navigator.clipboard.writeText(out.innerText); copy.textContent = "Copied"; setTimeout(()=>copy.textContent="Copy",1500); };
      res.append(out, copy);
    } catch(err) {
      failed++; res.innerHTML = '<div class="out err"></div>'; res.firstChild.textContent = err.message;
    }
  }
  $("#status").textContent = (failed ? failed + " of " + cards.length + " failed (see the red messages)." : "Done. Feedback is editable: tweak it, then copy.") + (skipped.length ? " Skipped " + skipped.length + " already returned in Teams." : "");
  $("#go").disabled = false; $("#dl").disabled = false; $("#dlteams").disabled = false;
};
</script></main></body></html>"""


ALLOWED_HOSTS = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}


class Handler(BaseHTTPRequestHandler):
    def _host_ok(self):
        """Refuse any other Host: stops a web page using DNS rebinding to read class lists from this server."""
        if (self.headers.get("Host") or "").lower() in ALLOWED_HOSTS:
            return True
        self._send(403, {"error": "forbidden"})
        return False

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self._host_ok():
            return
        if self.path == "/":
            self._send(200, PAGE.encode(), "text/html")
        elif self.path == "/api/courses":
            try:
                cfg = course_data()
            except (OSError, ValueError) as e:
                return self._send(200, {"error": f"courses: {e}"})
            docs = list(load_standards())
            for c in cfg.get("courses", []):  # resolve department -> standards document name
                c["doc"] = next((d for d in docs if c.get("department") and d.lower().startswith(c["department"].lower())), "")
            self._send(200, {"courses": cfg.get("courses", []), "quarters": cfg.get("quarters", []),
                             "school_year": cfg.get("school_year", ""), "source": cfg.get("source", ""),
                             "note": cfg.get("note", "")})
        elif self.path.startswith("/api/roster"):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            try:
                students = roster_for(q.get("name", [""])[0], q.get("quarter", [""])[0])
                self._send(200, {"students": students})
            except RuntimeError as e:
                self._send(200, {"error": str(e)})
        elif self.path == "/api/standards":
            docs = load_standards()
            self._send(200, {d: [{"id": x["id"], "label": x["label"]} for x in v] for d, v in docs.items()})
        elif self.path == "/api/models":
            try:
                models = [m["name"] for m in fb.http_json("/api/tags", timeout=5)["models"]]
                self._send(200, {"models": models, "default": fb.DEFAULT_MODEL if fb.DEFAULT_MODEL in models else models[0]})
            except (urllib.error.URLError, OSError):
                self._send(200, {"error": "Can't reach Ollama. Start it with `ollama serve` or open the Ollama app, then reload."})
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self._host_ok():
            return
        if self.path == "/api/parse":
            p = {}
            try:
                n = int(self.headers.get("Content-Length", 0))
                p = json.loads(self.rfile.read(n))
                rows = parse_upload(p["filename"], base64.b64decode(p["data"]), p.get("mode", "auto"))
                if isinstance(rows, dict):                      # Teams status export
                    return self._send(200, rows)
                if not rows:                                    # say why, rather than silently loading nothing
                    why = ("no text found. It may be a scanned image: export it as a text PDF or .docx, or paste the work in"
                           if p["filename"].lower().endswith(".pdf") else "no student work found in this file")
                    return self._send(200, {"error": f"{p['filename']}: {why}."})
                return self._send(200, {"students": [{"name": a, "work": b} for a, b in rows]})
            except Exception as e:
                return self._send(200, {"error": f"{p.get('filename', 'file')}: {type(e).__name__}: {e}"})
        if self.path != "/api/generate":
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            p = json.loads(self.rfile.read(n))
            rubric = p.get("rubric", "").strip()
            picked = [x["text"] for x in load_standards().get(p.get("doc"), []) if x["id"] in p.get("standards", [])]
            if picked:
                rubric = (rubric + "\n\n" if rubric else "") + "Learning standards (RCS 2026-27):\n\n" + "\n\n".join(picked)
            if not rubric:
                raise ValueError("Add an assignment description or choose learning standards.")
            text = fb.generate(p["model"], rubric, p.get("grade", ""), p.get("label", "student"), p["work"], p.get("notes", ""), p.get("level", ""), p.get("term", ""), p.get("length", fb.DEFAULT_LENGTH), p.get("title", ""))
            self._send(200, {"feedback": text})
        except (urllib.error.URLError, ConnectionError):
            self._send(200, {"error": "Can't reach Ollama. Start it with `ollama serve` (or open the Ollama app), then click Generate again."})
        except Exception as e:  # surface any failure to the page
            self._send(200, {"error": f"{type(e).__name__}: {e}"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    url = f"http://{HOST}:{PORT}"
    try:
        srv = ThreadingHTTPServer((HOST, PORT), Handler)
    except OSError:
        print(f"Student Feedback is already running at {url} - opening it in your browser.")
        webbrowser.open(url)
        raise SystemExit(0)
    print(f"Student Feedback running at {url}  (Ctrl+C to stop)")
    if not os.environ.get("NO_BROWSER"):
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
