#!/usr/bin/env python3
"""Measure how well the local model drafts feedback, using invented cases only (tools/quality_cases.py).

    python3 tools/draft_quality.py --model qwen2.5:14b --runs 3

It runs the app's own drafting (feedback.generate, with its retries) on each invented case, several times, and reports:
  accepted      how often a draft passed the app's own rules;
  first try     how often the very first reply already passed (fewer retries means a steadier model);
  rejected      why the rest were refused;
  audit         problems the app does NOT block, checked on accepted drafts: quotes the student never wrote, numbers that
                appear nowhere in the work, criteria not covered, a hidden instruction followed, a private note leaked,
                generic praise, wrong length.
Nothing real is read or sent: the cases are invented, the model is local (Ollama or LM Studio), and nothing is posted
anywhere. The report is a measurement to help choose a model or tune the prompt; it is not a grade of any student.
"""
import argparse, json, os, re, sys, time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import feedback as fb
from quality_cases import CASES

GENERIC_PRAISE = re.compile(r"\b(great job|well done|good job|nice work|excellent work|fantastic)\b", re.I)


def _flat(s):
    return " ".join(re.findall(r"[a-z0-9']+", (s or "").lower().replace("’", "'")))


def audit(text, case, length="detailed"):
    """Problems in an ACCEPTED draft that the app does not block. Returns a list of short labels."""
    out = []
    work, task = case["work"], case.get("task", "")
    rubric_txt = json.dumps(case.get("rubric") or {})
    if fb.unsourced_quotes(text, work, task, case.get("title", ""), rubric_txt):
        out.append("quote_not_in_work")
    src = _flat(work + " " + task + " " + rubric_txt)
    own = re.sub(r"[\"“][^\"”]*[\"”]", " ", text)
    if [n for n in re.findall(r"\d+(?:\.\d+)?", own) if not re.search(r"\b" + re.escape(n) + r"\b", src)]:
        out.append("number_not_in_work")
    criteria = [c["name"] for c in (case.get("rubric") or {}).get("criteria", [])]
    keys = [fb.rubric_criteria(task)] if task else []
    if fb.uncovered(text, keys[0] if keys else []):
        out.append("checklist_item_missing")
    low = text.lower()
    if any(m.lower() in low for m in case.get("marks", [])):
        out.append("followed_hidden_instruction_or_leaked_note")
    if re.search(r"\b(extending|proficient|developing|emerging)\b\s+(work|level)", own, re.I) and not case.get("level"):
        out.append("level_named")
    if GENERIC_PRAISE.search(own):
        out.append("generic_praise")
    paras = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    sentences = len(re.findall(r"[.!?](?:\s|$)", text))
    if length == "sentence" and sentences > 2:
        out.append("too_long_for_sentence")
    if length == "paragraph" and (len(paras) > 1 or len(text.split()) > 160):
        out.append("too_long_for_paragraph")
    if "[name]" in low:
        out.append("name_placeholder_left")
    return out


def run_case(model, case, length, chat_counter):
    """One draft. Returns {'accepted', 'attempts', 'text', 'why', 'issues', 'seconds'}."""
    chat_counter[0] = 0
    t0 = time.time()
    try:
        text = fb.generate(model, case["task"], case["grade"], "Student", case["work"], case.get("notes", ""), case.get("level", ""),
                           "", length, case.get("title", ""), assessment=case.get("rubric"))
        res = {"accepted": True, "text": text, "why": [], "issues": audit(text, case, length)}
    except fb.DraftRejected as e:
        res = {"accepted": False, "text": "", "why": [str(e).split(": ", 1)[-1].rstrip(". ")], "issues": []}
    res["attempts"] = chat_counter[0]
    res["seconds"] = round(time.time() - t0, 1)
    return res


def measure(model, runs=3, length="detailed", only=None, progress=None):
    """Runs every case `runs` times. fb.chat is wrapped to count attempts; nothing else is changed."""
    counter, real = [0], fb.chat
    def counting(*a, **k):
        counter[0] += 1
        return real(*a, **k)
    fb.chat = counting
    try:
        results = []
        for case in CASES:
            if only and case["id"] not in only:
                continue
            rows = []
            for i in range(runs):
                if progress:
                    progress(case["id"], i + 1, runs)
                rows.append(run_case(model, case, length, counter))
            results.append({"case": case["id"], "runs": rows})
    finally:
        fb.chat = real
    return results


