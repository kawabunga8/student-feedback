"""Class-wide patterns from the per-student criteria checklist, with no student names or work in the result.

The drafting step already records, for each student, which of the teacher's "Looking for" criteria the work met
(`done`) and which it did not (`missing`); see feedback.work_checklist. This module only counts those lists. It never
sees student names, work or feedback text, and it makes no model call, so it is safe to run on any set of rows.

    rows = [{"done": ["clear claim"], "missing": ["evidence"]}, ...]      # one dict per student, any order
    summary = summarize(rows, ["clear claim", "evidence"])
    print(render_markdown(summary, title="Task 2"))

Privacy rule: a class with fewer than `min_group` checked students gets no counts at all, because in a very small
group a count points at individuals. The teacher reviews the report before using or sharing it."""
import re

DEFAULT_MIN_GROUP = 5


def _norm(text):
    return re.sub(r"\W+", " ", str(text).lower()).strip()


def summarize(rows, criteria, min_group=DEFAULT_MIN_GROUP):
    """Count, per criterion, how many students met it and how many did not.

    A student counts for a criterion only if that criterion appears in their `done` or `missing` list; a student with
    neither (checklist unavailable) is "not checked" for it and is left out of its percentages. If a criterion is in
    both lists the student is treated as not checked for it, because the record contradicts itself.
    Returns {"students": n, "min_group": k, "suppressed": bool, "criteria": [ {criterion, met, not_met, checked,
    percent_not_met} ... ]}. Criteria keep the teacher's order; `suppressed` is True when no criterion has at least
    `min_group` checked students, and then every count is None."""
    rows = list(rows)
    out = []
    for crit in criteria:
        key = _norm(crit)
        met = not_met = 0
        for r in rows:
            done = {_norm(c) for c in (r.get("done") or [])}
            missing = {_norm(c) for c in (r.get("missing") or [])}
            if key in done and key in missing:
                continue
            if key in done:
                met += 1
            elif key in missing:
                not_met += 1
        checked = met + not_met
        if checked < min_group:
            out.append({"criterion": crit, "met": None, "not_met": None, "checked": checked, "percent_not_met": None})
        else:
            out.append({"criterion": crit, "met": met, "not_met": not_met, "checked": checked,
                        "percent_not_met": round(100 * not_met / checked)})
    return {"students": len(rows), "min_group": min_group,
            "suppressed": all(c["met"] is None for c in out), "criteria": out}


def render_markdown(summary, title=""):
    """A short report for the teacher: criteria from most to least often unmet, then a plain note on its limits."""
    lines = ["# Class patterns" + (f": {title}" if title else ""), ""]
    shown = [c for c in summary["criteria"] if c["met"] is not None]
    if not shown:
        lines += [f"Too few students were checked to report patterns (at least {summary['min_group']} are needed "
                  "for a criterion). Counts are hidden so they cannot point to individual students.", ""]
    else:
        lines += [f"{summary['students']} students in this set. Criteria are listed from most to least often not yet met.", "",
                  "| Criterion | Met | Not yet met | Not yet met (%) |", "|---|---|---|---|"]
        for c in sorted(shown, key=lambda c: (-c["percent_not_met"], summary["criteria"].index(c))):
            lines.append(f"| {c['criterion']} | {c['met']} | {c['not_met']} | {c['percent_not_met']}% |")
        hidden = [c["criterion"] for c in summary["criteria"] if c["met"] is None]
        if hidden:
            lines += ["", "Hidden because fewer than " + str(summary["min_group"]) + " students were checked: " + "; ".join(hidden) + "."]
        lines.append("")
    lines += ["This report counts what the automatic checklist found. It is a prompt for your own review of the work, "
              "not an assessment. It does not set levels or grades, and it has not been checked against the students' "
              "work. Review it before using or sharing it."]
    return "\n".join(lines) + "\n"
