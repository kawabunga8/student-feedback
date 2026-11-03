# Assessment Workflow — plan

## Current prototype status — 2026-11-02

Build small working prototypes, verify one real case, then refine. The dated logs below preserve earlier states; this summary is the current starting point.

| Capability | Built and verification scope |
|---|---|
| Assignment design, Course Hub context, saved sessions and approvals | Built; server rechecks approvals and edits invalidate review. Teacher chooses every level. |
| Background drafting and optional Teams rubric | Built. Real Qwen2.5 14B benchmark accepted 2/7 invented cases, neither first try; missing criterion names blocked five. Criterion-by-criterion reliability needs refinement. |
| Create unpublished MySchool assignment | Built: load courses, choose type/date/outcomes, preview, explicit Save and read-back. 32 synthetic checks pass. Live course loading works; live Save awaits a teacher-selected due date. |
| Create unpublished Teams draft | Built: Design preview, explicit confirmation, background creation and Drafts read-back. One invented Senior Band draft saved and checked live after recovering its empty trial draft. Publishing, dates, attachments and rubric creation are not automated. |
| Teams assignment/rubric reader | Wording/counts verified on Task 4 and Graphics Design Challenge; rubric descriptors verified on the latter only. Attachments are listed, not read. |
| Typed OneNote collection | One short typed page verified through the app, including save/reopen. Up to 40 pasted page addresses and roster matching are built and synthetic-tested; broader live collection is unverified. |
| Forms file import | One real English quiz export verified through parser and temporary upload UI: one response, 11 question blocks, score separate and no level assigned. Direct Forms web import and image/file answers are not built. |
| Per-student Teams statuses and Class overview | Built; synthetic-tested. Statuses are assignment-bound. Overview completion reflects manual posting ticks, not independent destination verification. |
| One-student Teams posting | Preview, explicit confirmation, Return and read-back built. Controls inspected live read-only; no live posting/notification behaviour verified. |
| One-student MySchool posting | One or several teacher-selected criterion levels, preview, explicit Save and read-back built. No live save verified; publishing is preserved. |
| Image transcription and transcription benchmark | Built; synthetic-tested only. PNG/JPEG to a local Ollama vision model; teacher edits and roster-matches the text. Not automatic OneNote image capture. Each image preview is bound to the saved assignment open when it was chosen; a switch discards it (synthetic-tested). |

Mandatory review remains in place. Bulk automated posting stays disabled. Quality reports, raw exports, student work and staging folders must stay out of commits.

**Validation:** the 17-file Mac run had 586 passes and two UI failures; MySchool and Teams statuses passed separately (44/44 and 29/29), covering 591 checks across runs. This was not a clean combined pass. The newer overview/vision tests are recorded separately below; earlier cloud counts do not establish a Mac pass.

**Next milestone:** complete one student end to end: collect work, draft feedback, teacher edits and selects the level, teacher approves, read-only Teams posting preview, then an explicitly confirmed Teams Return and MySchool save with read-back. No live posting or save is verified yet. In parallel, evaluate the criterion-by-criterion prompt refinement against the 2/7 baseline; no completed comparison result is available. Three-run model consistency, broader collection and real image transcription remain open.

## Historical handoff notes (2026-10-30)

Use the current prototype summary above for the active punch list. The following notes describe the earlier build.
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

*Historical (2026-10-30). This list predates the prototypes in the dated entries below; for the current state see "Current prototype status — 2026-11-02" at the top.*

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

*Historical plan (2026-10-30 and 2026-10-31). Much of it has since been built or revised; the current next steps are in "Current prototype status — 2026-11-02" at the top.*

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