def summarise(results):
    n = sum(len(r["runs"]) for r in results)
    acc = [x for r in results for x in r["runs"] if x["accepted"]]
    first = [x for x in acc if x["attempts"] == 1]
    why, issues = {}, {}
    for r in results:
        for x in r["runs"]:
            for w in x["why"]:
                key = re.sub(r"\(.*?\)|\".*?\"", "", w).strip()[:80]
                why[key] = why.get(key, 0) + 1
            for i in x["issues"]:
                issues[i] = issues.get(i, 0) + 1
    return {"drafts": n, "accepted": len(acc), "first_try": len(first),
            "mean_attempts": round(sum(x["attempts"] for r in results for x in r["runs"]) / n, 2) if n else 0,
            "rejected_reasons": why, "audit_issues": issues, "clean": len([x for x in acc if not x["issues"]])}


def report(model, length, runs, results):
    s = summarise(results)
    pct = lambda a: f"{100 * a // s['drafts']}%" if s["drafts"] else "-"
    L = [f"# Draft quality: {model}", "", f"Measured {datetime.now():%Y-%m-%d %H:%M}. Length: {length}. {runs} run(s) per case. Invented cases only; a measurement, not a grade.", "",
         f"- Accepted by the app's own rules: {s['accepted']}/{s['drafts']} ({pct(s['accepted'])})",
         f"- Accepted on the first try: {s['first_try']}/{s['drafts']} ({pct(s['first_try'])}); mean replies per draft {s['mean_attempts']}",
         f"- Accepted with no audit problems: {s['clean']}/{s['drafts']} ({pct(s['clean'])})", ""]
    if s["rejected_reasons"]:
        L += ["## Why drafts were refused", ""] + [f"- {k}: {v}" for k, v in sorted(s["rejected_reasons"].items(), key=lambda kv: -kv[1])] + [""]
    if s["audit_issues"]:
        L += ["## Problems the app does not block (accepted drafts)", ""] + [f"- {k}: {v}" for k, v in sorted(s["audit_issues"].items(), key=lambda kv: -kv[1])] + [""]
    L += ["## By case", "", "| case | accepted | first try | audit problems |", "|---|---|---|---|"]
    for r in results:
        a = [x for x in r["runs"] if x["accepted"]]
        L.append(f"| {r['case']} | {len(a)}/{len(r['runs'])} | {len([x for x in a if x['attempts'] == 1])}/{len(r['runs'])} | "
                 f"{', '.join(sorted({i for x in a for i in x['issues']})) or '-'} |")
    L += ["", "## Drafts (invented work)", ""]
    for r in results:
        for k, x in enumerate(r["runs"], 1):
            L += [f"### {r['case']} run {k}: " + ("accepted" if x["accepted"] else "refused") + f" after {x['attempts']} repl{'y' if x['attempts'] == 1 else 'ies'}, {x['seconds']}s",
                  "", x["text"] or "(" + "; ".join(x["why"]) + ")", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model"); ap.add_argument("--backend", choices=list(fb.BACKENDS))
    ap.add_argument("--runs", type=int, default=3); ap.add_argument("--length", choices=list(fb.LENGTHS), default=fb.DEFAULT_LENGTH)
    ap.add_argument("--cases", nargs="*"); ap.add_argument("--out", type=Path, default=Path("quality-reports"))
    a = ap.parse_args()
    if not 1 <= a.runs <= 10:
        sys.exit("--runs must be between 1 and 10.")
    model = fb.pick_model(a.model, a.backend)
    print(f"Measuring {fb.describe(model)}: invented cases only, nothing leaves this computer.")
    res = measure(model, a.runs, a.length, a.cases, lambda c, i, n: print(f"  {c} {i}/{n}", flush=True))
    a.out.mkdir(parents=True, exist_ok=True)
    dest = a.out / f"{datetime.now():%Y%m%d-%H%M%S}-{re.sub(r'[^A-Za-z0-9._-]+', '_', model)}.md"
    dest.write_text(report(model, a.length, a.runs, res), encoding="utf-8")
    s = summarise(res)
    print(f"\nAccepted {s['accepted']}/{s['drafts']}, first try {s['first_try']}, clean {s['clean']}. Report: {dest}")


if __name__ == "__main__":
    main()
