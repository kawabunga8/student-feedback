#!/usr/bin/env python3
"""Generate draft feedback for student work using a local Ollama model.

Everything runs on this laptop: student text is only ever sent to
http://localhost:11434 (Ollama). No internet or cloud AI is involved.

Usage:
    python3 feedback.py submissions/ --rubric rubric.txt
    python3 feedback.py submissions/ --rubric rubric.txt --model llama3.1:8b --out feedback/

Each submission is a .txt or .md file; the filename (without extension) is
used as the student's label. Output: one <label>.feedback.md per student.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

OLLAMA = "http://localhost:11434"
DEFAULT_MODEL = "qwen2.5:14b"  # falls back to the first installed model if missing

SYSTEM_TEMPLATE = """You are a supportive teaching assistant drafting feedback for a teacher to review.
Write directly to the student ("you"), in a warm, specific, honest tone.

{LANGUAGE}
(The language guidance above is only about HOW you write. Never mention it, and never give the student advice about
register, sentence length or vocabulary unless the assignment or rubric is itself about writing style.)

{FORMAT}

Rules:
- Only refer to things that are in the student's work. Never invent details, quotes, effort, or activities.
  If you quote, quote exactly.
- Do not praise generically ("great job", "well done") without saying what, exactly, was good.
- Give advice specific to THIS piece of work. Avoid stock advice that would fit any student's work.
- Judge the work against the rubric/standards provided. If a proficiency scale is given, use only the row for the
  student's grade to understand what stronger work looks like, and describe in plain words what the work shows and
  what would make it stronger.
- Only the teacher assigns levels. Never name or suggest a proficiency level (Emerging, Developing, Proficient,
  Extending, or a "+" level), and never say which level the work is at or is closest to.
- If the teacher has set a level for this work, treat it as settled: write feedback consistent with it, explain what in
  the work shows that level, and what would move it to the next one. Never contradict or second-guess it. A "+" level
  (e.g. Proficient+) means consistent, high-end learning at that level; the base level means solid learning with some
  inconsistencies. A sentence naming the level is added for you, so do not name it yourself.
- Command terms: if the assignment or rubric uses a command term (describe, explain, justify, analyse, compare and
  contrast, discuss, evaluate, list, identify), check whether the student's response does that kind of thinking.
  Describe = what happens; Explain = why it happens (reasons or causes); Justify = valid reasons or evidence for a
  conclusion; Analyse = break down into essential elements; Compare and contrast = similarities and differences,
  referring to both; Discuss = balanced range of arguments with an evidence-supported conclusion; Evaluate = weigh
  strengths and limitations. If the response only does a lower-level job (e.g. describes when asked to explain), say
  so kindly and show what adding the missing thinking would look like. Do not invent a command term the task lacks.
- Never write the student's work for them: no ready-made sentences, rewritten versions or example wording they could
  copy. Say what to add or change and why, and leave the writing to them. Use quotation marks only to quote the
  student's work or the task exactly.
- If the teacher lists criteria to cover, mention every one: as a strength if the work meets it, or as a next step if
  it doesn't.
- Do not use the student's name. Address them as "you". If a name is essential, write [NAME].
- No percentages, letter grades or scores.
- If the work is very short, off-task, or missing something the assignment required, say so kindly and plainly.
- Teacher notes, if given, are private context to shape focus and tone. Never quote them or mention that they exist."""


LENGTHS = {
    "sentence": """Format: exactly ONE sentence. It must name one specific thing the student did well AND one specific
next step, joined naturally (e.g. "You ..., and next ..."). No headings, bullets, labels or line breaks.""",
    "paragraph": """Format: ONE short paragraph of 3 to 5 sentences in plain prose: what worked (tied to something they
wrote), then the most important next step, then one small thing to try. No headings, bullets, labels or line breaks.""",
    "detailed": """Format (use these three bold headings, in this order, and start with the first heading):
