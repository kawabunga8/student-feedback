# Local feedback workspace

Start the existing app (`python3 app.py`) and open http://127.0.0.1:8765.
The workspace wraps the existing course, import, generation and CSV endpoints.

- Design assignment and the assignment bar: see "Saved assignments, Design step, Choose from Teams" below.
- Setup: assignment instructions, course, term, standards and local model.
- Collect: existing file uploads and Assessment-folder import. Notebook automation is not connected.
- Draft & review: existing student cards and editable drafts, student search, teacher-selected levels,
  separate MySchool comments, explicit review marks and stop after the current generation request.
- Export & posting: existing CSV exports plus a reviewed JSON snapshot. Posting is not connected.

Review marks bind student identity, source text, private notes, feedback, level, MySchool comment,
assignment instructions, selected standard labels, grade, course, school year and quarter. Editing these
invalidates the mark. A reviewed snapshot includes a SHA-256 fingerprint of source text. It is a portable
review snapshot, not the future durable posting authorization contract. There is no snapshot import yet.
Student work and review marks are not automatically persisted; export before closing. CSV exports contain
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

**Choose from Teams… (paste version).** Paste the assignment's Student view (⌘A, ⌘C in Teams) and type or paste the
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
