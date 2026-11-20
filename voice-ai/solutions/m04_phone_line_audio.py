"""Module 4 (phone-line-audio) solution: rank STT systems per audio condition. Run: python3.11 solutions/m04_phone_line_audio.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
pairs = v.jsonl(ed, "entity_pairs")
v.header(C, "Amount entity error rate by audio condition")
conds = ["wideband_16k", "g711_clean", "amr_g711", "amr_g711_loss5", "noise_10db"]
systems = ["sys_a", "sys_b", "sys_c"]
rows, ranks = [], {}
for cond in conds:
    sub = [p for p in pairs if p["condition"] == cond and any(e["type"] == "amount" for e in p["ref_entities"])]
    rates = {}
    for s in systems:
        wrong = sum(p["hyp_entities"][s][0]["value"] != p["ref_entities"][0]["value"] for p in sub)
        rates[s] = wrong / len(sub)
    ranks[cond] = sorted(systems, key=lambda s: (rates[s], s))
    rows.append([cond, len(sub)] + [f"{rates[s]:.3f}" for s in systems] + [" < ".join(ranks[cond])])
v.table(rows, ["condition", "amount utterances", *systems, "ranking (best first)"])
print()
phone = [p for p in pairs if p["condition"] != "wideband_16k" and any(e["type"] == "amount" for e in p["ref_entities"])]
pr = {s: sum(p["hyp_entities"][s][0]["value"] != p["ref_entities"][0]["value"] for p in phone) / len(phone) for s in systems}
best_wide = ranks["wideband_16k"][0]
order = sorted(systems, key=lambda s: (pr[s], s))
print(f"Best on wideband audio: {best_wide}. On all phone-path conditions pooled: " + " < ".join(order)
      + f" ({best_wide} places {order.index(best_wide) + 1} of 3).")
print("Gate STT on the phone-path columns; report the wideband column, never gate on it.")