**Strengths** - 2 or 3 things done well, each tied to something the student actually wrote.
**Next steps** - 2 or 3 concrete, actionable suggestions, most important first. Only if the request lists a command
term for this task and the work does a lower-level job, say so, naming that term.
**One thing to try** - a single small task the student can do next.
Under each heading write a short paragraph of plain prose: no bullet points or numbered lists.""",
}
DEFAULT_LENGTH = "paragraph"

LANGUAGE = {  # reading level and register rise with the grade
    9: """Language (Grade 9): keep it simple. Short, direct sentences (about 12 to 16 words). Everyday words; if you need a
subject term, explain it in plain words right away. One idea per sentence. Concrete, friendly and encouraging,
like a coach talking to a younger teen. Avoid abstract or academic vocabulary.""",
    10: """Language (Grade 10): clear and straightforward. Mostly everyday words, with basic subject terms used and briefly
explained when first used. Sentences of moderate length (about 15 to 20 words). Friendly but a step more grown-up
than for younger students.""",
    11: """Language (Grade 11): more sophisticated. Use precise vocabulary and standard subject terminology without
explaining basic terms. Sentences of about 18 to 24 words that link ideas (because, although, which suggests, whereas).
Treat the student as a capable, developing thinker and name the "why" behind each point.""",
    12: """Language (Grade 12): sophisticated, near-adult academic register. Precise, nuanced vocabulary and correct
subject terminology. Write fuller sentences of about 22 to 30 words with subordinate clauses and varied openings;
avoid choppy short sentences. You may weigh trade-offs and make finer distinctions and refer to how the work would
read to an outside audience. Respectful and collegial, still warm. Never talk down.""",
}
LANGUAGE_DEFAULT = LANGUAGE[10]


def language_for(grade_level):
    m = re.search(r"\d+", grade_level or "")
    return LANGUAGE.get(int(m.group()), LANGUAGE_DEFAULT) if m else LANGUAGE_DEFAULT


def system_prompt(length, grade_level=""):
    return (SYSTEM_TEMPLATE.replace("{FORMAT}", LENGTHS.get(length, LENGTHS[DEFAULT_LENGTH]))
            .replace("{LANGUAGE}", language_for(grade_level)))

LEVELS = ["Emerging", "Developing", "Proficient", "Extending"]
VALUE_WORDS = {  # school value-statement wording by level (Assessment at RCS)
    "Emerging": ("begins to", "partial"),
    "Developing": ("somewhat", "adequately"),
    "Proficient": ("substantial", "a range of"),
    "Extending": ("thorough", "a wide range of"),
}


def level_line(level):
    """Deterministic opening naming the teacher's level, its wording, and the next rung. '' if level is unknown."""
    m = re.fullmatch(r"\s*(Emerging|Developing|Proficient|Extending)(\+?)\s*", level or "", flags=re.I)
    if not m:
        return ""
    base, plus = m.group(1).capitalize(), bool(m.group(2))
    a, b = VALUE_WORDS[base]
    what = ("consistent, high-end learning at this level" if plus
            else "solid learning at this level, with some inconsistencies")
    line = f"This work is at the {base}{'+' if plus else ''} level: {what}. Work at this level is described with words like \u201c{a}\u201d and \u201c{b}\u201d."
    if plus and base == "Extending":
        return line + " This is the top of the scale; the next step is to keep that quality consistent and extend it further."
    if plus or base == "Extending":
        nxt = LEVELS[LEVELS.index(base) + 1] if plus else "Extending+"
    else:
        nxt = base + "+"
    if nxt in VALUE_WORDS:
        c, d = VALUE_WORDS[nxt]
        return line + f" To reach {nxt}, aim for \u201c{c}\u201d and \u201c{d}\u201d."
    return line + f" To reach {nxt}, make that quality consistent across the whole piece."

