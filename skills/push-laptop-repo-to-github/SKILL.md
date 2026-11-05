---
name: push-laptop-repo-to-github
description: Commit and/or push authorized student-feedback code and documentation changes from the local checkout to its GitHub remote. Use when asked to save project changes in Git, commit, push, or sync this repository.
---

# Commit and push student-feedback changes

Resolve the checkout relative to this skill (`../..`). Its expected remote is `git@github.com:kawabunga8/student-feedback.git`; verify the current branch, remote and working tree instead of assuming they are unchanged.

A request to update code or skills alone does not authorize a commit or push. A commit-only request stops after committing; a push-only request does not implicitly include unrelated uncommitted edits. An explicit commit-and-push request authorizes the ordinary local commit and remote push without another blanket confirmation.

## Prepare a reviewable commit

- Inspect `git status --short`, the current branch/upstream, recent history and the exact staged/unstaged diff. Preserve concurrent user changes. Identify the files that belong to the requested work; clarify ownership only when it is genuinely ambiguous.
- Inspect `.gitignore` and the staged content. Never include student submissions, generated feedback, roster/export files, assessment manifests, notebook screenshots/URLs with private content, Chrome profiles, job sidecars/journals, `.env*`, credentials or private teacher notes. Ignored patterns are not a substitute for checking the staged diff. Do not print secrets while inspecting files.
- Stage explicit paths or selected hunks. Do not use a blanket `git add .` or `git add -A` on a mixed working tree. Do not reset, clean or discard user work to produce a clean status.
- Run checks proportional to the change and `git diff --check`. For skills, validate each changed `SKILL.md` with an available skill validator and check referenced files. For JS/Python or posting changes, use the relevant synthetic suites and syntax checks. Consult [tests/README.md](../../tests/README.md): older suites may target removed dialogs, and the full runner needs production ports free. Do not stop the app/Ollama or run a live school write as an implicit test of a commit.
- Report a blocked or failing check accurately. Do not turn a targeted pass into a claim that the whole suite or a live posting workflow passed.

## Commit and push

Review `git diff --cached --stat` and `git diff --cached` before committing. Use a message describing the final behavior and scope. For multiline messages, use a temporary message file and `git commit -F`; do not interpolate untrusted Markdown into shell code. Do not amend an existing commit unless requested.

Before a push, verify the intended remote branch. Fetch when needed to establish remote state. If the remote is ahead or histories diverge, inspect the commits and reconcile within the user's authorized task; do not force-push, overwrite remote history or automatically merge unrelated work. Preserve the user's chosen branch. Push to `main` only when that is the requested/current intended destination; do not introduce a pull-request or branch workflow unnecessarily.

Use normal Git authentication. A missing credential or network/sandbox block is not permission to extract tokens, change remotes to an unapproved destination or bypass access controls.

## Verify and report

Check the resulting commit and working tree. After a push, verify that the destination branch contains the intended commit, using the successful push result and the remote ref when available. If remote verification is unavailable, state that limit instead of claiming it succeeded.

Report the commit hash, destination branch, checks actually run, and any requested work left uncommitted or unpushed. Do not say the working tree is clean unless it is; distinguish the task's changes from preserved unrelated edits. Creating/updating this skill is not itself an instruction to execute these Git mutations.
