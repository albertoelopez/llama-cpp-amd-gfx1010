#!/usr/bin/env python3
"""Summarize the corrected C3 measurement.

Two rules drive the output format, both from defects in the earlier attempts:

* Report DISTRIBUTIONS, never point values. Back-to-back identical HIP runs at
  -ncmoe 28 varied ~25%, so "HIP does 143.76 t/s" is a claim about one draw.
* Compare PAIRED. The harness interleaves the backends within each rep precisely so
  thermal/clock drift is shared; the per-rep ratio therefore cancels drift that an
  independent-means comparison would leave in. Where the per-rep ratios straddle 1.0,
  there is no reliable winner and we say so instead of quoting the average.
"""
import csv, statistics as st, sys
from collections import defaultdict

PATH = sys.argv[1] if len(sys.argv) > 1 else "/mnt/d/AI_Projects/llama-cpp-amd/verify/c3fix/results.csv"

rows = []
with open(PATH) as f:
    for r in csv.DictReader(f):
        try:
            r["tps"] = float(r["tps"]); r["rep"] = int(r["rep"])
        except (ValueError, KeyError):
            continue
        rows.append(r)

if not rows:
    sys.exit(f"no usable rows in {PATH}")

BE = {"hip-gfx1010": "HIP", "vulkan": "Vulkan"}
cells = defaultdict(list)
for r in rows:
    cells[(r["ncmoe"], r["test"], BE.get(r["backend"], r["backend"]))].append(r["tps"])

def spread(v):
    """Percent spread of the middle of the distribution; the honest 'how stable is this'."""
    return (max(v) - min(v)) / st.median(v) * 100 if len(v) > 1 and st.median(v) else 0.0

print(f"source: {PATH}   rows: {len(rows)}\n")
print("PER-CELL DISTRIBUTIONS  (t/s)")
print(f"{'ncmoe':>5} {'test':<16} {'backend':<7} {'n':>2} {'median':>8} {'min':>8} {'max':>8} {'spread%':>8}")
for (nc, test, be) in sorted(cells):
    v = cells[(nc, test, be)]
    print(f"{nc:>5} {test:<16} {be:<7} {len(v):>2} {st.median(v):>8.2f} {min(v):>8.2f} {max(v):>8.2f} {spread(v):>7.1f}%")

# Paired: same rep, same ncmoe, same test -> one HIP/Vulkan ratio per rep.
byrep = defaultdict(dict)
for r in rows:
    byrep[(r["ncmoe"], r["test"], r["rep"])][BE.get(r["backend"], r["backend"])] = r["tps"]

print("\nPAIRED HIP/Vulkan RATIO  (>1 = HIP faster; per-rep, so drift cancels)")
print(f"{'ncmoe':>5} {'test':<16} {'pairs':>5} {'median':>8} {'min':>8} {'max':>8}  verdict")
for (nc, test) in sorted({(k[0], k[1]) for k in byrep}):
    ratios = [d["HIP"] / d["Vulkan"]
              for k, d in byrep.items()
              if k[0] == nc and k[1] == test and d.get("Vulkan")and d.get("HIP")]
    if not ratios:
        continue
    lo, hi, med = min(ratios), max(ratios), st.median(ratios)
    if lo > 1.0:   verdict = f"HIP faster in every pair (>= {lo:.2f}x)"
    elif hi < 1.0: verdict = f"Vulkan faster in every pair (<= {hi:.2f}x)"
    else:          verdict = "NO RELIABLE WINNER - ratios straddle 1.0"
    print(f"{nc:>5} {test:<16} {len(ratios):>5} {med:>8.2f} {lo:>8.2f} {hi:>8.2f}  {verdict}")

print("\nNote: a cell with a large spread% cannot support a quoted point value.")
