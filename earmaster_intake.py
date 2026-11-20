"""Private intake and de-identification for the EarMaster reflection mode (handoff step 2b).

Run it yourself, in Terminal. Nothing here is sent anywhere; the only model is the local Ollama.

    python3 earmaster_intake.py make-key  VAULT --names roster.txt   start a key file (random codes) from a list of names
    python3 earmaster_intake.py intake    VAULT                      consent check, matching, case files, "check these" list
    python3 earmaster_intake.py run       VAULT [--model M]          Student Feedback on the cases; drafts stay in the vault
    python3 earmaster_intake.py scrub     VAULT                      de-identify cases, drafts, review log; side-by-side page
    python3 earmaster_intake.py publish   VAULT --approve S01 ...    copy approved, scrubbed copies to data/ (git-ignored)
    python3 earmaster_intake.py delete    [--vault VAULT]            clear data/ ; with --vault also clear the vault (key first)

VAULT is the folder of an encrypted disk image you create (for example /Volumes/StudentVault). It holds:
    key.csv           name, earmaster_name, onenote_name, nicknames, grade, consent, code   (+ optional others.csv: name, role)
    earmaster.csv     the teacher-version export, last 30 days (column names: earmaster_columns.json)
    reflections/      one .txt per student, named like the OneNote name
The script refuses to run if VAULT is inside this repo, OneDrive or an iCloud-synced Desktop/Documents folder.
Counts and codes are printed; names are never printed. Files that contain names are written only inside the vault.
"""
import argparse
import csv
import html
import json
import re
import secrets
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from earmaster_cases import validate

