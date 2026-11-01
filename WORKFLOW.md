# Assessment Workflow — plan

## For a new session/agent picking this up

Read this doc fully before doing anything, then jump straight to **"What to
build next"** near the bottom — it's the current punch list, kept up to date.
Status as of the evening of 2026-10-30: item 6 (verify the posting
actions) is in progress; see "Session log: 2026-10-30, RCS account" below.
One test student's ICT 9 Task 2 work and the Task 2 instructions from Teams
are loaded in the feedback app. Next: generate and review that draft, then
the first real Return in Teams and the first save in MySchool. A draft
`phase-b-upload` skill is in `skills/phase-b-upload/SKILL.md`. For what is implemented versus only
proposed, see `ARCHITECTURE.md`, "Status at a glance".

Also useful, in order of likely relevance:
- The `phase-a-collect-and-draft` skill (saved on Shingo's Claude account,
  invocable by name) — the whole collect→draft pipeline is already built and
  working; don't re-derive it, just use it. This skill is not in this repo
  since skills are account-scoped, not repo-scoped — if you're working from
  a different Claude account, you won't have it and will need to follow the
  Phase A steps below manually, or ask Shingo to run it from his own account.
- The `push-laptop-repo-to-github` skill (saved, same caveat as above) — how
  this repo got onto GitHub in the first place, and how to push future
  changes to it from Shingo's laptop.
- **Two Claude accounts.** Shingo works from two Claude accounts. The RCS
  organization account (Shingo confirmed on 2026-10-30 that it is approved
  by RCS for student work and feedback) cannot see the Assessment Project
  or the two skills above. To keep skills usable from either account, keep a
  copy of each SKILL.md in this repo under `skills/<name>/SKILL.md`.
  `phase-b-upload` is there; `phase-a-collect-and-draft` and
  `push-laptop-repo-to-github` still need copying in.
- `stage_submissions.py` and the rest of this repo.
- `TEAMS-ASSIGNMENT-SETUP.md` (companion doc, this repo) — the upstream
  half: how an Assignment should be set up so this pipeline gets clean input.
- `ARCHITECTURE.md` (this repo) — components, data flow, constraints.

This file and `TEAMS-ASSIGNMENT-SETUP.md` are mirrored from a Claude.ai
Project doc (the "Assessment" project, docs `assessment-workflow.md` and
`teams-assignment-setup.md`). The Project doc is the live copy that gets
updated as work continues; this repo copy is refreshed periodically so the
plan survives even for a session/account with no access to that Project.
If you're updating this plan, update the Project doc first (if you have
access to it) and copy the changes here afterward — don't let the two
drift apart silently. Changes made from the RCS organization account land
here first, because that account can't reach the Project doc; copy them
into the Project doc the next time you work from the other account.

---

Goal: a repeatable, semi-automated pipeline that takes student work from
submission → through the local `student-feedback` app → to feedback posted in
Teams Assignments and a mark/standard-level posted in MySchool, with Shingo
reviewing and approving every feedback draft before it goes anywhere.

**Design goal (Shingo, 2026-10-30): the local LLM on the Mac runs most of
the process.** Scripts on the Mac do the navigating and clicking, the local
model does the content work, Shingo reviews, and Claude builds and maintains
the tooling rather than sitting in the data path. See `ARCHITECTURE.md`,
"Target", for the proposed split, and "What to build next" below for the build order.

See also: `TEAMS-ASSIGNMENT-SETUP.md` — the upstream half (setting up the
Assignment itself so this pipeline runs cleanly).

## Shape of the workflow: three phases, two human checkpoints

This is **not** one continuous pipeline — it's three separately-triggered runs,
each unattended once started, with a folder on the laptop as the handoff point
between them:

```
Phase A: COLLECT + DRAFT  (on-demand, runs unattended)
   → stages submissions AND draft feedback into a local folder
   → stops and waits for Shingo
                    │
       Shingo reviews/edits the folder (Stage 3 — mandatory gate)
                    │
Phase B: UPLOAD  (on-demand, runs unattended once triggered)
   → posts everything in the approved folder to Teams + MySchool
   → no further per-student confirmation once Shingo starts this run
```

Both Phase A and Phase B are triggered by Shingo ("process assignment X" /
"upload the approved batch for X") and then run without needing him until
each phase's own stopping point. Nothing posts anywhere without the folder
having been through his review first.