### Read-only Teams reader: BUILT as a first version (2026-11-01); one live import through the app, compared by hand for one assignment (see the 2026-11-01 result below); everything else still unverified.

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
- **Live import result (2026-11-01, one class, one assignment: "Task 4"):** listing assignments returned 15; reading Task 4 through the app reached Student view after two navigation-timing fixes (the reader now waits for the address to settle, ignoring query and fragment). Compared by hand with Teams' Student view: instruction wording matches (all seven sections in order through the final reflection, 1,855 characters, no missing wording, no reference file name or flashcard-widget text); reference PDF listed by name and marked not read; title, class and status counts as expected. **Verified for this assignment only:** instruction wording and counts. **Known differences:** (1) Teams' bullet symbols and bold styling are not preserved (bullet items come through as separate lines); (2) the due time read by the app's Chrome (3:00 PM) differed from the time shown in the teacher's own Teams browser (4:00 PM); the cause is not confirmed, so treat the app's due time as unreliable and take it from Teams. **Still untested:** other classes, other list tabs and statuses, per-student statuses, rubric and attachments, and a full end-to-end run on any other assignment.
- **Due-time recheck (2026-11-01, after the teacher changed the computer locality/time setting):** the Mac reports `America/Vancouver` (UTC−07:00 at the check). After refreshing Teams and performing a fresh Task 4 read through the app, the Teams list, roster, Student view and app preview all showed **November 4, 2026, 4:00 PM**. The earlier 3:00/4:00 discrepancy no longer reproduced. The precise cause was not established; Teams account timezone settings were not inspected or changed. This verifies agreement for this read only, not general timezone handling.
- **Rubric (2026-11-01, second assignment: Graphics Design Challenge, Computer Programming 11):** Teams showed Rubric → View rubric with Skills and Make descriptors (Emerging–Extending); the app had wrongly said "no separate rubric section was shown" and imported none of it. Instruction wording, title, class, due date and counts matched. **Implemented:** the reader detects Teams' "View rubric" button (plus a "Rubric" heading directly before it, at the end of the instructions or inside the Points, Reference materials or My work blocks) and keeps it out of the instructions and points; a teacher's own word "rubric" is never touched. The preview and the saved record distinguish three states: `absent`, `present_unread`, `read`. **Not implemented:** reading the rubric itself (it sits behind the View rubric button, so it needs one more read-only click and a live look at the dialog). The `read` state is exercised only with a synthetic result. Live check of the first detection (text lines only): FAILED on the Graphics Design Challenge (reported no rubric button). Second attempt (2026-11-01): the reader now waits for the Student view text to stop changing (about 8 s at most), then also checks buttons/links by name (read-only, no clicks) and, if it sees something rubric-like that isn't exactly \u201cView rubric\u201d, shows what it saw in the preview. Live check of this second attempt (2026-11-01): PASSED on the Graphics Design Challenge (preview: rubric present in Teams, not read; counts 8 students, 7 viewed, 1 not turned in). Which part fixed it (waiting for the page to settle, or checking the controls) was not isolated. Verified for that one assignment only; rubric descriptors are still unread.
- **Rubric spike (2026-11-01, live, Graphics Design Challenge):** exactly one "View rubric" button (found in the page's controls, not in its text, which explains the first detection miss). One click opens a dialog in the same frame (no new tab, address unchanged), 1,655 characters over 39 lines: a title, then per criterion a name paragraph and a listbox "Criteria for <name>" whose options each hold a level word and a descriptor paragraph (two criteria, four levels each: Extending, Proficient, Developing, Emerging). Not a table. Wording matched the rubric seen in Teams. Report: `tools/spike_teams_rubric.py` (read-only; one extra click; closes the browser without clicking Close).
- **Rubric reading BUILT from that structure (2026-11-01), live run PASSED for one assignment (below):** when the "View rubric" button was found, the reader clicks it once (the only added click kind, exactly one such button required), reads each "Criteria for X" listbox into criterion name plus four level/descriptor pairs, and validates the result (title present; every criterion named once, matching the heading above it; exactly the four expected levels, each with a descriptor). Anything else (missing level, odd level word, no dialog, two buttons) leaves the rubric "present, not read" with a reason, and the instructions and counts are still returned; a new tab or a changed address stops the read. The rubric is kept apart from the instructions: shown in its own collapsed preview row ("Show full rubric") and saved in the record under `teams.rubric`; it is not imported into any field yet. Tested only against invented rubrics served from memory (tests/test_teams_rubric.py, plus the preview and saved-record checks). **Live check (2026-11-01, Graphics Design Challenge, through the app):** the expanded preview matched the Teams spike report: Skills and Make, all eight descriptors, exact wording and level order; rubric text stayed out of the instructions; status counts matched (8 students, 7 viewed, 1 not turned in). **Verified for this one assignment only.** **Not yet verified:** rubrics with other level counts or wording, rubrics on other assignments or classes, assignments with no rubric through this code path on a live read, and whether Teams ever shows the rubric differently (for example per-student).
- **Rubric feeds drafting (2026-11-01, built; not yet run with a real model):** an opt-in checkbox next to the drafting buttons, "Use the Teams rubric as assessment criteria" (off by default; unavailable unless a rubric was read from Teams for this assignment; applies to both Generate and background drafting). The rubric comes from the SAVED assignment record (never from the page) and is sent to the model as its own "Assessment criteria" block with every criterion and all four descriptors in full, separate from the assignment text and the learning standards. The model is told to name each criterion, describe evidence from the student's work and give a next step, and never to copy descriptor wording, name or imply a level, or say whether the work "meets" anything: only the teacher chooses levels, as before. Checks that trigger a retry (max two): any level word (existing check), 7+ consecutive words copied from a descriptor, a criterion not mentioned by name, invented quotes (existing). A background job records a fingerprint of the rubric when queued and refuses to continue if the saved rubric changes. One-sentence drafts leave the rubric out (they can't address each criterion). **Review fixes (2026-11-01):** (1) the checkbox is saved per assignment in the record (`teams.useRubric`), reflects the record when you switch assignments, and marks the assignment unsaved when changed; (2) the draft-outdated warning now also notices the rubric being switched on/off or changed, and a review approval records the setting and the exact rubric used: the server voids the approval if the saved setting or the rubric's wording changes ("Teams rubric setting" / "Teams rubric" reasons; approvals saved before this count as not using a rubric); (3) a draft that, after the retries, still names or implies a level (level words), copies descriptor wording, or skips a rubric criterion is REJECTED with a plain reason, not returned as the "best" attempt: in a background job that student is marked failed and the others continue. This rejection applies to the level-word rule with or without a rubric. Other checks (invented quotes, missing headings, uncovered teacher criteria) remain best-effort. Limits: the checks are wording checks, so the teacher still reviews every draft; wording quality with the real local model (qwen2.5:14b) is untested; a rejected draft means more failed students if the model is weak.
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

