"""Size production samples for rare policy violations, and stratify toward them.

Steelyard Credit is a fictional lender; its numbers are illustrative.
Standard library only. Python 3.11. No network. Seeded synthetic data.
Dataset: steelyard-calls (synthetic, seed 20261121).
--edition india switches to the India edition's fictional lender and data set
(its constants block sits between the INDIA EDITION markers below).

Run:
    python3.11 rare-violation-sampling.py                    # global edition
    python3.11 rare-violation-sampling.py --edition india    # India edition
"""
from __future__ import annotations

import argparse
import math
import random


def western(n: float, decimals: int = 0) -> str:
    """Western digit grouping: 130000 -> 130,000."""
    return f"{n:,.{decimals}f}"


def usd(x: float) -> str:
    return f"${x:,.2f}"


# ---- GLOBAL constants (copied from WORLD-GLOBAL.md WG1-WG7; do not edit here) -----
GLOBAL = {
    "lender": "Steelyard Credit, Inc. (fictional US lender, head office Tucson AZ)",
    "lender_note": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "products": {  # code: (ticket $ range, payment $ range)
        "AUTO": ((8_000, 35_000), (245, 680)),
        "PIL": ((1_000, 40_000), (95, 1_850)),
        "POS": ((300, 6_000), (45, 520)),
        "SBL": ((25_000, 250_000), (980, 7_200)),
        "SDL": ((300, 3_000), (35, 140)),  # biweekly
    },
    "campaigns": {"AUTO-early-nov": "AUTO", "PIL-digital-nov": "PIL", "POS-short-nov": "POS",
                  "SBL-guar-nov": "SBL", "SDL-biwk-nov": "SDL"},
    "windows": {"default": ("08:00", "21:00"), "SDL": ("09:00", "20:00")},  # borrower's local time
    "languages": {"English": 64, "Spanish-dominant": 18, "Spanglish": 14, "other": 4},
    "bot_languages": ("English", "Spanish-dominant", "Spanglish"),  # other -> human
    "customer_advocate": {"name": "Ms Dana Brooks", "email": "advocate@steelyard.example",
                          "phone": "(520) 555-0199",
                          "address": "1200 Example Avenue, Tucson, AZ 85701"},
    "money": "integer cents in tools and CRM; dollars in speech",
    "dates": "ISO in tools; words in speech; en-US month-first, es-US day-first",
    "versions": {"stt": "vendorA-2026-10", "taxonomy": "gl-fail-v4", "gold": "gold-v7"},
    "connects_per_day": 130_000, "calling_days_per_month": 26, "calling_days_per_week": 6,
}
# Edition settings for this recipe: judge prices (WG20, $ per judged call per dimension),
# number and money formats, and the frozen monthly judge line (WG20).
GLOBAL.update({
    "price": {"J1": 0.0075, "J3": 0.0075, "J2": 0.02},
    "fmt": western, "fmt_money": usd, "money_col": "J1 $/week",
    "month_cost": (2, 7003.36),          # (rounding digits, value): $7,003.36 a month
    "plan": "WG15",                      # world-bible section of the stratified judge plan
})
EDITIONS = {"global": GLOBAL}

# ---- INDIA EDITION START ------------------------------------------------------------
# ---- TARAZU constants (copied from WORLD.md W1-W7; do not edit here) --------
TARAZU = {
    "lender": "Tarazu Finance Ltd (fictional NBFC, head office Pune)",
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "seed": 20261120,
    "products": {  # code: (ticket Rs range, EMI Rs range)
        "TW": ((60_000, 1_50_000), (2_450, 6_800)),
        "PL": ((25_000, 5_00_000), (1_900, 18_500)),
        "CD": ((8_000, 80_000), (1_100, 7_300)),
        "SBL": ((2_00_000, 25_00_000), (9_800, 72_000)),
        "MFI": ((30_000, 75_000), (1_350, 3_400)),
    },
    "campaigns": {"TW-early-nov": "TW", "PL-digital-nov": "PL", "CD-short-nov": "CD",
                  "SBL-guar-nov": "SBL", "MFI-fort-nov": "MFI"},
    "windows": {"default": ("08:00", "19:00"), "MFI": ("09:00", "18:00")},
    "languages": {"Hinglish": 58, "Hindi": 21, "Indian English": 9, "Marathi": 7, "Kannada": 5},
    "bot_languages": ("Hinglish", "Hindi", "Indian English"),  # Marathi, Kannada -> human
    "grievance_officer": {"name": "Ms Neha Kulkarni", "email": "grievance@tarazu.example",
                          "phone": "020-4000-0000",
                          "address": "Tarazu House, Baner Road, Pune 411045"},
    "fractions": {"sava": 1.25, "dedh": 1.5, "dhai": 2.5, "paune": -0.25, "saade": 0.5},
    "money": "integer paise in tools and CRM; rupees in speech",
    "dates": "ISO in tools; words in speech; explicit dmy policy for numeric dates",
    "versions": {"stt": "vendorA-2026-10", "taxonomy": "tz-fail-v4", "gold": "gold-v7"},
    "connects_per_day": 1_30_000, "calling_days_per_month": 26, "calling_days_per_week": 6,
}
# -----------------------------------------------------------------------------