REPO = Path(__file__).resolve().parent
HOME = Path.home()
DATA = REPO / "data"
COLUMNS_FILE = REPO / "earmaster_columns.json"
KEY_COLS = ["name", "earmaster_name", "onenote_name", "nicknames", "grade", "consent", "code"]
DATE_FORMATS = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                "%m/%d/%Y", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%b %d, %Y %I:%M %p", "%b %d, %Y"]
INSTRUMENTS = r"flutes?|piccolo|clarinets?|oboe|bassoons?|saxophones?|saxes|sax|trumpets?|cornets?|horns?|trombones?|euphoniums?|baritones?|tubas?|percussion|drums?|snare|timpani|marimba|xylophone|vibraphone|piano|violin|viola|cello|bass|guitar|ukulele|mellophone"
MONTHS = r"jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?"
FLAG_PATTERNS = [
    ("date", re.compile(rf"\b(?:{MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?\b|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{MONTHS})\b|\b\d{{1,4}}[/-]\d{{1,2}}[/-]\d{{1,4}}\b|\b(?:mon|tues?|wed(?:nes)?|thu(?:rs)?|fri|sat(?:ur)?|sun)(?:day)?\b", re.I)),
    ("instrument", re.compile(rf"\b(?:{INSTRUMENTS})\b", re.I)),
    ("contact", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|\b\d{3}[-. ]\d{3}[-. ]\d{4}\b")),
]
# Capitalised words in the middle of a sentence are flagged as possible names or places, except these:
CAPS_OK = {"I", "EarMaster", "First", "Mate", "OneNote", "Teams", "Grade", "Band", "Where", "How", "Where to next", "Draft", "DRAFT", "My", "The"}
OPEN, CLOSE = "\x01", "\x02"        # markers around replaced names while a scrubbed copy is being built


# ---------- vault safety ----------
def vault_problem(vault, repo=REPO, home=HOME):
    """Return why this vault location is not allowed, or None if it is fine."""
    v, r, h = Path(vault).expanduser().resolve(), Path(repo).resolve(), Path(home).resolve()
    if v == r or r in v.parents or v in r.parents:
        return "the vault is inside (or contains) the git repo folder"
    if any(p.lower().startswith("onedrive") for p in v.parts) or (h / "Library" / "CloudStorage") in [v, *v.parents]:
        return "the vault is inside OneDrive or another cloud-synced folder"
    if (h / "Library" / "Mobile Documents") in [v, *v.parents]:
        return "the vault is inside iCloud Drive"
    icloud = h / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    for name in ("Desktop", "Documents"):
        if (h / name) in [v, *v.parents] and (icloud / name).exists():
            return f"the vault is inside ~/{name}, and iCloud is syncing {name}"
    return None


def need_vault(vault):
    v = Path(vault).expanduser()
    problem = vault_problem(v)
    if problem:
        sys.exit(f"Refusing to run: {problem}. Put the vault on an encrypted disk image, for example /Volumes/StudentVault.")
    if not v.is_dir():
        sys.exit(f"Vault folder not found: {v}")
    if not str(v.resolve()).startswith("/Volumes/"):
        print("Note: this vault is not on a mounted volume (/Volumes/...). Is it on your encrypted disk image?")
    return v.resolve()


# ---------- names ----------
def norm(name):
    """'Lee, Jordan' and 'Jordan Lee' become the same text. No fuzzy matching: anything else is a different name."""
    n = " ".join((name or "").replace(" ", " ").split())
    if n.count(",") == 1:
        last, first = [p.strip() for p in n.split(",")]
        n = f"{first} {last}"
    return n.casefold()


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def load_key(vault):
    path = vault / "key.csv"
    if not path.exists():
        sys.exit("No key.csv in the vault. Make one with: python3 earmaster_intake.py make-key VAULT --names roster.txt")
    rows = read_csv(path)
    missing = [c for c in KEY_COLS if rows and c not in rows[0]]
    if missing:
        sys.exit(f"key.csv is missing columns: {', '.join(missing)}")
    return rows


def consents(row):
    return (row.get("consent") or "").strip().casefold() == "yes"


def cmd_make_key(a):
    v = need_vault(a.vault)
    out = v / "key.csv"
    if out.exists():
        sys.exit("key.csv already exists; not overwriting it.")
    names = [n.strip() for n in Path(a.names).read_text(encoding="utf-8").splitlines() if n.strip()]
    pool = list(range(1, max(99, len(names) * 2) + 1))
    codes = []
    for _ in names:
        codes.append(f"S{pool.pop(secrets.randbelow(len(pool))):02d}")      # random, never derived from the name
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(KEY_COLS)
        for n, c in zip(names, codes):
            w.writerow([n, n, n, "", "", "", c])
    print(f"Wrote key.csv with {len(names)} students. Fill in nicknames, grade and consent (yes/no) for each, and fix any name that is spelled differently in EarMaster or OneNote.")
    return 0


# ---------- intake ----------
def load_columns(path=COLUMNS_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def parse_when(text):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), fmt)
        except ValueError:
            pass
    return None


def summarise(rows, cols):
    """Counts only. Returns (case fields, problem or None). No timestamps or durations leave this function."""
    att = []
    for r in rows:
        when = parse_when(r[cols["datetime"]])
        try:
            score = float(str(r[cols["score"]]).strip().rstrip("%"))
        except ValueError:
            return None, "a score could not be read"
        if when is None:
            return None, "a date could not be read"
        att.append((when, r[cols["exercise"]].strip(), r[cols["kind"]].strip().casefold() in [x.casefold() for x in cols["assigned_values"]],
                    r[cols["passed"]].strip().casefold() in [x.casefold() for x in cols["passed_values"]], score))
    att.sort(key=lambda x: x[0])
    if not att:
        return None, "no EarMaster rows"
    passed_at, after = {}, 0
    for i, (when, ex, assigned, passed, score) in enumerate(att):
        if ex in passed_at:
            after += 1
        elif passed:
            passed_at[ex] = i
    assigned_passed = sorted({ex for (_, ex, assigned, _, _) in att if assigned and ex in passed_at})
    self_chosen = sorted({ex for (_, ex, assigned, _, _) in att if not assigned})
    return {"lessons_completed": assigned_passed, "self_chosen_exercises": self_chosen, "attempts_30d": len(att),
            "active_days_30d": len({a[0].date() for a in att}), "attempts_after_pass": after,
            "accuracy_first_pct": att[0][4], "accuracy_latest_pct": att[-1][4]}, None