## Architecture

See `ARCHITECTURE.md` for the components, where each runs, how student work
moves between them, the app's local interface, and the privacy boundaries.
Two limits shape this plan: Microsoft 365 is reachable only through a
browser, and anything that calls the app or Course Hub runs on the Mac
itself, not in the device-bridge shell.

## Built so far

- **`stage_submissions.py`** (script, this repo) — folder-staging for Phase A.
  Calls the running app's own `/api/roster` endpoint to match collected files
  against the live class roster, writes into the exact
  `~/Desktop/Teaching/Assessment/<year>/<quarter>/<course>/<assignment>/FirstName_LastName.txt`
  convention `app.py` already expects. Dry-run by default; `--commit` to
  write. Unmatched files staged as `_NEEDS_ATTENTION_<name>.txt`; students
  with nothing submitted listed in `_MISSING_SUBMISSIONS.txt`.
- **`phase-a-collect-and-draft`** (Claude skill, saved on Shingo's account) —
  the full Phase A workflow: confirms assignment details, collects from
  ClassNotebook (vision-based reading; the skill text predates the typed-page spike), handwriting photos, Teams
  attachments, and Canva/SharePoint links; runs `stage_submissions.py`; runs
  `feedback.py`'s batch drafting; stops with a status report. No posting.
  Triggered by Shingo saying things like "process assignment X."
- **Teams Assignments and MySchool posting click-paths** — both mapped
  2026-10-30 (see below). Phase B skill not yet written.
- **This repo pushed to GitHub** — private repo at
  `github.com/kawabunga8/student-feedback`, pushed 2026-10-30.
- **`skills/phase-b-upload/SKILL.md`** — draft Phase B skill (2026-10-30).
  Runs in pilot mode (one student, then stop and check) until the posting
  actions are verified. Its input conventions are still assumptions; see
  "What to build next".
- **Feedback app reachable from Claude's browser pane** at
  `http://127.0.0.1:8765` (2026-10-30), so a session can load a student's
  work and the assignment instructions into it directly.

## Access-method priority (applies to every step in both phases)

For any step that reaches Microsoft 365, MySchool, or any other external
system, try methods in this order and fall back only when the one above fails:

1. **API / connector** — unavailable for RCS's tenant (Conditional Access
   block, see Known Issue below).
2. **Built-in-browser automation** — the default for everything in this
   workflow. Works for ClassNotebook navigation, Teams Assignments grading,
   and MySchool's Grade Grid/Assessment tab (all three mapped below).
3. **Computer-use** — not needed anywhere mapped so far; stays a documented
   fallback only.

**Browser practicalities (learned 2026-10-30):**
- Claude's browser pane keeps its own sign-in, separate from Chrome. It
  needed one Microsoft sign-in from Shingo; after that, Teams, SharePoint
  and OneNote worked. MySchool uses Staff → school single sign-on.
  Claude in Chrome connects only when the extension is signed in to the same
  Claude account as the session.
- The pane blocks popups and new tabs opened by Claude's clicks (Teams'
  "Go to website" icon, "Open online" on a submitted file). Navigate to the
  URL directly instead, or ask Shingo to click it himself.
- Sites approved for the pane so far: `onenote.com`,
  `onenote.cloud.microsoft`, `cac-onenote.officeapps.live.com` and
  `127.0.0.1:8765`. Any other site asks once.
- Set the tab to the light colour scheme before reading Teams or OneNote; in
  dark mode much of the text is too faint to read. A 1000x1450 viewport gave
  clearly legible screenshots.
- Copy and paste between tabs did not carry text over. Text read from
  OneNote is transcribed from screenshots and entered with form input, so
  spot-check it against the original.

## ClassNotebook structure and read method (resolved 2026-10-30)

**How to reach a ClassNotebook** (also captured in the `phase-a-collect-and-draft` skill):

1. Open the relevant Teams team (e.g. "RCS - H - Q1 ICT 9 [2026-27]" — each
   quarter is its own separate team).
2. Team's left nav (desktop width — see viewport note) → **Class Notebook**.
   Loads inline via an embedded OneNote add-in with no usable nav tree for
   automation.
3. Click the tab-toolbar **"Go to website"** icon to pop out to a real
   `rcschool.sharepoint.com/.../_layouts/15/Doc.aspx?...` OneNote Online tab.
