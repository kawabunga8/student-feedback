"""Synthetic text shaped like what Teams' Assignments frame showed on 2026-11-01. Every name, class, title and
identifier here is invented. No real student, class or assignment data belongs in this file."""

CLASS_A = "RCS - H - Q1 ICT 9 [2026-27]"      # generic class names in the school's naming format
CLASS_A2 = "RCS - H - Q2 ICT 9 [2026-27]"
CLASS_ID = "11111111-2222-4333-8444-555555555555"
ASSIGNMENT_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"

LIST = """Assignments
Upcoming
Ready to grade
Past due
Returned
Drafts
Nov 2nd
Tomorrow
N
Sample Readiness Statement
Due at 11:59 PM
RCS - X - Sample Course A [2026-27]
3/20
0/3
Nov 4th
Wednesday
T
Task A: Build & Share
Due at 3:00 PM
RCS - H - Q1 ICT 9 [2026-27]
2/28
0/2
Nov 6th
Friday
S
Stage 1 – Sample Context
Due at 11:59 PM
RCS - X - Sample Course B [2026-27]
2/8
0/2
S
Sample Summative: Design Challenge
Due at 11:59 PM
RCS - X - Sample Course C [2026-27]
0/8
Next week
Nov 9th
Monday
T
Task B: Review & Share
Due at 3:00 PM
RCS - H - Q1 ICT 9 [2026-27]
0/28
Further out
Jan 8, 2027
Friday
S
Stage 5 – Sample Share
Due at 11:59 PM
RCS - X - Sample Course B [2026-27]
0/8
Task A: Build & Share
Due at 3:00 PM
RCS - H - Q2 ICT 9 [2026-27]
0/20
"""

names = [("TA", "Test, Alpha"), ("TB", "Test, Bravo"), ("TC", "Test, Charlie"), ("TD", "Test, Delta"), ("TE", "Test, Echo"), ("TF", "Test, Foxtrot")]
sts = ["Viewed", "Viewed", "Viewed", "Not turned in", "Turned in", "Viewed"]


def roster(rows, results, to_ret, ret=0):
    body = "\n".join(f"{a}\n{n}\n{s}" for (a, n), s in rows)
    return (f"Back\nReturn\nTask A: Build & Share\nDue November 4, 2026 3:00 PM\n•\nMultiple submissions allowed\nTo return ({to_ret})\n"
            f"Returned ({ret})\nActivate the context menu for more options.\nName\nActivate the context menu for more options.\nStatus\n"
            f"Activate the context menu for more options.\nFeedback\n{body}\n\n{results} results found")


SV = """You are viewing a preview of what this assignment will look like when it is assigned to your students.
Back
Task A: Build & Share
Due November 4, 2026 3:00 PM
•
Multiple submissions allowed
Instructions

Instructions:




Build a small sample project. Use slides 3–5 of the sample deck.




Where to submit: Class Notebook → Homework → Sample Page.




Your tasks:




1. Keep building.

3+ working screens: every screen has meaningful content.
No crashes: test every path.

Reference materials
Sample deck.pptx
Sample docs
My work
Add work
Turn in
Points
No points
Turn this doc into flashcards
"""


# Same synthetic page, with Teams' rubric marker after the instructions (the rubric text itself is not on this page).
SV_RUBRIC = SV.replace("\nPoints", "\nRubric\nView rubric\nPoints", 1)
