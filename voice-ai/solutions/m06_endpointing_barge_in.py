"""Module 6 (endpointing-barge-in) solution: an endpointing curve and an operating point. Run: python3.11 solutions/m06_endpointing_barge_in.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
pauses = v.jsonl(ed, "pauses")
v.header(C, "Endpointing: false cutoffs against dead air")
THRESHOLDS = list(range(200, 1001, 50))
WEIGHT = {"date": 5.0, "amount": 5.0, "dispute": 3.0, "small_talk": 1.0, "none": 1.0}
DEAD_AIR_COST_PER_100MS = 0.2  # cost units per 100 ms of dead air on every end pause


def curve(rows, t):
    holds = [p for p in rows if p["label"] == "hold"]
    ends = [p for p in rows if p["label"] == "end"]
    cut = sum(p["pause_ms"] > t for p in holds)
    return cut / len(holds), t, len(holds), len(ends)


def cost_per_1000(rows, t):
    total = 0.0
    for p in rows:
        if p["label"] == "hold" and p["pause_ms"] > t:
            total += WEIGHT[p["content_tag"]]
        elif p["label"] == "end":
            total += DEAD_AIR_COST_PER_100MS * t / 100
    return 1000 * total / len(rows)


rows = []
for g in C["language_groups"]:
    sub = [p for p in pauses if p["language_group"] == g and p["pause_id"] != "T05-p1"]
    fc300 = curve(sub, 300)[0]
    fc600 = curve(sub, 600)[0]
    at5 = next((t for t in THRESHOLDS if curve(sub, t)[0] <= 0.05), None)
    rows.append([g, len(sub), v.pct(fc300), v.pct(fc600), at5])
v.table(rows, ["language group", "pauses", "false cutoff at 300 ms", "at 600 ms", "silence for <= 5% cutoff (ms)"])
print()
mono = all(curve(pauses, a)[0] >= curve(pauses, b)[0] for a, b in zip(THRESHOLDS, THRESHOLDS[1:]))
print(f"False cutoff never rises as the threshold rises: {mono}")
print()
print("Chosen silence budget per campaign and call state (minimum expected cost per 1,000 pauses):")
rows = []
for camp, info in C["campaigns"].items():
    for state in ("default", "amount_asked", "date_asked"):
        sub = [p for p in pauses if p["campaign"] == camp and p["call_state"] == state]
        best = min(THRESHOLDS, key=lambda t: (cost_per_1000(sub, t), t))
        current = info["budget_ms"] if state == "default" else info["budget_asked_ms"]
        rows.append([camp, state, len(sub), best, current, v.pct(curve(sub, current)[0])])
v.table(rows, ["campaign", "call state", "pauses", "chosen ms", "world budget ms", "false cutoff at world budget"])
print()
t05 = next(p for p in pauses if p["pause_id"] == "T05-p1")
verdicts = ", ".join(f"{b} ms {'cuts it off' if t05['pause_ms'] > b else 'waits'}" for b in (300, 400, 600, 800))
print(f"T05: a {t05['pause_ms']} ms hold before a date. {verdicts}.")
print("Silence alone cannot separate this hold from a turn end; a detector that reads the content helps.")
print()
thr = 0.5
for g in C["language_groups"]:
    sub = [p for p in pauses if p["language_group"] == g]
    holds = [p for p in sub if p["label"] == "hold"]
    cut_a = sum(p["pause_ms"] > 300 and p["model_a_hold_prob"] < thr for p in holds) / len(holds)
    print(f"{g}: at 300 ms, silence-only cuts {v.pct(curve(sub, 300)[0])} of holds; "
          f"model A (wait when hold probability >= {thr}) cuts {v.pct(cut_a)}")
