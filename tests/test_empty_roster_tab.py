"""A roster tab nobody is in ('Returned (0)') is a complete, empty tab; a half-loaded list is not. Invented page text only."""
import os, sys, tempfile
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); os.chdir(APPDIR)
import teams_read as T, teams_batch as B
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:160]) if x != "" else ""))

EMPTY_RETURNED = "Back\nReturn\nTask 5\nDue November 9\nMultiple submissions allowed\nTo return (28)\nReturned (0)\nGrab a snack. Let's grade."
p = T.parse_roster_students(EMPTY_RETURNED)
check("1 the parser alone still calls it incomplete (no column headings)", not p["complete"] and "column headings" in p["why"])
check("2 a tab labelled (0) with no rows counts as empty", B.empty_tab(EMPTY_RETURNED, "Returned", p))
check("3 the other tab is not empty just because Returned says 0", not B.empty_tab(EMPTY_RETURNED, "To return", p))
LOADING = "Back\nReturn\nTask 5\nTo return (28)\nReturned (0)\nLoading"
check("4 a half-loaded 'To return' (label says 28) is never treated as empty", not B.empty_tab(LOADING, "To return", T.parse_roster_students(LOADING)))
HALF = "To return (28)\nReturned (0)\nName\nStatus\nFeedback\nAda Test\nViewed\n-\n1 result found"
check("5 a list that has headings but too few rows is not empty", not B.empty_tab(HALF, "Returned", T.parse_roster_students(HALF)))
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
