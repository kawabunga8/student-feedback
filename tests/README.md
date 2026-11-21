# Tests

Automated checks for the feedback app. They use **synthetic data only**: invented students, classes, assignments and
identifiers, a stand-in model server, and text shaped like what Teams showed on 2026-11-01. No real student data,
browser profile, or sign-in material belongs in this folder. Each test builds a throwaway `HOME`, so your real
Assessment folder, Application Support folder and Chrome profile are never touched.

## Run them

One-time setup (Playwright and a browser; the tools venv from `tools/spike_onenote_text.py` already has Playwright):

    python3 -m venv ~/.venvs/student-feedback-tools        # skip if it exists
    ~/.venvs/student-feedback-tools/bin/pip install playwright
    ~/.venvs/student-feedback-tools/bin/playwright install chromium

Or use the Google Chrome you already have, and skip the last line: set `TEST_BROWSER_CHANNEL=chrome`.

**Quit the feedback app and Ollama first.** The tests start their own app on port 8765 and a stand-in model on 11434,
and `run_all.py` refuses to run if either port is busy. Then, from the repo folder:

    ~/.venvs/student-feedback-tools/bin/python tests/run_all.py
    TEST_BROWSER_CHANNEL=chrome ~/.venvs/student-feedback-tools/bin/python tests/run_all.py     # with installed Chrome

A single file runs the same way (`python tests/test_sessions_ui.py`). It prints PASS or FAIL per check and exits non-zero
on any failure.

## What each file covers

| File | Covers |
|---|---|
| `test_assignment_records_ui.py` | Saved assignment records, the Design step, "Choose from Teams" by paste, version conflicts between two tabs |
| `test_sessions_ui.py` | Persistent sessions: save and reopen, edits voiding review marks, posting ticks, two tabs, switching assignments, folder-name safety |
| `test_server_approvals.py` | Server-side approval validation, forged approvals, re-approval stamping, the gated posting reader |
| `test_job_queue_http.py` | The background job queue over HTTP: app killed mid-job, resume without redoing work, cancel, model engine down, refused requests, no student text in the journal |
| `test_background_drafting_ui.py` | The "Draft in the background" panel: progress, drafts applied only if the work is unchanged, collecting drafts after the page was closed |
| `test_teams_parsers.py` | The Teams text parsers on synthetic fixtures: assignment list, roster counts, Student view sections, identifiers, exact class-and-title matching |
| `test_teams_import.py` | The Teams read jobs and the import dialog with a stand-in reader: sign-in wait, profile in use, mismatch, preview, saved source references, paste fallback |
| `test_teams_lock_cli.py` | The shared browser lock and the reader's click allowlist (never starts Chrome) |

## What these tests do not show

They never contact Teams, Course Hub, MySchool, OneNote or a real model. Passing them says the app's own logic behaves as
written on fixture text. Whether the real Teams pages still look like the fixtures is checked by running
`tools/spike_teams_assignments.py` and by a live import through the app, compared with Teams by eye.

`teams_fixtures.py` holds the synthetic Teams text. If Teams' layout changes, update it from a **sanitised** spike output
(replace every student name, class and identifier) and never paste real names into it.

MySchool pilot: `TEST_BROWSER_CHANNEL=chrome ~/.venvs/student-feedback-tools/bin/python tests/test_myschool_pilot.py` uses port 18865, a temporary HOME, a stand-in worker and in-memory synthetic browser pages. It does not contact MySchool or launch your signed-in profile. The full runner still requires production ports 8765/11434 free for older suites.

## Additional prototype suites

