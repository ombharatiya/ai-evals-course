"""pass^k and a run-count planner for voice agent release gates (aievals.co recipe R9).

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Standard library only.
Python 3.11. No network. Seeded synthetic data.
--edition india switches to the India edition's fictional lender and segment labels
(its constants block sits between the INDIA EDITION markers below). The statistics
are the same in both editions, so every computed line prints the same numbers.

Five parts:
  1. pass^k and pass@k for one task, exact and unbiased.
  2. Suite estimators on 60 scenarios x 8 trials, against the plug-in shortcuts.
  3. Wilson and Clopper-Pearson intervals for single rates (the dispute segment).
  4. Run counts: closed-form unpaired and paired (McNemar) sizes, checked by a
     seeded power simulation.
  5. A release gate over the 12 gated segments: paired bootstrap deltas per
     segment, Holm across segments.

Run:
    python3.11 voice-pass-k-planner.py                    # global edition
    python3.11 voice-pass-k-planner.py --edition india    # India edition
"""
from __future__ import annotations

import argparse
import math
import random
from math import comb, sqrt
from statistics import NormalDist

# ---- GLOBAL constants (copied from the world bible, world-global-v1.1) ---------
GLOBAL = {
    "lender": "Steelyard Credit, Inc. (fictional US lender, head office Tucson AZ)",
    "fiction_note": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "products": {  # code: (ticket $ range, payment $ range; SDL payments are biweekly)
        "AUTO": ((8_000, 35_000), (245, 680)),
        "PIL": ((1_000, 40_000), (95, 1_850)),
        "POS": ((300, 6_000), (45, 520)),
        "SBL": ((25_000, 250_000), (980, 7_200)),
        "SDL": ((300, 3_000), (35, 140)),
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
    "versions": {"agent": "hazel-3.2.1", "prompt": "collections-v17", "gold": "gold-v7"},
    "nightly": {"scenarios": 240, "k": 4, "per_segment": 20, "segments": 12},
    # WG15: 3 language groups x 4 flow groups = 12 gated segments
    "lang_groups": ("English", "Spanish-dominant", "Spanglish"),
}

EDITIONS = {"global": GLOBAL}

# ---- INDIA EDITION START --------------------------------------------------------
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
    "versions": {"agent": "asha-3.2.1", "prompt": "collections-v17", "gold": "gold-v7"},
    "nightly": {"scenarios": 240, "k": 4, "per_segment": 20, "segments": 12},
}
TARAZU["fiction_note"] = "Tarazu Finance is a fictional lender; its numbers are illustrative."
# W15: 3 language groups x 4 flow groups = 12 gated segments
TARAZU["lang_groups"] = ("Hinglish", "Hindi-dominant", "Indian English")
EDITIONS["india"] = TARAZU
# ---- INDIA EDITION END ----------------------------------------------------------

ARGS = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ARGS.add_argument("--edition", choices=list(EDITIONS), default="global",
                  help="which fictional world's data to use (default: global)")
WORLD = EDITIONS[ARGS.parse_args().edition]

# One random stream family for the suite, the release run, the power simulations and
# the gate, the same in both editions, so every computed line prints the same numbers
# in both. The edition seed names the edition's dataset.
STATS_SEED = 20261120
# Language groups map by position across editions (lead language group, the second
# group, the third), so the seeded regression lands in the same cell in both.
LANG_GROUPS = WORLD["lang_groups"]
LANG_W = max(15, max(len(x) for x in LANG_GROUPS) + 1)
FLOW_GROUPS = ("promise", "dispute+paid", "hardship+complaint", "other parties")
Z = NormalDist()


# ---- Part 1: pass^k and pass@k ----------------------------------------------
def pass_hat_k(c: int, n: int, k: int) -> float:
    """Unbiased per-task pass^k from c successes in n trials (tau-bench): C(c,k)/C(n,k)."""
    if k > n:
        raise ValueError("pass^k needs at least k trials per task")
    return comb(c, k) / comb(n, k)


def pass_at_k(c: int, n: int, k: int) -> float:
    """Unbiased per-task pass@k (Codex paper): 1 - C(n-c,k)/C(n,k)."""
    if k > n:
        raise ValueError("pass@k needs at least k trials per task")
    return 1.0 - comb(n - c, k) / comb(n, k)


# ---- Part 2: suite estimators ------------------------------------------------
def suite_pass_hat_k(counts: list[int], n: int, k: int) -> float:
    return sum(pass_hat_k(c, n, k) for c in counts) / len(counts)


def suite_pass_at_k(counts: list[int], n: int, k: int) -> float:
    return sum(pass_at_k(c, n, k) for c in counts) / len(counts)


def plugin_per_task(counts: list[int], n: int, k: int) -> float:
    """Shortcut 1: average of (c/n)^k. Biased upward for every task with 0 < c < n."""
    return sum((c / n) ** k for c in counts) / len(counts)


