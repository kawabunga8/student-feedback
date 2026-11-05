---
name: phase-b-upload
description: Post a saved, reviewed student-feedback assessment to Teams, MySchool, or both, for one student or a specified batch. Use for requests to upload approved assessments or run Phase B.
---

# Post reviewed assessments

Work from the current `student-feedback` app and its saved approvals. This skill applies to Codex or Claude when the necessary tools and school account are available. It does not draft feedback, select proficiency levels, or approve unreviewed work.

## Establish the batch

- Resolve the repository relative to this file (`../..`). Read the posting sections of [README.md](../../README.md) and, when troubleshooting, the relevant worker and UI. Code and current observations take precedence over historical workflow logs.
- Open `http://127.0.0.1:8765`, choose the saved assignment, and verify course, school year, quarter, assignment title and intended students. Save outstanding assignment/session changes; resolve conflicts before posting.
- Use the app's current review status. A `.feedback.md` file, a missing `HOLD` prefix, or an exported snapshot alone is not a current server-validated approval. Do not forge approvals, edit the manifest to make work approved, or bypass the app's posting gate.
- Teams receives the reviewed detailed feedback. MySchool receives the reviewed comment and teacher-selected criterion levels. The MySchool comment may default to the feedback; use the saved reviewed text, without rewriting or shortening it during posting.
- Establish the destination(s), one-student or batch scope, and whether MySchool status should become Graded. For several MySchool criteria, obtain one teacher-selected level per named criterion; never copy a single overall level across all criteria by inference.

## Preview and authorization

Use the app's Export & posting controls. Prefer its job workers over manually reproducing browser clicks or calling write scripts directly. Access troubleshooting is covered by [rcs-teams-and-myschool-access](../rcs-teams-and-myschool-access/SKILL.md).

1. Read the destination without writing. Confirm the Teams class/assignment and student match, or the MySchool Assessment address and the course/title/publication state read from it.
2. Check existing versus proposed feedback or criterion levels/comments, the included and skipped counts, and existing-content replacement. Compare the complete proposed text with the saved reviewed assessment even if a dialog exposes only readiness rows.
3. Present the concrete batch summary before the first write. When the user has already explicitly authorized this exact reviewed batch to these destinations, proceed with the app's confirmation controls where the host's confirmation policy allows it. Otherwise obtain that authorization now. Do not request it again for each unchanged student.
4. Explain that Teams Return may notify students and that saving an already published MySchool assignment may expose results immediately. Preserve publication settings; creating or publishing assignments is outside this skill.

A changed destination, student identity, criterion mapping, approval or proposed content requires a new preview and authorization for the changed action. An expired preview must be replaced through the app, never by editing timestamps or preview claims.

## Run and verify

- For Teams, use the student's Post action or the class posting action. The worker skips already Returned students, checks existing feedback, revalidates approval before writing, fills feedback, clicks plain Return, and reads back the saved feedback from the same assignment/submission/student. Leave points, Copilot, revision and excused controls alone.
- For MySchool, use the student's MySchool action or Save to MySchool for the class. Check the per-criterion preview and Graded choice. The worker verifies the same student and criterion identities, saves once, reopens the assessment and checks levels, comment, status and unchanged publication/other students.
- Keep the batch dialog available for progress; do not start a second worker on the same Chrome profile. Stop ends the run at its supported boundary; verify the current student's result before reporting it as stopped without changes.
- Record success only from a verified worker receipt. Returned status alone does not prove the feedback matches. A successful Teams receipt is independent of a successful MySchool receipt.

## Interrupted or uncertain outcomes

Stop on the first write problem. Distinguish verified successes, already-complete skips, the student with an uncertain outcome, and students never attempted. A generic failed job or a misleading “nothing posted/saved” summary is not evidence that no write occurred.

Do not resume an old posting request, replay a Save/Return click, or assume a consumed preview can be reused. Read the affected destination first, reconcile what persisted, then use a fresh preview for any remaining authorized work. Do not re-post verified students just to recover the rest of a batch.

Report counts by destination, skip reasons, uncertain outcomes and required teacher actions. Keep student names/work/private notes out of routine chat summaries and commits; retain detailed records in the assignment's existing session/job storage. Do not create a competing approval or completion ledger.

## Evidence limits

The repository records a live Teams/MySchool run for 18 students on a single-criterion ICT 9 assignment on 2026-11-03. That does not validate every layout, multi-criterion MySchool assignment, notification behavior or later code change. Consult current tests and receipts rather than treating that run as blanket verification.