def cmd_intake(a):
    v = need_vault(a.vault)
    cols = load_columns(a.columns)
    key = load_key(v)
    # 1. consent first: students without consent are dropped before their data is read at all
    consenting = [r for r in key if consents(r)]
    dropped = len(key) - len(consenting)
    check = []
    # EarMaster rows, grouped by normalised name. Rows for non-consenting students are never summarised.
    csv_path = Path(a.csv) if a.csv else v / "earmaster.csv"
    if not csv_path.exists():
        sys.exit(f"No EarMaster export at {csv_path}")
    rows = read_csv(csv_path)
    if rows:
        absent = [cols[k] for k in ("student", "datetime", "exercise", "kind", "score", "passed") if cols[k] not in rows[0]]
        if absent:
            sys.exit("The export's header row is: " + ", ".join(rows[0].keys()) + "\nThese names in earmaster_columns.json are not in it: " + ", ".join(absent))
    by_student = {}
    for r in rows:
        by_student.setdefault(norm(r[cols["student"]]), []).append(r)
    in_key = {norm(r["earmaster_name"]) for r in key} | {norm(r["name"]) for r in key}
    for n in sorted(set(by_student) - in_key):
        check.append(f"EarMaster name not in key.csv ({len(by_student[n])} rows): {n}")
    # one-to-one name counts across the WHOLE key, so a shared name can never be silently given to the wrong person
    em_count, on_count = {}, {}
    for r in key:
        em_count[norm(r["earmaster_name"])] = em_count.get(norm(r["earmaster_name"]), 0) + 1
        on_count[norm(r["onenote_name"])] = on_count.get(norm(r["onenote_name"]), 0) + 1
    files = {}
    for p in sorted((v / "reflections").glob("*.txt")) if (v / "reflections").is_dir() else []:
        files.setdefault(norm(p.stem), []).append(p)
    used_codes, made = set(), []
    (v / "cases").mkdir(exist_ok=True)
    for r in consenting:
        code = r["code"].strip()
        who = f"code {code}"
        if not re.fullmatch(r"S\d{2,}", code) or code in used_codes:
            check.append(f"{who}: code is missing, malformed or used twice")
            continue
        used_codes.add(code)
        em, on = norm(r["earmaster_name"]), norm(r["onenote_name"])
        if em_count[em] > 1 or on_count[on] > 1:
            check.append(f"{who}: the same name appears for more than one student in key.csv, so I can't tell whose it is")
            continue
        if em not in by_student:
            check.append(f"{who}: no EarMaster rows under the EarMaster name in key.csv")
            continue
        if len(files.get(on, [])) != 1:
            check.append(f"{who}: {'no' if not files.get(on) else 'more than one'} reflection file under the OneNote name")
            continue
        try:
            grade = int(r["grade"])
        except ValueError:
            check.append(f"{who}: grade missing or not a number")
            continue
        fields, problem = summarise(by_student[em], cols)
        if problem:
            check.append(f"{who}: {problem}")
            continue
        case = {"case_id": code, "grade": grade, **fields, "journal_entry": files[on][0].read_text(encoding="utf-8").strip(), "first_mate_note": ""}
        bad = validate(case)
        if bad:
            check.append(f"{who}: {'; '.join(bad)}")
            continue
        (v / "cases" / f"{code}.json").write_text(json.dumps(case, indent=2) + "\n", encoding="utf-8")
        made.append(code)
    (v / "check-these.txt").write_text("\n".join(check) + ("\n" if check else ""), encoding="utf-8")
    print(f"Consent: {len(consenting)} students included, {dropped} left out (their data was not read).")
    print(f"Cases written to the vault: {len(made)}  ({', '.join(made) or 'none'})")
    print(f"Needs a look: {len(check)}" + ("  (see check-these.txt in the vault; nothing was guessed)" if check else ""))
    return 0


