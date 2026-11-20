"""Choose an endpointing operating point per campaign and call state.

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Standard library only. Python 3.11.
No network. --edition india switches to the India edition's fictional lender and
data set (its constants block sits between the INDIA EDITION markers below).

Run:
    python3.11 endpointing-operating-point.py
"""
from __future__ import annotations

import argparse
import csv
import math
import random
from dataclasses import dataclass

# --- GLOBAL constants block (copied from WORLD-GLOBAL.md, world-global-v1.1) -----
GLOBAL = {
    "lender": "Steelyard Credit, Inc. (fictional; numbers are illustrative)",
    "banner": "Synthetic Steelyard data (Steelyard Credit is a fictional lender; its numbers are illustrative)",
    "seed": 20261121,
    "products": ["AUTO", "PIL", "POS", "SBL", "SDL"],
    "campaigns": {
        "AUTO-early-nov": {"book": "AUTO", "dpd": (1, 30)},
        "PIL-digital-nov": {"book": "PIL", "dpd": (1, 60)},
        "POS-short-nov": {"book": "POS", "dpd": (1, 30)},
        "SBL-guar-nov": {"book": "SBL", "dpd": (1, 90)},
        "SDL-biwk-nov": {"book": "SDL", "dpd": (1, 30)},
    },
    "calling_window": {"default": ("08:00", "21:00"), "SDL": ("09:00", "20:00")},
    "customer_advocate": ("Ms Dana Brooks", "advocate@steelyard.example",
                          "(520) 555-0199", "1200 Example Avenue, Tucson, AZ 85701"),
    # WG12 endpointing operating points (ms): default, amount-or-date asked, threshold
    "points": {
        "AUTO-early-nov": (400, 600, 0.70),
        "PIL-digital-nov": (400, 600, 0.70),
        "POS-short-nov": (400, 600, 0.70),
        "SBL-guar-nov": (450, 650, 0.72),
        "SDL-biwk-nov": (600, 800, 0.78),
    },
    "points_label": "WG12",
    "detector_allowance_ms": 150,  # WG11: end-of-turn delay SLO = silence budget + 150 ms
}
# ---------------------------------------------------------------------------

# Synthetic generator settings per edition. Every value here was invented for this
# recipe; none is a lender measurement or a vendor's number. The pause model per
# language group: median hold pause (ms), lognormal sigma, and the beta parameters
# of the detector's hold score on hold pauses (how well it separates hold from end).
SYNTH = {
    "global": {
        "groups": ["English", "Spanish-dominant", "Spanglish"],
        "group_code": {"English": "ENG", "Spanish-dominant": "SPD", "Spanglish": "SPG"},
        "group_model": {
            "English":          {"hold_median": 215, "sigma": 0.50, "hold_beta": (5.0, 1.5)},
            "Spanish-dominant": {"hold_median": 215, "sigma": 0.50, "hold_beta": (4.5, 1.8)},
            "Spanglish":        {"hold_median": 220, "sigma": 0.50, "hold_beta": (5.0, 1.5)},
        },
        # Campaign profiles: pace multiplier on pauses and language mix (WG2 languages).
        "campaign_profile": {
            "AUTO-early-nov":  {"pace": 1.00, "mix": {"English": 0.7, "Spanish-dominant": 0.3}},
            "PIL-digital-nov": {"pace": 1.00, "mix": {"Spanglish": 0.6, "English": 0.4}},
            "POS-short-nov":   {"pace": 1.00, "mix": {"Spanish-dominant": 0.6, "English": 0.4}},
            "SBL-guar-nov":    {"pace": 1.10, "mix": {"English": 0.6, "Spanglish": 0.4}},
            "SDL-biwk-nov":    {"pace": 1.30, "mix": {"English": 0.6, "Spanish-dominant": 0.4}},
        },
        "longest": "SDL-biwk-nov",      # older borrowers, longest budget (WG12)
        "t05": ("SY-T05", "English"),   # WG16 T05: P01, English, 720 ms hold before a date
        "csv_group": "English",
        "csv": "steelyard_pauses_english.csv",
    },
}

EDITIONS = {"global": GLOBAL}

