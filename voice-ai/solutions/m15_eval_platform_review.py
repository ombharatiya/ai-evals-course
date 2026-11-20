"""Module 15 (eval-platform-review) solution: incident coverage table for the capstone. Run: python3.11 solutions/m15_eval_platform_review.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
v.header(C, "Capstone evidence: which component catches each incident")
BY_CODE = {"ENT.DATE": "spoken-entity round-trip suite (TTS -> 8 kHz -> STT)", "LAT.TAIL": "P95 tool-turn gate + load test at peak",
           "TURN.CUTOFF": "false-cutoff gate per campaign and call state", "OUT.AMD": "six-class AMD matrix gate",
           "STT.LID": "code-switch simulation + clarification-loop check", "TURN.BARGEIN": "barge-in recovery suite",
           "POL.HARDSHIP": "C09 order check + J2 once validated", "POL.COERCE": "lexicon on every call + J1 flags to human audit",
           "ENT.AMOUNT": "amount entity error rate gate", "POL.DISCLOSE": "C04 ordered-event check on every call"}
rows = []
for iid, t in v.traces(ed).items():
    if not iid.startswith("T"):
        continue
    code = t["labels"][0]["code"]
    fails = v.failed(v.run_checks(t, C))
    diff = v.task_diff(t)
    parts = [", ".join(fails)] if fails else []
    if diff:
        parts.append("CRM diff")
    parts.append(BY_CODE.get(code, "-"))
    rows.append([iid, code, " | ".join(parts)])
v.table(rows, ["trace", "first failure", "caught by (checks | CRM diff | component)"])
print()
caught_twice = sum(1 for r in rows if r[2].count("|") >= 1)
print(f"Incidents caught by two or more independent components: {caught_twice} of {len(rows)}")
cm = C["cost_model"]
print(f"Budget frame: today {v.major(C, cm['baseline_total'])} under {v.major(C, cm['monthly_cap_today'], 0)}; "
      f"at {cm['capstone_volume_factor']}x about {v.major(C, cm['capstone_total'])} against {v.major(C, cm['monthly_cap_capstone'], 0)}.")
