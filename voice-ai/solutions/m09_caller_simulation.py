"""Module 9 (caller-simulation) solution: coverage and sim-versus-real. Run: python3.11 solutions/m09_caller_simulation.py [--edition india]"""
from collections import defaultdict

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
prod = v.jsonl(ed, "production_sample")
v.header(C, "Simulated callers: coverage and fidelity")

fg = {f: g for g, fl in C["flow_groups"].items() for f in fl}
cover = defaultdict(set)
for c in calls:
    s = c["scenario"]
    cover[(fg[s["flow"]], s["language_group"])].add(s["scenario_id"])
rows = [[g, lg, len(cover[(g, lg)])] for g in C["flow_groups"] for lg in C["language_groups"]]
v.table(rows, ["flow group", "language group", "scenarios"])
missing = [r for r in rows if r[2] == 0]
print(f"Gated segments without a scenario: {len(missing)}")
print()
sim = defaultdict(lambda: [0, 0])
for c in calls:
    res = {x["id"]: x["result"] for x in v.run_checks(c, C)}
    for cid in ("C04", "C08", "C09", "C12"):
        if cid in res:
            sim[cid][1] += 1
            sim[cid][0] += res[cid] == "pass"
real = defaultdict(lambda: [0, 0])
for r in prod:
    if not r["checks"]:
        continue
    for cid, res in r["checks"].items():
        if res != "n/a":
            real[cid][1] += 1
            real[cid][0] += res == "pass"
rows = []
for cid in ("C04", "C08", "C09", "C12"):
    s_ok, s_n = sim[cid]
    r_ok, r_n = real[cid]
    rows.append([cid, f"{s_ok}/{s_n}", v.pct(s_ok / s_n) if s_n else "-", f"{r_ok}/{r_n}", v.pct(r_ok / r_n) if r_n else "-",
                 f"{100 * (s_ok / s_n - r_ok / r_n):+.1f} pts" if s_n and r_n else "-"])
v.table(rows, ["check", "sim pass", "sim rate", "real pass", "real rate", "sim minus real"])
print("A simulator whose pass rates sit far from production on the same checks is not yet a stand-in for real callers.")