| File | Covers |
|---|---|
| `test_onenote_class.py` | Whole-class OneNote collection: page-list discovery, picking a page by title or one task number (never between two), identity from the rewritten address, wrong-student fallback, job handler outcomes (29 checks) |
| `test_posting_guards.py` | MySchool criteria identity in the preview, Teams read-back identity, posting jobs never resumed (11 checks) |
| `test_posting_jobs.py` | Teams/MySchool batch job handlers: partial runs, cancel, uncertain outcomes, approval changed (10 checks) |
| `test_rubric_drafting.py` | Saved rubric criteria, setting persistence, stale drafts/approvals and rejected level wording |
| `test_teams_rubric.py` | Separate rubric parsing and supported dialog controls |
| `test_team_assessment.py` | Team assessment dialog: greyed students never overwritten, required fields, one level and comment to each member, no level chosen for you, one member's edit voids only their review (20 checks) |
| `test_onenote_collect.py` | Typed-page collection, batch outcomes, roster checks and assignment ownership |
| `test_teams_students.py` | Complete roster status reads, privacy, jobs and assignment switching |
| `test_teams_grading_spike.py` | Field labels exclude contents/values, masking and read-only inspection |
| `test_myschool_pilot.py` | Older one-student MySchool dialog (removed 2026-11-03; this suite targets that dialog and needs updating or retiring) |
| `test_teams_post.py` | Older one-student Teams pilot worker: preview, destination identity, explicit Return, single-use previews and read-back (the card was removed 2026-11-03; the worker's helpers are still used) |
| `test_forms_import.py` | Local Forms export parsing, metadata exclusion, limits, notices and upload UI |
| `test_draft_quality.py` | Draft benchmark counts and audits with scripted replies |
| `test_closing_mode.py` | End-of-term feedback: the 7-day rule, the no-next-steps prompt and formats, the advice check, and the app picking the mode from the saved quarter dates |
| `test_class_overview.py` | Read-only card states, filters and next actions |
| `test_vision_read.py` | Synthetic images, stand-in vision model, editable text, roster matching and the assignment-binding guard |
| `test_transcribe_check.py` | Character/word error calculations on invented text |

The runner discovers files automatically; counts depend on the current checkout. The last 17-file Mac run reported 586 passes and two UI-file failures. Separate reruns passed MySchool 44/44 and Teams statuses 29/29. Do not report that as a clean combined run. Newer feature tests are listed separately in WORKFLOW.md.

Real-model measurements are deliberately outside the synthetic runner. Start Ollama and use `tools/draft_quality.py`; use `tools/transcribe_check.py` with image/reference-text pairs for transcription. Never add real exports, work, images, credentials or generated feedback to fixtures.

`test_teams_create.py`: 30 isolated checks for student-facing payloads, Forms/browser guards, draft-editor identity, authorization before autosave, Save as draft without publishing, reopened exact read-back, stale/duplicate requests, changed-record revocation, and the full preview/confirm/job/receipt GUI flow. Uses invented Teams pages and a stand-in runner only.

`test_myschool_create.py`: 32 isolated synthetic checks for student-facing payloads, required teacher choices, browser/host/new-page guards, unsafe publication defaults, preview without writes, outcome validation, explicit single Save, reopened read-back, stale/duplicate requests, pre-Save revocation and the complete course/preview/outcome/confirm/receipt GUI flow. No MySchool contact.

## Not covered by these suites (2026-11-03)

The one-session engines (`teams_batch.py`, `myschool_batch.py`), their job types and the single posting dialogs (`ui/teams_post.js`, `ui/myschool.js`) have no suite here. They were checked three ways instead: read-only and dry-run live runs against real Teams and MySchool (reading, name matching, opening and closing panels, with nothing typed or clicked), mocked-job checks of the dialogs in a browser (ready/skipped/error rows, the one confirmation, stop at the first failure, per-criterion levels), and one live class (ICT 9 Q1 Task 2, 18 students) posted and saved with read-back. A Playwright suite for the new dialogs, using mocked jobs, is still to be written; the older MySchool and Teams posting suites above target removed dialogs.

## Notes (2026-11-04)

- Run from a stopped app **and a stopped Ollama** (ports 8765 and 11434). A first run right after restarting can time out once; rerun the single file.
- `test_server_approvals.py` and `test_assignment_records_ui.py` pass. `test_sessions_ui.py` and `test_myschool_pilot.py` time out at the same step with and without the 2026-11-04 changes (they look for an older posting checkbox that is no longer visible), so they need updating or retiring.
- Not covered: the "No work found…" dialog's Apply step, and `skills/assignment-followup/scripts/` (they drive real Teams, OneNote, Code.org and chat, so they are checked live by hand). The no-submission field was checked with a direct approval-validation script (a new approval is current, an older one without the field is still current, changing the field voids it).
| `test_observe.py` | Observation model: levels never defaulted, validation and caps, notes for drafting name no level, claim check, counts-only summary, versioned sidecar. |
| `test_evidence_collect.py` | Evidence listing: metadata only, conservative student/assignment matching, no file opened, symlinks and depth limit, CLI dry run and commit. |
| `test_observations_http.py` | Observation routes in the real app (temporary HOME): versions and 409, notes, claim check, SharePoint-only https links, origin guard, manifest untouched. |
| `test_observe_ui.py` | Observe screen in a browser against a stand-in server: nothing pre-filled, autosave, copy-notes without duplication, no HTML injection. |
| `test_sharepoint_listing.py` | SharePoint listing export: address checks (https, sharepoint.com, /sites/ only), list items to entries (Submitted files only), counts-only output, owner-only file, no browser. |