# ---- INDIA EDITION START --------------------------------------------------------
# --- TARAZU constants block (copied from WORLD.md, world-v1.1) ---------------
TARAZU = {
    "lender": "Tarazu Finance Ltd (fictional; numbers are illustrative)",
    "banner": "Synthetic Tarazu data (Tarazu Finance is a fictional lender; its numbers are illustrative)",
    "seed": 20261120,
    "products": ["TW", "PL", "CD", "SBL", "MFI"],
    "campaigns": {
        "TW-early-nov": {"book": "TW", "dpd": (1, 30)},
        "PL-digital-nov": {"book": "PL", "dpd": (1, 60)},
        "CD-short-nov": {"book": "CD", "dpd": (1, 30)},
        "SBL-guar-nov": {"book": "SBL", "dpd": (1, 90)},
        "MFI-fort-nov": {"book": "MFI", "dpd": (1, 30)},
    },
    "calling_window": {"default": ("08:00", "19:00"), "MFI": ("09:00", "18:00")},
    "grievance_officer": ("Ms Neha Kulkarni", "grievance@tarazu.example",
                          "020-4000-0000", "Tarazu House, Baner Road, Pune 411045"),
    # W12 endpointing operating points (ms): default, amount-or-date asked, threshold
    "points": {
        "TW-early-nov": (400, 600, 0.70),
        "PL-digital-nov": (400, 600, 0.70),
        "CD-short-nov": (400, 600, 0.70),
        "SBL-guar-nov": (450, 650, 0.72),
        "MFI-fort-nov": (600, 800, 0.78),
    },
    "points_label": "W12",
    "detector_allowance_ms": 150,  # W11: end-of-turn delay SLO = silence budget + 150 ms
}
SYNTH["india"] = {
    "groups": ["Hinglish", "Hindi-dominant", "Indian English"],
    "group_code": {g: g[:3].upper() for g in ["Hinglish", "Hindi-dominant", "Indian English"]},
    "group_model": {
        "Hinglish":       {"hold_median": 220, "sigma": 0.50, "hold_beta": (5.0, 1.5)},
        "Hindi-dominant": {"hold_median": 215, "sigma": 0.50, "hold_beta": (4.5, 1.8)},
        "Indian English": {"hold_median": 215, "sigma": 0.50, "hold_beta": (5.0, 1.5)},
    },
    "campaign_profile": {
        "TW-early-nov":   {"pace": 1.00, "mix": {"Hinglish": 0.7, "Hindi-dominant": 0.3}},
        "PL-digital-nov": {"pace": 1.00, "mix": {"Hinglish": 0.6, "Indian English": 0.4}},
        "CD-short-nov":   {"pace": 1.00, "mix": {"Hindi-dominant": 0.6, "Hinglish": 0.4}},
        "SBL-guar-nov":   {"pace": 1.10, "mix": {"Hindi-dominant": 0.6, "Hinglish": 0.4}},
        "MFI-fort-nov":   {"pace": 1.30, "mix": {"Hindi-dominant": 1.0}},
    },
    "longest": "MFI-fort-nov",
    "t05": ("TZ-T05", "Hinglish"),
    "csv_group": "Hinglish",
    "csv": "tarazu_pauses_hinglish.csv",
}
EDITIONS["india"] = TARAZU
# ---- INDIA EDITION END ----------------------------------------------------------

ARGS = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ARGS.add_argument("--edition", choices=list(EDITIONS), default="global",
                  help="which fictional world's data to use (default: global)")
EDITION = ARGS.parse_args().edition
WORLD = EDITIONS[EDITION]
GEN = SYNTH[EDITION]

SEED = WORLD["seed"]
GROUPS = GEN["groups"]
GROUP_MODEL = GEN["group_model"]
CAMPAIGN_PROFILE = GEN["campaign_profile"]
COL = max(16, max(len(g) for g in GROUPS) + 2)   # group column width
TAGS = ["small_talk", "dispute", "amount", "date"]
BUDGETS = list(range(200, 1251, 50))      # silence budgets swept, ms
HOLD_EXTENSION_MS = 500                    # extra wait when the model says "hold"
T05_HOLD_MS = 720                          # T05: the caller's pause before a date (both editions)