def indian(n: float, decimals: int = 0) -> str:
    """Indian digit grouping: 130000 -> 1,30,000."""
    neg = n < 0
    s = f"{abs(n):.{decimals}f}"
    whole, _, frac = s.partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups + [tail])
    return ("-" if neg else "") + whole + ("." + frac if frac else "")


def rs(x: float) -> str:
    return "Rs " + indian(x, 2 if abs(x - round(x)) > 1e-9 else 0)


TARAZU["lender_note"] = "Tarazu Finance is a fictional lender; its numbers are illustrative."
TARAZU.update({
    "price": {"J1": 0.15, "J3": 0.15, "J2": 0.40},   # Rs per judged call per dimension (W20)
    "fmt": indian, "fmt_money": rs, "money_col": "J1 Rs/week",
    "month_cost": (0, 140067),           # Rs 1,40,067 a month
    "plan": "W15",
})
EDITIONS["india"] = TARAZU
# ---- INDIA EDITION END --------------------------------------------------------------

WORLD: dict = GLOBAL  # set from --edition in main()

# World rates (WG15, WG16, WG17, WG20; identical to W15-W17 in the India edition).
# All [W] or [C]; none is an industry rate. Set in main() from the edition block.
CONNECTS = DAYS_WEEK = DAYS_MONTH = 0
ANGRY_SHARE = 1 / 600            # angry path, share of connected calls (T09)
THREAT_IN_ANGRY = 1 / 40         # threat rate on the angry path while collections-v17-p1 was live
PATCH_DAYS = 3                   # 2026-11-16 to 2026-11-18
OLD_UNIFORM = 0.02               # judge sample before T09: 2% of all calls, uniform
RISK_PER_DAY = 5_200             # risk strata judged 100% from 2026-11-19 (about 4% of connects)
REST_FRACTION = 0.02             # plus 2% of the rest
J1_RECALL = 15 / 18              # J1 v1 validation recall (advisory judge; same in both editions)
AUDITS_PER_WEEK = 400

# Planning assumptions for the allocation and reweighting steps. These are NOT
# measurements of the fictional lender; they exist so the estimators have a known truth.
ASSUMED_RATE = {"angry": THREAT_IN_ANGRY, "other_risk": 0.004, "rest": 0.0005}


# ---- step 1: detection probability and calls needed ---------------------------
def p_detect(n: float, rate: float) -> float:
    """P(at least one violation among n independent calls at this rate)."""
    return 1.0 - (1.0 - rate) ** n


def calls_needed(rate: float, target: float = 0.95) -> int:
    """Smallest n with p_detect(n, rate) >= target (the log formula, then checked)."""
    n = math.ceil(math.log(1.0 - target) / math.log(1.0 - rate))
    while p_detect(n - 1, rate) >= target:
        n -= 1
    while p_detect(n, rate) < target:
        n += 1
    return n


# ---- step 2: zero-event and exact bounds ----------------------------------------
def rule_of_three(n: int) -> float:
    return 3.0 / n


def zero_upper_one_sided(n: int, alpha: float = 0.05) -> float:
    """Exact one-sided upper bound when 0 of n: solve (1 - p)^n = alpha."""
    return 1.0 - alpha ** (1.0 / n)


def binom_cdf(k: int, n: int, p: float) -> float:
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 0.0 if k < n else 1.0
    lp, lq = math.log(p), math.log1p(-p)
    return sum(math.exp(math.lgamma(n + 1) - math.lgamma(i + 1) - math.lgamma(n - i + 1)
                        + i * lp + (n - i) * lq) for i in range(k + 1))


def cp_upper(k: int, n: int, tail: float) -> float:
    """Clopper-Pearson upper limit: the p where P(X <= k | p) = tail (bisection)."""
    if k >= n:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = (lo + hi) / 2
        if binom_cdf(k, n, mid) > tail:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


