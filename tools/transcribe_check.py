#!/usr/bin/env python3
"""Measure how well a local vision model reads handwriting, on pages YOU supply with the correct text.

    python3 tools/transcribe_check.py --model qwen3-vl:8b page1.jpg page1.txt  page2.png page2.txt

Each image is followed by a plain-text file holding what the page really says. Use pages you have permission to use and
that carry no identifying information (invented, your own handwriting, or de-identified practice work). The images
go only to Ollama on this computer. Nothing is saved except the figures printed here: no image, no transcription.

Reports per page: character error rate (CER: edits needed / characters in the real text; 0% is perfect),
word error rate (WER), parts the model marked [illegible], and seconds. Lower is better. Compare models by running it
twice with different --model values (for example qwen3-vl:8b and qwen2.5vl:7b) on the same pages.
"""
import argparse, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import vision_read as V


def edits(a, b):
    """Levenshtein distance between two sequences."""
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def norm(t):
    return re.sub(r"\s+", " ", t.replace("’", "'")).strip()


def rates(truth, got):
    """(CER, WER) of `got` against `truth`, ignoring spacing differences. Bracketed notes such as [drawing: ...] are
    not part of the written words, so they are removed from the model's text; [illegible] counts as a miss."""
    t, g = norm(truth), norm(re.sub(r"\[(?:drawing|diagram|table|picture|image|photo)[^\]]*\]", " ", got, flags=re.I))
    cer = edits(t, g) / max(1, len(t))
    tw, gw = t.split(), g.split()
    return cer, edits(tw, gw) / max(1, len(tw))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pairs", nargs="+", help="image1 truth1 image2 truth2 ...")
    ap.add_argument("--model", default="")
    a = ap.parse_args()
    if len(a.pairs) % 2:
        sys.exit("Give pairs: an image, then a text file with what it says.")
    tot = []
    for img, truth in zip(a.pairs[::2], a.pairs[1::2]):
        raw, want = open(img, "rb").read(), open(truth, encoding="utf-8").read()
        t0 = time.time()
        try:
            r = V.transcribe(raw, a.model)
        except V.VisionError as e:
            print(f"{os.path.basename(img)}: {e}")
            continue
        cer, wer = rates(want, r["text"])
        tot.append((cer, wer))
        print(f"{os.path.basename(img)}: CER {cer:.0%}  WER {wer:.0%}  illegible {r['illegible']}  {time.time() - t0:.0f}s  ({r['model']})")
    if tot:
        print(f"Mean over {len(tot)} page(s): CER {sum(c for c, _ in tot) / len(tot):.0%}  WER {sum(w for _, w in tot) / len(tot):.0%}")


if __name__ == "__main__":
    main()