4. Click the small notebook icon top-left to expand sections: `Welcome`,
   `Collaboration Space`, `Content Library`, `_Teacher Only`, then **one
   section per student** (full name).
5. Each student's section has page groups (`Handouts`, `Homework`) containing
   individual assignment pages by title.
6. Stable URL form:
   `.../Doc.aspx?sourcedoc={notebook-guid}&wd=target(<StudentName>/<PageGroup>.one|<section-guid>/<PageTitle>|<page-guid>/)`

**Update 2026-10-31:** a script read one typed page as text from OneNote's frame (`tools/spike_onenote_text.py`), so the
screenshot method below is now the fallback for handwriting, images and pages the spike hasn't covered, not the only way.

**Read method — screenshot/vision transcription.** `get_page_text`/`read_page`
can't see into OneNote's cross-origin canvas. The `computer` tool's `zoom`
action resolves on-screen text to fully legible quality — tested successfully
on a real submission. Scroll and re-screenshot until no new content appears
(a test page ran off-screen mid-sentence).

**Viewport note:** Teams' responsive layout drops the left nav (including
Class Notebook, and the global Assignments rail icon's surrounding labels)
below ~768px width — force a desktop-width viewport (1440x900 used this
session) before relying on any Teams nav.

**A second navigation gotcha, found while mapping Teams Assignments (below):**
embedded Teams panels (Class Notebook, the *team-level* Assignments tab) are
cross-origin iframes that `find`/`read_page` can't see into AND that don't
reliably respond to coordinate clicks either — multiple attempts to open an
assignment from inside a team's own "Assignments" nav item failed silently
with no visible error. The **global Assignments icon in the left rail**
(outside any team context, showing all classes at once) is the reliable path
in and does respond normally — use that, not the team-embedded one. Browser
back-navigation inside the Assignments app was also unreliable (repeatedly
landed on a stale previously-viewed student); prefer re-navigating fresh
(global Assignments icon → class → list) over using the browser back button.

**Route into a Class Notebook without the popup (2026-10-30).** Teams'
"Go to website" opens a new tab, which the browser pane blocks. This works
instead:
1. Get the class team's group id. It's in the `src` of the Class Notebook
   tab's iframe (`groupId=...`).
2. Go to `https://rcschool.sharepoint.com/_layouts/15/groupstatus.aspx?id=<group id>&target=site`.
   This redirects to the class site, e.g. `/sites/RCS-H-Q1ICT92026-27`.
3. Open `<site>/SiteAssets/Forms/AllItems.aspx` and click the
   "<team name> Notebook" item. It opens in OneNote on the web in the same tab.
4. Switch to **Viewing** (the "Editing ▾" menu, top right) before selecting
   anything, so nothing on a student's page can be changed by accident.
5. Notebook search only covers the current Section or Page, so browse
   instead: student section → Homework → the page by title.

Page titles don't always match the instructions. Task 2 asked for a page
named "Stage 2 – Define & Ideate", but one student's page was titled "Task 2"
and another's "Stage 2". Page dates don't help either: pages copied from a
template keep the template's date (a 2026 submission page showed April 18,
2022). Phase A should match by content, not by title or date. Distributed
pages also hold the task's wording with the student's answers in between, so
collection has to set the task wording aside.

## Build-strategy decision: browser automation first, scripts where it's safe

> **Revisited 2026-10-30.** With the local-first goal, collection and
> posting move to Playwright scripts on the Mac (see `ARCHITECTURE.md`,
> "Target"). Claude's browser automation becomes the fallback and the way
> new click-paths get mapped, not the routine path. The original reasoning
> below still explains why posting was browser-driven at all.

- **Posting (Phase B)** — stays browser automation. Both sites rely on
  SSO/SAML sessions easiest to reuse through the signed-in browser pane, and
  revisiting a dedicated script only makes sense once the click-path is
  proven stable over several real runs (now mapped, but not yet exercised
  repeatedly).
- **Folder-staging (Phase A)** — small custom script, built as
  `stage_submissions.py`.
- **Collection (Phase A)** — stays a skill (Claude-driven judgment), built as
  `phase-a-collect-and-draft`.
- General principle: script when self-contained/deterministic; skill/browser
  automation when the target is a live site that can shift or needs judgment.

## System map

