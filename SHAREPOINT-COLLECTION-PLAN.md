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
- `Submitted files/` contains **one folder per student** (display names), not one per assignment. What is inside a student
  folder (assignment subfolders vs flat files) is **UNKNOWN** and must be checked once on a real synced copy before
  finalising the matcher.
- Band submissions are likely audio/video recordings (Scales, EarMaster). Those cannot be text-drafted; they must be
  listed and counted, not read.
- The Microsoft 365 connector and Graph are blocked by Conditional Access (AADSTS53003). Do not plan on a Graph app
  registration unless RCS IT approves one.

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
