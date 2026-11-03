# student-feedback

Local, private assignment feedback for students. Runs on this laptop with a local model in Ollama
(`qwen2.5:14b`); LM Studio is supported too (see below). Student work is only ever sent to `localhost`.

```bash
cd ~/Repos-folder/student-feedback && python3 app.py     # web page at http://127.0.0.1:8765
python3 feedback.py submissions/ --rubric rubric.txt --grade 10   # command line
```

## Working prototypes

The app follows Design → Setup → Collect → Draft & review → Export & posting. Save the assignment and session before closing. Only you choose levels and approve feedback; later edits require review again.

- Create an unpublished MySchool assignment from Design: load courses, choose course/type/due date and learning outcomes, review, then explicitly Save. Publish stays No and student email stays off.
- Create an unpublished ordinary assignment in Teams from Design: review the class/title/instructions, confirm, then check the verified Drafts receipt. Publishing, attachments and Forms quiz creation are separate and not automated.
- Read Teams assignment instructions and rubrics, then optionally use the saved rubric as separate drafting criteria.
- Collect typed OneNote pages from pasted addresses, or the whole class at once from one notebook address (it tries the likely page titles for each student and lists those it can't find), or upload Forms response exports with Upload files. Forms scores are shown separately and are never proficiency levels.
- Load an Assessment folder (`Assessment/<year>/<quarter>/<course>/<assignment>`) and the app sets itself up: it picks the course and quarter and the class list from Course Hub, finds the matching assignment in that course's confirmed Teams class (read-only), imports its name and instructions, saves the assignment, and loads any `<name>.feedback.md` drafts beside each student's work as editable cards.
- Draft locally in the foreground or background, or load drafts made by `feedback.py` (below). Class overview shows the next action for each student, including per-destination progress (posted to Teams, saved to MySchool).
- Review: **Mark all reviewed** / **Unreview all**, or each student's own toggle. A level is optional (feedback only) for Teams; MySchool needs one. A student's MySchool comment defaults to their feedback and stays editable.
- Post to Teams and save to MySchool, each for one student or the whole class, on one engine per destination that reads and writes in a single Chrome session. Every write is confirmed once, re-checks that student's approval at the moment of writing, and is verified by reading the destination back. See the two sections below.
- Image transcription is an experimental local-vision prototype. Check every line yourself. Open a saved assignment first: each image preview is bound to it, and switching assignments discards the preview instead of adding it to the wrong class.

See [WORKFLOW.md](WORKFLOW.md) for current verification limits and the development log. One typed notebook page and one Forms quiz export have been verified live; those checks do not cover every submission type.

**Verified live (2026-11-03, ICT 9 Q1 Task 2, 18 students):** posting and Returning feedback in Teams, and saving levels, comments and Graded status in MySchool, each confirmed by reading the destination back. Not verified: what a Teams Return sends to the student, behaviour on other assignment layouts, MySchool assignments with several criteria, and the Playwright suites for the new dialogs (they need a browser install and were not run).

## Posting reviewed feedback to Teams

In **Export & posting**, click **Post** on a student's row for one student, or **Post to all (Teams)** for the class (it skips students already posted). The dialog opens and reads Teams by itself, in one Chrome session: students already **Returned** are skipped, a name that is not on the roster is flagged, and each remaining student shows ready, with a warning if feedback is already there that posting would replace. Nothing is changed while reading.

Tick the one confirmation and post. For each student the app re-checks their approval, confirms the feedback in Teams is still what the preview showed, types the approved feedback, checks the editor kept it, clicks **Return** (which may notify the student), and then verifies: the roster lists the student under **Returned**, and the feedback Teams actually kept, read back from the Returned panel, matches the approved text. The first problem stops the run; students after it are not attempted. **Check Teams** reads who is already Returned (read-only) and updates the table. Names come from Course Hub as "Last, First"; the app asks you to type a name only when it cannot find the student.

## Saving reviewed assessments to MySchool

In **Export & posting**, click **Save to MySchool (all)**, or the **MySchool** button on one student's row. Review and save the assignment first. A student's MySchool comment defaults to their Teams feedback (editable on its own) and is part of the review.

Only the MySchool assignment's **Assessment** address is needed; it is remembered for the assignment. The app reads MySchool in one Chrome session: the assignment's own course, title and publication state (shown as "From MySchool: course → title"; check it is the right assignment), and each student, matched automatically by name. A student it cannot match exactly once is reported, never guessed. Each student's saved level is used for a single-criterion assignment; with several criteria a Levels box appears and you type one level per criterion, in page order (a single level never fills several criteria).

Expand a student's full preview (each criterion existing → proposed, the whole comment, the status, and a warning if the assignment is published), tick the one confirmation, and save. Each student's approval is re-checked at the moment of writing; the Save click is never retried; a student counts as saved only after MySchool is reopened and the levels, comment and status match, other students are unchanged and the publication setting is preserved. The run stops at the first problem. An uncertain Save needs a check in MySchool before trying again. Live MySchool saving has not yet been verified: try one student first.


## Drafting from the command line

`feedback.py` writes one `<name>.feedback.md` per student. Before drafting it asks the local model, per criterion in your rubric's "Looking for" list, whether the work already does it, and the model must quote the evidence, which the code checks against the work. Criteria already met are credited and not asked for again; a draft that still asks for them is retried. Options: `--notes <folder>` (private `<name>.txt` notes per student), `--no-check` (skip that check), `--lean` (send a one-line assignment aim instead of the full rubric; tested, mixed results), `--length`, `--level`. A draft is a starting point: read each one. Put the drafts beside the staged work as `<same name>.feedback.md` and loading the folder in the app shows them as editable cards.

## Tests and model quality

Stop the app and Ollama before running synthetic tests:

```bash
TEST_BROWSER_CHANNEL=chrome ~/.venvs/student-feedback-tools/bin/python tests/run_all.py
```

Tests use temporary data and stand-in models. The last 17-file Mac run needed separate reruns of two UI files; it was not a clean combined pass. See [tests/README.md](tests/README.md) for scope and current validation notes.

With Ollama running, measure the real drafting model on invented cases:

```bash
python3 tools/draft_quality.py --model qwen2.5:14b --runs 1
```

The first seven-case paragraph benchmark accepted 2/7 drafts, both after retries; omitted criterion names caused five refusals. An automatic audit flag count is not a complete quality judgement. Use `--runs 3` for a repeated baseline. Reports stay in git-ignored `quality-reports/`.

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

The link from a Teams class to a Course Hub course (for example `RCS - H - Q1 ICT 9 [2026-27]` → ICT 9 (Q1)) is confirmed once and kept in `~/Library/Application Support/student-feedback/class-map.json`. When a course has exactly one confirmed class, the app uses it automatically (the Design step's Intended Teams class, the Choose from Teams list filter, and loading an Assessment folder). A wrong confirmation (a different class mapped to the same course) makes the app offer a choice or link the wrong class: delete that entry from the file and restart. The posting steps work from the saved assignment's Teams class and assignment ids, so check the class named in the assignment bar before posting.

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
- `jobs.py` - background job queue (drafting, Teams/OneNote reads, posting jobs). `ui/` - the workspace's scripts and styles; see `ui/README.md`.
- `teams_read.py` - read-only Teams assignment, rubric and student-status reader. `onenote_read.py` - read-only typed OneNote page reader. `onenote_class.py` - the whole-class version: one Chrome session, tries likely page titles per student and accepts a page only when its title matches.
- `forms_import.py` - Microsoft Forms response-export parser (local file, no network). `vision_read.py` - local vision-model image transcription.
- `teams_batch.py`, `myschool_batch.py` - the one-session posting engines for Teams and MySchool (read, preview, post/save, verify; one student or a whole class). `teams_post.py`, `myschool_post.py` - the earlier one-student workers; the engines reuse their page helpers and safeguards.
- `stage_submissions.py` - stages collected files into the Assessment folder. `check_session_folder.py` - checks macOS lets the app save there.
- `tools/` - spikes, `draft_quality.py` and `transcribe_check.py` (real-model measurements). `tests/` - synthetic-data suites; see `tests/README.md`.
- `standards/` - 2026-27 learning-standards PDFs (parsed on load).
- `courses.json` - fallback course list, quarter dates, department rules.
- `.env.local` - Course Hub URL/key (git-ignored).
- `WORKFLOW.md` - assessment workflow plan and status. `ARCHITECTURE.md` - how the pieces fit.
  `TEAMS-ASSIGNMENT-SETUP.md` - setting up assignments. `skills/` - copies of the workflow's Claude skills.
