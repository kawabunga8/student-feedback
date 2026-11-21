# Plan: collect student work from SharePoint (synced folder)

Status: PLAN ONLY (2026-11-14). Written in Claude (Cowork) to hand to Claude Code. No code has been written for this.
Read first: ARCHITECTURE.md ("How student work moves", "Privacy boundaries"), ATTACHMENT-COLLECTION.md, stage_submissions.py.

## Goal
Let student-feedback read submitted work from each class team's SharePoint **Student Work** library, stage it into the
existing `Assessment/<year>/<quarter>/<course>/<assignment>/First_Last.txt` convention, and feed the existing
Draft -> Review -> Post pipeline. All reading and drafting stays on this Mac (local model); student work never goes to Claude.

## What was verified live (2026-11-14, Sr Band team, read-only, no student files opened)
- Each class team site has a separate document library **Student Work** (Sr Band: 324 items, updated daily). It is NOT the
  channel Files tab (that library only shows `General`). Site contents URL:
  `https://rcschool.sharepoint.com/sites/<site>/_layouts/15/viewlsts.aspx`.
- Top level of Student Work: `Submitted files` and `Working files`.
- `Submitted files/` contains **one folder per student** (display names), not one per assignment. Layout confirmed
  below (counts from a read-only SharePoint list query run in the signed-in page; no names or file contents read).
- Band submissions are likely audio/video recordings (Scales, EarMaster). Those cannot be text-drafted; they must be
  listed and counted, not read.
- The Microsoft 365 connector and Graph are blocked by Conditional Access (AADSTS53003). Do not plan on a Graph app
  registration unless RCS IT approves one.

## Layout findings (2026-11-14, Sr Band, counts only)
- Paths: `Submitted files/<student>/<folder>/[<subfolder>/]<file>`. 42 student folders, 39 second-level folders (likely
  one per assignment), 23 third-level folders. Files sit at depth 3 (52 files) or depth 4 (55 files). No files directly
  in a student folder. 24 of 42 students have at least one file; many student folders are empty (not yet submitted).
- So the assignment match must use the second-level folder name, and must tolerate one extra level below it.
- File types (107 files): 98 video (46 .mov, 47 .mp4, 5 .webm), 8 .docx, 1 .whiteboard. About 92% of Sr Band
  submissions so far are video recordings, so text drafting covers almost none of this class. Plan a separate
  "listening/viewing notes" input for Band performance assessment, and list video as non-text (name, type, size only).
  Do not attempt transcription of video by default.
- `Working files/` holds 143 items and was not analysed; do not stage from it until Shingo says what it is.
- Other classes (ICT, Computer Programming, Biblical Perspectives, CLE) likely differ; repeat this count per team.

## Sync status (2026-11-14)
The shortcut saved in Shingo's OneDrive web under My files > Shortcuts, but the OneDrive Mac app would not sign in, so
nothing synced locally. Do NOT depend on the sync. Fallbacks, in order: (1) ask RCS IT whether the OneDrive client is
allowed and the sign-in error code; (2) manual **Download** of an assignment folder from SharePoint (zip) into a local
Assessment staging folder; (3) a browser-based reader in the existing Chrome automation, read-only, like
attachment_collect.py. The reader module should take a local folder either way, so steps 2 and 3 produce the same input.

## Decision: transport = OneDrive-synced local folder (read-only)
The teacher syncs each Student Work library with "Add shortcut to OneDrive"/"Sync" (one-time, done by Shingo in the
browser, not by automation). The app then reads ordinary files from the local sync folder
(macOS: under `~/Library/CloudStorage/OneDrive-*/...`, exact path to be confirmed).
Why: no API auth, no Conditional Access issue, no browser session, works offline once hydrated, files stay local.
Rejected: Graph API (blocked/needs IT), browser download via Chrome automation (slow, fragile; keep only as fallback for
SharePoint *links* inside Teams attachments, which attachment_collect.py already handles).
Keep a thin `Transport` seam (list students/files, open file bytes) so Graph or another source can be added later.

