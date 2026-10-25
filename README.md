# student-feedback

Local, private assignment feedback for students. Runs on this laptop with Ollama
(`qwen2.5:14b`); student work is only ever sent to `localhost`.

```bash
cd ~/Repos-folder/student-feedback && python3 app.py     # web page at http://127.0.0.1:8765
python3 feedback.py submissions/ --rubric rubric.txt --grade 10   # command line
```

## Writing assignment instructions

List what you're looking for after a label, and each item becomes a checklist the
feedback must cover (as a strength if the work meets it, as a next step if not):

```
Assignment: one persuasive paragraph.
Looking for: clear claim, at least two supporting reasons, evidence, concluding sentence.
```

or as bullets under the label:

```
Success criteria:
- vivid imagery
- a clear rhyme scheme
```

- Labels recognised: `Looking for:`, `Success criteria:`, `Criteria:`, `Must include:`, `Requirements:`.
- Keep each item short (8 words or fewer) and separate items with commas, semicolons or bullets.
- Only your own instructions are used, not the ticked learning standards.
- Not used for one-sentence feedback (too short to cover a list).
- Without a label the feedback still works, just without the checklist.
- The check only confirms each item is mentioned, not that the judgement is right.

Use command terms (describe, explain, justify, analyse, compare and contrast, discuss,
evaluate, list, identify) in the instructions if you want feedback on that kind of
thinking. The feedback only says "the task asks you to explain…" when the task does.

Drafts that name a proficiency level you didn't set, invent a command term, write
sentences for the student to copy, or skip a checklist item are regenerated (up to
twice). Only you set levels: choose one on the student's card, or leave "No level".
Always review drafts before sharing.

## Courses and terms come from Course Hub

On load the page asks Course Hub (`/api/courses`, `/api/quarters`) for the current
school year's courses and quarter dates. The term is picked from today's date and the
course list is filtered to that quarter. Departments (which learning-standards PDF to
use) are assigned by `department_rules` in `courses.json`.

Setup (one time). The key is read server-side only and never sent to the browser:

```bash
grep '^COURSE_HUB_API_KEY=' ~/Repos-folder/course-hub/.env.local > ~/Repos-folder/student-feedback/.env.local
echo 'COURSE_HUB_URL=http://localhost:3005' >> ~/Repos-folder/student-feedback/.env.local
```

Course Hub must be running (port 3005, same as the report card tool expects).

If Course Hub is unreachable the page says so and falls back to:
1. `courses.cache.json` - the last successful live copy, else
2. `courses.json` - a hand-kept list (last resort).

## Files
- `app.py` - web UI + server. `feedback.py` - prompt, Ollama call, CLI.
- `standards/` - 2026-27 learning-standards PDFs (parsed on load).
- `courses.json` - fallback course list, quarter dates, department rules.
- `.env.local` - Course Hub URL/key (git-ignored).