`python3 tests/run_all.py` runs every `tests/test_*.py` against synthetic fixtures (currently 447 checks in 12 files). Quit the real app and Ollama first: the tests use ports 8765 and 11434. Needs Playwright with Chromium (set `TEST_BROWSER_CHANNEL=chrome` to use installed Chrome in a temporary profile).

The tests use a temporary HOME and data folder, a stand-in model and a stand-in Teams runner. `SF_FORBID_BROWSER=1` makes the Teams reader refuse to launch any browser. They never open your signed-in Chrome profile, contact Teams or touch the real Assessment folder. Live checks are separate and manual (`tools/spike_teams_assignments.py`, or an import through the app). The full suite passed 447 checks in 12 files locally on 2026-11-02. See `tests/README.md`.

## Live no-rubric regression: 2026-11-01

Re-read Task 4: Make & Skills through the app with the rubric reader enabled. No rubric row appeared and Source reported no rubric button. The full 1,855-character instructions retained all seven tasks through the final reflection. Counts remained 24 viewed, 2 not turned in and 2 turned in (28 total). The reference PDF remained listed by name and marked not read. Saved the local assignment record, reloaded the app and confirmed the saved no-rubric state survived. Verified for this assignment only; nothing was changed in Teams.

## Local-model rubric drafting trial: 2026-11-01

All 320 synthetic checks passed locally. A direct Qwen2.5 14B trial used one invented submission with the captured teacher rubric enabled and disabled; no student records were changed. Both drafts completed. The rubric-enabled draft named Skills and Make but included “move toward proficiency”, which the current level-word check did not reject, and introduced an explanation expectation not explicit in the supplied task. Rubric drafting remains a prototype requiring teacher review. Follow-up: add this failure as a regression case, strengthen the level-word check and repeat the trial.

## Collect student work, version 1 (prototype): 2026-11-01

Built and tested on synthetic pages only; not yet run against a real notebook page through the app.

What it does: Collect step > OneNote card > "Collect from OneNote…". The teacher pastes the address of ONE student's typed Class Notebook page (https, sharepoint.com, Doc.aspx). A background job (`onenote_read`) opens it read-only (`action=view`) in the shared automated Chrome profile, scrolls it top to bottom and back, and reads the text of OneNote's own page area. The preview shows the student-name hint (from the address, editable), page, size, an UNVERIFIED completeness note, and the non-text items found (images, drawings, files, frames: listed, not read). "Add as a student card" fills an empty card for that name or adds one. The text is shown in full only when asked.

Guardrails: read-only (no typing, no clicks; the page is only opened and scrolled); the shared browser lock ("browser profile in use"); stops, returning nothing, if OneNote's page area is not found (it never falls back to whole-frame text, which would include menus); a sign-in page leaves the job "waiting for sign-in"; AADSTS policy blocks are reported as blocked. Student text goes only to the job's sidecar in the assignment's own Assessment folder (`.jobs/`), never to the journal, logs or error messages. The assignment must be saved first.

Known limits of version 1: one page per run; typed text only; handwriting and pictures are not read (listed when detected); multi-box pages untested; pages with very little text may be refused (the reader waits for the frame to hold at least 200 characters); task wording on the page is not separated from the student's work; the source reference (address, read time) is shown in the preview but not saved on the card; the text stays in the job sidecar after delivery. Text extraction was verified live earlier on one real typed page (tools/spike_onenote_text.py); the app path has not been.