END_BETA = (2.0, 5.0)          # detector hold score on true end-of-turn pauses
CONTENT_STRETCH = {"small_talk": 1.0, "dispute": 1.2, "amount": 1.6, "date": 1.6}
# Content mix of hold pauses by call state.
STATE_TAGS = {
    "default":      {"small_talk": 0.6, "dispute": 0.2, "amount": 0.1, "date": 0.1},
    "amount_asked": {"small_talk": 0.15, "dispute": 0.05, "amount": 0.4, "date": 0.4},
}
# Cost units: 1.0 = one second of dead air on a finished turn.
WEIGHTS = {"small_talk": 1.0, "dispute": 1.5, "amount": 2.5, "date": 2.5}
DEAD_AIR_PER_S = 1.0


@dataclass
class Pause:
    call_id: str
    turn_id: int
    group: str
    label: str        # "eot" (true end of turn) or "hold" (mid-turn pause)
    tag: str          # content that follows a hold, or the turn's content for eot
    ms: int           # silence length; for eot, the caller stays silent
    score: float      # detector hold score in [0, 1]


def gen_pauses(group: str, n: int, seed: int, state: str = "default",
               pace: float = 1.0, prefix: str = "") -> list[Pause]:
    """At least n labeled pauses, whole calls of 4 turns; holds before amounts and dates run longer."""
    rng = random.Random(f"{seed}:{group}:{state}:{pace}:{prefix}")
    m = GROUP_MODEL[group]
    tags, probs = zip(*STATE_TAGS[state].items())
    out: list[Pause] = []
    call = 0
    while len(out) < n:
        call += 1
        call_id = f"{prefix}{GEN['group_code'][group]}-{call:04d}"
        call_pace = pace * math.exp(rng.gauss(0, 0.25))     # speaker effect: clusters
        for turn in range(4):
            for _ in range(rng.choice([0, 1, 1, 2, 2, 3])):
                tag = rng.choices(tags, probs)[0]
                ms = m["hold_median"] * call_pace * CONTENT_STRETCH[tag] * math.exp(rng.gauss(0, m["sigma"]))
                out.append(Pause(call_id, turn, group, "hold", tag, max(100, int(ms)),
                                 rng.betavariate(*m["hold_beta"])))
            out.append(Pause(call_id, turn, group, "eot", rng.choices(tags, probs)[0],
                             5000, rng.betavariate(*END_BETA)))
    return out


def wait_ms(p: Pause, budget: int, thr: float | None) -> int:
    """Silence before the detector commits. thr=None is the silence-only baseline."""
    if thr is not None and p.score >= thr:
        return budget + HOLD_EXTENSION_MS
    return budget


def point(pauses: list[Pause], budget: int, thr: float | None) -> tuple[float, float]:
    """(false-cutoff rate on holds, mean dead air in ms on true ends)."""
    holds = [p for p in pauses if p.label == "hold"]
    ends = [p for p in pauses if p.label == "eot"]
    cut = sum(p.ms >= wait_ms(p, budget, thr) for p in holds) / len(holds)
    lat = sum(wait_ms(p, budget, thr) for p in ends) / len(ends)
    return cut, lat


def sweep(pauses, thr, budgets=BUDGETS):
    return [(b, *point(pauses, b, thr)) for b in budgets]


def at_budget(curve, ms: int) -> float:
    """False-cutoff rate at a mean-latency budget: best point with latency <= ms."""
    ok = [c for b, c, lat in curve if lat <= ms]
    return min(ok) if ok else float("nan")


def at_cutoff(curve, rate: float) -> float:
    """Mean latency at a false-cutoff budget: lowest latency with cutoff <= rate."""
    ok = [lat for b, c, lat in curve if c <= rate]
    return min(ok) if ok else float("nan")


def by_call(pauses):
    calls: dict[str, list[Pause]] = {}
    for p in pauses:
        calls.setdefault(p.call_id, []).append(p)
    return list(calls.values())