def cmd_run(a):
    v = need_vault(a.vault)
    if not (v / "cases").is_dir():
        sys.exit("No cases folder in the vault. Run intake first.")
    argv = [sys.executable, str(REPO / "earmaster_feedback.py"), str(v / "cases"), "--out", str(v / "outputs")] + (["--model", a.model] if a.model else [])
    return subprocess.run(argv, cwd=REPO).returncode


# ---------- scrubbing ----------
def people(key, others):
    """[(variant text, replacement kind, owner code)] for everyone on the roster, longest variants first."""
    out = []
    for r in key:
        names = [r["name"], r["earmaster_name"], r["onenote_name"]]
        singles = [x.strip() for x in (r.get("nicknames") or "").split(";") if x.strip()]
        for n in names:
            n = " ".join(n.split())
            if not n:
                continue
            if n.count(",") == 1:
                last, first = [p.strip() for p in n.split(",")]
            else:
                parts = n.split()
                first, last = " ".join(parts[:-1]), parts[-1]
                if len(parts) == 1:
                    singles.append(n)
                    continue
            out += [(f"{first} {last}", r["code"]), (f"{last}, {first}", r["code"]), (f"{last} {first}", r["code"])]
            singles += [t for t in first.split() + [last] if len(t) > 1]
        out += [(s, r["code"], True) for s in singles]
    for o in others:
        n = " ".join(o["name"].split())
        role = "[teacher]" if o.get("role", "").strip().casefold() == "teacher" else "[student]"
        parts = n.split()
        out += [(n, role)] + ([(t, role, True) for t in parts if len(t) > 1] if len(parts) > 1 else [(n, role, True)])
    seen, norm_out = set(), []
    for item in out:
        text, repl, single = item[0], item[1], len(item) == 3
        if (text, single) not in seen:
            seen.add((text, single))
            norm_out.append((text, repl, single))
    return sorted(norm_out, key=lambda x: -len(x[0]))


def scrub_text(text, own_code, roster, ok=()):
    """Return (marked text, flags). Own name -> own code; everyone else on the roster -> [student] or [teacher]."""
    s = text
    for variant, repl, single in roster:
        # the student's own code is used for their own name; every other roster name becomes [student] (or [teacher])
        if repl.startswith("S") and repl[1:].isdigit():
            repl = repl if repl == own_code else "[student]"
        flags = 0 if single else re.I                  # single words (first names, nicknames) are matched exactly as written
        s = re.sub(rf"(?<![\w{OPEN}{CLOSE}])" + re.escape(variant) + rf"(?![\w{OPEN}{CLOSE}])", lambda m: OPEN + repl + CLOSE, s, flags=flags)
    return s, find_flags(s, ok)


def find_flags(marked, ok=()):
    plain = re.sub(f"[{OPEN}{CLOSE}]", "", re.sub(f"{OPEN}.*?{CLOSE}", "[x]", marked))
    found = []
    for kind, pat in FLAG_PATTERNS:
        found += [(kind, m.group(0)) for m in pat.finditer(plain)]
    for m in re.finditer(r"\b[A-Z][a-z]{1,}\b", plain):
        before = plain[:m.start()].rstrip()
        if before and before[-1] not in ".!?:*\n\"“" and m.group(0) not in CAPS_OK and m.group(0) not in ok:
            found.append(("capitalised word (name or place?)", m.group(0)))
    return found


def strip_marks(s):
    return re.sub(f"[{OPEN}{CLOSE}]", "", s)


