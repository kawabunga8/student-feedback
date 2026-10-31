# student-feedback

Local, private assignment feedback for students. Runs on this laptop with a local model in Ollama
(`qwen2.5:14b`); LM Studio is supported too (see below). Student work is only ever sent to `localhost`.

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

## Ollama or LM Studio

Ollama is the engine in use. LM Studio was tried with an MLX build of the same model (2026-10-30) and
removed (2026-10-31); the app still supports it, so another engine or model can be tested later without
code changes.

The **Model** menu lists models from both engines, grouped as Ollama and LM Studio. Pick one and click
Generate; the choice is remembered. An engine that isn't running is left out of the list, and the page says so.

- **Ollama** (`localhost:11434`) loads its model on demand. Start it with `ollama serve` or the Ollama app.
- **LM Studio** (`localhost:1234`) needs its server on: **Model Server** in LM Studio, or `lms server start`.
  It loads a downloaded model on demand. Set the model's context length to at least 8192 in LM Studio's
  model settings; Ollama gets that per request, LM Studio doesn't.
- **Memory:** this Mac (16 GB) holds one 14B model at a time. When you switch engines, the app first
  unloads the other engine's model (`ollama` via its API; LM Studio via `lms unload --all` if the `lms`
  command is installed). If LM Studio's model stays loaded, eject it in LM Studio.
- **Command line:** `python3 feedback.py submissions/ --rubric rubric.txt --backend lmstudio`
  (or `--model lmstudio::<name>`). Without `--backend`, it uses Ollama as before.
- Different addresses: set `OLLAMA_URL` or `LMSTUDIO_URL` in the environment.

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
- `app.py` - web UI + server. `feedback.py` - prompt, model call (Ollama or LM Studio), CLI.
- `standards/` - 2026-27 learning-standards PDFs (parsed on load).
- `courses.json` - fallback course list, quarter dates, department rules.
- `.env.local` - Course Hub URL/key (git-ignored).
- `WORKFLOW.md` - assessment workflow plan and status. `ARCHITECTURE.md` - how the pieces fit.
  `TEAMS-ASSIGNMENT-SETUP.md` - setting up assignments. `skills/` - copies of the workflow's Claude skills.