def plugin_suite(counts: list[int], n: int, k: int) -> float:
    """Shortcut 2: (mean pass rate)^k. Ignores that hard tasks drag pass^k down."""
    return (sum(counts) / (n * len(counts))) ** k


# ---- Part 3: intervals for single rates --------------------------------------
def wilson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    z = Z.inv_cdf(1 - (1 - conf) / 2)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def binom_cdf(k: int, n: int, p: float) -> float:
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k + 1))


def clopper_pearson(k: int, n: int, conf: float = 0.95) -> tuple[float, float]:
    """Exact two-sided interval by bisection on the binomial CDF."""
    a = (1 - conf) / 2

    def bisect(f, lo=0.0, hi=1.0):
        for _ in range(100):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(mid) else (lo, mid)
        return (lo + hi) / 2

    lower = 0.0 if k == 0 else bisect(lambda p: 1 - binom_cdf(k - 1, n, p) < a)
    upper = 1.0 if k == n else bisect(lambda p: binom_cdf(k, n, p) > a)
    return lower, upper


def all_pass_needed(bar: float, conf: float = 0.95) -> int:
    """Smallest n where n of n passing puts the Wilson lower bound at or above `bar`."""
    n = 1
    while wilson(n, n, conf)[0] < bar:
        n += 1
    return n