def bootstrap(pauses, stat, reps=1000, seed=SEED):
    """95% percentile interval, resampling whole calls (pauses in a call are correlated)."""
    rng = random.Random(seed)
    calls = by_call(pauses)
    vals = sorted(stat([p for c in rng.choices(calls, k=len(calls)) for p in c]) for _ in range(reps))
    return vals[int(0.025 * reps)], vals[int(0.975 * reps) - 1]


def expected_cost(pauses, budget, thr, weights=WEIGHTS):
    """Cost per 1,000 turns: weighted false cutoffs plus seconds of dead air."""
    turns = sum(p.label == "eot" for p in pauses)
    cost = 0.0
    for p in pauses:
        w = wait_ms(p, budget, thr)
        if p.label == "hold" and p.ms >= w:
            cost += weights[p.tag]
        elif p.label == "eot":
            cost += DEAD_AIR_PER_S * w / 1000
    return 1000 * cost / turns


def campaign_pauses(campaign, state, n=600):
    prof = CAMPAIGN_PROFILE[campaign]
    out = []
    for g, share in prof["mix"].items():
        out += gen_pauses(g, round(n * share), SEED, state, prof["pace"], prefix=f"{campaign[:3]}-")
    return out


def best_budget(pauses, thr, weights=WEIGHTS):
    return min((expected_cost(pauses, b, thr, weights), b) for b in BUDGETS)


def choose(campaign, state, weights=WEIGHTS):
    thr = WORLD["points"][campaign][2]
    pauses = campaign_pauses(campaign, state)
    best_cost, best_b = best_budget(pauses, thr, weights)
    return best_b, best_cost, pauses, thr


def choice_interval(pauses, thr, reps=200, seed=SEED):
    """Range of chosen budgets over call-clustered resamples (central 95%)."""
    rng = random.Random(seed)
    calls = by_call(pauses)
    picks = sorted(best_budget([p for c in rng.choices(calls, k=len(calls)) for p in c], thr)[1]
                   for _ in range(reps))
    return picks[int(0.025 * reps)], picks[int(0.975 * reps) - 1]


def write_csv(path, pauses):
    """One row per pause, with eot-bench's label names (eot, hold)."""
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["call_id", "turn_id", "language", "label", "content_tag", "pause_ms", "hold_score"])
        for p in pauses:
            w.writerow([p.call_id, p.turn_id, p.group, p.label, p.tag,
                        p.ms if p.label == "hold" else "", f"{p.score:.3f}"])