## Design
New module `sharepoint_collect.py` (stdlib only, no network, no browser), plus a thin CLI; app.py/UI integration is a
second step.

1. **Config** (outside git, in APP_DATA, e.g. `sharepoint-sync.json`): per Course Hub course -> sync root path
   (`.../Student Work/Submitted files`). CLI also accepts `--root`.
2. **Discover**: walk `Submitted files/<student>/...` (max depth 3). Never follow symlinks. Never write inside the sync
   root; refuse any output path under it.
3. **Assignment match**: support both layouts once confirmed: `<student>/<assignment>/<files>` and flat
   `<student>/<files>` (match by folder or file name). Normalise with `stage_submissions._norm`. Accept exact match or a
   single unique containment match; ambiguous or none -> flagged, never guessed (same rule as the Teams reader).
   Optional `--since` using file modified time, with a note that sync time can differ from submit time.
4. **Student match**: reuse `stage_submissions.fetch_roster` + `match_student`. Unmatched -> `_NEEDS_ATTENTION_` file,
   missing roster students -> `_MISSING_SUBMISSIONS.txt` (existing behaviour; reuse `stage()` rather than duplicating).
5. **Extract text** by type, bounded sizes:
   - `.txt/.md`: read. `.docx`: `attachment_collect.docx_text` (already bounded). `.pdf`: `pdftotext` (as app.py does).
   - `.xlsx/.csv`: not auto-turned into prose; list as non-text (Forms exports have their own importer).
   - Audio/video/images/.pptx/.mscz etc.: **non-text**: record name, type, size only. Images can go to the existing
     local vision prototype later, behind explicit review.
   - Multiple files per student: concatenate with source labels (`[file: name]`), same convention as attachment import.
6. **OneDrive Files On-Demand**: files may be cloud-only placeholders; reading hydrates them. Detect dataless files
   (macOS `st_flags & SF_DATALESS`), report the count, and require `--hydrate` (or a UI confirm) before bulk reading;
   cap total bytes per run.
