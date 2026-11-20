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
print(f"Caller turns where the STT entity differs from the reference transcript: {len(hidden)} (first {min(3, len(hidden))} shown)")
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

# 4. Transcript view: what a reviewer sees from the STT and TTS text alone (world bible, incident log).
VIEW = {"T01": "not visible", "T02": "partly visible", "T03": "visible", "T04": "partly visible", "T05": "visible",
        "T06": "not visible", "T07": "visible", "T08": "visible", "T09": "visible", "T10": "partly visible"}
print("Incident traces: transcript view, and the evidence outside the STT and TTS text")
for iid, t in v.traces(ed).items():
    if not iid.startswith("T"):
        continue
    human = [x for x in t["turns"] if x["speaker"] == "caller" and x["source"] == "human"]
    agent = [x for x in t["turns"] if x["speaker"] == "agent"]
    evidence = []
    if any(x["ref_entities"] != x["stt_entities"] for x in human):
        evidence.append("REF lane (misheard entity)")
    if any(x.get("tts") and x["tts"].get("audio_reading") for x in agent):
        evidence.append("audio (TTS read the text differently)")
    if any(x["barge_in"] for x in agent):
        evidence.append("timeline (barge_in)")
    gap = max(t["timings_summary"]["turn_gap_ms"], default=0)
    if gap >= 3000:  # T04-scale dead air; ordinary tool turns stay under it
        evidence.append(f"timeline ({gap} ms turn gap)")
    tags = sorted({tag for x in human for tag in x["tags"]})
    if tags:
        evidence.append("tags (" + "; ".join(tags) + ")")
    print(f"  {iid} {t['labels'][0]['code']:<13} {VIEW[iid]:<15} {', '.join(evidence) or 'none needed'}")