| Stage | System | Notes |
|---|---|---|
| Submission | OneNote ClassNotebook (primary), Teams attachments, Canva/SharePoint links | Mapped, vision read — see above |
| Draft feedback | `student-feedback` app (local: Ollama or LM Studio, localhost only) | Runs automatically within Phase A |
| Human review | Shingo | Mandatory gate, between Phase A and B |
| Post feedback | Teams Assignments | Mapped 2026-10-30 — see below |
| Post grade | MySchool Grade Grid | Mapped 2026-10-30 — see below |

## Phase A — Collect + Draft — BUILT

See the `phase-a-collect-and-draft` skill for authoritative steps. Summary:
collect (vision for ClassNotebook/photos, browser automation for
links/attachments, flagging anything uncertain) → stage via
`stage_submissions.py` → draft via `feedback.py`'s batch CLI, automatically,
same unattended pass → stop and report. No posting.

## Stage 3 — Human review (the mandatory gate, between Phase A and B)

- Shingo reviews/edits drafts in the staged folder (plain text files, or the
  app's web UI at localhost:8765).
- Flagged items need explicit resolution before Phase B treats that student
  as ready.
- Worth spot-checking a few vision-transcribed OneNote pages against the
  originals early on, before trusting the method at full scale.

## Phase B — Upload — click-paths mapped 2026-10-30, skill drafted (`skills/phase-b-upload/SKILL.md`), posting not yet verified

### Teams Assignments — mapped

1. Click the **global Assignments icon** in Teams' left rail (not a team's
   own embedded Assignments tab — see the navigation gotcha above). This
   shows all classes' assignments together, grouped by due date.
2. Click an assignment's title to open its roster: every student, their
   status (Viewed / Turned in / Not turned in / Returned), and a per-student
   **Feedback** icon.
3. Click a student's row (or the Feedback icon) to open their individual
   grading panel. Confirmed layout:
   - **Student Work** panel — shows what they submitted (a link, file, etc.)
     with a "View History" option.
   - **Feedback** box — rich-text editor (bold/italic/underline/highlight/
     lists), with an "Enhance feedback"/"Feedback with Copilot" toggle
     (leave this off — feedback is already drafted by `feedback.py`; this
     toggle is Teams' own AI assist, not something this workflow should
     invoke).
   - **Points** field (this class uses "No points" — proficiency levels
     live in MySchool instead, not here).
   - **Return** button — this is what actually posts/returns the feedback
     to the student. Its dropdown (checked 2026-10-30) offers **Return**
     (the default), **Return for revision**, and **Mark as excused and
     return**. Phase B uses plain Return. Still unknown: whether plain
     Return notifies the student.
   - Prev/next arrows at top-right to move between students without
     returning to the roster list.
   - **Submitted files (2026-10-30):** the panel's viewer could not display
     students' SharePoint-link submissions, and "Open online" (or clicking
     the file card) opens a popup the browser pane blocks. A student can
     also show as "Turned in" with nothing attached, because their work is
     in the Class Notebook.
   - **Assignment instructions:** the assignment's `...` menu → **Student
     view** shows the full instructions read-only, including the
     assessment descriptors. That's the source for the feedback app's
     instructions box.
   - Confirmed again 2026-10-30: inside a team's own Assignments tab, a
     click on a student row did nothing; the global Assignments icon worked
     straight away.
4. **Not yet tested:** actually typing into the Feedback box and clicking
   Return (stopped short of this to avoid posting test content to a real
   student during mapping). This is the first thing to verify carefully —
   ideally on a low-stakes/already-returned assignment or with Shingo
   watching — before Phase B does this unattended for a whole class.

### MySchool — mapped

1. From the Grade Grid (`Assignments` in the left nav → course selected),
   each cell has a **level-only dropdown** (click or double-click a cell):
   EXT+, EXT, PRF+, PRF, DEV+, DEV, EMG+, EMG, NYM. This is fast for setting
   just the level, but has **no written-feedback field** — confirmed by
   testing directly on a real cell.
2. **Written feedback and the full per-student grading view live
   elsewhere**: open **"View All Assignments"** (bottom of the Grade Grid),
   click the assignment title to open its edit page, then click the
   **Assessment** tab (alongside Planning/Options). This shows one card per
   student with:
   - The rubric/criteria text for each learning standard being assessed.
   - A **cluster of colored level bubbles** (EXT+/EXT/PRF+/PRF/DEV+/DEV/
     EMG+/EMG/gray-for-ungraded) — click a bubble to set that criterion's
     level. Multiple clusters appear when an assignment is tied to more than
     one standard/criterion.
   - A status dropdown (seen as "Not yet graded").
   - A **comment** text box — this is the written-feedback field.
   - "Student submission" (shows "no submission made" when nothing's
     attached) and an "Upload correction" file picker.
