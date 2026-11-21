# Design: performance evidence (video) and teacher-observation feedback

Status: DESIGN ONLY (2026-11-14). Written in Claude (Cowork) for Claude Code to implement.
Companion to SHAREPOINT-COLLECTION-PLAN.md (collection) and ARCHITECTURE.md (existing pipeline).

## Problem
Sr Band's submitted work is mostly video: of 107 files in the Sr Band Student Work library, 98 are .mov/.mp4/.webm and
8 are .docx. Text drafting from submitted text does not apply. A local text model cannot judge musical quality, and
recordings of students must not be sent to any model. The teacher must watch and judge; the app should make that fast
and turn the teacher's judgments into good, reviewable feedback.

## Principles
1. The video is evidence the teacher watches. No model sees video or audio. No transcription of performances.
2. The model only ever sees the teacher's typed observations plus the rubric (never names, never media).
3. Teacher chooses every level and approves every comment. No level is ever pre-filled by the app.
4. Nothing large is copied: videos stay in SharePoint; the app stores metadata and a link.
5. Reuse the existing pipeline: assignment record, session, rubric/criteria, local drafting, review flags, posting.
6. Read-only toward SharePoint. No renames, moves, deletes or shares.

## Flow (new step inside Collect, then existing steps)
Design -> Setup -> **Collect: Performance evidence** -> **Observe** -> Draft & review -> Export & posting

1. **Collect evidence list** (job kind `evidence_list`, read-only). For the chosen course/assignment, list each student's
   submitted files from the SharePoint Student Work library (via the transport in SHAREPOINT-COLLECTION-PLAN.md). Store,
   per student: items `{name, type, bytes, modified, kind: video|audio|document|other, sharepoint_url}`. Match students
   to the Course Hub roster with the existing exact-or-flag rules. Students with no files are shown as "nothing found",
   never guessed, and can use the existing **No work found...** flow.
2. **Observe screen** (new, `ui/observe.js`): a queue of students for the assignment.
   - Left: student, evidence items with an **Open in SharePoint** button (new tab, no download). Status chips: not
     watched / observed / needs another look.
   - Right: the assignment's rubric criteria (from the saved record's `design.criteria` and level descriptors). For each
     criterion: level buttons (the rubric's own levels, e.g. Emerging / Developing / Proficient / Extending as seen in the
     Teams rubric reader) and a short free-text note. An overall "strengths" and "next step" box. Optional timestamp
     field per note (text like 1:24) for the teacher's own reference.
   - Next/previous student with keyboard shortcuts; autosave per student; nothing is posted from here.
   - Docx items are extracted by the existing text path and shown as normal Work (collapsible), not as video.
3. **Draft**: the local model gets the criteria, level descriptors, the teacher's levels and notes, and (for docx
   students) the extracted text. It writes the student-facing comment in the app's existing feedback style. It may not
   introduce praise or criticism that is not in the notes. A check (like the existing evidence-quote check) verifies each
   claim in the draft maps to a note; unsupported sentences are flagged for the teacher.
4. **Review/Export**: existing review toggle, levels, and posting to Teams/MySchool unchanged. Evidence changes require
   re-review (existing rule).

## Data model additions (assignment session record; no media, no student names in sidecars beyond existing)
```
student.evidence = [{name, kind, bytes, modified, url}]         # metadata only
student.observation = {
  status: "unobserved"|"observed"|"revisit",
  criteria: [{id, level, note, ts}],     # level is teacher-chosen, never defaulted
  strengths, next_step, updated, reviewed: false
}
```
Saved in the existing session JSON beside the work. Editing any observation sets `reviewed=false`.

## Components
- `evidence_collect.py`: lists files, classifies by extension (video: mov mp4 webm m4v; audio: mp3 wav m4a; document:
  docx pdf; other), returns metadata only. Never downloads media. Same transport seam as sharepoint_collect.
- `observe.py`: validates/normalises observation payloads; builds the drafting prompt from notes + rubric; claim-to-note
  check; counts-only summaries.
- `app.py` routes: GET/POST evidence list, GET/POST observation per student (CSRF/same-origin like existing POSTs).
- `ui/observe.js`, `ui/observe.css` (or in workspace.css): queue, rubric panel, autosave.
- `jobs.py`: new read-only job kind `evidence_list` (no write, resumable like other read jobs).
- Tests (synthetic only, existing `tests/_common.py` guards): classification, empty folders, roster mismatch flagged,
  observation validation, level never defaulted, edit un-reviews, prompt contains notes and no names/media, claim
  check flags an invented sentence, UI queue navigation and autosave, SharePoint URL never fetched in tests.

## Privacy and safety
- No video/audio bytes are read, transcribed, thumbnailed or screenshotted by the app or by Claude.
- Observation text may contain names the teacher types; it stays local and goes only to the local model on localhost.
- URLs open in the teacher's own browser tab; the app never fetches them.
- Logs and test fixtures contain no real names or file names. Counts-only summaries by default.
- RCS approval for the local-LLM workflow with student work must be confirmed in writing before first real use.
- Every comment is reviewed by the teacher; grading and level decisions stay with the teacher.

## Defaults chosen (change if Shingo says otherwise)
- Levels: the assignment's own rubric levels; if no rubric is saved, the four-level Emerging to Extending scale.
- Videos open in SharePoint in a new tab (not embedded) to avoid downloads and auth problems in the app.
- Observe is optional per assignment: text-based classes keep the current flow untouched.

## Optional later
- Import scores from outside tools (EarMaster, FromTheStart) as extra evidence beside observations, once their export
  format is known. Not in scope until a sample export is reviewed.
- Class-level "patterns" from observations (counts per criterion/level, no names), like Class patterns today, hidden
  below 5 students.
- Audio-only or spoken reflections: a separate decision about local transcription; out of scope here.

## Build order for Claude Code
1. `observe.py` + data model + tests (pure functions, no UI).
2. Routes in app.py + tests (HTTP).
3. UI queue and capture screen + tests.
4. `evidence_collect.py` + `evidence_list` job on a synthetic folder tree; then a real counts-only run by Shingo.
5. Drafting prompt + claim check + tests; try with a few invented observations on the local model.
6. Docs: README, ARCHITECTURE.md, WORKFLOW.md.