# ---- step 3: sampling policies over strata ---------------------------------------
def strata_per_day() -> dict[str, float]:
    angry = CONNECTS * ANGRY_SHARE
    return {"angry": angry, "other_risk": RISK_PER_DAY - angry, "rest": CONNECTS - RISK_PER_DAY}


def judged_per_day(fractions: dict[str, float]) -> float:
    return sum(strata_per_day()[h] * f for h, f in fractions.items())


def threat_reach_prob(fractions: dict[str, float], days: float, recall: float = 1.0) -> float:
    """P(the judge sees at least one T09 threat), threats living only on the angry path."""
    n_angry_judged = strata_per_day()["angry"] * fractions["angry"] * days
    return p_detect(n_angry_judged, THREAT_IN_ANGRY * recall)


def mc_reach(fraction: float, days: int, trials: int, rng: random.Random) -> float:
    """Monte Carlo check: Poisson threats per day, each judged with probability `fraction`."""
    lam = CONNECTS * ANGRY_SHARE * THREAT_IN_ANGRY
    hits = 0
    for _ in range(trials):
        seen = False
        for _ in range(days):
            # Poisson by inversion (stdlib has no Poisson sampler)
            u, k, p = rng.random(), 0, math.exp(-lam)
            cdf = p
            while u > cdf:
                k += 1
                p *= lam / k
                cdf += p
            if any(rng.random() < fraction for _ in range(k)):
                seen = True
        hits += seen
    return hits / trials


# ---- step 4: allocation of a fixed audit budget --------------------------------------
def allocate(N: dict[str, int], S: dict[str, float], n: int, method: str) -> dict[str, float]:
    keys = list(N)
    if method == "proportional":
        w = {h: N[h] for h in keys}
    elif method == "equal":
        w = {h: 1.0 for h in keys}
    elif method == "neyman":
        w = {h: N[h] * S[h] for h in keys}
    else:
        raise ValueError(method)
    alloc, free, budget = {}, set(keys), float(n)
    while True:  # cap at the stratum size and give the excess to the others
        tot = sum(w[h] for h in free)
        trial = {h: budget * w[h] / tot for h in free}
        over = [h for h in free if trial[h] > N[h]]
        if not over:
            alloc.update(trial)
            return alloc
        for h in over:
            alloc[h] = float(N[h])
            budget -= N[h]
            free.discard(h)


def stratified_se(N: dict[str, int], p: dict[str, float], n: dict[str, float]) -> float:
    total = sum(N.values())
    var = 0.0
    for h in N:
        if n[h] <= 0:
            return float("inf")
        fpc = 1.0 - n[h] / N[h]
        var += (N[h] / total) ** 2 * p[h] * (1 - p[h]) / n[h] * fpc
    return math.sqrt(var)


# ---- step 5: reweighting on one synthetic week ----------------------------------------
def simulate_week(rng: random.Random, fractions: dict[str, float]) -> dict[str, dict[str, int]]:
    per_day = strata_per_day()
    out = {}
    for h in per_day:
        N = round(per_day[h] * DAYS_WEEK)
        n = round(N * fractions[h])
        population = [rng.random() < ASSUMED_RATE[h] for _ in range(N)]
        sample = rng.sample(range(N), n)
        out[h] = {"N": N, "n": n, "v_pop": sum(population),
                  "v_sample": sum(population[i] for i in sample)}
    return out


