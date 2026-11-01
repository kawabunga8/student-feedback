import sys, json
from _common import APPDIR, guard, guard_app, block_live_browser
sys.path.insert(0, APPDIR)
import teams_read as T
block_live_browser(T)
ok=[]
def check(l,c,x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ")+l+(("  | "+str(x)[:200]) if x!="" else ""))

from teams_fixtures import LIST, names, sts, roster, SV, CLASS_ID, ASSIGNMENT_ID
items = T.parse_list(LIST)
check("1 list: 7 rows read", len(items)==7, len(items))
t4=[x for x in items if x["title"].startswith("Task A") and "Q1" in x["class_name"]][0]
check("  title, class, fractions, date heading", t4["class_name"]=="RCS - H - Q1 ICT 9 [2026-27]" and t4["fractions"]==["2/28","0/2"] and t4["due_heading"]=="Nov 4th" and t4["due_text"]=="Due at 3:00 PM", t4)
check("  initials line is not taken as title", all(len(x["title"])>3 for x in items))
check("  a row with one fraction", [x for x in items if x["title"].startswith("Sample Summative")][0]["fractions"]==["0/8"])
check("  year heading 'Jan 8, 2027' read", [x for x in items if x["title"]=="Stage 5 – Sample Share"][0]["due_heading"]=="Jan 8, 2027")
# matching
m=T.match_assignment(items,"RCS - H - Q1 ICT 9 [2026-27]","Task A: Build & Share")
check("2 match on class AND title picks the Q1 one", m["class_name"].endswith("Q1 ICT 9 [2026-27]") and m["fractions"]==["2/28","0/2"])
try: T.match_assignment(items,"RCS - H - Q1 ICT 9 [2026-27]","Task A"); check("  partial title refused", False)
except T.ReadError as e: check("  partial title refused, near candidates listed", e.kind=="differs" and len(e.extra["candidates"])>=2, e.extra)
try: T.match_assignment(items+[dict(t4)],"RCS - H - Q1 ICT 9 [2026-27]","Task A: Build & Share"); check("  two exact matches refused", False)
except T.ReadError as e: check("  two exact matches refused", "2 assignments" in str(e))

r=T.parse_roster(roster(list(zip(names,sts)),6,6))
check("3 roster: whole-row counts, 6 students", r["statuses"]=={"Viewed":4,"Not turned in":1,"Turned in":1} and r["rows_read"]==6 and r["consistent"], r)
check("  'Returned' is not counted from the tab label", "Returned" not in r["statuses"] and r["returned"]==0 and r["to_return"]==6)
check("  'Turned in' not counted inside 'Not turned in'", r["statuses"]["Turned in"]==1)
check("  no names in the result", not any(n in json.dumps(r) for _,n in names))
r2=T.parse_roster(roster(list(zip(names,sts)),7,7))
check("  rows not matching 'N results found' -> inconsistent", r2["consistent"] is False)
r3=T.parse_roster(roster(list(zip(names,["Viewed"]*5+["Needs a look"])),6,6))
check("  unknown status reported", r3["unknown_statuses"]=={"Needs a look":1}, r3["unknown_statuses"])
r4=T.parse_roster(roster(list(zip(names,sts)),6,6).replace("Test, Charlie\n","").replace("Test, Charlie",""))
check("  ragged rows -> inconsistent, no crash", r4["consistent"] is False)
r5=T.parse_roster("nonsense")
check("  unrelated text -> inconsistent, no crash", r5["consistent"] is False and r5["rows_read"]==0)

v=T.parse_student_view(SV)
check("4 student view: title, due, flags", v["title"]=="Task A: Build & Share" and v["due"]=="Due November 4, 2026 3:00 PM" and v["multiple_submissions"] and v["is_preview"] and v["found"], {k:v[k] for k in ("title","due")})
check("  instructions kept whole, stops at Reference materials", v["instructions"].startswith("Instructions:") and "No crashes: test every path." in v["instructions"] and "Sample deck" not in v["instructions"], v["instructions"][-60:])
check("  reference materials listed by name, marked not read", v["reference_materials"]==["Sample deck.pptx","Sample docs"] and v["reference_materials_read"] is False)
check("  points section", v["points"]=="No points", v["points"])
check("  Teams' flashcards widget is dropped", "flashcards" not in json.dumps(v))
check("  sections found", v["sections_found"]==["Instructions","Reference materials","My work","Points"], v["sections_found"])
check("  blank-line runs collapsed", "\n\n\n" not in v["instructions"])
v2=T.parse_student_view("Back\nSome other page\nHello")
check("  a non-assignment page is not 'found'", v2["found"] is False)
v3=T.parse_student_view(SV.replace("Reference materials\nSample deck.pptx\nSample docs\n",""))
check("  no Reference materials section -> empty list, instructions to next heading", v3["reference_materials"]==[] and "Sample docs" not in v3["instructions"] and v3["instructions"].endswith("every path."))
# a rubric-like heading inside instructions stays inside instructions
v4=T.parse_student_view(SV.replace("1. Keep building.","Rubric\nEmerging: starts\nProficient: finishes\n1. Keep building."))
check("  a 'Rubric' line inside the instructions stays in the instructions (no separate rubric section assumed)", "Proficient: finishes" in v4["instructions"])
u="https://assignments.example.test/classes/11111111-2222-4333-8444-555555555555/assignment-review/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee?x=1"
u2="https://assignments.example.test/classes/11111111-2222-4333-8444-555555555555/assignments/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee/preview"
check("5 ids from the roster and preview addresses agree", T.ids_from_url(u)==T.ids_from_url(u2) and T.ids_from_url(u)["assignment_id"].startswith("aaaaaaaa"))
check("  no ids from other addresses", T.ids_from_url("https://x/classes/all/list")=={"class_id":"","assignment_id":""})
pv="https://assignments.example.test/classes/11111111-2222-4333-8444-555555555555/assignments/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee/preview"
check("6 preview address: plain, trailing slash, query and fragment all count", all(T.is_preview_url(x) for x in (pv, pv+"/", pv+"?a=1", pv+"#top", pv+"/?a=1#x")))
check("  roster address and other pages are not the preview", not T.is_preview_url(u) and not T.is_preview_url("") and not T.is_preview_url(pv+"/edit"))
sh=T.url_shape(pv+"?token=SECRET#x")
check("  address shape masks ids and drops the query value", "<id>" in sh and "SECRET" not in sh and "11111111" not in sh and sh.startswith("/classes/<id>/assignments/<id>/preview"), sh)
rv=u.split("?")[0]
check("  roster address: review path counts (query ok); preview, list and empty do not", T.is_review_url(rv) and T.is_review_url(u) and not T.is_review_url(pv) and not T.is_review_url("https://assignments.example.test/classes/all/list") and not T.is_review_url(""))
print(f"\n{sum(ok)}/{len(ok)} passed"); sys.exit(0 if all(ok) else 1)
