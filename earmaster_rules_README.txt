Rule-based comparison (modelled on OnTask: if the data meets a condition, send a set message).
YOU write the rules: copy earmaster_rules_template.csv to earmaster_rules.csv and add 5-6 rows.

Each rule: up to two conditions (both must be true), then one message.
  status                   leave blank for a live rule; rows whose status starts with EXAMPLE or OFF are skipped
  condition_N_field        one of: grade, attempts_30d, active_days_30d, attempts_after_pass,
                           accuracy_first_pct, accuracy_latest_pct, accuracy_change (latest minus first),
                           lessons_completed_count, self_chosen_count, journal_entry, first_mate_note,
                           and the four fields you code by hand (below)
  condition_N_operator     >  >=  <  <=  ==  !=  contains  (contains is for journal_entry / first_mate_note, ignores capitals)
  condition_N_value        a number, or the word to look for
  message_to_student       plain text. You can drop in data with braces, e.g. {accuracy_first_pct} or {accuracy_latest_pct}
  condition_2_*            leave blank if the rule has only one condition

Fields you code by hand (optional; the rules cannot read free text, so you read each reflection and fill these in):
  goal_stated              yes or no: did the student state a goal?
  area_named               a short word such as rhythm, or empty
  prompts_answered         a number: how many of the page's reflection prompts were answered
  prompts_on_page          a number: how many prompts the page had (give both numbers or neither)
A rule on a field you did not code simply does not fire. Time yourself while coding: the minutes go in the
"coding_minutes" column of the review log, because the coding is a cost of the rules mode.
These four fields are NEVER sent to the AI mode (they are kept out of facts_block). The AI reads the journal itself;
giving it your codes too would make the comparison unfair.
When you copy a reflection from OneNote, keep each question's label above its answer in journal_entry, so it is
clear which prompts were answered.

Run:  python3 earmaster_rules.py earmaster_cases/
It prints, for each case, the messages whose rules fired, and the newest AI draft from earmaster_outputs/ next to it.
Saved to earmaster_outputs/comparison_<timestamp>.md.