def main() -> None:
    global WORLD, CONNECTS, DAYS_WEEK, DAYS_MONTH
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--edition", choices=list(EDITIONS), default="global",
                    help="which fictional world's data to use (default: global)")
    WORLD = EDITIONS[ap.parse_args().edition]
    CONNECTS = WORLD["connects_per_day"]
    DAYS_WEEK = WORLD["calling_days_per_week"]
    DAYS_MONTH = WORLD["calling_days_per_month"]
    PRICE, fmt, money = WORLD["price"], WORLD["fmt"], WORLD["fmt_money"]

    rng = random.Random(WORLD["seed"])
    print(WORLD["lender_note"])
    print(f"Dataset: {WORLD['dataset']}\n")

    # Step 1 --------------------------------------------------------------------------
    print("1. Detection probability: P(at least one) = 1 - (1 - rate)^n")
    n95 = calls_needed(1 / 1000)
    print(f"   calls for 95% at 1 in 1,000   : {fmt(n95)}  "
          f"(p = {p_detect(n95, 1/1000):.5f}; {fmt(n95 - 1)} gives {p_detect(n95 - 1, 1/1000):.5f})")
    p1000 = p_detect(1000, 1 / 2000)
    print(f"   1,000 calls at 1 in 2,000     : {p1000:.3f}")
    n_week = calls_needed(1 / 2000)
    print(f"   calls for 95% at 1 in 2,000   : {fmt(n_week)}  "
          f"({fmt(n_week - 1)} gives {p_detect(n_week - 1, 1/2000):.5f})")
    rest_week = round((CONNECTS - RISK_PER_DAY) * REST_FRACTION * DAYS_WEEK)
    print(f"   2% of non-risk calls a week   : {fmt(rest_week)}  "
          f"(p at 1 in 2,000 = {p_detect(rest_week, 1/2000):.4f})")
    print("   rate        n for 50%    n for 95%    n for 99%")
    for denom in (500, 1000, 2000, 10000, 24000):
        r = 1 / denom
        print(f"   1/{denom:<8}{fmt(calls_needed(r, 0.50)):>10}"
              f"{fmt(calls_needed(r, 0.95)):>13}{fmt(calls_needed(r, 0.99)):>13}")
    assert n95 == 2995 and p_detect(2994, 1 / 1000) < 0.95 <= p_detect(2995, 1 / 1000)
    assert round(p1000, 3) == 0.394
    assert n_week == 5990 and round(p_detect(5989, 1 / 2000), 5) == 0.94998
    assert rest_week == 14976 and rest_week > n_week

    # Step 2 --------------------------------------------------------------------------
    print("\n2. Upper bounds on the rate (95%)")
    print("   k / n        rule of 3   exact 1-sided   Clopper-Pearson 2-sided")
    rows = [(0, 300), (0, 400), (0, 3000), (1, 300), (2, 300)]
    for k, n in rows:
        r3 = f"{rule_of_three(n):.4f}" if k == 0 else "   n/a"
        one = zero_upper_one_sided(n) if k == 0 else cp_upper(k, n, 0.05)
        two = cp_upper(k, n, 0.025)
        print(f"   {k} / {fmt(n):<8}{r3:>10}{one:>16.4f}{two:>26.4f}")
    assert round(rule_of_three(300), 4) == 0.0100
    assert round(cp_upper(0, 300, 0.025), 4) == 0.0122
    assert abs(cp_upper(0, 300, 0.025) - (1 - 0.025 ** (1 / 300))) < 1e-9
    assert round(zero_upper_one_sided(400) * 100, 3) == 0.746
    assert round(rule_of_three(3000), 4) == 0.0010

    # Step 3 --------------------------------------------------------------------------
    per_day = strata_per_day()
    print("\n3. T09: threats live on the angry path")
    print(f"   angry calls a day        : {per_day['angry']:.1f}  "
          f"(a week: {fmt(per_day['angry'] * DAYS_WEEK)})")
    threats_day = per_day["angry"] * THREAT_IN_ANGRY
    print(f"   threat calls a day       : {threats_day:.2f}  "
          f"(1 in {fmt(1 / (ANGRY_SHARE * THREAT_IN_ANGRY))} connects)")
    uniform = {"angry": OLD_UNIFORM, "other_risk": OLD_UNIFORM, "rest": OLD_UNIFORM}
    strat = {"angry": 1.0, "other_risk": 1.0, "rest": REST_FRACTION}
    same_cost = judged_per_day(strat) / CONNECTS
    uniform_eq = {h: same_cost for h in uniform}
    p_t09 = threat_reach_prob(uniform, PATCH_DAYS)
    print(f"   reaching a 2% judge      : {threats_day * OLD_UNIFORM:.2f} a day")
    mc = mc_reach(OLD_UNIFORM, PATCH_DAYS, 20_000, rng)
    print(f"   P(judge sees one, 3 days): {p_t09:.3f} exact, {mc:.3f} Monte Carlo (20,000 runs)")
    print("   policy                     judged/day   1 day   3 days   1 week" + f"{WORLD['money_col']:>13}")
    for name, fr in (("uniform 2% (before T09)", uniform),
                     (f"uniform {same_cost:.2%} (same count)", uniform_eq),
                     (f"stratified {WORLD['plan']} plan", strat)):
        jd = judged_per_day(fr)
        print(f"   {name:<27}{fmt(jd):>10}{threat_reach_prob(fr, 1):>8.3f}"
              f"{threat_reach_prob(fr, 3):>9.3f}{threat_reach_prob(fr, DAYS_WEEK):>9.3f}"
              f"{fmt(jd * DAYS_WEEK * PRICE['J1'], 2):>13}")
    flag_day = threat_reach_prob(strat, 1, J1_RECALL)
    print(f"   stratified, J1 flags at least one in a day (recall {J1_RECALL:.3f}): {flag_day:.3f}")
    assert round(p_t09, 2) == 0.28 and abs(mc - p_t09) < 0.02
    assert round(threats_day * OLD_UNIFORM, 2) == 0.11
    assert round(judged_per_day(strat)) == 7696
    for d in (1, 3, DAYS_WEEK):  # never worse than uniform at the same judged count
        assert threat_reach_prob(strat, d) >= threat_reach_prob(uniform_eq, d)

    angry_week = per_day["angry"] * DAYS_WEEK
    print(f"\n   angry path judged 200 times a week needs {200 / angry_week:.1%} of "
          f"{fmt(angry_week)}; judging all of it costs {money(angry_week * PRICE['J1'])} a week for J1")
    all_three = sum(PRICE.values())
    week_cost = judged_per_day(strat) * DAYS_WEEK * all_three
    month_cost = judged_per_day(strat) * DAYS_MONTH * all_three
    digits, frozen_month = WORLD["month_cost"]
    print(f"   {WORLD['plan']} plan with J1, J3 and J2: {money(week_cost)} a week, "
          f"{money(round(month_cost, digits))} a month")
    assert round(200 / angry_week, 3) == 0.154
    assert round(month_cost, digits) == frozen_month

    # Step 4 --------------------------------------------------------------------------
    N = {h: round(per_day[h] * DAYS_WEEK) for h in per_day}
    S = {h: math.sqrt(ASSUMED_RATE[h] * (1 - ASSUMED_RATE[h])) for h in N}
    true_rate = sum(N[h] * ASSUMED_RATE[h] for h in N) / sum(N.values())
    print(f"\n4. {AUDITS_PER_WEEK} human audits a week across strata "
          f"(assumed rates: angry 1/40, other risk 1/250, rest 1/2,000)")
    print(f"   stratum sizes a week: " + ", ".join(f"{h} {fmt(N[h])}" for h in N))
    print("   allocation      angry  other_risk     rest   expected found   SE of overall rate")
    results = {}
    for m in ("proportional", "equal", "neyman"):
        a = allocate(N, S, AUDITS_PER_WEEK, m)
        found = sum(a[h] * ASSUMED_RATE[h] for h in N)
        se = stratified_se(N, ASSUMED_RATE, a)
        results[m] = (found, se)
        print(f"   {m:<14}{a['angry']:>7.1f}{a['other_risk']:>12.1f}{a['rest']:>9.1f}"
              f"{found:>17.2f}{se:>21.6f}")
    print(f"   true overall rate under these assumptions: {true_rate:.6f}")
    assert all(abs(sum(allocate(N, S, AUDITS_PER_WEEK, m).values()) - AUDITS_PER_WEEK) < 1e-6
               for m in results)
    assert results["neyman"][1] <= min(results["proportional"][1], results["equal"][1])
    assert results["equal"][0] > results["neyman"][0] > results["proportional"][0]

    # Step 5 --------------------------------------------------------------------------
    wk = simulate_week(rng, strat)
    tot_N = sum(s["N"] for s in wk.values())
    tot_n = sum(s["n"] for s in wk.values())
    tot_v = sum(s["v_sample"] for s in wk.values())
    pop_rate = sum(s["v_pop"] for s in wk.values()) / tot_N
    naive = tot_v / tot_n
    weighted = sum(s["N"] * s["v_sample"] / s["n"] for s in wk.values()) / tot_N
    print(f"\n5. One synthetic week under the {WORLD['plan']} plan (judge treated as perfect here)")
    print("   stratum      calls     judged  violations seen")
    for h, s in wk.items():
        print(f"   {h:<11}{fmt(s['N']):>9}{fmt(s['n']):>11}{s['v_sample']:>17}")
    print(f"   population rate (truth) : {pop_rate:.6f}")
    print(f"   naive rate over judged  : {naive:.6f}  ({naive / pop_rate:.1f}x too high)")
    print(f"   stratum-weighted rate   : {weighted:.6f}")
    assert tot_n == 46176
    assert naive > 3 * pop_rate and abs(weighted - pop_rate) / pop_rate < 0.25

    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
