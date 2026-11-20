"""Module 13 (voice-monitoring) solution: sample sizes for rare violations. Run: python3.11 solutions/m13_voice_monitoring.py [--edition india]"""
import math
from collections import Counter

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
prod = v.jsonl(ed, "production_sample")
wr, vol = C["world_rates"], C["volumes"]
v.header(C, "Production monitoring: rare violations")

human = [r for r in prod if r["human_answer"]]
strata = Counter(r["stratum"] for r in human)
rows = []
for s, n in sorted(strata.items(), key=lambda x: -x[1]):
    lo, hi = v.wilson(n, len(human))
    rows.append([s, n, v.pct(n / len(human), 2), f"[{v.pct(lo, 2)}, {v.pct(hi, 2)}]"])
v.table(rows, ["stratum", "human-answered calls", "share", "Wilson 95%"])
risky = sum(n for s, n in strata.items() if s != "other") / len(human)
print(f"Risk strata share in the sample: {v.pct(risky, 2)} (world plan: {v.pct(wr['risk_strata_share_of_connects'], 1)} of connects)")
print()
p_detect = lambda rate, n: 1 - (1 - rate) ** n
n95 = math.ceil(math.log(0.05) / math.log(1 - 1 / 1000))
print(f"Calls to see a 1-in-1,000 violation with 95% probability: {n95}")
print(f"1,000 sampled calls at 1 in 2,000: P(at least one) = {p_detect(1 / 2000, 1000):.3f}")
print(f"0 violations in 300 audited calls: rule of three {3 / 300:.4f}; exact two-sided upper {v.cp_upper(0, 300, 0.025):.4f}")
print()
connects = vol["connected_calls_per_day"]
threat = wr["threat_per_connect_after_patch"]
uni = wr["uniform_judge_fraction_before_t09"]
per_day = connects * threat * uni
print(f"T09: {connects:,} connects a day, threat rate 1 in {round(1 / threat):,}, uniform {uni:.0%} judge sample")
print(f"  threat calls reaching the judge per day: {per_day:.3f}; over 3 days P(at least one) = {1 - math.exp(-3 * per_day):.2f}")
angry = connects * wr["angry_path_per_connect"]
print(f"  stratified: the angry stratum has about {angry:.0f} calls a day; judging all of them sees about "
      f"{angry * wr['threat_per_angry_after_patch']:.1f} threat calls a day")
need = math.ceil(math.log(0.05) / math.log(1 - 1 / 2000))
print(f"A 1-in-2,000 violation within a week at 95%: {need} sampled calls a week")