Tests: tests/test_onenote_collect.py (63 checks): address checks, read-only address, page identity, text cleaning; run() against synthetic pages (no clicks or key events reach the page, menus excluded, image listed as not read, area-missing, empty, sign-in, redirect, AADSTS stops); job type, folders and privacy; the dialog. Whole suite: 392 checks in 11 files, passed locally on 2026-11-01.

### Collection preview assignment guard (2026-11-01)

The collection dialog binds each preview to its assignment. Switching assignments clears the preview and ignores late responses; Add checks the assignment again. Returning to the original assignment can recover its undelivered result. The collector suite passed 63/63 checks locally, including three assignment-switch regressions. The earlier full local run had 379 passing checks and one transient Failed to fetch page error; the collector rerun passed before this change too. The final full suite passed locally: 392 checks in 11 files.

### Intended Teams class picker (2026-11-01)

The Design context uses a select instead of a placeholder-only text box. It fills a unique confirmed class match for the selected Course Hub course and school year, offers multiple confirmed matches for selection, and clears a known class belonging to another course. With no match it offers Choose class from Teams through the existing read-only import/mapping dialog. Saved unconfirmed class text remains visible as such. All 69 assignment-record UI checks passed locally, including four new picker/course-switch checks; no JavaScript errors. The final full suite also passed locally (392 checks in 11 files).

### Forms quiz submission type (2026-11-01)

Design → Submission setup now offers Microsoft Forms quiz. The existing assignment design record persists this type. Student instructions direct students to the quiz linked in Teams, with Submit in Microsoft Forms as the default completion action. Notebook and attachment fields are hidden for this type; custom completion wording is preserved. A teacher-only note explains that Forms-to-Excel response import is not implemented. JavaScript syntax and diff whitespace checks passed; no live Forms extraction is included.

### Final local regression run (2026-11-01)

392 checks passed in 11 files, zero failed, using installed Chrome and synthetic data. Forms selection, hidden fields, completion wording, student-preview instructions and restoring Both/Notebook are covered. The strengthened collector isolation assertion verifies that the original read stays offered while the other assignment has no job. The earlier transient Failed to fetch page error did not recur. Live OneNote collection through the app remains unverified; Forms response import remains unbuilt.

## MySchool read-only capacity check: 2026-11-01

Staff SSO worked in the in-app browser. Navigated Grade Grid → View All Assignments → EarMaster Rhythm Check — FromTheStart → Assessment. The opened assignment is linked to Concert Band 12 (the all-assignments list includes other courses). Assessment exposes level controls EXT+/EXT/PRF+/PRF/DEV+/DEV/EMG+/EMG/NYM/IE, editable comment textareas, a status selector including Not yet graded and Graded, and a Save control. Planning shows publication status No. No levels, comments, statuses or publication settings were changed and Save was not clicked. Browser access and DOM readability are verified; successful writes, persistence after save and Grade Grid read-back remain unverified. The span-based level controls will need scoped selectors.

## MySchool one-student posting pilot (2026-11-01)

Built: Export & posting → Post reviewed assessment to MySchool. Requires a saved assignment/session, a server-current approval, a teacher-selected level and separately reviewed MySchool comment. The teacher enters the exact MySchool assignment edit URL, title, course and student display name. Preview reads the existing values and publication state. Save requires a separate explicit checkbox and button. Only one criterion is supported; multiple/missing students, criteria or controls stop the operation. Optional Graded status is an explicit choice; otherwise status is preserved.

The worker uses the tools Python, existing automated Chrome profile and shared browser lock. Immediately before edits/Save, a child-process handshake makes the server revalidate approval and cancellation while holding the session-save lock. The lock is bounded by a 40-second save/read-back timeout. Previews expire after ten minutes and are single-use for Save. If values already match after a lost response, a fresh read verifies without another Save. Save jobs cannot use generic Resume and are never automatically retried. The browser reopens the assignment and checks the exact level/comment/status, other students and publication state before reporting verified. Assignment publishing is never changed. Bulk automated posting remains disabled; this explicit one-student pilot is separately guarded.

Requests/results containing names and comments live only in the assignment Assessment .jobs sidecars. The job journal and preview-claim ledger hold no names, comments or work. Browser failures use fixed messages, not raw page errors. No live MySchool save was performed during development. Real save behaviour remains unverified; this is a pilot, not batch posting. Keep the dialog open until the result; completion ticks remain manual after checking the receipt.