# ---- Part 4: run counts --------------------------------------------------------
def n_unpaired(p1: float, p2: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """Per-arm n for a one-sided two-proportion z test (pooled variance under H0)."""
    za, zb = Z.inv_cdf(1 - alpha), Z.inv_cdf(power)
    pb = (p1 + p2) / 2
    num = za * sqrt(2 * pb * (1 - pb)) + zb * sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    return num ** 2 / (p1 - p2) ** 2


def n_paired(p10: float, p01: float, alpha: float = 0.05, power: float = 0.80) -> float:
    """Pairs for a one-sided McNemar test (normal approximation).

    p10: old passes, new fails. p01: old fails, new passes.
    """
    za, zb = Z.inv_cdf(1 - alpha), Z.inv_cdf(power)
    pd, d = p10 + p01, p10 - p01
    return (za * sqrt(pd) + zb * sqrt(pd - d * d)) ** 2 / d ** 2


def sim_power_unpaired(n: int, p1: float, p2: float, reps: int, rng: random.Random,
                       alpha: float = 0.05) -> float:
    za = Z.inv_cdf(1 - alpha)
    hits = 0
    for _ in range(reps):
        x1 = sum(rng.random() < p1 for _ in range(n))
        x2 = sum(rng.random() < p2 for _ in range(n))
        pb = (x1 + x2) / (2 * n)
        se = sqrt(2 * pb * (1 - pb) / n)
        hits += se > 0 and (x1 - x2) / n / se > za
    return hits / reps


def sim_power_paired(n: int, cells: dict[str, float], reps: int, rng: random.Random,
                     alpha: float = 0.05) -> float:
    """Each pair lands in one of four cells; McNemar z on the discordant counts."""
    za = Z.inv_cdf(1 - alpha)
    edges, acc = [], 0.0
    for name in ("10", "01", "11", "00"):
        acc += cells[name]
        edges.append((acc, name))
    hits = 0
    for _ in range(reps):
        b = c = 0
        for _ in range(n):
            u = rng.random()
            cell = next(name for edge, name in edges if u < edge)
            b += cell == "10"
            c += cell == "01"
        hits += b + c > 0 and (b - c) / sqrt(b + c) > za
    return hits / reps


# ---- Part 5: segment gate --------------------------------------------------------
def holm(pvals: list[float]) -> list[float]:
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m, adj, running = len(pvals), [0.0] * len(pvals), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


def paired_bootstrap(deltas: list[float], margin: float, reps: int, rng: random.Random,
                     conf: float = 0.95) -> tuple[float, float]:
    """One-sided upper bound on the mean paired delta, and the bootstrap p-value for
    H0: delta >= -margin (no regression beyond the allowed drop)."""
    n = len(deltas)
    means = sorted(sum(deltas[rng.randrange(n)] for _ in range(n)) / n for _ in range(reps))
    upper = means[min(reps - 1, int(conf * reps))]
    p = (sum(m >= -margin for m in means) + 1) / (reps + 1)
    return upper, p


def main() -> None:
    rng = random.Random(STATS_SEED)
    print(WORLD["fiction_note"])
    print(f"dataset: {WORLD['dataset']}")
    if WORLD["seed"] != STATS_SEED:
        print(f"statistics stream: seed {STATS_SEED}, shared by both editions so computed lines match")

    # Part 1 ---------------------------------------------------------------
    print("\n[1] pass^k for one task with a fixed per-trial rate p: p^k")
    print("p      k=1     k=4     k=8     k=16")
    for p in (0.95, 0.90, 0.80):
        print(f"{p:.2f}  " + "  ".join(f"{p ** k:.4f}" for k in (1, 4, 8, 16)))
    assert round(0.8 ** 8, 4) == 0.1678
    assert round(0.9 ** 8, 4) == 0.4305
    assert [round(0.9 ** k * 100) for k in (4, 8, 16)] == [66, 43, 19]
    u, s = pass_hat_k(6, 8, 4), (6 / 8) ** 4
    print(f"c=6 of n=8, k=4: unbiased C(6,4)/C(8,4) = {comb(6, 4)}/{comb(8, 4)} = {u:.4f}; "
          f"shortcut (6/8)^4 = {s:.4f}; pass@4 = {pass_at_k(6, 8, 4):.4f}")
    assert round(u, 4) == 0.2143 and round(s, 4) == 0.3164

    # Part 2 ---------------------------------------------------------------
    n_trials = 8
    scen = []  # (flow group, true per-trial rate)
    for p in (0.85, 0.80, 0.75, 0.80):  # dispute segment: 4 scenarios, mean 0.80
        scen.append(("dispute+paid", p))
    for _ in range(56):
        hard = rng.random() < 0.2
        p = rng.betavariate(6, 2) if hard else rng.betavariate(40, 1)
        scen.append(("other", p))
    trials = [[rng.random() < p for _ in range(n_trials)] for _, p in scen]
    counts = [sum(t) for t in trials]

    print("\n[2] Suite of 60 scenarios x 8 trials (synthetic; dispute segment = 4 scenarios)")
    # The v3.2 release run: one trial per scenario, a separate seeded draw chosen to
    # be green, as it was in the incident. Print how likely a green run was.
    rel_rng = random.Random(STATS_SEED + 6)
    release = [rel_rng.random() < p for _, p in scen]
    disp_release = release[:4]
    p_green = math.prod(p for _, p in scen)
    p_disp = math.prod(p for _, p in scen[:4])
    print(f"release run (1 trial per scenario): {sum(release)}/60 passed; "
          f"dispute {sum(disp_release)}/4")
    print(f"chance of that run being all green: {p_green:.3f}; dispute alone 4/4: {p_disp:.3f}")
    print("k   unbiased pass^k  per-task (c/n)^k  (mean p)^k  pass@k")
    rows = {}
    for k in (1, 2, 4, 8):
        rows[k] = (suite_pass_hat_k(counts, n_trials, k), plugin_per_task(counts, n_trials, k),
                   plugin_suite(counts, n_trials, k), suite_pass_at_k(counts, n_trials, k))
        a, b, c, d = rows[k]
        print(f"{k:<3} {a:>15.3f}  {b:>16.3f}  {c:>10.3f}  {d:>6.3f}")
    for k in (2, 4, 8):
        assert rows[k][1] >= rows[k][0], "per-task plug-in must not fall below unbiased"
    assert rows[8][3] > rows[1][0] > rows[8][0]
    true8 = sum(p ** 8 for _, p in scen) / len(scen)
    print(f"true suite pass^8 from the generating rates: {true8:.3f}")
    # Frozen numbers the chapter and this page quote (identical in both editions)
    assert f"{p_green:.3f}/{p_disp:.3f}/{true8:.3f}" == "0.037/0.408/0.751"
    assert [f"{v:.3f}" for v in rows[8]] == ["0.800", "0.857", "0.776", "1.000"]
    assert [f"{v:.3f}" for v in rows[4][:3]] == ["0.886", "0.904", "0.881"]

    # Part 3 ---------------------------------------------------------------
    print("\n[3] Intervals for single rates (95%)")
    disp_counts = counts[:4]
    k_d, n_d = sum(disp_counts), 4 * n_trials
    lines = [("release run, all 60", sum(release), 60),
             ("release run, dispute", sum(disp_release), 4),
             ("8 trials, dispute (32 runs, 4 tasks)", k_d, n_d)]
    print("rate                                   k/n      Wilson           Clopper-Pearson")
    for name, k, n in lines:
        w, cp = wilson(k, n), clopper_pearson(k, n)
        print(f"{name:<38} {k:>2}/{n:<4} [{w[0]:.3f}, {w[1]:.3f}]   [{cp[0]:.3f}, {cp[1]:.3f}]")
    lo4 = wilson(4, 4)[0]
    need = all_pass_needed(0.90)
    print(f"4 of 4 passing: Wilson lower bound {lo4:.3f}; to clear a 0.90 bar with zero "
          f"failures you need {need} of {need}")
    print("the 32 dispute runs come from 4 scenarios, so they are not 32 independent "
          "trials: the scenario is the unit for any gate")
    assert sum(disp_release) == 4, "the seeded release run must show a green dispute segment"
    assert round(lo4, 3) == 0.510 and need == 35

    # Part 4 ---------------------------------------------------------------
    print("\n[4] Runs needed to detect 90% -> 85% (one-sided alpha 0.05, power 0.80)")
    nu = n_unpaired(0.90, 0.85)
    cells = {"10": 0.07, "01": 0.02, "11": 0.83, "00": 0.08}
    npd = n_paired(cells["10"], cells["01"])
    print(f"unpaired, closed form: {nu:.1f} -> {math.ceil(nu)} scenarios per arm "
          f"({2 * math.ceil(nu):,} scenario runs)")
    print(f"paired (McNemar), discordant cells 7% / 2%: {npd:.1f} -> {math.ceil(npd)} scenarios, "
          f"each run on both versions")
    assert math.ceil(nu) == 540 and round(npd, -1) == 220
    sim_rng = random.Random(STATS_SEED + 4)
    pw_u = sim_power_unpaired(math.ceil(nu), 0.90, 0.85, 2000, sim_rng)
    pw_p = sim_power_paired(math.ceil(npd), cells, 2000, sim_rng)
    pw_p60 = sim_power_paired(60, cells, 2000, sim_rng)
    print(f"seeded simulation, 2,000 reps: unpaired power {pw_u:.3f}; paired power {pw_p:.3f}; "
          f"paired at 60 scenarios {pw_p60:.3f}")
    assert 0.76 < pw_u < 0.84 and 0.76 < pw_p < 0.84 and pw_p60 < 0.45
    assert f"{pw_u:.3f}/{pw_p:.3f}/{pw_p60:.3f}" == "0.791/0.804/0.358"

    # Part 5 ---------------------------------------------------------------
    print("\n[5] Release gate: 240 scenarios, 20 per gated segment, k=4, old vs new")
    k_n, per_seg, margin = WORLD["nightly"]["k"], WORLD["nightly"]["per_segment"], 0.05
    regress = (LANG_GROUPS[1], "dispute+paid")  # seeded regression, second language group
    seg_rows = []
    gate_rng = random.Random(STATS_SEED + 5)
    for lang in LANG_GROUPS:
        for flow in FLOW_GROUPS:
            deltas, new_counts, old_sum, new_sum = [], [], 0, 0
            for _ in range(per_seg):
                p_old = gate_rng.betavariate(18, 2)
                p_new = p_old - 0.30 if (lang, flow) == regress else p_old
                old = sum(gate_rng.random() < p_old for _ in range(k_n))
                new = sum(gate_rng.random() < max(0.0, p_new) for _ in range(k_n))
                deltas.append((new - old) / k_n)
                new_counts.append(new)
                old_sum, new_sum = old_sum + old, new_sum + new
            upper, p = paired_bootstrap(deltas, margin, 2000, gate_rng)
            seg_rows.append([lang, flow, old_sum / (per_seg * k_n), new_sum / (per_seg * k_n),
                             sum(deltas) / per_seg, upper, p,
                             suite_pass_hat_k(new_counts, k_n, k_n)])
    adj = holm([r[6] for r in seg_rows])
    print(f"allowed drop {margin:.2f}; block when the Holm-adjusted p for "
          f"'delta below -{margin:.2f}' is under 0.05")
    print(f"{'language':<{LANG_W + 1}}flow                old    new    delta  upper95  p      "
          "p_holm  new pass^4  gate")
    blocked = []
    for r, pa in zip(seg_rows, adj):
        verdict = "BLOCK" if pa < 0.05 else "pass"
        if verdict == "BLOCK":
            blocked.append((r[0], r[1]))
        print(f"{r[0]:<{LANG_W}} {r[1]:<18} {r[2]:.3f}  {r[3]:.3f}  {r[4]:+.3f}  {r[5]:+.3f}   "
              f"{r[6]:.4f} {pa:.4f}  {r[7]:.3f}       {verdict}")
    print(f"blocked segments: {', '.join(' x '.join(b) for b in blocked)}")
    assert blocked == [regress], blocked
    pooled = sum(r[4] for r in seg_rows) / len(seg_rows)
    hit = seg_rows[LANG_GROUPS.index(regress[0]) * len(FLOW_GROUPS) + 1]
    assert [f"{v:.3f}" for v in hit[2:6]] == ["0.912", "0.613", "-0.300", "-0.163"]
    assert f"{hit[6]:.4f}/{adj[seg_rows.index(hit)]:.4f}/{hit[7]:.3f}" == "0.0005/0.0060/0.300"
    print(f"pooled delta over all 240 scenarios: {pooled:+.3f} (the regression is diluted "
          f"12 ways; a pooled gate alone would read it as a small dip)")
    assert f"{pooled:+.3f}" == "-0.022"
    print("\nall assertions passed")


if __name__ == "__main__":
    main()
