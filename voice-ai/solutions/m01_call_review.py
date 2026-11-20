"""Module 1 (call-review) solution: listen, then code. Run: python3.11 solutions/m01_call_review.py [--edition india]"""
from collections import Counter

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
v.header(C, "Error analysis on calls")

# 1. What the transcript hides: caller turns where the STT entity differs from the reference entity.
hidden = []
for c in calls:
    for t in c["turns"]:
        if t["speaker"] == "caller" and t["source"] == "human" and t["ref_entities"] != t["stt_entities"]:
            hidden.append((c["call_id"], t["turn_id"], t["reference_text"], t["stt_final"]["text"]))
print(f"Caller turns where the STT entity differs from the reference transcript: {len(hidden)}")
for cid, tid, ref, hyp in hidden[:3]:
    print(f"  {cid} turn {tid}")
    print(f"    REF: {ref}")
    print(f"    STT: {hyp}")
print()

# 2. First-failure codebook from the primary reviewer (one code per call).
first = Counter(next(l["code"] for l in c["labels"] if l["labeler"] == "rv-03") for c in calls)
failing = sum(n for code, n in first.items() if code != "NONE")
print(f"Taxonomy {C['taxonomy']['version']}: {failing} of {len(calls)} calls have a first failure")
rows = []
for cat, info in C["taxonomy"]["categories"].items():
    for code in info["codes"]:
        if first.get(code):
            rows.append([code, cat, first[code], v.pct(first[code] / failing)])
v.table(rows, ["code", "category", "calls", "share of failing"])
print()

# 3. Reviewer agreement on the 30 shared calls.
pairs = []
for c in calls:
    if c["review_set"] != "shared-30":
        continue
    a = next(l["code"] for l in c["labels"] if l["labeler"] == "rv-03")
    b = next(l["code"] for l in c["labels"] if l["labeler"] == "rv-11")
    pairs.append((a, b))
agree = sum(a == b for a, b in pairs)
print(f"Shared calls: {len(pairs)}; same first-failure code: {agree}; Cohen's kappa {v.kappa(pairs):.3f}")
for a, b in pairs:
    if a != b:
        print(f"  disagreement: rv-03 {a} vs rv-11 {b}")
print()

# 4. Which incident failures are invisible in a transcript-only review?
print("Incident traces: does the STT text alone show the failure turn's problem?")
for iid, t in v.traces(ed).items():
    if not iid.startswith("T"):
        continue
    lab = t["labels"][0]
    diff = any(x["speaker"] == "caller" and x["source"] == "human" and x["reference_text"].replace(",", "") != x["stt_final"]["text"].replace(",", "")
               and x["ref_entities"] != x["stt_entities"] for x in t["turns"])
    print(f"  {iid} {lab['code']:<13} STT differs from REF on an entity: {'yes' if diff else 'no'}")