3. **Not yet tested:** actually entering a level + comment and saving/
   publishing for a real student. Same caution as Teams above — verify this
   carefully before it runs unattended.
4. **Open question:** whether saving here from the Assessment tab also
   updates the Grade Grid's cell display (expected, but unconfirmed), and
   exactly what action (a Save button, auto-save, a separate Publish step)
   actually commits the grade+comment — the screenshot taken during mapping
   didn't scroll far enough to capture the save/publish control for this
   card.

### What Phase B still needs before it can be built as a skill

1. **Verify the actual posting action** for both systems on one real but
   low-risk case (a test row, or with Shingo present) — confirm what Return
   (Teams) and Save/Publish (MySchool) actually do, and that typed feedback
   text survives round-trip correctly (rich-text formatting, length limits).
2. Confirm the **MySchool save/publish control** location (cut off during
   mapping — need to scroll further in a student's Assessment card).
3. Decide whether Phase B sets the MySchool level via the **quick Grade Grid
   cell dropdown** (fast, but no comment) or the **Assessment tab per-student
   card** (slower, but has both level and comment in one place — almost
   certainly the right choice since both are needed per student anyway).
4. Write the `phase-b-upload` skill: for each approved student, open their
   Teams Assignments grading panel (type feedback, Return), then open their
   MySchool Assessment card (set level bubble(s), type comment, save/publish),
   skip anyone still flagged, and produce the end-of-run summary.

## Known issue — Microsoft 365 connector is blocked entirely (confirmed)

Tested 2026-10-30 against three connector calls (`get_granted_scopes`,
`get_me`, `sharepoint_folder_search`) — all failed identically:

```
AADSTS53003: Access has been blocked by Conditional Access policies.
userPrincipalName: skawamura@myrcs.ca
tenantId: f57aca7a-cfc1-4ff1-a02a-0be623a72500
```

Total, tenant-wide block. Every Microsoft 365 touchpoint in this workflow
goes through built-in-browser automation instead. Worth flagging to RCS IT
using the trace IDs above if Shingo wants the faster path back.

## What to build next

**Revised build order (2026-10-31, after an outside review of the plan):**
1. **Prove read access and extraction quality** with `tools/spike_onenote_text.py`. **Typed page passed
   (2026-10-31):** sign-in worked, the script read OneNote's page container (menus left out), and Shingo
   confirmed every answer was there, in order, to the bottom. Still to test: handwriting (ink), a pasted
   image, and more than one text box. The script reports completeness as unverified and lists any non-text
   elements in the page.
2. **Define the data contracts** in `ARCHITECTURE.md`: the manifest (atomic writes, keyed by Course Hub
   student ID), the name mapping for Teams, MySchool and the notebook, collection outcomes, the approval
   record and per-destination posting states.
3. **Build collection for one assignment format.**
4. **Add the vision model** only for pages that need it.
5. **Build posting dry runs** that show the destination student, the assignment and the exact values to be
   posted, without posting.
6. **Verify one real Teams return and one MySchool save** by reading them back, then test an interrupted
   run and a retry.
7. **Add app buttons** once those operations are dependable.

**Assignment record plan (2026-10-31).** The saved assignment record is the centre (see `ARCHITECTURE.md`,
"Assignment records"). Order:
1. Save and reopen assignments locally. **Done 2026-10-31.**
2. Design step with a Teams-ready preview and copy actions. **Done 2026-10-31.**
3. Read-only Teams picker ("Choose from Teams…") through the local Chrome worker. **Built 2026-11-01 (first version); not
   yet run through the app against live Teams.** The dialog still accepts pasted Student view text as the fallback.
4. Wire the field buttons to the selected Teams assignment.
5. "Create draft in Teams" through the browser worker; publishing stays a separate, explicit action.
6. Refresh with change detection, and link the record to collection, the manifest and approval.

First milestone: choose an existing Teams assignment → import → confirm the Course Hub match → save → reopen with the
same instructions and criteria ready for feedback. This works with the pasted Student view, and with the reader once it has been run live.

**Status (2026-10-31): persistent sessions and the first job queue are built.** Sessions: work, drafts, levels, notes, comments, review marks and posting ticks survive closing the page (see `ARCHITECTURE.md`, "Assessment sessions"). The queue (see "Background job queue") runs one job type, drafting feedback in the background with the local model; it survives an app restart and never resumes on its own. Next: run `tools/spike_teams_assignments.py` (written, not yet run) to see what Teams' Assignments frame exposes as text. Still to do, in this order: the read-only Teams picker, collection jobs, then posting automation (off, pilot mode, read-back).

### Read-only Teams reader: BUILT as a first version (2026-11-01); spike evidence from one class and one assignment; not yet run end to end through the app on live Teams.

**Spike result (2026-11-01, one run, ICT 9 "Task 4" opened):**

- The automated Chrome profile stayed signed in; no sign-in policy block.
- **Waiting for the frame:** the first run found no frame text and the second read it. The third run showed the cause:
  the wait printed "no frame" for 120 s while the frames table printed straight afterwards listed it. Playwright's Python
  API only sees new frames while one of its own calls is running, and the wait used `time.sleep()`. **Reader rule: poll
  with `page.wait_for_timeout()`, never `time.sleep()`, and log when the frame appeared and how much text it had.** Strongly
  indicated by that run; the corrected wait has not been run yet.
- **Assignment list: readable as text.** Each assignment shows title, due date and time, the **Teams class name** (so the
  dialog's "Teams class" box can be filled automatically), and one or two fractions. The fractions are not labelled.
  They are probably turned in / assigned and returned / turned in (2/28 then 0/2 matched a roster with 2 turned in);
  **inferred from one case, to be confirmed.** The list rows are not links (0 anchors), so there is no address per row
  before opening one.
- **Roster: readable as text.** Tabs "To return (28)" and "Returned (0)" give the counts directly, and a "28 results found"
  line is shown. Each student row has a status: Viewed, Turned in, Not turned in seen so far. Statuses for returned work,
  "Returned for revision" and excused are unseen. Counting must use whole lines: counting words overcounts ("Turned in"
  also matches inside "Not turned in", and "Returned" matches the tab label). The spike's first version did this; fixed.
- **Selectors seen:** the list showed 15 list items (one per assignment row); the roster showed 29 rows, header included
  (28 students). Exact counts from this run: Viewed 24, Not turned in 2, Turned in 2, Returned 0.
- **Matching:** assignments are matched on class and title together, never the first partial title match; zero or several
  matches stop the read with the candidates listed. Identifiers are kept with the result.
- **Identifiers:** after opening an assignment the frame's address carries a class id and an assignment id
  (`/classes/<class id>/assignment-review/<assignment id>`). Rows link to those addresses. This is the stable source
  reference; the title is not. Read them from the frame address, not from the list.
- **Student view (third run):** the "..." menu on the roster page holds Hide student names, Edit assignment, Mark as
  inactive, Student view, Export to Excel and Delete assignment. **The reader may click only an exact "Student view"
  item and nothing else in that menu.** Student view opened in the same frame (one page, no new tab) at
  `/classes/<class id>/assignments/<assignment id>/preview`, and the instructions read as text (2,187 characters, with
  headings such as Instructions, Where to submit and Your tasks). Likely the same text the paste dialog receives, so the
  existing parser may be reusable: **a hypothesis, to be tested on real text.** Not yet seen: whether the text has a
  rubric section, reference materials or attachments (the output was cut at 1,500 characters). The spike now prints the
  section labels it finds.
- **Not yet tested:** attachments (reference materials are listed by name only and never opened), other list tabs (Returned, Drafts, Past due), other statuses (Returned, Returned for revision, excused), other classes and assignment types, and an assignment with a rubric or points. The Student view output was truncated on screen, so **extraction is not marked complete until the full text has been compared with Teams by eye.**
- **Decision (2026-11-01):** the page is readable, so the reader was built (see `ARCHITECTURE.md`, "Read-only Teams reader").

(Original proposal follows.)

Nothing below is built. The first step is `tools/spike_teams_assignments.py` (written, not yet run). **Its result decides
whether to build the browser reader or to improve the paste fallback.** Do not fix the reader's interface before the
spike shows what the Assignments list and the Student view actually expose; aggregate status counts may need a
different view from the one the list shows. The Microsoft 365 connector is blocked, so there is no API route.

**Version 1 scope (Shingo's decision):** assignment details and aggregate status counts only. Per-student statuses (needed
for "skip Returned") come later, after assignment selection and identity matching are proven.

**Plan, if the spike shows the frame is readable:**

1. **`teams_read.py`**: list assignments (class, title, due date); read one assignment (instructions from Student view,
   points, rubric text, status counts). It runs in the automated Chrome profile.
2. **A `teams_read` job on the existing queue**, one browser job at a time. A sign-in page puts the job in
   `waiting_for_sign_in`; the teacher signs in and resumes. The journal still holds no student text.
3. **The "Choose from Teams" dialog** gets a "List my assignments" button and fills the same preview rows the paste does,
   followed by the existing Course Hub match step. Paste stays as the fallback.
4. **Every result carries its source:** Teams class and assignment identifiers where Teams exposes them, the page URL,
   and the time of the read. A title alone is not an identifier: the same title can exist in more than one class or term.
5. **The import preview keeps these apart:** assignment instructions, rubric text, and attached resources. Reading the
   instructions does not mean attached reference material was read. Attachments are listed by name and marked "not read"
   unless they were actually opened and read.

**Read-only is a guardrail, not a guarantee.** The reader may click only a fixed set of navigation targets (the
Assignments icon, a list row, Student view). It must also never type, submit a form, or touch grading controls
(Feedback, Return, Points, Edit assignment), and it must treat any unexpected navigation as a failure. At each step it
checks that the page matches what it expects (right frame, right heading, no dialog) and **stops with a plain message
when the page differs**, rather than trying other clicks.

**One owner for the Chrome profile.** The OneNote spike, the Teams reader and any later collection or posting worker
share one profile folder, and Chrome allows only one process per profile. The app takes a single "browser in use" lock
before starting any browser job; a second job waits or is refused with "browser profile in use (OneNote collection
running)", never silently started. The two spikes do not check any lock yet: until the app owns it, run only one browser script at a time and close its Chrome window first.

**Testing:** parser tests on saved frame text with student names replaced; the failure cases (signed out, blocked
sign-in policy, assignment not found, profile in use, page differs from expectations); then one real read compared with
Teams by eye. None of this has been done.

**Posting approach (Shingo, 2026-10-31): assisted now, automate next.** The workspace's Export & posting step opens Teams and MySchool and copies each reviewed student's approved text; Shingo pastes and submits. Automation follows in stages: a read-only Teams/MySchool test, a dry run that fills but doesn't submit, one verified real post with Shingo watching, then batches.

**Next milestone:** one complete, traceable student record, from captured work through approved feedback to
values read back from Teams and MySchool. The numbered list below is the earlier punch list, kept for its
detail; where it differs, the order above wins.


1. ~~Test the OneNote/SharePoint pull~~ — done.
2. ~~Folder-staging script~~ — done, `stage_submissions.py` deployed.
3. ~~Decide the ClassNotebook read method~~ — decided then as screenshot/vision; since narrowed by the typed-page spike (see the update note in the OneNote section).
4. ~~Phase A skill~~ — done, `phase-a-collect-and-draft` saved.
5. ~~Map Teams Assignments and MySchool posting click-paths~~ — done,
   2026-10-30 (see Phase B section above). Actual posting actions
   (Return / Save-Publish) still need verification before full trust.
6. **Verify the posting actions** on one real low-risk case (see "What Phase
   B still needs" above) — **in progress (2026-10-30)**. Done: the Return
   dropdown options are known. In progress: one test student's ICT 9
   Task 2 work and the Teams instructions are loaded in the feedback app.
   Next: generate and review the draft, Shingo picks the level, then the
   first real Return in Teams and the first save in MySchool, with Shingo's
   go-ahead for each.
7. **Phase B skill** — drafted as `skills/phase-b-upload/SKILL.md`. After
   step 6, fill in its "Verified behaviour" section, drop pilot mode, and
   save it as a skill in each Claude account.
8. Leave Stage 3 (review) as manual folder editing for now.
9. **Copy the other two skills into this repo** (`skills/phase-a-collect-and-draft/`,
   `skills/push-laptop-repo-to-github/`) so the RCS organization account
   can use them.
10. **Settle Phase B's input conventions**, which are assumptions in the
    draft: where Phase A writes the `*.feedback.md` files; how a student is
    marked as not ready (the draft uses a first line starting `HOLD`);
    whether MySchool gets the full feedback or a shorter comment; and what
    to do when a MySchool card has more than one criterion.
11. **Connect the Assessment folder to the Claude session.** The session
    could not be given access to `~/Desktop/Teaching/Assessment` on
    2026-10-30, and the app's folder menu showed "No Assessment folders
    found". Phase B reads from that folder, so it needs to be added with
    the desktop app's "Add folder" button (or moved somewhere that can be).
    Only needed while Claude runs Phase B; local scripts on the Mac read the
    folder directly.
12. **Local-first spike (next, alongside step 6).** A short Playwright
    script, run on the Mac, that opens the ICT 9 Class Notebook by the
    mapped route with a signed-in persistent Chrome profile and prints one
    page's text. Success means collection can move to the Mac. Then follow
    the revised build order at the top of this section. Written as
    `tools/spike_onenote_text.py` (setup and run steps at the top of the
    file); waiting for Shingo to run it on the Mac.
13. Step 6's posting test still matters under the local-first goal: the
    scripts need the same answers (what Return sends, how MySchool saves).

## Open questions

- Whether to escalate the Conditional Access block to RCS IT, or proceed
  with browser-automation-only permanently.
- How much Shingo wants to spot-check vision-transcribed OneNote pages before
  trusting the method unattended at full class scale.
- MySchool's exact save/publish control for the Assessment tab (cut off
  during mapping — needs one more look).
- Whether to set MySchool levels via the Grade Grid's quick cell dropdown or
  the Assessment tab's per-student card (leaning Assessment tab, since
  comment entry lives there too — see "What Phase B still needs" above).