Tests: 34 new synthetic checks cover URL restrictions, browser-off guard, exact destination identity, duplicate names, single-criterion limit, stale/expired previews, approval revocation immediately before Save, save/read-back, unchanged other students/publication, uncertain save outcomes, idempotent read-back, confirmation/reuse/resume guards, journal privacy and GUI preview/confirmation/receipt. They run on an alternate local port with temporary HOME and invented MySchool pages, without contacting MySchool.

Validation for the MySchool addition: full local run passed 425 checks in 12 files with zero failures. After adding the final identity-reset check and published-assignment warning, the targeted MySchool suite passed 34/34. Current expected full-suite total is 426; the full suite was not repeated for that last UI change. No live records were changed.

## Live in-app OneNote collection: 2026-11-02

Passed for one typed Stage 4 page in the ICT 9 Q1 notebook, collected under the saved Task 4 assignment. The app returned 512 characters. Comparing the entire expanded preview with the source page-content DOM gave an exact match after the collector’s whitespace normalisation. The student-name hint matched the section in the page address. No images/drawings were detected; completeness remains UNVERIFIED rather than a claim about handwriting or other non-text content. Added one local student card, observed the session save, and reopened the app in a fresh tab: student identity and all 512 characters were unchanged. Zero drafts, approvals or levels were created; nothing was posted or changed in OneNote, Teams or MySchool. No student names, text or page addresses are recorded in this log. Verified for this one short typed page only. Handwriting, pictures, long pages requiring scrolling, pages with more than one text box, whole-class navigation and other page layouts have not been verified through the app.

## Directional level-word regression: 2026-11-02

Added a wording check for scale levels described as destinations, including the real-trial phrase “move toward proficiency” and variants using toward/towards, approach, reach, achieve, attain, become, aim and progress. Ordinary actions such as developing ideas and extending a melody remain allowed; quoted student evidence follows the existing quotation exemption. The system prompt tells the model to describe the specific improvement instead. Persistent violations are rejected after retries, with or without a Teams rubric. This remains a wording check, not a guarantee against every implied level judgement.

Verification: rubric-drafting suite passed 52/52; full local suite passed 447 checks in 12 files with zero failures. A subsequent real Qwen2.5 14B trial used the same invented submission and captured teacher rubric as before. Three attempts contained no detected directional level wording, but the best attempt still omitted the criterion name Skills, so the generator rejected it. No draft was inserted into a student card, no teacher level selected, and no MySchool action performed. Consistent usable output from the real model remains a separate tuning task. App and Ollama restarted.

## Prototypes added 2026-11-02 (synthetic-tested only; nothing live-verified)

- **Multi-criterion MySchool posting.** The MySchool form now takes one level per criterion, in page order (`codes`). The preview lists "n. label: existing -> chosen". If the criterion count on the page differs from the levels given, nothing is saved. Matching is by page order; criterion labels are best-effort until seen live.
- **Multi-page OneNote collection.** "Collect from OneNote..." accepts up to 40 page addresses (one per line). Pages are read one at a time (items p1..pN) with per-page failure, cancel between pages, and sign-in resume from the failed page. A preview table lets the teacher match each page to a student before adding. Still read-only; completeness is always UNVERIFIED.
- **Teams per-student statuses.** "Read Teams statuses" reads the assignment's roster rows (name + status), complete only when the row count equals "N results found". Statuses are shown on the student cards. Read-only.
- **Teams grading panel spike (not posting).** `tools/spike_teams_grading_panel.py --class ... --title ... --student "Last, First"` opens one student's panel read-only and writes a name-masked report. Run it on a low-stakes assignment with an empty Feedback box. Teams feedback posting is NOT built until the report shows what the Feedback box and Return dropdown do (and whether Return notifies the student).
- Cloud test run: 516 checks in 14 files, 0 failed. Run locally with the app and Ollama stopped before committing.

## Prototype fixes and one-student Teams posting (2026-11-02)

The latest prototype adds Export & posting → Post reviewed feedback to Teams. It uses the assignment's saved Teams class/title and imported class/assignment IDs. Select one server-approved student, enter their exact Teams roster name, then read a preview. The preview shows the exact destination, existing feedback and approved feedback separately. A separate confirmation checkbox and Post feedback and Return button authorise replacement and Return. Return may notify the student. There is no bulk posting, level selection by the model, or use of revision/excused/Copilot/points controls.

Live read-only inspection of Task 4 confirmed the submission link, selected-student control, dialog containing #editorAnchor (contenteditable textbox labelled Feedback), Return button and menu options. No feedback was entered and Return was not clicked. The live Return transition, any confirmation dialog, autosave timing and persistence are still unverified. The prototype stops with an uncertain-outcome message if read-back cannot confirm the same submission under Returned with the exact feedback; a click alone never counts as success. Completion ticks remain manual after checking.

