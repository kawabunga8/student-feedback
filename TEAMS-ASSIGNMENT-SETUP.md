# Teams Assignment Setup — for efficient downstream assessment

Companion doc to `WORKFLOW.md`. This covers the *upstream* half: how an
assignment should be structured in Microsoft Teams Assignments / ClassNotebook so
that the feedback pipeline (student-feedback app → Teams → MySchool) runs smoothly
afterward, with minimal manual cleanup.

This file is mirrored from the Claude.ai "Assessment" Project doc
`teams-assignment-setup.md`. See the note at the top of `WORKFLOW.md` for how
the two copies relate — update the Project doc first if you have access to
it, then copy changes here.

## Why this matters

The student-feedback app's checklist-based review only works well when:
- Submission format is predictable (so Claude/the workflow can locate and extract
  work without guessing)
- Instructions are phrased in a way the app can parse into a checklist
- Learning standards are pre-selected per assignment, not decided ad hoc at grading time

A messy assignment setup (mixed submission types, vague instructions, no standard
tagging) pushes all the friction downstream into the grading session, which is
exactly what this project is trying to eliminate.

## Recommended assignment-setup checklist (per assignment, at creation time)

1. **Instruct students to post in ClassNotebook whenever possible.**
   - Every Assignment's instructions should tell students to submit by writing
     directly in their individual ClassNotebook page — this is the preferred
     default submission channel.
   - This is guidance to students, not a hard technical gate: the collection
     stage of the workflow auto-fetches from whatever a student actually used
     (Canva link, SharePoint link, direct Teams attachment), so a student who
     can't use ClassNotebook for a given medium (e.g. a Canva poster) doesn't
     break the pipeline. The instruction exists to make the *common* case
     simple, not to block other cases.
   - If photos of handwritten work are expected (e.g. music notation, sketches),
     say so in the instructions so students know to attach images directly
     (to the Assignment or a ClassNotebook page) rather than describe their
     work in text.
   - Seen on ICT 9 Task 2 (2026-10-30): submissions were a mix of Class
     Notebook pages, SharePoint links, and "Turned in" with nothing attached
     (the work was in the notebook). Teams' grading panel couldn't display
     the SharePoint files, so Notebook pages are the easiest to collect.

2. **Write instructions in the `student-feedback` app's parseable format.**
   From the app's README, use one of these recognized labels followed by a short,
   comma/semicolon/bullet-separated list (each item ≤8 words):
   ```
   Assignment: <one-line task description>
   Looking for: <item>, <item>, <item>
   ```
   or
   ```
   Success criteria:
   - <item>
   - <item>
   ```
   Recognized labels: `Looking for:`, `Success criteria:`, `Criteria:`,
   `Must include:`, `Requirements:`.
   - Use command terms deliberately (describe, explain, justify, analyse, compare
     and contrast, discuss, evaluate, list, identify) only where that's the actual
     cognitive demand — the app checks for whether the task asks for that kind of
     thinking.
   - Skip the checklist format entirely for genuinely one-sentence tasks (the app
     ignores it below a length threshold anyway).
   - Seen on ICT 9 Task 2 (2026-10-30): the instructions had numbered tasks
     but no recognized label, so the app had nothing to build a checklist
     from. One added line such as `Success criteria: 5+ app ideas; how each
     helps client; compare on three questions; justified choice; contextual
     factors` fixes that, either in Teams or pasted into the app.
   - The full instructions, including the assessment descriptors, can be read
     back from the assignment's `...` menu → **Student view**. That's how they
     get into the app's instructions box.

3. **Decide and tag the learning standard(s) up front, not at grading time.**
   - `courses.json` / Course Hub already map each course to a department (ADST,
     Bible, Career, Fine Arts, Worship Leadership) and the correct standards PDF.
   - At assignment-creation time, pick which specific standard(s) from that
     department's PDF this assignment will be assessed against, and note it in
     the assignment description or a consistent internal tag (e.g. in the
     assignment title or a leading line in the instructions:
     `[Standard: <code or short label>]`).
   - This removes a judgment call from the grading session — the proficiency
     level (Extending / Proficient / Developing / Emerging) gets applied against
     a standard you already chose, not improvised per student.

4. **Set the Teams Assignment's point value / rubric consistently with MySchool.**
   - If MySchool expects a proficiency-scale mark rather than points, consider
     setting the Teams Assignment grading scheme to match (or clearly map one to
     the other) so there's no silent mismatch between what Teams shows students
     and what lands in MySchool.

5. **Due-date and folder hygiene.**
   - Keep one Assignment = one due date = one ClassNotebook section/page naming
     convention (e.g. `Unit3-Lesson2-StudentName`), so a later batch-pull (OneNote
     via Microsoft 365 connector, or auto-fetched links/attachments) can be
     scripted or scanned predictably instead of hunted for.
   - Page titles drift. Task 2 asked for a page named "Stage 2 – Define &
     Ideate", but at least one student titled theirs "Task 2". Distributing a
     pre-titled page to every student from the Class Notebook tools would
     remove the guesswork.

## What a background/future session should do with this

When asked to "set up Teams assignments efficiently for assessment," a session
should:
1. Read this doc and `WORKFLOW.md`.
2. Ask Shingo for: course, due date, task description, and the specific learning
   standard(s) to target (offering the relevant department's standards list if
   available).
3. Draft the Teams Assignment instructions in the parseable format above,
   including the instruction to submit via ClassNotebook whenever possible.
4. Confirm submission channel guidance and point/grading scheme match
   MySchool's scale.
5. Create the Assignment via the Microsoft 365 Teams tools (or hand Shingo
   ready-to-paste text if API creation isn't available), and confirm back what
   was set up.

## Open items (not yet decided)
- Whether Teams Assignments API (via `mcp__Microsoft_365__teams_*` tools) supports
  creating an Assignment directly, or whether this always needs the built-in
  browser / manual entry in Teams. To be confirmed when this is actually built.
  (Update 2026-10-30: the Microsoft 365 connector is blocked by RCS
  Conditional Access, so creation goes through the browser. Shingo's
  `rcs-teams-and-myschool-access` skill covers creating Teams assignments
  as drafts.)
- Exact tag/label convention for recording the targeted learning standard per
  assignment (title prefix vs. instructions line vs. a separate tracking sheet).
