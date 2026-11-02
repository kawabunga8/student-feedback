# Current workspace prototypes (2026-11-02)

Use WORKFLOW.md's current summary for verification status. The historical implementation notes below describe earlier builds.

The workspace now includes persistent assignment/session records, server-validated approvals, background drafting, read-only Teams assignment/rubric import, typed OneNote batch collection, Forms export uploads, per-student Teams statuses, Class overview, and explicit one-student Teams/MySchool posting pilots. Live posting has not been verified. Class overview completion uses manual destination ticks.

The image-transcription card uses local Ollama and requires edited text plus a roster match before Add. It is synthetic-tested only, is not integrated with OneNote image capture, and needs a saved assignment: each image preview is bound to the assignment open when the image was chosen. Switching assignments discards the preview, and Add and late model replies re-check it.

Forms import was verified on one actual quiz export in a temporary local view. Real-model drafting accepted only 2/7 invented cases in the first benchmark; criterion coverage is the next refinement. Teacher level selection and approval remain mandatory.

# Local feedback workspace

Start the existing app (`python3 app.py`) and open http://127.0.0.1:8765.
The workspace wraps the existing course, import, generation and CSV endpoints.

- Design assignment and the assignment bar: see "Saved assignments, Design step, Choose from Teams" below.
- Setup: assignment instructions, course, term, standards and local model.
- Collect: file uploads (including Forms exports), Assessment-folder import, typed OneNote page collection and the image-transcription card. Collection is read-only and its completeness is always unverified.
- Draft & review: existing student cards and editable drafts, student search, teacher-selected levels,
  separate MySchool comments, explicit review marks and stop after the current generation request.
- Export & posting: CSV exports, a reviewed JSON snapshot, copy-and-tick assisted posting, and explicit one-student Teams and MySchool posting pilots (preview, confirmation, read-back; live posting unverified). Bulk posting is disabled.

Review marks bind student identity, source text, private notes, feedback, level, MySchool comment,
assignment instructions, selected standard labels, grade, course, school year and quarter. Editing these
invalidates the mark. A reviewed snapshot includes a SHA-256 fingerprint of source text. It is a portable
review snapshot, not the future durable posting authorization contract. There is no snapshot import yet.
Once the assignment is saved, student work, drafts, levels, review marks and posting ticks are kept in its session and come back when you reopen it (see "Persistent sessions" below). Until the assignment is saved, nothing is kept between visits: the page says so. CSV exports contain
all generated drafts, including unreviewed ones, and must still be checked before manual posting.

Checked in isolated Chrome with synthetic data and mocked API responses: stage navigation, generation,
review invalidation and snapshot download. Python compilation and JavaScript syntax checks also passed.
Live collection, actual model inference, actual Course Hub and destination posting were not exercised.

## Assisted posting (2026-10-31)

