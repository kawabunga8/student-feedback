# EarMaster draft outputs

Drafts from `earmaster_feedback.py` on MADE-UP cases only (no real students). Each stress folder is the 16 cases in
`earmaster_cases_stress/`, 3 runs each (48 drafts) on qwen2.5:14b, plus a `summary_*.md` with the automatic checks.
The folder names are historical: some name the prompt version and some the rubric version. This table says what each one is.

| folder | prompt | rubric | first drafts clean | final drafts clean | notes |
|---|---|---|---|---|---|
| `stress/` | v0.2 | v0.1 | 38/48 | 46/48 | first stress batch |
| `stress-v0.3/` | v0.3 | v0.1 | 41/48 | 47/48 | |
| `stress-v0.4/` | v0.4 | v0.1 | 36/48 | 46/48 | |
| `stress-rubric-v0.2/` | v0.4 | v0.2 | 41/48 | 47/48 | Weidlich et al. additions |
| `stress-rubric-v0.2.1/` | v0.4 | v0.2.1 | | | v0.2 fixes; run in progress 2026-11-21 |
| `stress-v0.5/` | v0.5 | v0.2 | 40/48 | 46/48 | from another session; prompt v0.5 not committed yet |

`sample-01-MADE-UP__*.md` is a single run on `earmaster_cases/sample-01.json`.
Real students' drafts never go here: they stay in the vault (see `earmaster_intake.py`).