def avoid_words(level):
    """Value-statement words that belong to levels other than the teacher's level."""
    m = re.fullmatch(r"\s*(Emerging|Developing|Proficient|Extending)(\+?)\s*", level or "", flags=re.I)
    if not m:
        return []
    i = LEVELS.index(m.group(1).capitalize())
    return [w for k, ws in enumerate(VALUE_WORDS[l] for l in LEVELS) if k != i for w in ws]

def wrong_level_words(text, words):
    """Banned words found in the model's own wording (text inside quotation marks is the student's, so ignored)."""
    own = re.sub(r"[\"\u201c][^\"\u201d]*[\"\u201d]", " ", text)
    return [w for w in words if re.search(r"\b" + re.escape(w) + r"\b", own, flags=re.I)]

def named_levels(text):
    """Level names in the model's own wording: only the teacher assigns levels. A capitalised level name mid-sentence
    ("at the Proficient level") or with a "+" counts; "Developing your ideas..." opening a sentence does not."""
    own = re.sub(r"[\"“][^\"”]*[\"”]", " ", text)
    pat = r"(?:(?<=[a-z,;:(] )(?:Emerging|Developing|Proficient|Extending)\b\+?|\b(?:Emerging|Developing|Proficient|Extending)\+)"
    return sorted(set(re.findall(pat, own)))

COMMAND_TERMS = {  # term -> pattern for the term and its noun ("explain", "explanation")
    "describe": r"describ\w*|description", "explain": r"explain\w*|explanation", "justify": r"justif\w*",
    "analyse": r"analy[sz]\w*", "compare and contrast": r"compar\w*|contrast\w*", "discuss": r"discuss\w*",
    "evaluate": r"evaluat\w*", "list": r"list", "identify": r"identif\w*",
}


def command_terms(task):
    """Command terms the assignment or rubric actually uses."""
    return [t for t, p in COMMAND_TERMS.items() if re.search(r"\b(?:" + p + r")\b", task, flags=re.I)]


def invented_terms(text, terms):
    """Command terms the model says the task asks for ("the task asks you to explain") that the task never uses."""
    own = re.sub(r"[\"“][^\"”]*[\"”]", " ", text)
    asked = re.findall(r"\b(?:asks?|asked|requires?|required|wants?|expects?|calls? for)\s+(?:(?:you|students?|the\s+student)\s+to|for\s+an?|an?)?\s*(\w+)",
                       own, flags=re.I)
    found = [next((t for t, p in COMMAND_TERMS.items() if re.fullmatch(p, w, flags=re.I)), None) for w in asked]
    return sorted({t for t in found if t and t not in terms})


DETAILED_HEADINGS = ["Strengths", "Next steps", "One thing to try"]
BULLET = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
CRITERIA_LINE = re.compile(r"^\s*(?:looking for|success criteria|criteria|must include|requirements?)\s*:[ \t]*(.*)$", re.I | re.M)
GENERIC = {"the", "and", "for", "with", "your", "you", "least", "two", "three", "four", "one", "each", "some", "more",
           "clear", "clearly", "good", "strong", "well", "supporting", "sentence", "sentences", "paragraph", "use", "uses",
           "using", "include", "includes", "including"}


def rubric_criteria(rubric):
    """The teacher's checklist ("Looking for: a, b, c" or bullets under "Looking for:"); [] if there is none.
    Only the teacher's own text: app.py appends the standards after "Learning standards (RCS"."""
    teacher = rubric.split("Learning standards (RCS")[0]
    items = []
    for m in CRITERIA_LINE.finditer(teacher):
        if m.group(1).strip():
            items += re.split(r"\s*[;,]\s*", m.group(1).strip().rstrip("."))
        else:
            for line in teacher[m.end():].lstrip("\n").splitlines():
                if not BULLET.match(line):
                    break
                items.append(BULLET.sub("", line))
    items = [i.strip(" .") for i in items]
    return list(dict.fromkeys(i for i in items if 0 < len(i.split()) <= 8))