def scrub_json(obj, own, roster, flags, ok=()):
    if isinstance(obj, str):
        t, f = scrub_text(obj, own, roster, ok)
        flags += f
        return t
    if isinstance(obj, list):
        return [scrub_json(x, own, roster, flags, ok) for x in obj]
    if isinstance(obj, dict):
        return {k: scrub_json(x, own, roster, flags, ok) for k, x in obj.items()}
    return obj


def unmark(obj):
    if isinstance(obj, str):
        return strip_marks(obj)
    if isinstance(obj, list):
        return [unmark(x) for x in obj]
    if isinstance(obj, dict):
        return {k: unmark(x) for k, x in obj.items()}
    return obj


def cmd_scrub(a):
    v = need_vault(a.vault)
    key = load_key(v)
    others = read_csv(v / "others.csv") if (v / "others.csv").exists() else []
    roster = people(key, others)                 # the FULL roster, consenting or not, plus First Mates and staff
    out = v / "scrubbed"
    shutil.rmtree(out, ignore_errors=True)
    (out / "cases").mkdir(parents=True)
    (out / "outputs").mkdir()
    sections, flagged, okw = [], {}, {}

    def add(code, label, original, marked, flags):
        sections.append((code, label, original, marked, flags))
        if flags:
            flagged.setdefault(code, []).extend(flags)

    for p in sorted((v / "cases").glob("S*.json")):
        case = json.loads(p.read_text(encoding="utf-8"))
        code, flags = case["case_id"], []
        okw[code] = set(re.findall(r"[A-Za-z]+", " ".join(case["lessons_completed"] + case["self_chosen_exercises"])))   # lesson names are not identifying
        marked = scrub_json(case, code, roster, flags, okw[code])
        (out / "cases" / p.name).write_text(json.dumps(unmark(marked), indent=2) + "\n", encoding="utf-8")
        add(code, f"case {p.name}", json.dumps(case, indent=2), json.dumps(marked, indent=2), flags)
    for p in sorted((v / "outputs").glob("S*.md")) if (v / "outputs").is_dir() else []:
        code = p.name.split("__")[0]
        text = p.read_text(encoding="utf-8")
        marked, flags = scrub_text(text, code, roster, okw.get(code, ()))
        (out / "outputs" / p.name).write_text(strip_marks(marked), encoding="utf-8")
        add(code, f"draft {p.name}", text, marked, flags)
    for p in sorted(v.glob("review_log*.csv")):
        rows = list(csv.reader(open(p, newline="", encoding="utf-8-sig")))
        scrubbed_rows, per_code = [], {}
        for i, row in enumerate(rows):
            code = row[0].strip() if i else ""
            new, fl = [], []
            for cell in row:
                t, f = scrub_text(cell, code, roster, okw.get(code, ())) if i else (cell, [])
                new.append(t)
                fl += f
            scrubbed_rows.append(new)
            if i and code:
                add(code, f"review log row ({p.name})", " | ".join(row), " | ".join(new), fl)
        with open(out / p.name, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([[strip_marks(c) for c in r] for r in scrubbed_rows])
    (out / "flags.json").write_text(json.dumps({c: sorted({f"{k}: {t}" for k, t in fl}) for c, fl in flagged.items()}, indent=2) + "\n", encoding="utf-8")
    (v / "review-sidebyside.html").write_text(render(sections), encoding="utf-8")
    codes = sorted({s[0] for s in sections})
    print(f"Scrubbed {len(sections)} items for {len(codes)} cases into the vault's scrubbed/ folder.")
    print(f"Cases with flags to check by hand: {', '.join(sorted(flagged)) or 'none'}")
    print("Open review-sidebyside.html in the vault. Yellow = replaced; orange = flagged. Edit scrubbed/ files if needed, then run publish.")
    return 0


def render(sections):
    def mark(s, flags):
        e = html.escape(s).replace(OPEN, "<mark>").replace(CLOSE, "</mark>")
        for _, t in sorted(set(flags), key=lambda x: -len(x[1])):
            e = re.sub(rf"(?<![\w>])({re.escape(html.escape(t))})(?![\w<])", r'<mark class="flag">\1</mark>', e)
        return e
    parts = ["<!doctype html><meta charset=utf-8><title>Scrub review</title><style>body{font:14px system-ui;margin:2rem}table{width:100%;border-collapse:collapse;margin:.5rem 0 1.5rem}"
             "td{vertical-align:top;width:50%;padding:.5rem;border:1px solid #ccc;white-space:pre-wrap}mark{background:#ff6;}mark.flag{background:#f93}</style><h1>Original | scrubbed</h1>"]
    for code, label, orig, marked, flags in sections:
        parts.append(f"<h3>{html.escape(code)} &mdash; {html.escape(label)}</h3><table><tr><td>{html.escape(orig)}</td><td>{mark(marked, flags)}</td></tr></table>")
    return "".join(parts)


# ---------- publish and delete ----------
def cmd_publish(a):
    v = need_vault(a.vault)
    src = v / "scrubbed"
    if not src.is_dir():
        sys.exit("Nothing scrubbed yet. Run scrub first.")
    flags = json.loads((src / "flags.json").read_text(encoding="utf-8"))
    approved = set(a.approve) | set(a.approve_flagged)
    unknown = [c for c in approved if not (src / "cases" / f"{c}.json").exists()]
    if unknown:
        sys.exit(f"No scrubbed case for: {', '.join(unknown)}")
    blocked = [c for c in a.approve if flags.get(c)]
    if blocked:
        sys.exit(f"{', '.join(blocked)} still have flags (possible identifying details). Check them in the side-by-side page, fix the scrubbed copy, "
                 f"then approve with --approve-flagged {' '.join(blocked)}")
    for sub in ("cases", "outputs"):
        (DATA / sub).mkdir(parents=True, exist_ok=True)
    for c in sorted(approved):
        shutil.copy(src / "cases" / f"{c}.json", DATA / "cases" / f"{c}.json")
        for p in (src / "outputs").glob(f"{c}__*.md"):
            shutil.copy(p, DATA / "outputs" / p.name)
    for p in src.glob("review_log*.csv"):
        rows = list(csv.reader(open(p, newline="", encoding="utf-8")))
        with open(DATA / p.name, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(rows[:1] + [r for r in rows[1:] if r and r[0].strip() in approved])
    print(f"Published {len(approved)} approved, de-identified cases to {DATA} (git-ignored).")
    return 0


def cmd_delete(a):
    if DATA.exists():
        shutil.rmtree(DATA)
        print("Cleared data/.")
    if not a.vault:
        return 0
    v = need_vault(a.vault)
    if input(f"This permanently empties the vault '{v.name}' (the key is deleted first). Type the vault's folder name to confirm: ").strip() != v.name:
        print("Not confirmed; the vault was not touched.")
        return 1
    for p in [v / "key.csv"] + [q for q in v.iterdir() if q.name != "key.csv"]:
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    print("Vault emptied. To be sure nothing lingers, also delete the encrypted disk image file itself.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("make-key", "intake", "run", "scrub", "publish"):
        s = sub.add_parser(name)
        s.add_argument("vault")
        if name == "make-key":
            s.add_argument("--names", required=True, help="text file with one student name per line")
        if name == "intake":
            s.add_argument("--csv", help="EarMaster export (default: earmaster.csv in the vault)")
            s.add_argument("--columns", default=COLUMNS_FILE, help="column names file (default: earmaster_columns.json)")
        if name == "run":
            s.add_argument("--model")
        if name == "publish":
            s.add_argument("--approve", nargs="*", default=[], help="codes with no flags")
            s.add_argument("--approve-flagged", nargs="*", default=[], help="codes whose flags you checked by hand")
    d = sub.add_parser("delete")
    d.add_argument("--vault")
    a = ap.parse_args(argv)
    return globals()["cmd_" + a.cmd.replace("-", "_")](a)


if __name__ == "__main__":
    sys.exit(main())
