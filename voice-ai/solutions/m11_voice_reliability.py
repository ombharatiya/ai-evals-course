"""Module 11 (voice-reliability) solution: pass^k from repeated trials. Run: python3.11 solutions/m11_voice_reliability.py [--edition india]"""
from collections import defaultdict

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
v.header(C, "pass^k from 8 simulated trials per scenario")

trials = defaultdict(list)
meta = {}
for c in calls:
    s = c["scenario"]
    ok = not v.task_diff(c) and not v.failed(v.run_checks(c, C))
    trials[s["scenario_id"]].append(ok)
    meta[s["scenario_id"]] = (s["flow"], s["language_group"])
rows = []
for sid in sorted(trials):
    t = trials[sid]
    c_, n = sum(t), len(t)
    rows.append([sid, meta[sid][0], meta[sid][1], f"{c_}/{n}"] + [f"{v.pass_hat_k(c_, n, k):.3f}" for k in (1, 2, 4, 8)])
v.table(rows, ["scenario", "flow", "language group", "passes", "pass^1", "pass^2", "pass^4", "pass^8"])
print()
for k in (1, 2, 4, 8):
    unbiased = sum(v.pass_hat_k(sum(t), len(t), k) for t in trials.values()) / len(trials)
    plugin = sum((sum(t) / len(t)) ** k for t in trials.values()) / len(trials)
    print(f"suite pass^{k}: unbiased {unbiased:.3f}   plug-in (c/n)^k {plugin:.3f}")
print()
print(f"Worked check: c=6, n=8, k=4 gives {v.pass_hat_k(6, 8, 4):.4f} unbiased and {(6 / 8) ** 4:.4f} plug-in.")
print(f"pass^8 at 80% per trial: 0.8^8 = {0.8 ** 8:.4f}; at 90%: {0.9 ** 8:.4f}")
