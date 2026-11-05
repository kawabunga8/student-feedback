---
name: rcs-teams-and-myschool-access
description: Open or troubleshoot Richmond Christian School Teams, Class Notebook and MySchool access for the student-feedback workflow. Use for school sign-in, notebook navigation, shared-browser contention or destination identity checks.
---

# Access Teams, Class Notebook and MySchool

Access/navigation is read-only unless the user's task explicitly includes a write. This skill establishes the correct signed-in destination; it does not approve assessments, post feedback or publish assignments.

## Use the available access path

Prefer a connected service tool when it supports the task. For `student-feedback` collection/posting, prefer the app's existing jobs: they preserve source identity, previews and approval checks. For manual inspection, use the host's documented computer/browser tools with fresh UI observations. Do not assume Claude-specific browser tools exist in Codex or that the user's everyday browser shares the app worker's session.

Repository context: resolve `../..` from this skill. Read [README.md](../../README.md) for the current UI. The app runs at `http://127.0.0.1:8765`. `./start.sh --with-course-hub` starts the app with its live-course dependencies when starting them is within the user's task; do not stop/restart a running app or browser worker while a collection/posting job is active.

## Sessions and sign-in

- Workers use a dedicated persistent Chrome profile under `~/Library/Application Support/student-feedback/chrome-profile`, protected by the shared `browser.lock`. Teams, MySchool and OneNote workers contend for this same profile; run them serially. Never delete a lock/profile or kill a live worker simply to make access work.
- Check whether the profile is genuinely in use, or whether the job is waiting for school sign-in. Let an active operation finish; if cancellation is requested, use its supported Stop/Cancel and inspect the current result. Do not expose profile contents, cookies, tokens, credentials or `.env.local` values.
- Use the existing school session and ordinary Staff SSO path. Follow the host's login and consent rules; let the user complete MFA, security challenges or unanticipated access grants. Do not extract credentials or weaken browser/school security to get past a block.
- The app's tools Python is normally `~/.venvs/student-feedback-tools/bin/python`. A missing Playwright/browser is a setup problem, distinct from a Microsoft sign-in or tenant-policy block. Report that distinction; do not repeatedly retry policy-blocked sign-in.

## Teams

Open the existing Teams app/web session or `https://teams.cloud.microsoft/`. Find the exact class and assignment. Current app workers use the Assignments rail and support different tabs and lazily loaded assignment lists; do not rely on an old note that every class Assignments tab ignores clicks.

For posting inspections, verify class ID, assignment ID, student and submission identity as well as visible titles. For read-only instructions/rubrics/statuses, use the app's corresponding read controls. Do not use Return, change points, edit an assignment or toggle Copilot to test access.

## Class Notebook

In Teams, choose the intended class → Class Notebook. Expand student/section/page navigation as exposed in the current UI. Read the actual page list when available; do not interpret a matching title on a fallback page as the intended student's work.

The app's OneNote reader accepts a SharePoint `Doc.aspx` notebook/page address and opens it in view mode. Use an address observed in the authorized UI, not a fabricated notebook or student identifier. A Teams navigation problem is distinct from a notebook read problem: report whether the tab, notebook, student section or page was actually reached.

If Teams cannot activate the notebook, use its observed Open in browser/website link when available, or an already known authorized notebook address. Do not create sharing links or expand access permissions. The old SharePoint `groupstatus.aspx`/SiteAssets route is historical fallback guidance, not a reason to invent URLs or inspect hidden tokens.

If UI actions do nothing, refresh the observed state and try a supported alternative. If coordinate input or accessibility repeatedly fails, identify the concrete blocker and ask the user to open the control manually; do not claim notebook access until its pages are visible.

## MySchool

Use `https://rcs.myschoolmanagement.com/` and Staff SSO. Navigate through Assignments/Grade grid to the intended course/assignment and its Assessment view. The app accepts the assignment address shaped as:

`https://rcs.myschoolmanagement.com/content/assignment/assignment_edit.php?exercise_id=…`

Verify the course, title, publication state and student/criteria read from that assignment. Extra parameters, another host or a guessed exercise ID are not equivalent destinations. Viewing the assessment does not authorize Save, Graded, Publish or student email changes.

## Handoff

State which destination and content were actually reached, the current sign-in/layout/profile blocker if any, and the next available read-only route. Report student counts rather than names unless the user needs a specific identity to resolve the task. For authorized reviewed posting, continue with [phase-b-upload](../phase-b-upload/SKILL.md); for collection, use [phase-a-collect-and-draft](../phase-a-collect-and-draft/SKILL.md).
