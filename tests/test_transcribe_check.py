"""The handwriting measuring tool's arithmetic (tools/transcribe_check.py). Pure functions; no model, no images."""
import os, sys, tempfile
from _common import APPDIR, guard
HOME = tempfile.mkdtemp(); os.environ["HOME"] = HOME; guard(HOME)
sys.path.insert(0, APPDIR); sys.path.insert(0, os.path.join(APPDIR, "tools"))
import transcribe_check as C
ok = []
def check(l, c, x=""): ok.append(bool(c)); print(("PASS " if c else "FAIL ") + l + (("  | " + str(x)[:200]) if x != "" else ""))
check("1 identical text is 0% error", C.rates("My bag is light.", "My bag is light.") == (0.0, 0.0))
check("2 spacing and line breaks do not count as errors", C.rates("My bag\nis light.", "My  bag is   light.") == (0.0, 0.0))
cer, wer = C.rates("the bag is light", "the bag is bright")
check("3 one wrong word out of four is 25% WER, and a few characters of CER", abs(wer - 0.25) < 1e-9 and 0 < cer < 0.2, (cer, wer))
check("4 a bracketed drawing note is not counted as writing", C.rates("My bag", "My bag\n[drawing: a bag with two straps]") == (0.0, 0.0))
check("5 [illegible] counts as a miss", C.rates("my plan is good", "my plan [illegible] good")[1] == 0.25)
check("6 an empty transcription is 100% error and does not divide by zero", C.rates("abc def", "") == (1.0, 1.0) and C.rates("", "")[0] == 0.0)
check("7 edit distance is right on a known case", C.edits("kitten", "sitting") == 3)
print(f"\n{sum(ok)}/{len(ok)} checks passed"); sys.exit(0 if all(ok) else 1)