Export & posting lists every reviewed student, sorted by surname (roughly Teams' order). For each one:
**Copy feedback** (Teams) and **Copy comment** (MySchool) put the approved text on the clipboard, with the
level shown as MySchool's code (for example PRF+). **Open Teams** and **Open MySchool** open those sites in
named tabs, reused each time; an optional link per assignment (remembered in this browser) opens a specific
page, and only `https://` Teams or MySchool addresses are ever opened. Shingo pastes, clicks Return or saves
there himself, checks it, then ticks **Done in Teams** / **Done in MySchool**. Copy is disabled until a
student is reviewed, and MySchool copy is disabled when the comment is empty. A tick records the exact
reviewed values: any later edit marks it "Changed after posting" and unticks it, so it's re-done and
re-ticked. Ticks are included in the reviewed snapshot (`posting`). Nothing here posts automatically and
nothing reads Teams or MySchool back; ticks are the teacher's own confirmation.

Checked in a browser with synthetic students: only reviewed students listed, copy to clipboard, ticks and
progress, an edit after posting marked as changed and unticked, re-review and re-tick, a non-Teams address
refused, the MySchool link opened, and ticks in the snapshot.

## Saved assignments, Design step, Choose from Teams (2026-10-31)

The workspace now opens with **1 Design assignment**, and an assignment bar sits under the steps: pick a saved
assignment, **Save assignment**, or **Choose from Teams…**. The bar shows the saved version and whether there are
unsaved changes; leaving the page with unsaved changes asks first. The last assignment reopens when the page loads,
with its name, instructions, feedback focus, course, grade, term and standards. (What a record holds: see
`ARCHITECTURE.md`, "Assignment records".)

**Setup fields.** Assignment name and instructions have **Get from Teams**, course has **Match Teams class**, grade has
**Use course grades**. Under each field is where its value came from and when ("Teams (Student view, pasted)",
"Course Hub (match you confirmed)", "Edited here", …).

**Choose from Teams…** has two routes into the same preview rows. **List my assignments** reads your Teams assignment list in the app's own Chrome window (read-only); choose one and the app reads its Student view and aggregate status counts. The second route is the paste described next, which stays as the fallback. Details are under "Reading Teams" at the end of this file.

**Paste route.** Paste the assignment's Student view (⌘A, ⌘C in Teams) and type or paste the
class name from the Assignments list. Each row shows the Teams value beside what Setup has now, with **Use**;
replacing the instructions asks first and keeps the feedback focus. Reference materials are listed separately, not
added to the instructions. The course row suggests a Course Hub course from the class name for Shingo to confirm
(saved per school year and offered next time); the grade row uses Course Hub's grades only. **Import all assignment
details** fills the name and instructions, plus the course and grade when a confirmed match and a single grade exist,
and says what is left to do. A picker that reads Teams directly (through the local Chrome worker) replaces the paste
in a later step.

**Design assignment.** Context (mirrors Setup's fields); Student task (purpose, directions, the command terms found,
required evidence); Success criteria (each with how students show it and a linked standard, with warnings for more
than 8 words, no evidence or no standard); Submission setup (notebook section and page title, or a file or link, and
how students show they're done); Feedback setup, teacher only (length, what feedback must address, MySchool comment
type and guidance, notes for marking); and Preview: the student-facing title and instructions with **Copy title** and
**Copy instructions**, beside the teacher-only brief. **Use this design in Setup** puts the student-facing
instructions and the feedback focus into Setup and ticks the linked standards. **Create draft in Teams** is shown but
disabled until the browser worker exists; publishing will stay a separate step. The teacher-only brief also sits,
folded, at the top of Draft & review.

Checked in Chromium with a stand-in model and synthetic courses (65 checks, including the two-tab save check described below): paste and read, confirming and reusing a
class match, Import all, field sources, save as version 1, a name-only save recorded as "title", an instructions
change recorded as "content" with the draft flagged and its review mark voided, a reload reopening the same record,
switching to a new assignment and back, the mixed-grade prompt, criterion warnings, the student preview and copied
instructions free of teacher-only text, Use this design in Setup, the brief in Draft & review, refused cross-origin
and non-JSON saves, and no sideways scrolling at phone width.

**Two tabs.** Each save names the version the page loaded. If the assignment was saved in another tab or window in
the meantime, nothing is written: the bar says so and offers **Load version N** (drops the edits on this page) or
**Save mine as version N+1**. Checked with two tabs: the second save refused and the file unchanged, then both choices. Not exercised: live Course Hub, real Teams text (the
sample was modelled on the Student view), and Safari's clipboard prompt.

## Saved sessions (2026-10-31)

Student work no longer disappears when the page closes. Once the assignment is saved, the assignment bar shows
"Session saved …" and the folder under Assessment it is stored in. Reopening the assignment (or the page, which reopens
the last assignment) brings back each student's work, feedback as edited, level, private notes, MySchool comment,
review mark and posting ticks. A change to anything reviewed, or to the assignment's instructions or standards, voids
the review mark as before. Students typed in before the assignment is first saved are kept when you save it. If a
second tab saved the session first, nothing is overwritten: choose **Load the saved session** or **Save mine on top**.
"New assignment" clears the students; the saved session stays.

Checked in Chromium with synthetic students and a stand-in model (39 session checks, plus the 65 earlier checks):
save and reopen, an edit voiding a review mark and staying void after reopening, the posting tick showing as changed,
instruction changes voiding review, two tabs, switching assignments, folder names that try to leave the Assessment
folder, and refused cross-origin and non-JSON saves. The macOS permission check passed on the real Assessment folder
on 2026-10-31 (`check_session_folder.py` saved, read back and removed a test file); a full save and reopen of a real
class through the app has not been done. Not exercised: live Course Hub class lists and very large classes.

Server-side approvals: the server, not only the page, decides whether a review mark still holds (see `ARCHITECTURE.md`,
"Assessment sessions"). If a student is reviewed on the page but not approved on the server (for example you reviewed
against instructions you hadn't saved yet), the session line says so and what to do: save the assignment, or mark them
reviewed again. Checked with 31 further checks: each stored value changed under an unchanged approval, forged and
unreadable approvals, instruction, title, standards and focus changes, a change that shouldn't void anything, re-approval
stamping, posting ticks, and the gated posting reader. `check_session_folder.py` (in the repo root) tests that macOS lets
the app save into your real Assessment folder (passed 2026-10-31).

Background drafting (`ui/jobs.js`): in Draft & review, "Draft in the background" queues the students who have work and no
feedback yet (tick "Redraft" to include the others). The app writes them one after another and keeps going if you close
the page; the panel shows progress with Cancel, and Resume if the app was closed mid-job. Drafts come back into the cards
only if that student's work hasn't changed since you queued them. The assignment must be saved first. Checked with 22
checks over HTTP (restart mid-job, resume without redoing finished drafts, cancel, Ollama not running, refused requests,
no student text in the journal) and 12 in a browser. Not exercised: a real Ollama run, a large class, and a real restart
of the Mac app.

Reading Teams (`teams_read.py`, `ui/assignment.js`): "List my assignments" queues a read-only job. The app opens its
automated Chrome profile, clicks Teams' Assignments icon, and reads the embedded Assignments frame. "Read this
assignment" matches on class and title together, then reads the Student view and the roster page's counts. The preview
shows the instructions, reference materials by name only (**not opened or read**), aggregate status counts (no student
names), and the source: class id, assignment id, read time. Teams shows no separate rubric section on the assignment
tested, so assessment descriptors, if any, are inside the instructions. If Microsoft asks for sign-in, the job waits and
the dialog offers a resume button; if Chrome's profile is already open elsewhere, it says "Browser profile in use".
Checked with 28 parser checks on fixture text with invented names, and 30 checks of the job and dialog with a stand-in
reader. **Not yet run end to end through the app against live Teams**; the spike (`tools/spike_teams_assignments.py`)
read one class and one assignment on 2026-11-01. Extraction is not marked complete until the full output has been
compared with Teams by eye.

Teams posting pilot (2026-11-02): Export & posting → Post reviewed feedback to Teams. One saved, approved student; read-only preview followed by explicit confirmation and Return. The preview shows destination, existing feedback and exact approved feedback. It may replace existing feedback; Return may notify the student. A verified receipt requires reopening the same submission under Returned. No bulk posting or automatic retries. Synthetic coverage is in tests/test_teams_post.py; live posting is not yet verified.
