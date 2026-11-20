"""Module 3 (stt-entities) solution: WER and entity error rate disagree. Run: python3.11 solutions/m03_stt_entities.py [--edition india]"""
import random

import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
pairs = v.jsonl(ed, "entity_pairs")
v.header(C, "WER versus entity error rate")


def amount_errors(rows, sys):
    units = {}
    for p in rows:
        gold = [e for e in p["ref_entities"] if e["type"] == "amount"]
        if not gold:
            continue
        hyp = [e for e in p["hyp_entities"][sys] if e["type"] == "amount"]
        wrong = int(not hyp or hyp[0]["value"] != gold[0]["value"])
        k, n = units.get(p["speaker_id"], (0, 0))
        units[p["speaker_id"]] = (k + wrong, n + 1)
    return units


def ratio(units):
    k = sum(a for a, _ in units.values())
    n = sum(b for _, b in units.values())
    return k / n, k, n


def clustered_ci(units, seed=C["seed"], reps=1000):
    rng = random.Random(seed)
    keys = sorted(units)
    stats = []
    for _ in range(reps):
        draw = [units[rng.choice(keys)] for _ in keys]
        n = sum(b for _, b in draw)
        stats.append(sum(a for a, _ in draw) / n if n else 0.0)
    return v.percentile(stats, 0.025), v.percentile(stats, 0.975)


t01 = next(p for p in pairs if p["pair_id"] == "T01")
e, n = v.wer(t01["reference"], t01["hyps"]["sys_a"])
print(f"T01 utterance: WER {e}/{n} = {e / n:.3f}; amount correct: "
      f"{t01['hyp_entities']['sys_a'][0]['value'] == t01['ref_entities'][0]['value']}")
print()
rows = []
for sys in ("sys_a", "sys_b", "sys_c"):
    errs = refs = 0
    for p in pairs:
        a, b = v.wer(p["reference"], p["hyps"][sys])
        errs += a
        refs += b
    units = amount_errors(pairs, sys)
    r, k, nn = ratio(units)
    lo, hi = clustered_ci(units)
    low_wer_wrong = 0
    for p in pairs:
        a, b = v.wer(p["reference"], p["hyps"][sys])
        g = [x for x in p["ref_entities"] if x["type"] == "amount"]
        h = [x for x in p["hyp_entities"][sys] if x["type"] == "amount"]
        if g and a / b < 0.10 and (not h or h[0]["value"] != g[0]["value"]):
            low_wer_wrong += 1
    rows.append([sys, f"{errs / refs:.3f}", f"{r:.3f} [{lo:.3f}, {hi:.3f}]", f"{k}/{nn}", low_wer_wrong])
v.table(rows, ["system", "corpus WER", "amount entity error rate [95% speaker-clustered]", "wrong amounts", "WER<10% but amount wrong"])
print()
print("Lower WER does not mean fewer wrong amounts: rank the systems by the metric the task depends on.")