7. **Output**: write a staging temp dir (mode 0700) of `<First Last>.txt`, then call `stage_submissions.stage(...)`.
   Dry run is default; `--commit` writes. Re-runs must be idempotent (skip identical text; never overwrite a reviewed
   student's work silently; flag changed submissions instead).
8. **Reporting**: shows counts (matched, flagged, missing, non-text files by type, cloud-only) **and student names**
   (Shingo's decision, 2026-11-14: the app runs locally for the teacher, who needs names to act on flagged/missing
   students). Add `--counts-only` for output that will be shared with Claude, logs or anyone else. Claude sessions
   must not run this on real class data or ask for its full output unless RCS approval of that is confirmed.
9. **UI step (later)**: a "Collect from SharePoint folder" card beside OneNote/Teams in Collect, as a background job via
   `jobs.py` (read-only job kind), preview showing counts and flagged students, explicit "Add reviewed selections to
   Work" like attachments. Evidence changes require re-review (existing rule).

## Privacy and safety rules (non-negotiable)
- Read-only on SharePoint/OneDrive. No uploads, renames, deletes, shares, or "free up space" changes.
- No student names, file contents or file names in logs, commit messages, tests, fixtures, or Claude chat. Tests use
  invented students only (see tests/README.md rules; use `_common.guard`).
- Student work and the sync config stay out of git (`.gitignore`: add the sync config path and any new staging dirs).
- Only the local model drafts. RCS approval for this workflow has not been confirmed in writing: Shingo must confirm it
  before the first real class is processed. Teacher reviews every draft; levels/grades stay the teacher's decision.
- Never print or store sign-in tokens (the Chrome profile holds live tokens; unrelated to this plan, still do not touch).

## Test plan (synthetic only)
New `tests/test_sharepoint_collect.py` in the existing PASS/FAIL style, building a temp tree: flat and nested layouts,
duplicate/ambiguous names, nickname/initial matches, empty files, oversized docx, unsupported types counted as non-text,
dataless-file simulation, symlink escape, output-inside-sync-root refusal, idempotent re-run, changed-submission flag,
counts-only output contains no names. Add to `run_all.py` automatically (glob). Run with the tests venv.

## Steps for Claude Code
1. Branch off; note `git status` shows many uncommitted changes in app.py, jobs.py, feedback.py etc. Do not mix them
   into this work; commit separately or ask Shingo.
2. Shingo syncs one real Student Work library (Sr Band suggested), then runs
   `find "<sync root>/Submitted files" -maxdepth 3 -type d | sed 's#.*/##' | sort | uniq -c | sort -rn | head` himself.
   Its output includes student folder names (fine on his screen); he shares only the *shape* with Claude (depth,
   whether assignment folders exist). Update step 3 of Design to match.
3. Implement `sharepoint_collect.py` + tests; wire CLI; dry-run on a synthetic tree.
4. Real dry run by Shingo on his own machine (names shown to him). Review flagged/missing. Share `--counts-only`
   output with Claude if needed.
5. Add app.py route + `ui/` card + job kind; extend tests; update README, ARCHITECTURE.md (How student work moves) and
   WORKFLOW.md log.
6. Later options: image transcription for pictures, audio-submission handling for Band (a different workflow: rubric
   + teacher listening notes, not text drafting).

## Built so far (2026-11-14, branch `sharepoint-collect`)
Step 3 is done, tested on synthetic folders only (no real class data has been read):
- `sharepoint_collect.py`: `--list-assignments`; dry run / `--commit`; `--hydrate`, `--since`, `--max-mb`,
  `--counts-only`, `--roster-file`. Handles both layouts, since the real one is still unknown.
- `tools/deidentify_shape.py`: name-free copy of a synced folder's shape for checking the matcher against real quirks
  (replaces Step 2's `find` command when the shape is to be shared with Claude).
- Tests: `tests/test_sharepoint_collect.py` (38 checks), `tests/test_deidentify_shape.py` (16 checks).

Departures from the design above:
- Design 7: does not call `stage_submissions.stage()`, which overwrites silently. It reuses `match_student`,
  `staged_path` and `fetch_roster` and writes the same file names, but never overwrites: identical work is skipped,
  differing work goes to `_CHANGED_<First_Last>.txt`. Also writes `_NON_TEXT_SUBMISSIONS.txt`.
- Year folder: `stage()` defaults to the calendar year ("2026"); this takes the school year ("2026-27") from the app's
  `/api/courses`, or `--year`.
- Students with only non-text, cloud-only or ambiguous submissions count as submitted (not "missing"); a student with
  two matching folders, or two folders for one student, is flagged rather than picked.
- No sync config file yet (`--root` only); it comes with the UI step.

## Open questions for Shingo
- Exact local sync path and whether one sync root per class team is acceptable.
- Layout inside a student folder (step 2 above).
- Should audio/video Band submissions get a "listening notes" input card instead of text drafting?
- Written RCS approval for the local-LLM workflow with student work.

## See also
BAND-PERFORMANCE-EVIDENCE-DESIGN.md: how video-heavy classes (Sr Band) are handled: evidence list + teacher observation
capture + local drafting from notes.

## Build status (2026-11-14)
Built with synthetic tests only: `sharepoint_listing.py` (read-only listing export through the app's Chrome profile, counts-only
output, owner-only local file), `evidence_collect.py` (matching, kinds, CLI), `observe.py` + `ui/observe.js` (observations).
NOT built: staging text from the 8 .docx-type submissions through this path (use the existing docx import for now), the
OneDrive-sync transport (sign-in blocked), a job-queue/UI card for the listing (CLI only), and any live run. First live
steps for Shingo: dry-run `sharepoint_listing.py` on Sr Band, then `evidence_collect.py --entries ...` without `--commit`.