def uncovered(text, criteria):
    """Criteria the feedback never mentions, judged by their key words ("concluding sentence" -> "conclu...")."""
    low = text.lower()
    out = []
    for c in criteria:
        keys = [w[:5] for w in re.findall(r"[a-z]+", c.lower()) if len(w) > 2 and w not in GENERIC]
        if keys and not any(re.search(r"\b" + k, low) for k in keys):
            out.append(c)
    return out


def unsourced_quotes(text, *sources):
    """Quoted passages of 4+ words found in neither the student's work nor the task: wording written for the student
    to copy (or a misquote). A quote shortened with "..." is checked piece by piece."""
    flat = lambda s: " ".join(re.findall(r"[a-z0-9']+", s.lower().replace("’", "'")))
    src = flat(" ".join(sources))
    out = []
    for q in re.findall(r"[\"“]([^\"”]+)[\"”]", text):
        if len(q.split()) >= 4 and any(flat(p) not in src for p in re.split(r"\.{3}|…", q) if flat(p)):
            out.append(q.strip())
    return out


def unbullet(text):
    """Detailed format asks for prose: join each run of bullet or numbered lines into one paragraph."""
    end = lambda s: s.rstrip() + ("" if re.search(r"[.!?:;\"”)]$", s.rstrip()) else ".")  # items become sentences
    lines, in_list, gap = [], False, False
    for line in text.split("\n"):
        if BULLET.match(line):
            item = BULLET.sub("", line).strip()
            if in_list:
                lines[-1] = end(lines[-1]) + " " + item
            else:
                lines.append(item)
            in_list, gap = True, False
        elif in_list and not line.strip():
            gap = True  # a blank line between bullets: keep the list together
        else:
            if in_list:
                lines[-1] = end(lines[-1])
            if gap:
                lines.append("")
            lines.append(line)
            in_list = gap = False
    if in_list:
        lines[-1] = end(lines[-1])
    return "\n".join(lines)


def fix_headings(text):
    """Detailed format: normalise '**Heading**:' to '**Heading**', re-insert a dropped first heading, drop any
    remark before the first heading, and turn bullet lists into prose."""
    for h in DETAILED_HEADINGS:
        text = re.sub(r"^[# \t]*\*{0,2}" + re.escape(h) + r"\*{0,2}\s*:?\*{0,2}[ \t]*$", f"**{h}**", text, flags=re.I | re.M)
    if "**Strengths**" not in text and "**Next steps**" in text and not text.lstrip().startswith("**"):
        text = "**Strengths**\n" + text.lstrip()  # the model dropped only the opening heading
    i = text.find("**Strengths**")
    if i > 0:
        text = text[i:]  # an opening remark before the first heading ("Your paragraph ... a strong start.")
    text = unbullet(text)
    m = re.search(r"\*\*One thing to try\*\*[ \t]*\n+[^\n]+(?:\n(?!\n)[^\n]+)*", text)
    if m:
        text = text[:m.end()]  # drop any closing remark after the last section's paragraph
    return text


def missing_headings(text):
    return [h for h in DETAILED_HEADINGS if f"**{h}**" not in text]


def http_json(path, payload=None, timeout=300):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        OLLAMA + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def pick_model(requested):
    try:
        models = [m["name"] for m in http_json("/api/tags", timeout=5)["models"]]
    except (urllib.error.URLError, OSError):
        sys.exit(
            "Can't reach Ollama. Start it with `ollama serve` (or open the Ollama app) and try again."
        )
    if not models:
        sys.exit("Ollama has no models yet. Run e.g. `ollama pull llama3.1:8b` first.")
    if requested:
        if requested not in models:
            sys.exit(f"Model '{requested}' not installed. Installed: {', '.join(models)}")
        return requested
    return DEFAULT_MODEL if DEFAULT_MODEL in models else models[0]


