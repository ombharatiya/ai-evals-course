"""Module 14 (collections-compliance) solution: compliance checks as code. Run: python3.11 solutions/m14_collections_compliance.py [--edition india]"""
from collections import Counter

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
pol = v.policies(ed)
v.header(C, "Compliance checks on the incident traces")
print("Not legal advice: the checks implement the fictional lender's reading of the rules.")
print(f"Policy pack {pol['policy_pack']}: {len(pol['policies'])} policies; check types: "
      + ", ".join(f"{k} {n}" for k, n in sorted(Counter(p['check_type'] for p in pol['policies']).items())))
print()
rows = []
for iid, t in v.traces(ed).items():
    res = v.run_checks(t, C)
    fails = [f"{x['id']} (turns {', '.join(map(str, x['evidence_turns']))})" for x in res if x["result"] == "fail"]
    rows.append([iid, t["scenario"]["title"][:38], len(res), "; ".join(fails) or "all pass"])
v.table(rows, ["trace", "title", "checks run", "failures with evidence turns"])
print()
cnt = Counter()
for c in v.calls(ed):
    for x in v.run_checks(c, C):
        if x["result"] == "fail":
            cnt[x["id"]] += 1
print("Failures over the 200 simulated calls: " + ", ".join(f"{k} {n}" for k, n in sorted(cnt.items())))