Posting jobs use the shared browser lock and tools Python. Previews expire after ten minutes and are single-use. The server checks the approval and saved Teams destination again immediately before any editor change, holding the same bounded approval lock used by the MySchool pilot. Teams can autosave feedback before Return: failures may therefore leave draft feedback. Jobs never automatically retry or allow generic Resume; check Teams and create a fresh preview after an uncertain outcome. Names and feedback stay in the assignment's Assessment/.jobs sidecars, not the journal or preview-claim ledger. Bulk AUTOMATED_POSTING remains False; the explicit one-student pilot is separately guarded.

Review fixes: Teams statuses are tied to the assignment and cleared on switching/new assignments. Batch OneNote Add checks every selected name against the current Course Hub roster and rejects duplicate resolved students, including when the roster is missing. The grading spike no longer falls back to editor contents/input values for field labels; short names are masked, raw browser errors are suppressed and direct calls respect the browser-off guard. The MySchool test model response now includes the required offline-engine list. Synthetic regression tests cover these fixes and the posting pilot; live posting remains unverified.

Validation for this prototype: 552 individual synthetic checks across 15 files passed across the broad run and targeted reruns. The combined run reported 544 passes and two UI-file failures (MySchool's unscoped Reviewed student selector, and a Teams pilot launch timeout). After scoping the MySchool selector, its file passed 44/44. The final Teams pilot file passed 31/31 on its targeted rerun. This is not recorded as a clean single-pass full-suite run. The 85 collector, 29 Teams-status and 13 grading-spike checks passed. No live posting was exercised. App/model services were stopped during tests and restored afterwards.

## Forms response import and draft-quality harness (2026-11-02)

- **Forms response import (read-only, local file).** "Upload files..." now recognises a Microsoft Forms response export (.xlsx or .csv: columns Id, Start time, Completion time, plus questions). One card per named student; the work is each question with the answer. Forms' own columns (times, ids, emails, auto-scores, quiz feedback) are kept out of the work. A quiz's Total points is shown on the card as "Forms auto-score: not a level, not sent to the model". Anonymous exports add no cards and say why. A student who submitted twice: the last response in the file is loaded and the teacher is told. Blank responses are skipped and counted; answers over 4,000 characters are cut and counted; at most 300 responses and 80 columns. Nothing contacts Forms. Names still go through the usual class-list matching. Not built: reading Forms directly from the web, per-question scoring, picture or file-upload answers (they arrive as links and are not read).
- **Draft-quality harness.** `python tools/draft_quality.py --model qwen2.5:14b --runs 3` runs the app's own drafting on seven invented cases (strong, thin, off-topic, a hidden instruction in the work, a private note, a set level) and writes a report to `quality-reports/` (git-ignored; invented text only). It reports how often drafts were accepted, how often on the first reply, why drafts were refused, and problems the app does not block (quotes the student never wrote, numbers not in the work, a checklist item missed, hidden instruction followed, private note leaked, generic praise, wrong length). A measurement for choosing a model or tuning the prompt, not a grade. Needs Ollama (or LM Studio) running; `--cases` picks cases, `--length` picks the format.
- Tests: forms_import 21 checks, draft_quality 18 checks (scripted stand-in model, no network). Cloud full run: 591 checks in 17 files, 0 failed.

## Class overview (2026-11-02)

Draft & review now starts with a read-only "Class overview": one row per student card with their Teams status, level and the next thing to do (add work, match to the class list, resolve a duplicate, draft, choose a level, review, review again, ready to post, done). Order of checks: no work, not matched, duplicate, draft failed, instructions changed, no draft, no level, changed since review, not reviewed, then posting ticks. A filter shows Needs attention / Still to do / Ready to post / Done; clicking a name jumps to that card. It reads the page's own cards, sends nothing, changes nothing, and never copies work or feedback text. Files: ui/overview.js, a CSS block in ui/workspace.css, script tag and allowlist entry in app.py. Test: tests/test_class_overview.py (12 checks). Cloud full run: 603 checks in 18 files, 0 failed.


## Local Forms and real-model checks (2026-11-02)

Downloaded one real Excel response export from the personally owned Meaning of Life quiz in Microsoft Forms (the two Teams class copies had zero responses). The export has one named response, 40 columns and 11 question columns: ten answered, one blank. The app's parsed question/answer text matched an independent XML read exactly (1,251 characters); the exported name matched, and metadata/points/quiz-feedback columns were excluded from the work. A temporary local app view with saving, generation and posting disabled produced one ungraded card with 11 question blocks and a separate Forms auto-score note. The source workbook was unchanged. No real response was put into the model, saved to a class session, copied into tests or added to git. This verifies one English quiz export only; other layouts, real CSV exports, file/image answers and class-roster matching are not covered by this live check.

The Mac's 17-file run reported 586 passes and two UI failures: MySchool's posting launch timed out; the Teams-status UI reported transient Failed to fetch errors. Each file then passed separately (44/44 and 29/29), covering all 591 checks across the combined run and reruns. This is not a clean single-pass full-suite result. A separate Class overview addition arrived during validation; its newer 18-file/603-check claim has not been verified by this run.

Ran tools/draft_quality.py against real local qwen2.5:14b, paragraph length, one run per seven invented cases, without changing the prompt or model. Two of seven drafts were accepted, neither on the first try; five were refused for omitted rubric criterion names. Mean replies per draft: 2.71 (19 model replies in total). Both accepted drafts had no automatic audit flags, which does not establish full quality: the audit does not establish a specific evidence-based next step for each criterion. All four design cases were refused; the mixed essay and teacher-level-set essay were accepted after two replies, and the off-topic essay was refused. Rejected-case outputs are not retained by the current harness, so injection/private-note outcomes cannot be inferred from rejection alone. This is a first functional benchmark, not the planned three-run stability measurement. Report: quality-reports/20261102-062716-qwen2.5_14b.md, with a baseline sidecar recording the model digest and source fingerprints. Both are git-ignored and contain invented work only. App and Ollama were restored. No grades or feedback were posted, and nothing was committed.

## Pre-commit documentation and targeted checks (2026-11-02)

Updated README, the current workflow/architecture summaries, workspace notes and test coverage documentation to describe the built prototypes and distinguish live checks from synthetic coverage. The newer Mac targeted tests passed: Class overview 12/12, transcription error scoring 7/7 and image-transcription prototype 19/19. These do not establish real-model image accuracy, live posting or a clean combined 20-file run. Image previews are not yet bound to their original assignment; add that guard before normal collection use. **(Since fixed: see "Image-preview assignment guard (2026-11-02)" below.)** Earlier cloud/full-suite counts remain historical results, not substitutes for this narrower Mac verification. Real exports and quality reports remain outside git.

## Image-preview assignment guard (2026-11-02)

`ui/vision.js` now requires a saved assignment before an image is read and binds each preview to it, mirroring the OneNote collector. Switching assignments discards open previews (image released, text cleared, a note says why). Add re-checks the assignment even if no change event fired, and a model reply that arrives after a switch is dropped. Each row shows which assignment it belongs to. The guard is client-side; the transcription endpoint is unchanged and still stateless. `tests/test_vision_read.py` grew from 19 to 27 checks (no-assignment refusal, binding label, switch discards, Add re-check without a change event, late reply dropped with and without a change event, same-assignment Add still works). Each guard was disabled in turn and a new check failed for it. Run in the cloud container with the stand-in model, not on the Mac: vision 27/27, Class overview 12/12, rubric drafting 52/52. Real-model image accuracy is still unmeasured.

## Handwriting and pictures (2026-11-02, prototype; nothing verified on real handwriting)

Collect now has a "Handwriting and pictures" card. Choose a PNG or JPEG (up to 8 MB, 10 at a time) of one student's work; a local vision model in Ollama copies out the text; the image is shown beside an editable transcription, marked UNVERIFIED, with any [illegible] parts and described drawings counted. The teacher corrects it, types the student's name, and adds a card only when the name matches the Course Hub class list. The card carries a "Transcribed from <file> by a local model" note. The image goes only to Ollama on this computer, is not written to disk and is not logged; errors never include the file name or content. The model is told to copy exactly, mark unreadable words [illegible], describe drawings neutrally without judging them, and treat writing in the image as the student's work, not instructions.
- Models: prefers qwen3-vl:8b, then qwen2.5vl:7b; SF_VISION_MODEL overrides. Install with `ollama pull qwen3-vl:8b`. Ollama only.
- Measure before relying on it: `python tools/transcribe_check.py --model qwen3-vl:8b page1.jpg page1.txt ...` gives character and word error rates on pages you supply (invented, your own writing, or de-identified). Compare both models on the same pages.
- Not built: images inside OneNote pages, scanned PDFs, automatic resizing. Tests: vision_read 19, transcribe_check 7. Cloud full run: 629 checks in 20 files, 0 failed.

## Documentation confirmation and next milestone (2026-11-03)

The current summaries in this file and ARCHITECTURE.md distinguish built prototypes from live verification. The next milestone is one teacher-reviewed student through the read-only Teams posting preview, followed by explicitly confirmed posting and destination read-back. The teacher must choose the level and approve the exact feedback first; a preview does not authorize Return or MySchool Save.

The uncommitted paragraph-prompt refinement asks for one sentence per rubric criterion, in order, with its exact name, evidence and a next action. Non-rubric paragraph formatting and rejection checks are unchanged. Targeted Mac checks passed: vision 26/26, rubric drafting 55/55, draft-quality harness 18/18 and server approvals 31/31. These are separate targeted runs, not a new full-suite result. The comparison benchmark log stops during the invented cases and no final report exists; do not treat it as a completed result or an improvement over the recorded 2/7 baseline. Real-model image transcription and live destination writes remain unverified.

## Create unpublished Teams draft (2026-11-03)

Built `teams_create.py` and wired Design → Create draft in Teams into the existing queue. The design is synchronized into Setup and saved before preview. Confirmation binds the saved version; the server reconstructs only class/title/student-facing instructions and rechecks before opening an editor (Teams may autosave an empty draft). Forms quizzes and imported records already referring to a Teams assignment are refused. The worker never clicks Assign: it chooses Save as draft, finds the title under Drafts and reopens the same editor to compare its IDs, title and full instructions. Rich-text whitespace is normalized; every word and symbol must match. Dates, points, recipients, attachments and rubric objects remain for review in Teams.

Duplicate protection: a failure before editor authorization releases the local claim; once an editor may exist, a fresh creation is blocked. For a failed attempt, the optional existing-draft URL reuses the same editor instead of creating another. Only HTTPS Teams editor URLs are accepted, query/fragment are removed, class must match, and existing contents must be empty or already match the requested title/instructions. No automatic retry or generic Resume is allowed.

Validation: 30 new synthetic checks pass on the Mac (including delayed menus/editor, no publishing, class/address checks, exact-word read-back, stale/repeat requests, teacher-only exclusion and recovery without overwriting different text). Existing assignment UI 74 checks and queue HTTP 22 checks passed separately before the final timing/recovery refinements; no new full-suite result is claimed. Python compilation, JavaScript syntax and diff whitespace checks pass.

Live trial: teacher authorized an invented assignment. The app saved “Prototype draft — Senior Band Rhythm Reflection” locally for Band 10 and targeted the Senior Band Teams class. Early attempts stopped on ambiguous rail buttons, delayed controls, class stored in a placeholder, and rich-text update/spacing. The worker now scopes the Apps navigation, waits for controls, checks the Assign to placeholder and blurs/waits for edits. A trial-created empty draft was reused via recovery; the app reported verified unpublished success after reopening it from Drafts. No student work, levels, feedback or Assign/publish action was involved. Earlier untitled trial drafts were not automatically deleted; inspect them in the class-specific Drafts view (the global list omitted them). This verifies one draft after recovery, not broad fresh-create reliability across classes or quiz workflows. App and Ollama are running. Changes are uncommitted.

Final live read-only recheck in the normal Teams browser confirmed the prototype title under Senior Band → Drafts. Two Untitled assignment entries remain visible; they were not deleted. The local creation dialog restores the prior verified receipt on reopening and prevents another creation request (covered by the 30th synthetic check). Screenshot proof is outside the repo at /private/tmp/student-feedback-teams-draft.png.

## MySchool assignment-creation prototype (2026-11-03)

Built `myschool_create.py`, `ui/myschool_create.js`, job handlers and Design integration. Saves only the saved title/student-facing instructions plus explicit course/type/due/outcome choices. Publish remains No, no scheduled publication and student email off. MySchool defaults (scale, weight 1 and Do not accept submissions) are displayed and preserved. No student assessments, proficiency levels, attachments or rubric descriptors are created. Preview validity, server write authorization, per-course duplicate protection and reopened verification are described in ARCHITECTURE.md.

Live read-only inspection identified the course/type radios, ISO due-date input, TinyMCE instructions frame, publication/email controls, Options outcome tree and lowercase Save button. The unsaved inspection form was closed without Save. Through the app, Load MySchool courses successfully returned the real course list using the shared Chrome profile. The first live copy is planned for the existing invented Senior Band prototype in D Concert Band 10 (4 Credit); the teacher selected November 23, 2026. Live preview succeeded for Formative, SC - Proficiency, weight 1 and Do not accept submissions; Applying Skills and Techniques and Analyzing were selected. The first live Save/read-back is in progress. No assignment has been saved to MySchool by this new feature yet.

32 new synthetic checks pass on the Mac. Existing MySchool assessment-posting suite passes 44/44. The first Teams-create regression run had a local Failed to fetch / dialog timeout; its isolated recheck passed 30/30. No new combined full-suite result is claimed. Files remain uncommitted; the earlier Teams-creation changes and both staging folders are preserved.
