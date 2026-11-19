# BUILD_LOG: EarMaster reflection feedback mode

For Shingo's ETEC 543 Assignment 2 AI-use statement. Records what Claude Code built or changed and what Shingo decided.
Rules: no real student data; everything local through Ollama.

## 2026-11-19
- Shingo confirmed the repo: `~/Repos-folder/student-feedback` (not the SSD copy, not `student-feedback-sharepoint`).
- Step 1 (explore, no code changes): Claude Code read `feedback.py`, README and ARCHITECTURE. Model is Ollama `qwen2.5:14b`;
  prompts live in `SYSTEM_TEMPLATE`/`generate()` in `feedback.py`. Left `collected/`, `feedback/`, `quality-reports/` unread (may hold real data).
- Step 2 (test case format): added `earmaster_cases.py` (field list, validator, loader). No duration field by design.
  Check with `python3 earmaster_cases.py earmaster_cases/`. Nothing committed.
- Open questions for Shingo: which BC standards to tie to; CSV review log vs `*.csv` in `.gitignore`.

## 2026-11-19 (later)
- Shingo chose RCS Fine Arts 9-12 as the standards. At his request, Claude Code checked Course Hub (local Supabase `learning_standards`, subject `FA`): same 5 standards as the PDF, no teacher edits to rubric text. Only read standards tables, no student data.
- Step 3: added `earmaster_rubric.md` (v0.1; standards 1-3 with per-grade focus; Hattie & Timperley three questions) and `earmaster_feedback.py` (prompt `earmaster-prompt-v0.1`; separate from `feedback.py`, which is unchanged). Code checks each draft for person-praise, practice-time words and the three headings, retrying up to twice; appends a "Data used" line and a DRAFT notice.
- Step 4: added one made-up case `earmaster_cases/sample-01.json` (case_id marked MADE-UP).
- Ran the mode on sample-01 (qwen2.5:14b). v0.1 draft noted low timing scores but did not ask about setup; Claude Code tightened the prompt (v0.2) so a timing mention forces one setup question. v0.2 draft does so. Also strips a stray "(N words)" the model adds. Shingo still needs to read the output himself: v0.2 acknowledged self-chosen exercises as a good habit but not explicitly practising past a pass.
- Step 5 (batch run): `earmaster_feedback.py` now takes a folder. `python3 earmaster_feedback.py earmaster_cases/` runs every case and saves `earmaster_outputs/<case_id>__<timestamp>.md`, each with a header: case_id, model, rubric_version (from `earmaster_rubric.md`), prompt_version, timestamp, status DRAFT. One failed case does not stop the rest. Tested on sample-01 (1 case). Outputs folder is not in `.gitignore`; it holds only made-up-case drafts.
- Step 6 (review log): Shingo approved a `.gitignore` exception. Added `earmaster_review_log_template.csv` (header only, 9 columns from the brief) and un-ignored that one filename. Copy it to e.g. `earmaster_review_log.csv` to fill in; that copy stays git-ignored.
- Step 7 (rule-based comparison): added `earmaster_rules_template.csv` (one EXAMPLE row; Shingo writes the real 5-6 rules), `earmaster_rules_README.txt` (fields/operators), and `earmaster_rules.py` (applies rules to cases; prints rule messages beside the newest AI draft; no model, no network). Claude Code wrote NO rules. Tested with a throwaway 3-rule file in the scratchpad, not saved in the repo. `.gitignore` exception for the template only.
- README section added (appended at the end; README.md already had uncommitted edits from before). All seven steps built; nothing committed.
