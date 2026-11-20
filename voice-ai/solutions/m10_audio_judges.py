"""Module 10 (audio-judges) solution: validate a judge per language group. Run: python3.11 solutions/m10_audio_judges.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
rows = v.jsonl(ed, "judge_labels")
v.header(C, "Judge validation per language group and dimension")
BAR = 0.90


def stats(sub, judge):
    tp = sum(r["human_label"] and r[judge] for r in sub)
    fn = sum(r["human_label"] and not r[judge] for r in sub)
    fp = sum(not r["human_label"] and r[judge] for r in sub)
    tn = sum(not r["human_label"] and not r[judge] for r in sub)
    n = len(sub)
    return tp, fn, fp, tn, (tp + tn) / n, v.kappa([(r["human_label"], r[judge]) for r in sub])


out = []
for dim in ("C07", "TONE.PACE"):
    for g in C["language_groups"]:
        sub = [r for r in rows if r["dimension"] == dim and r["language_group"] == g]
        for judge in ("transcript_judge", "blueprint_judge"):
            tp, fn, fp, tn, agree, k = stats(sub, judge)
            rec_lo, rec_hi = v.wilson(tp, tp + fn)
            spec_lo, spec_hi = v.wilson(tn, tn + fp)
            verdict = "admit" if rec_lo >= BAR and spec_lo >= BAR else "advisory"
            out.append([dim, g, judge.replace("_judge", ""), f"{tp}/{fn}/{fp}/{tn}", f"{agree:.3f}", f"{k:.3f}",
                        f"{tp / (tp + fn):.3f} [{rec_lo:.3f}, {rec_hi:.3f}]", f"{tn / (tn + fp):.3f} [{spec_lo:.3f}, {spec_hi:.3f}]",
                        f"{tp / (tp + fp):.3f}" if tp + fp else "-", verdict])
v.table(out, ["dim", "group", "judge", "TP/FN/FP/TN", "agree", "kappa", "recall [Wilson 95%]", "specificity [Wilson 95%]", "precision", "gate"])
print()
print(f"Gate: admit only when the Wilson lower bounds of recall and specificity both reach {BAR:.2f}.")
n = 1000
k = 30
print(f"Prevalence trap: an always-compliant judge at {k / n:.0%} prevalence agrees on {(n - k) / n:.3f} of calls, "
      f"kappa {v.kappa([(i < k, False) for i in range(n)]):.3f}.")
print()
for g in C["language_groups"]:
    sub = [r for r in rows if r["language_group"] == g]
    print(f"Human raters A vs B, {g}: kappa {v.kappa([(r['rater_a'], r['rater_b']) for r in sub]):.3f}")