def sanitize_feedback(text):
    """Strip preambles, trailing asides and sign-offs the model sometimes adds (cf. report-card-local)."""
    t = text.strip()
    t = re.sub(r"^(here'?s?|here is|below is|sure|certainly)[^\n]*:\s*\n+", "", t, flags=re.I)
    t = re.sub(r"^-{3,}\s*\n+", "", t)
    t = re.split(r"\n+-{3,}\s*(?:\n|$)", t)[0]
    t = re.sub(r"\n+\*{0,2}(?:note|teacher note)[^\n]*[\s\S]*$", "", t, flags=re.I)
    t = re.sub(r"\n+(?:i hope|let me know|feel free|keep up the)[^\n]*$", "", t, flags=re.I)
    return t.strip()


def display_name(label):
    """First name to substitute for [NAME]; falls back to 'the student' for codes like R002."""
    first = label.strip().split()[0] if label.strip() else ""
    if re.search(r"\bp\d+$", label.strip()):  # "poems p3": a page label, not a name
        return "the student"
    if re.fullmatch(r"[A-Za-z][A-Za-z'\-]+", first) and first.lower() not in {"student", "unknown"}:
        return first
    return "the student"


def generate(model, rubric, grade_level, label, work, notes="", level="", term="", length=DEFAULT_LENGTH, title=""):
    terms = command_terms(title + "\n" + rubric)
    criteria = rubric_criteria(rubric) if length != "sentence" else []  # one sentence can't cover a checklist
    user = (
        f"Grade level: {grade_level}\n"
        + (f"Term: {term}\n" if term else "")
        + (f"Assignment: {title.strip()}\n" if title.strip() else "")
        + "\n"
        f"Rubric / what the teacher is looking for:\n{rubric}\n\n"
        + (f"Command terms this task uses: {', '.join(terms)}.\n\n" if terms else
           "This task uses no command term (describe, explain, justify, analyse, compare, discuss, evaluate, list, identify), "
           "so never say the task asks for one.\n\n")
        + ("Criteria to cover (mention every one: as a strength if the work meets it, as a next step if it doesn't):\n"
           + "\n".join(f"- {c}" for c in criteria) + "\n\n" if criteria else "")
        + (f"Teacher's private notes about this student (do not quote or reveal):\n{notes.strip()}\n\n" if notes.strip() else "")
        + (f"Teacher's assessment: this work is at the {level.strip()} level. Write feedback consistent with that. "
           "A sentence naming the level and the school's wording for it is added automatically before your text, so do not "
           "name the level yourself or repeat it; just give the specific strengths and next steps. "
           + (f"Do not use these words or phrases to describe the work, because they belong to other levels: "
              f"{', '.join(chr(34) + w + chr(34) for w in avoid_words(level))}. " if avoid_words(level) else "")
           + "Describe the work in plain, level-neutral words instead.\n\n" if level.strip() else "")
        + f"Student work (student: [NAME]):\n\"\"\"\n{work}\n\"\"\"\n\n"
        + {"sentence": "Write the feedback now: exactly one sentence.",
           "paragraph": "Write the feedback now: one short paragraph.",
           "detailed": "Write the feedback now."}.get(length, "Write the feedback now.")
    )
    bad = avoid_words(level)
    best, best_hits = None, None
    keep_format = {"sentence": "as exactly one sentence",
                   "paragraph": "as one short paragraph, with no headings or bullets"}
    for attempt in range(3):  # regenerate (max twice) if a draft breaks a rule the code can check
        if attempt:  # name each problem, ask only for that fix, and restate the chosen length so a retry can't change format
            problems = ([", ".join(f'"{w}"' for w in words)] if words else []) + (
                [f"it says the task asks for {' / '.join(invented)}, but the task never asks for that"] if invented else []) + (
                ["it writes wording for the student to copy: " + "; ".join(f'"{q}"' for q in ghost)] if ghost else []) + (
                ["it never mentions: " + ", ".join(gaps)] if gaps else []) + (
                ["missing heading: " + ", ".join(missing)] if missing else [])
            asks = (["without the quoted words"] if words else []) + (
                ["without saying the task asks for a kind of thinking it doesn't name"] if invented else []) + (
                ["saying what to add instead of writing it for them"] if ghost else []) + (
                ["covering every listed criterion"] if gaps else []) + (
                ["with all three bold headings (Strengths, Next steps, One thing to try)"] if missing
                else [keep_format[length]] if length in keep_format else [])
            msg = user + "\n\nYour previous draft had problems: " + "; ".join(problems) + ". Rewrite it " + " and ".join(asks) + "."
        else:
            msg = user
        out = http_json(
            "/api/chat",
            {
                "model": model,
                "stream": False,
                "options": {"temperature": 0.4 + 0.2 * attempt, "num_ctx": 8192},
                "messages": [
                    {"role": "system", "content": system_prompt(length, grade_level)},
                    {"role": "user", "content": msg},
                ],
            },
        )
        text = sanitize_feedback(out["message"]["content"])
        if length == "detailed":
            text = fix_headings(text)
        words = wrong_level_words(text, bad) + named_levels(text)  # the teacher's level is added below, never by the model
        invented = invented_terms(text, terms)
        ghost = unsourced_quotes(text, work, rubric, title)
        gaps = uncovered(text, criteria)
        missing = missing_headings(text) if length == "detailed" else []
        score = len(words) + len(invented) + len(ghost) + len(gaps) + len(missing)
        if best is None or score < best_hits:
            best, best_hits = text, score
        if not score:
            break
    text = best
    if length in ("sentence", "paragraph"):
        text = re.sub(r"\*\*(?:" + "|".join(map(re.escape, DETAILED_HEADINGS)) + r"):?\*\*:?\s*", "", text, flags=re.I)  # stray labels like **Strengths**
        text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)                  # other bold: keep the words, drop the asterisks
        text = re.sub(r"^\s*[-*\u2022]\s+", "", text, flags=re.M)         # bullets
        text = re.sub(r"\s*\n+\s*", " ", text).strip()
    lead = level_line(level) if length != "sentence" else ""
    if lead:
        text = lead + (" " if length == "paragraph" else "\n\n") + text
    return re.sub(r"\[name\]", display_name(label), text, flags=re.I)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("submissions", type=Path, help="folder of .txt/.md student submissions")
    ap.add_argument("--rubric", type=Path, required=True, help="text file describing the assignment/rubric")
    ap.add_argument("--out", type=Path, default=Path("feedback"), help="output folder (default: feedback/)")
    ap.add_argument("--model", help="Ollama model name (default: qwen2.5:14b)")
    ap.add_argument("--grade", type=int, choices=[9, 10, 11, 12], default=9, help="grade level (9-12)")
    ap.add_argument("--length", choices=list(LENGTHS), default=DEFAULT_LENGTH, help="sentence, paragraph or detailed")
    ap.add_argument("--level", default="", help="optional teacher-set level for all work, e.g. 'Developing+'")
    args = ap.parse_args()

    files = sorted(p for p in args.submissions.iterdir() if p.suffix.lower() in {".txt", ".md"})
    if not files:
        sys.exit(f"No .txt or .md files found in {args.submissions}")

    rubric = args.rubric.read_text(encoding="utf-8")
    model = pick_model(args.model)
    args.out.mkdir(parents=True, exist_ok=True)
    print(f"Using model: {model}  ({len(files)} submissions)")

    for i, f in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {f.stem} ...", end=" ", flush=True)
        text = generate(model, rubric, f"Grade {args.grade}", f.stem, f.read_text(encoding="utf-8"), level=args.level, length=args.length)
        dest = args.out / f"{f.stem}.feedback.md"
        dest.write_text(f"# Feedback: {f.stem}\n\n{text}\n\n---\n_Draft generated locally; teacher reviewed: [ ]_\n", encoding="utf-8")
        print("done")
    print(f"\nDrafts written to {args.out}/ - please review before sharing with students.")


if __name__ == "__main__":
    main()