def main():
    # Frozen numbers shared by both editions: the operating points and the T05 replay.
    assert list(WORLD["points"].values()) == [(400, 600, 0.70), (400, 600, 0.70), (400, 600, 0.70),
                                              (450, 650, 0.72), (600, 800, 0.78)]
    assert WORLD["detector_allowance_ms"] == 150 and T05_HOLD_MS == 720
    label = WORLD["points_label"]
    print(WORLD["banner"])
    print(f"seed {SEED}; budgets {BUDGETS[0]}-{BUDGETS[-1]} ms in 50 ms steps\n")

    # Step 1-2: curves per language group, silence-only vs model detector.
    sets = {g: gen_pauses(g, 600, SEED) for g in GROUPS}
    print("Curves per language group (default state; pauses = whole calls, at least 600)")
    print(f"{'group':<{COL}}{'detector':<14}{'pauses':>7}{'holds':>6}{'cut@300':>9}{'cut@600':>9}{'lat@5%':>8}{'lat@10%':>9}")
    for g, ps in sets.items():
        for name, thr in (("silence-only", None), ("model t=0.70", 0.70)):
            curve = sweep(ps, thr)
            cuts = [c for _, c, _ in curve]
            lats = [lat for _, _, lat in curve]
            assert all(a >= b for a, b in zip(cuts, cuts[1:])), "cutoff must not rise with budget"
            assert all(a <= b for a, b in zip(lats, lats[1:])), "latency must not fall with budget"
            holds = sum(p.label == "hold" for p in ps)
            print(f"{g:<{COL}}{name:<14}{len(ps):>7}{holds:>6}{at_budget(curve, 300):>9.1%}{at_budget(curve, 600):>9.1%}"
                  f"{at_cutoff(curve, 0.05):>8.0f}{at_cutoff(curve, 0.10):>9.0f}")
        assert at_budget(sweep(ps, 0.70), 600) < at_budget(sweep(ps, None), 600)
    print()

    # Step 3: call-clustered intervals at the lead campaign's budgets before and after T05.
    print("False cutoff at a fixed silence budget, model t=0.70, 95% CI clustered by call")
    for g, ps in sets.items():
        calls = len(by_call(ps))
        row = f"{g:<{COL}}{calls:>4} calls"
        for b in (300, 400):
            est = point(ps, b, 0.70)[0]
            lo, hi = bootstrap(ps, lambda x, b=b: point(x, b, 0.70)[0])
            row += f"   {b} ms {est:5.1%} [{lo:.1%}, {hi:.1%}]"
        print(row)
    print()

    # Step 4-5: cost-weighted choice per campaign and call state, with its uncertainty.
    print("Chosen silence budget per campaign and state (cost per 1,000 turns;")
    print("range = central 95% of choices over 200 call-clustered resamples)")
    print(f"{'campaign':<16}{'state':<14}{'thr':>5}{'chosen':>8}{'range':>12}{'cost':>6}{'cutoff':>8}{label:>6}")
    chosen = {}
    for camp, (w_def, w_amt, thr) in WORLD["points"].items():
        picks = []
        for state, ref in (("default", w_def), ("amount_asked", w_amt)):
            b, cost, ps, _ = choose(camp, state)
            lo, hi = choice_interval(ps, thr)
            picks.append(b)
            print(f"{camp:<16}{state:<14}{thr:>5.2f}{b:>8}{f'{lo}-{hi}':>12}{cost:>6.0f}"
                  f"{point(ps, b, thr)[0]:>8.1%}{ref:>6}")
            assert lo <= ref <= hi, f"{camp} {state}: {label} point outside the resampled range"
        chosen[camp] = tuple(picks)
        assert picks[1] >= picks[0], f"{camp}: amount-or-date state must not be shorter"
    longest = chosen[GEN["longest"]]
    assert all(longest[0] >= d and longest[1] >= a for d, a in chosen.values()), \
        f"{GEN['longest']} must be longest"
    print()

    # Step 6: sensitivity. Doubling the amount and date weights never shortens a choice.
    heavy = dict(WEIGHTS, amount=2 * WEIGHTS["amount"], date=2 * WEIGHTS["date"])
    print(f"Sensitivity: amount and date weights {WEIGHTS['amount']} -> {heavy['amount']}")
    for camp in WORLD["points"]:
        d2 = choose(camp, "default", heavy)[0]
        a2 = choose(camp, "amount_asked", heavy)[0]
        assert d2 >= chosen[camp][0] and a2 >= chosen[camp][1], "heavier weights must not shorten"
        print(f"{camp:<16}default {chosen[camp][0]} -> {d2} ms   amount/date {chosen[camp][1]} -> {a2} ms")
    print()

    # Step 7: T05's 720 ms hold before a date, scored by the wait rule (same in both editions).
    t05_id, t05_group = GEN["t05"]
    replay = []
    for b in (300, 400, 600):
        for score, note in ((0.40, "no hold signal"), (0.90, "hold signal")):
            t05 = Pause(t05_id, 0, t05_group, "hold", "date", T05_HOLD_MS, score)
            w = wait_ms(t05, b, 0.70)
            replay.append((b, note, w, t05.ms >= w))
            print(f"T05 at {b} ms, {note:<14}: waits {w:>4} ms -> {'cut off' if t05.ms >= w else 'held'}")
    assert [(w, cut) for _, _, w, cut in replay] == [(300, True), (800, False), (400, True),
                                                     (900, False), (600, True), (1100, False)]

    rows = sets[GEN["csv_group"]]
    write_csv(GEN["csv"], rows)
    print(f"\nwrote {GEN['csv']} ({len(rows)} rows)")
    print("All assertions passed. The numbers are synthetic; the method transfers to your labeled pauses.")


if __name__ == "__main__":
    main()
