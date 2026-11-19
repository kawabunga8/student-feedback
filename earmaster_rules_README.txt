Rule-based comparison (modelled on OnTask: if the data meets a condition, send a set message).
YOU write the rules: copy earmaster_rules_template.csv to earmaster_rules.csv and add 5-6 rows.

Each rule: up to two conditions (both must be true), then one message.
  status                   leave blank for a live rule; rows whose status starts with EXAMPLE or OFF are skipped
  condition_N_field        one of: grade, attempts_30d, active_days_30d, attempts_after_pass,
                           accuracy_first_pct, accuracy_latest_pct, accuracy_change (latest minus first),
                           lessons_completed_count, self_chosen_count, journal_entry, first_mate_note
  condition_N_operator     >  >=  <  <=  ==  !=  contains  (contains is for journal_entry / first_mate_note, ignores capitals)
  condition_N_value        a number, or the word to look for
  message_to_student       plain text. You can drop in data with braces, e.g. {accuracy_first_pct} or {accuracy_latest_pct}
  condition_2_*            leave blank if the rule has only one condition

Run:  python3 earmaster_rules.py earmaster_cases/
It prints, for each case, the messages whose rules fired, and the newest AI draft from earmaster_outputs/ next to it.
Saved to earmaster_outputs/comparison_<timestamp>.md.
