# Design: group projects (one assessment, shared by team members)

Status: v1 BUILT (2026-11-21): the "Team assessment..." dialog in `ui/workspace.js`, tested in
`tests/test_team_assessment.py` (20 checks, synthetic cards, stand-in model). Not yet tried on a real class or against live
Teams and MySchool; see "Verification to do". Everything under "Later" is design only.
Companion to ARCHITECTURE.md (session, approvals, posting) and BAND-PERFORMANCE-EVIDENCE-DESIGN.md (same principles).

## Problem
Group projects are often one video per team. Shingo watches it and gives one level and one comment, which every member
receives (Teams Return and MySchool save). The app is per student throughout, so today that means pasting the same level
and comment into each member's card by hand.

## What already exists (re-checked 2026-11-21)
- **Posting is built and verified live**: Teams (Post feedback and Return, read back from the Returned tab) and MySchool
  (preview, save, reopen and compare), per student or whole class. Posting reads each student's own current approval.
- **A shared level and comment already exists**: the **Record no submission...** dialog
  ([ui/workspace.js:305](../ui/workspace.js)) ticks several students, applies one level and one comment to each card's
  feedback and MySchool comment, and marks them reviewed through the normal approval path.
- **Why it can't be used for teams as is:** it offers only matched students with empty Work and no draft, requires
  "sources checked" ticks, and writes "No submission found <date> in: ..." into each record, which would be false for a
  team that submitted a video.

So the shared-assessment step is mostly built. The design is to generalise that dialog, not to add a new entity.

## Principles
1. **Posting and approval do not change.** Each member still has their own card, their own approval and their own posting
   ticks. The server's approval check (`check_reviewed`) is untouched.
2. **Teacher chooses every level and approves every comment.** No level is pre-filled and no comment is generated.
3. **No model in v1.** The teacher watches the video; nothing is drafted, and no recording or name goes to any model.
4. **Additive, no data-model change in v1.** No new manifest fields, so no whitelist or legacy-manifest risk.
5. **Existing work is never overwritten.** Same rule as the no-work dialog.

## v1: "Team assessment" dialog
A sibling of **Record no submission...** in the *Review assessments* toolbar group, sharing its code.

| | Record no submission... (today) | Team assessment (new) |
| --- | --- | --- |
| Offers | matched students, empty Work, no draft | same; others are listed greyed with the reason ("already has work", "has feedback") |
| Inputs | sources-checked ticks, level, comment | **Team name**, **Evidence** (what was assessed: link or description, watched date), level, comment |
| Writes to Work | nothing (stays empty) | `Team <name>: <evidence>` so Work is non-empty and honest |
| Writes to no-submission note | "No submission found <date> in: ..." | nothing |
| Comment default | fixed "no submission" text | **empty**: the teacher must write it |
| After apply | marks reviewed | marks reviewed |
| Posting | separate step, own preview and confirmation | same |

Flow:
1. Open **Team assessment**, tick the team's members (matched, unique roster IDs only).
2. Type the team name and the evidence line, for example `Team 3: group video, Teams file "Demo.mp4", watched 2026-11-21`.
3. Pick the level (any, or none), write the comment, **Apply and mark reviewed**.
4. Each member card now holds identical Work evidence, level and comment, reviewed. Repeat per team.
5. **Post to all (Teams)** and **Save to MySchool (all)** as usual.

Behaviour after apply, all from existing mechanisms:
- Editing one member's level or comment voids only that member's approval ("review again"); the others stay posted-ready.
  This is how an individual adjustment is made.
- Editing the evidence line voids that member's approval, as any Work edit does.
- A member who did not contribute is left out of the tick list and handled on their own card (including **Record no
  submission...** if that is the truth).
- The team name lives only in the Work text, so there is no stored team and no way for a team to drift from its members.

Where the evidence comes from: typed or pasted by the teacher in v1. **Performance observations** (per criterion level and
note, already built) can be used on one member's card; a later step could copy a card's observations to the other members
(see Later).

## Verification to do before relying on it
These are real gaps in what is verified, not assumptions of the design:
1. **Teams:** members who never submitted individually appear under *To return* and can be Returned. The 2026-11-04 run
   did this for seven no-work students, but the "Apply" step of the no-work dialog was never verified end to end, and
   what a Return sends the student is unverified. Try one team of two first.
2. **MySchool:** assignments with several criteria are unverified; with several criteria a Levels box asks for one level per
   criterion, in page order.
3. **Feedback box:** confirm the feedback text can be set by the dialog (`window.insertDraft`) on a card with no model
   draft, and that Mark reviewed accepts it.
4. **Tests:** the existing browser suites for sessions and the MySchool pilot were noted as failing independently of recent
   changes (tests/README.md); the new dialog needs its own test, run in the way the README describes.

## Later (only if v1 is not enough)
- **Saved teams.** If teams should persist between sessions (reused groups, "which teams are done"), add an optional `teams`
  list to the manifest: `{team_id, name, members:[student_id], evidence, level, comment}`, plus `team_id` on members, with
  `team_id` and a hash of the team values added to the approval's reviewed values so a team edit voids member approvals.
  Older approvals count those as empty, so none are voided. The save path whitelists student fields, so it must be told
  about the new ones or they will be dropped.
- **Copy observations to members** from one card, for teams assessed with per-criterion notes.
- **Group Maker import.** Group Maker keeps no groups and copies text. Check its clipboard format before writing an
  importer; persisting groups belongs in Course Hub.
- **Class patterns** counts students and hides criteria checked for fewer than 5. Teams make the unit smaller, so most
  classes would show nothing; leave unchanged until real use shows what is wanted.
- **Model drafting for teams** (a prompt that writes to "your team" from the teacher's notes, never inferring individual
  contribution, never seeing names). Not needed for a teacher-written shared comment.

## Open questions
1. How does a team's video arrive: one Teams file from one member, a SharePoint link, or each member submitting the same link?
   This only affects what the Evidence line says in v1; it matters for collection if the app is ever to list it.
2. Is an identical comment to every member always what is wanted, or do some assessments need a short per-member line?
   (v1 handles this by editing the member's card afterwards.)
3. Does MySchool at RCS ever assess a group as one entry? (Assumed per student; unverified.)
4. RCS approval for using this on real student work must be confirmed, as for the other prototypes.