- Whether Teams' plain "Return" notifies the student. The dropdown's
  options are now known (see Phase B above).
- Which Claude account becomes the main one for this work. The RCS
  organization account can't see the Assessment Project or the account-level
  skills, which is why the repo now carries the plan and the skill files.

## Session log: 2026-10-30, RCS account

Worked from the RCS organization Claude account, with the repo folder
connected through the desktop app.
- Removed five leftover git lock files from `.git` (left by an earlier
  session's commit). Git works again; `main` matched `origin/main`.
- Signed in to Microsoft in Claude's browser pane. Claude in Chrome was not
  reachable from this account.
- Teams: mapped the Return dropdown; confirmed the global-Assignments route;
  found that SharePoint-link submissions can't be opened from Claude's clicks.
- Class Notebook: found a route that avoids the blocked popup (see above)
  and read one test student's Task 2 page.
- Feedback app: opened it in the browser pane and loaded the assignment
  name, course (ICT 9 Q1, which set the department to ADST), the student
  from the class list, the student's work (transcribed), and the Task 2
  instructions from Teams' Student view. Level left unset; nothing generated
  yet.
- Drafted `skills/phase-b-upload/SKILL.md`.
- Added LM Studio as a second local engine in the app and `feedback.py`
  (Model menu grouped by engine; switching unloads the other engine's
  model). First LM Studio timing: 10.11 tokens/s, 84.30 s to the first
  token, for one paragraph.
- 2026-10-31: removed LM Studio and its MLX model; Ollama stays the engine.
  The app's LM Studio support remains for later tests.
- Nothing has been posted to Teams or MySchool yet.

## Related
- `TEAMS-ASSIGNMENT-SETUP.md` — how to set up the Teams Assignment itself so
  this downstream pipeline has clean, parseable input.

## Running the automated tests

`python3 tests/run_all.py` runs every `tests/test_*.py` against synthetic fixtures (239 checks in 8 files). Quit the real app and Ollama first: the tests use ports 8765 and 11434. Needs Playwright with Chromium (set `TEST_BROWSER_CHANNEL=chrome` to use installed Chrome in a temporary profile).

The tests use a temporary HOME and data folder, a stand-in model and a stand-in Teams runner. `SF_FORBID_BROWSER=1` makes the Teams reader refuse to launch any browser. They never open your signed-in Chrome profile, contact Teams or touch the real Assessment folder. Live checks are separate and manual (`tools/spike_teams_assignments.py`, or an import through the app). These results have not yet been reproduced on your Mac. See `tests/README.md`.
