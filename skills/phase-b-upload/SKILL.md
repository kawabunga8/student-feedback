---
name: phase-b-upload
description: Post Shingo's reviewed feedback and proficiency levels for one assignment to Teams Assignments and MySchool. Use when he says "upload the approved batch for <assignment>" or "run Phase B for <assignment>".
---

# Phase B: upload approved feedback (Teams Assignments + MySchool)

Phase B of the RCS assessment workflow (see `WORKFLOW.md` in `~/Repos-folder/student-feedback`). Phase A (`phase-a-collect-and-draft`) stages work and drafts feedback into the assignment folder. Shingo then reviews and edits it. Phase B posts what he approved. It never drafts, rewrites or "improves" feedback, and it never decides a level.

> **DRAFT: posting steps not yet verified.** Two steps are still unverified: what Teams' **Return** button does, and MySchool's save/publish control on the Assessment tab. Until the "Verified behaviour" section below is filled in, run in **pilot mode**: post one student, stop, and show Shingo the result in both systems before continuing.

## 0. Before starting

- **Approval.** RCS has approved this account for handling student work and feedback (confirmed by Shingo 2026-10-30). Keep student names out of chat replies, memory and any file outside the assignment folder. In chat, report by count.
- **Browser.** Use Claude's built-in browser, at desktop width (1440x900; Teams hides its left nav below about 768px). If a Microsoft sign-in, MFA or consent prompt appears, stop and ask Shingo to complete it. Never type a password. If he asks for his Chrome instead, follow the `rcs-teams-and-myschool-access` skill.
- **Never touch:** Edit assignment, Mark as inactive, Delete, the Teams "Enhance feedback / Feedback with Copilot" toggle, or anything that publishes a MySchool assignment.

## 1. Read the approved folder

> **Planned change (2026-10-31):** Phase B will read the approval records in the assignment's
> `manifest.json` (see `ARCHITECTURE.md`, "Data contracts") instead of the `HOLD` convention below. Approval
> will bind the exact feedback, level, MySchool comment, source fingerprint and assignment/rubric version,
> and any change voids it. Until the manifest exists, use the conventions below.

Folder: `~/Desktop/Teaching/Assessment/<year>/<quarter>/<course>/<assignment>/`. Read it on Shingo's computer, never by staging copies.

- Feedback files are `FirstName_LastName.feedback.md`, in the folder itself or its `feedback/` subfolder. *(Confirm against where `phase-a-collect-and-draft` writes them.)*
- **Ready** means a feedback file exists, is not empty, and its first line does not start with `HOLD`.
- **Skip and log:** any `_NEEDS_ATTENTION_*` file, any name listed in `_MISSING_SUBMISSIONS.txt` that has no feedback file, and any file marked `HOLD`.
- **Level:** read it from the feedback's opening sentence, which `feedback.py` writes as `This work is at the <Level>[+] level:`. Map it to MySchool's codes: Extending → EXT, Proficient → PRF, Developing → DEV, Emerging → EMG, each with `+` kept. If there's no level sentence, post the Teams feedback but leave the MySchool level ungraded, and log it as "no level set".
- **Text to post:** the whole file, with Markdown removed (`**`, `#`, bullets). Keep paragraph breaks.

Before posting anything, show Shingo one summary: assignment, course or team, number ready, number skipped and why. Wait for his yes. That yes covers the whole batch; after it, no per-student confirmation is needed except in pilot mode.

## 2. Teams Assignments (feedback)

1. Open Teams and click the **global Assignments icon** in the left rail, not a team's own Assignments tab (that one is an iframe and ignores clicks). Re-navigate fresh; don't use the browser's back button.
2. Find the assignment with **Search by assignment title** and press Return. Open it to see the roster.
3. For each ready student, match the Teams name to the file name (underscores as spaces). If the match is ambiguous or missing, skip and log.
   - If the status is already **Returned**, don't assume it's done: it may be an earlier manual return. Open the panel and compare the feedback shown with the approved feedback. If they match, log it as verified; if not, stop and ask Shingo.
4. Open the student's grading panel. If the **Feedback** box already has text, skip and log ("existing feedback"). Otherwise click it and type the feedback.
   - Leave Points as is ("No points"; levels live in MySchool).
5. Click **Return**. *(Unverified: which option the dropdown arrow offers, and whether the plain button notifies the student. Record it under "Verified behaviour".)*
6. After each Return, reopen the student's panel and confirm the feedback shown matches the approved text before logging it as verified. After a timeout or an unexpected page, check the panel before clicking anything again. Then use the prev/next arrows to move on.

## 3. MySchool (level + comment)

1. `https://rcs.myschoolmanagement.com/content/common/dashboard.php` → **Staff** sign-in if asked.
2. Left menu **Assignments** → Grade grid → choose the course → **View All Assignments** (bottom) → click the assignment title → **Assessment** tab.
3. For each ready student's card:
   - Click the level bubble that matches the mapped code. If the card has **more than one** criterion cluster and the feedback gives one level, stop and ask Shingo whether that level applies to every criterion.
   - Type the approved MySchool comment into the **comment** box: a short comment Shingo reviewed separately, never the Teams feedback cut down automatically.
   - Leave "Upload correction" alone.
   - Save. *(Unverified: whether this is a Save button, auto-save, or a separate publish step, and what the status dropdown should be set to.)*
4. Don't change the assignment's own **Publish** setting. If it's unpublished, students won't see grades until Shingo publishes it, so say so in the report.
5. Reopen the card and confirm the level and comment match the approved record, and check the Grade grid cell shows the new level. Only then log MySchool as verified. Teams and MySchool are logged separately, so a retry finishes only the unfinished one.

## 4. Report

- Write `_PHASE_B_LOG.txt` into the assignment folder: one line per student with the Teams result, MySchool result, and the reason for any skip.
- In chat, give counts only: posted to Teams, posted to MySchool, skipped (by reason), and anything Shingo still needs to do (publish the MySchool assignment, resolve flagged students, set missing levels).

## Stop and ask when

- A sign-in, MFA or consent prompt appears, or a browser dialog freezes the tab.
- The page layout doesn't match these steps (a button is missing or renamed).
- A posted result doesn't look right in the screenshot.

## Verified behaviour

*(Fill in from the step 6 test, then remove pilot mode and the DRAFT note.)*

- Teams navigation (2026-10-30): a team's own Assignments tab again ignored a click on a student row; the global Assignments rail icon → assignment → student row opened the grading panel straight away.
- Submitted files (2026-10-30): the grading panel's viewer could not display a student's SharePoint file, and **Open online** / clicking the file card opens a popup that the browser pane blocks when Claude clicks it. Shingo has to click it himself (or supply the URL). This matters more for Phase A collection than for Phase B.
- Class Notebook without a popup (2026-10-30, Phase A): Teams' "Go to website" opens a new tab, which the browser pane blocks. What worked: `https://rcschool.sharepoint.com/_layouts/15/groupstatus.aspx?id=<team group id>&target=site` → `/SiteAssets/Forms/AllItems.aspx` → click the "<team name> Notebook" item. The group id is in the Class Notebook tab's iframe `src`. Notebook search only covers the current section or page, so browse instead: student section → Homework → page by title. Set the tab to the light colour scheme first; in dark mode the page text is too faint to read.
- Teams **Return** dropdown (2026-10-30): **Return** (default, ticked), **Return for revision**, **Mark as excused and return**. Phase B uses plain **Return**. Default notifies student: _; formatting kept (paragraphs, length): _
- MySchool save control: _; status dropdown value: _; Grade grid updates: _
