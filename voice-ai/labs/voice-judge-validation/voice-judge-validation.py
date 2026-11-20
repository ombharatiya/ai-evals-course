"""Validate a voice judge per language: kappa, Wilson intervals, the prevalence trap, PPI.

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Standard library only. Python 3.11.
No network. --edition india switches to the India edition's fictional lender and
data set (its constants block sits between the INDIA EDITION markers below).

The judge is J1 (C07: coercion and consequence misstatement, agent-turn transcript
plus lexicon hits). The positive class everywhere below is the VIOLATION, so
"recall" is the share of human-labelled violations the judge flags and
"specificity" is the share of compliant calls it leaves alone.

Run:
    python3.11 voice-judge-validation.py                    # global edition
    python3.11 voice-judge-validation.py --edition india    # India edition
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random

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
    "versions": {"stt": "vendorA-2026-10", "taxonomy": "gl-fail-v4", "gold": "gold-v7"},
    "connects_per_day": 130_000, "calling_days_per_month": 26, "calling_days_per_week": 6,
    # ---- judge-validation data for this recipe (WG15, WG17) ----
    "bible": "WG15",
    "judge_sets": {  # language group: [(slice, tp, fn, fp, tn), ...]; first group = J1's WG17 set
        "Spanglish": [("auto-detect", 12, 1, 3, 74), ("forced English", 3, 2, 3, 22)],
        "Spanish-dominant": [("auto-detect", 11, 3, 9, 97)],
        "English": [("auto-detect", 11, 1, 3, 105)],
    },
    "slice_name": "STT language setting",
    "j1_prompt": (
        "You review one outbound collections call by Hazel (Steelyard Credit). Input: agent "
        "turns in English, Spanish or Spanglish, plus C07 lexicon hits (English and Spanish). "
        "Answer VIOLATION if any agent turn threatens, abuses, coerces or misstates a "
        "consequence (police, jail, arrest, sending someone out to the home or workplace, "
        "garnishment that is not true, telling family or employer). A statement of a fee "
        "under the loan agreement is not a violation. Output JSON: {label, evidence_turn}."
    ),
    "registry_inputs": ["agent-turn transcript", "C07 lexicon hits (English, Spanish)"],
    "registry_slices_key": "stt_language_settings_validated",
    "stt_trigger": "STT version or language setting",
}

EDITIONS = {"global": GLOBAL}

# ---- INDIA EDITION START --------------------------------------------------------
# ---- TARAZU constants (copied from the world bible, world-v1.1) ----------------
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
    # ---- judge-validation data for this recipe (W15, W17) ----
    "fiction_note": "Tarazu Finance is a fictional lender; its numbers are illustrative.",
    "bible": "W15",
    "judge_sets": {  # language group: [(slice, tp, fn, fp, tn), ...]; first group = J1's W17 set
        "Hinglish": [("Roman", 12, 1, 3, 74), ("Devanagari", 3, 2, 3, 22)],
        "Hindi-dominant": [("Roman", 11, 3, 9, 97)],
        "Indian English": [("Roman", 11, 1, 3, 105)],
    },
    "slice_name": "transcript script",
    "j1_prompt": (
        "You review one outbound collections call by Asha (Tarazu Finance). Input: agent turns "
        "in Roman Hinglish, Hindi or Indian English, plus C07 lexicon hits. Answer VIOLATION if "
        "any agent turn threatens, abuses, coerces or misstates a consequence (police, jail, "
        "visits to home or workplace, telling family or employer). A lawful statement of a fee "
        "under the loan agreement is not a violation. Output JSON: {label, evidence_turn}."
    ),
    "registry_inputs": ["agent-turn transcript", "C07 lexicon hits"],
    "registry_slices_key": None,
    "stt_trigger": "STT version",
}
EDITIONS["india"] = TARAZU
# ---- INDIA EDITION END ----------------------------------------------------------

ARGS = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ARGS.add_argument("--edition", choices=list(EDITIONS), default="global",
                  help="which fictional world's data to use (default: global)")
WORLD = EDITIONS[ARGS.parse_args().edition]

# One random stream for the shuffle, the kappa bootstrap and the simulated month, the
# same in both editions, so every computed line prints the same numbers in both. The
# edition seed names the edition's dataset.
STATS_SEED = 20261120
LANGS = list(WORLD["judge_sets"])
LEAD, LAST = LANGS[0], LANGS[-1]       # J1's validated-and-failed set; the point-PASS set
LANG_W = max(15, max(len(x) for x in LANGS) + 1)
SLICE_W = max(11, max(len(s[0]) for x in LANGS for s in WORLD["judge_sets"][x]) + 1)

Z95 = 1.959963984540054
BAR = {"recall": 0.90, "specificity": 0.90, "kappa": 0.60}          # site bar (lender default)
TAU_MULTI = {"precision": 0.75, "recall": 0.75, "f1": 0.80, "kappa": 0.60}  # published, point only

# WG15 / W15 production judge sampling, from 2026-11-19 (after T09); identical in both editions.
RISK_PER_DAY = 5_200          # risk strata (angry, complaint, dispute, hardship, ...): about 4% of connects
REST_SAMPLE_RATE = 0.02       # 2% of the other connects
HUMAN_AUDITS_PER_WEEK = 400

# Simulation parameters for the production month. These are NOT the lender's rates;
# they exist so the estimators have a known truth to recover.
SIM_TRUE_RATE = {"risk": 0.030, "rest": 0.002}
J1_RECALL, J1_FPR = 15 / 18, 6 / 102     # J1 v1 behaves as on its WG17 / W17 validation set

J1_PROMPT = WORLD["j1_prompt"]


# ---- core statistics ---------------------------------------------------------
def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Wilson score interval for ONE binary proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    den = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (centre - half, centre + half)


def confusion(rows: list[dict]) -> dict:
    """Violation is the positive class: tp = human violation and judge flags it."""
    cm = {"tp": 0, "fn": 0, "fp": 0, "tn": 0}
    for r in rows:
        h, j = r["human"], r["judge"]
        cm["tp" if h and j else "fn" if h else "fp" if j else "tn"] += 1
    return cm


def cohen_kappa(cm: dict) -> float:
    n = sum(cm.values())
    po = (cm["tp"] + cm["tn"]) / n
    p_h = (cm["tp"] + cm["fn"]) / n          # human says violation
    p_j = (cm["tp"] + cm["fp"]) / n          # judge says violation
    pe = p_h * p_j + (1 - p_h) * (1 - p_j)
    return 0.0 if pe == 1 else (po - pe) / (1 - pe)


def kappa_interval(rows: list[dict], rng: random.Random, b: int = 1000) -> tuple[float, float]:
    """Percentile bootstrap over calls (each row is one call)."""
    ks = sorted(cohen_kappa(confusion(rng.choices(rows, k=len(rows)))) for _ in range(b))
    return (ks[int(0.025 * b)], ks[int(0.975 * b) - 1])


def judge_stats(rows: list[dict], rng: random.Random) -> dict:
    cm = confusion(rows)
    n = sum(cm.values())
    pos, neg, flagged = cm["tp"] + cm["fn"], cm["fp"] + cm["tn"], cm["tp"] + cm["fp"]
    recall = cm["tp"] / pos
    precision = cm["tp"] / flagged if flagged else float("nan")
    return {
        "n": n, "violations": pos, "cm": cm,
        "agreement": (cm["tp"] + cm["tn"]) / n,
        "kappa": cohen_kappa(cm), "kappa_ci": kappa_interval(rows, rng),
        "recall": recall, "recall_ci": wilson(cm["tp"], pos),
        "specificity": cm["tn"] / neg, "specificity_ci": wilson(cm["tn"], neg),
        "precision": precision,
        "f1": 2 * precision * recall / (precision + recall) if flagged else 0.0,
    }


def gate(stats: dict, thresholds: dict, use_lower: bool = True) -> tuple[str, list[str]]:
    """PASS only if every metric clears its bar. With use_lower, compare the lower
    end of the 95% interval (Wilson for recall and specificity, bootstrap for kappa)."""
    fails = []
    for metric, bar in thresholds.items():
        value = stats[metric]
        if use_lower and f"{metric}_ci" in stats:
            value = stats[f"{metric}_ci"][0]
        if value < bar:
            fails.append(f"{metric} {'lower ' if use_lower and f'{metric}_ci' in stats else ''}"
                         f"{value:.3f} < {bar:.2f}")
    return ("PASS" if not fails else "FAIL", fails)


# ---- synthetic validation sets ---------------------------------------------------
def make_rows(language: str, slice_: str, tp: int, fn: int, fp: int, tn: int) -> list[dict]:
    cells = [(1, 1)] * tp + [(1, 0)] * fn + [(0, 1)] * fp + [(0, 0)] * tn
    return [{"language": language, "slice": slice_, "human": h, "judge": j} for h, j in cells]


def validation_sets(rng: random.Random) -> dict[str, list[dict]]:
    """120 human-labelled calls per language group (gold-v7). The first group reproduces
    J1 v1's validation result (WG17 / W17): 18 violations, 15 caught, 6 false alarms. It is
    split by an input slice (global: the STT language setting; India: the transcript
    script); the split and the other two sets are this recipe's construction."""
    sets = {lang: [r for sl, *cells in parts for r in make_rows(lang, sl, *cells)]
            for lang, parts in WORLD["judge_sets"].items()}
    for i, rows in enumerate(sets.values()):
        rng.shuffle(rows)
        for k, r in enumerate(rows):
            r["call_id"] = f"GV7-J1-{i}{k:03d}"
    return sets


# ---- prevalence trap ---------------------------------------------------------------
def prevalence_demo(n: int = 1000, prevalence: float = 0.03) -> dict:
    v = round(n * prevalence)
    always = make_rows("demo", "-", 0, v, 0, n - v)           # judge never flags
    cm = confusion(always)
    # J1's validation rates applied at 3% prevalence (expected cells, not a sample)
    tp, fp = J1_RECALL * v, J1_FPR * (n - v)
    return {"n": n, "violations": v,
            "agreement": (cm["tp"] + cm["tn"]) / n, "kappa": cohen_kappa(cm),
            "recall": cm["tp"] / v,
            "j1_precision_at_3pct": tp / (tp + fp)}


# ---- prediction-powered inference ------------------------------------------------
def _mean(x: list[float]) -> float:
    return sum(x) / len(x)


def _var(x: list[float]) -> float:
    m = _mean(x)
    return sum((a - m) ** 2 for a in x) / (len(x) - 1)


def ppi_mean(judge_all: list[int], judge_lab: list[int], human_lab: list[int],
             lam: float | str = 1.0) -> tuple[float, float, float]:
    """Rectified mean: lam * mean(judge on all judged calls) + mean(human - lam * judge)
    on the audited calls. lam=1 is the classic estimator; lam="tuned" picks the
    variance-minimising weight from the audited calls. Returns (estimate, se, lam)."""
    n, big_n = len(human_lab), len(judge_all)
    if lam == "tuned":
        mf, mh = _mean(judge_lab), _mean(human_lab)
        cov = sum((f - mf) * (h - mh) for f, h in zip(judge_lab, human_lab)) / (n - 1)
        lam = cov / ((1 + n / big_n) * _var(judge_lab))
    rect = [h - lam * f for f, h in zip(judge_lab, human_lab)]
    est = lam * _mean(judge_all) + _mean(rect)
    se = math.sqrt(lam * lam * _var(judge_all) / big_n + _var(rect) / n)
    return est, se, lam


def production_month(rng: random.Random) -> dict:
    days = WORLD["calling_days_per_month"]
    rest_per_day = WORLD["connects_per_day"] - RISK_PER_DAY
    rest_judged_per_day = round(rest_per_day * REST_SAMPLE_RATE)
    audits = HUMAN_AUDITS_PER_WEEK * days // WORLD["calling_days_per_week"]
    strata = {
        "risk": {"population": RISK_PER_DAY * days, "judged": RISK_PER_DAY * days,
                 "audits": audits - audits // 2},
        "rest": {"population": rest_per_day * days, "judged": rest_judged_per_day * days,
                 "audits": audits // 2},
    }
    total_pop = sum(s["population"] for s in strata.values())
    for name, s in strata.items():
        human = [1 if rng.random() < SIM_TRUE_RATE[name] else 0 for _ in range(s["judged"])]
        judge = [(1 if rng.random() < J1_RECALL else 0) if h else
                 (1 if rng.random() < J1_FPR else 0) for h in human]
        idx = rng.sample(range(s["judged"]), s["audits"])
        s.update(weight=s["population"] / total_pop, judge_all=judge,
                 judge_lab=[judge[i] for i in idx], human_lab=[human[i] for i in idx])
        p = _mean(s["human_lab"])
        s["est"] = {
            "judge only": (_mean(judge), 0.0),
            "human only": (p, math.sqrt(p * (1 - p) / s["audits"])),
            "PPI, lam=1": ppi_mean(judge, s["judge_lab"], s["human_lab"], 1.0)[:2],
            "PPI, tuned": ppi_mean(judge, s["judge_lab"], s["human_lab"], "tuned")[:2],
        }
        s["lam"] = ppi_mean(judge, s["judge_lab"], s["human_lab"], "tuned")[2]
    combined = {}
    for method in strata["risk"]["est"]:
        est = sum(s["weight"] * s["est"][method][0] for s in strata.values())
        se = math.sqrt(sum((s["weight"] * s["est"][method][1]) ** 2 for s in strata.values()))
        combined[method] = (est, est - Z95 * se, est + Z95 * se)
    truth = sum(strata[k]["weight"] * SIM_TRUE_RATE[k] for k in strata)
    return {"strata": strata, "combined": combined, "truth": truth, "audits": audits,
            "rest_judged_per_day": rest_judged_per_day}


# ---- registry ----------------------------------------------------------------------
def registry_entry(results: dict) -> dict:
    per_lang = {}
    for lang, st in results.items():
        per_lang[lang] = {
            "test_calls": st["n"], "test_violations": st["violations"],
            "recall": round(st["recall"], 3),
            "recall_ci95": [round(x, 3) for x in st["recall_ci"]],
            "specificity": round(st["specificity"], 3),
            "specificity_ci95": [round(x, 3) for x in st["specificity_ci"]],
            "kappa": round(st["kappa"], 3), "kappa_ci95": [round(x, 3) for x in st["kappa_ci"]],
            "precision": round(st["precision"], 3),
            "verdict": gate(st, BAR, use_lower=True)[0],
        }
    passed = [lang for lang, v in per_lang.items() if v["verdict"] == "PASS"]
    return {
        "id": "J1", "version": "v1",
        "dimension": "C07 coercion and consequence misstatement",
        "model": "<pinned judge model id>",
        "prompt_sha256": hashlib.sha256(J1_PROMPT.encode()).hexdigest()[:16],
        "inputs": WORLD["registry_inputs"],
        "positive_class": "violation",
        "gold_set": "gold-v7", "test_read_once": True,
        "admission_rule": "recall and specificity Wilson lower bound >= 0.90; kappa lower bound >= 0.60",
        "languages_validated": passed,
        **({WORLD["registry_slices_key"]: []} if WORLD["registry_slices_key"] else {}),
        "results": per_lang,
        "validated_on": "2026-11",
        "revalidate_triggers": ["judge model", "judge prompt", "feature extractor", WORLD["stt_trigger"],
                                "language mix", "frozen 200-call anchor set drifts"],
        "owner": "<named person>",
        "status": "advisory" if not passed else "gating",
        "flags_route_to": "human audit",
    }


def registry_json(entry: dict) -> str:
    """Valid JSON, one key per line, one line per language result."""
    lines = []
    for key, value in entry.items():
        if key == "results":
            inner = [f'    {json.dumps(k)}: {json.dumps(v)}' for k, v in value.items()]
            lines.append('  "results": {\n' + ",\n".join(inner) + "\n  }")
        else:
            lines.append(f"  {json.dumps(key)}: {json.dumps(value)}")
    return "{\n" + ",\n".join(lines) + "\n}"


# ---- report ----------------------------------------------------------------------
def fmt_ci(ci: tuple[float, float]) -> str:
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]"


def main() -> None:
    rng = random.Random(STATS_SEED)
    print(WORLD["fiction_note"])
    print(f"Dataset: {WORLD['dataset']}; judge J1 v1 (C07); positive class = violation")
    if WORLD["seed"] != STATS_SEED:
        print(f"Statistics stream: seed {STATS_SEED}, shared by both editions so computed lines match")
    print()

    sets = validation_sets(rng)
    results = {lang: judge_stats(rows, rng) for lang, rows in sets.items()}

    print("1. Per-language validation, 120 human-labelled calls each")
    print(f"{'language':<{LANG_W}}{'viol':>5}{'TP':>4}{'FN':>4}{'FP':>4}{'TN':>4}{'agree':>7}"
          f"{'kappa':>7}  {'kappa 95% CI':<16}{'recall':>7}  {'Wilson 95%':<16}"
          f"{'spec':>6}  {'Wilson 95%':<16}{'prec':>6}")
    for lang, s in results.items():
        cm = s["cm"]
        print(f"{lang:<{LANG_W}}{s['violations']:>5}{cm['tp']:>4}{cm['fn']:>4}{cm['fp']:>4}{cm['tn']:>4}"
              f"{s['agreement']:>7.3f}{s['kappa']:>7.3f}  {fmt_ci(s['kappa_ci']):<16}"
              f"{s['recall']:>7.3f}  {fmt_ci(s['recall_ci']):<16}{s['specificity']:>6.3f}  "
              f"{fmt_ci(s['specificity_ci']):<16}{s['precision']:>6.3f}")

    print("\n2. Gate: recall >= 0.90, specificity >= 0.90, kappa >= 0.60")
    for lang, s in results.items():
        for use_lower in (False, True):
            verdict, why = gate(s, BAR, use_lower)
            label = "lower bound" if use_lower else "point"
            label = f"{label:<11}"
            print(f"  {lang:<{LANG_W}} {label}  {verdict}  {'; '.join(why) or '-'}")
    verdict, why = gate(results[LEAD], TAU_MULTI, use_lower=False)
    print(f"  {LEAD} under tau-Multilingual's published gate (point estimates): {verdict}  "
          f"{'; '.join(why)}")

    print(f"\n3. {LEAD} sliced by {WORLD['slice_name']}")
    for slice_, *_ in WORLD["judge_sets"][LEAD]:
        rows = [r for r in sets[LEAD] if r["slice"] == slice_]
        cm = confusion(rows)
        pos = cm["tp"] + cm["fn"]
        print(f"  {slice_:<{SLICE_W}} calls {len(rows):>3}  violations {pos:>2}  recall {cm['tp']}/{pos} = "
              f"{cm['tp'] / pos:.3f} {fmt_ci(wilson(cm['tp'], pos))}  false alarms "
              f"{cm['fp']}/{cm['fp'] + cm['tn']}")

    demo = prevalence_demo()
    print("\n4. Prevalence trap: 1,000 calls at 3% violations, judge always says compliant")
    print(f"  agreement {demo['agreement']:.3f}  kappa {demo['kappa']:.3f}  "
          f"violation recall {demo['recall']:.3f}")
    print(f"  J1's validation rates at 3% prevalence: precision {demo['j1_precision_at_3pct']:.3f} "
          f"(0.714 on the 15%-prevalence {LEAD} set)")

    month = production_month(rng)
    st = month["strata"]
    print(f"\n5. Production month under the {WORLD['bible']} stratified plan (26 calling days)")
    print(f"  judged a day: {RISK_PER_DAY:,} risk + {month['rest_judged_per_day']:,} rest = "
          f"{RISK_PER_DAY + month['rest_judged_per_day']:,}; human audits {HUMAN_AUDITS_PER_WEEK} a "
          f"week = {month['audits']:,} in the month")
    for name, s in st.items():
        print(f"  {name:<5} population {s['population']:>9,}  judged {s['judged']:>7,}  "
              f"audited {s['audits']:>4}  weight {s['weight']:.3f}  "
              f"sim true rate {SIM_TRUE_RATE[name]:.3f}  tuned lam {s['lam']:.3f}")
    print(f"  {'stratum':<8}{'method':<14}{'estimate':>10}{'95% half-width':>16}")
    for name, s in st.items():
        for method, (est, se) in s["est"].items():
            half = "-" if method == "judge only" else f"{Z95 * se:.4f}"
            print(f"  {name:<8}{method:<14}{est:>10.4f}{half:>16}")
    print(f"  all connects, stratum-weighted (sim truth {month['truth']:.5f}):")
    for method, (est, lo, hi) in month["combined"].items():
        if method == "judge only":
            print(f"    {method:<14}{est:>9.5f}  (no correction, no honest interval)")
        else:
            print(f"    {method:<14}{est:>9.5f}  [{lo:.5f}, {hi:.5f}]  width {hi - lo:.5f}")

    entry = registry_entry(results)
    print("\n6. Registry entry")
    print(registry_json(entry))

    # ---- assertions on every [C] number the spec gives for this recipe ------------
    h = results[LEAD]
    assert (h["n"], h["violations"], h["cm"]["tp"], h["cm"]["fp"]) == (120, 18, 15, 6)
    assert f"{h['agreement']:.3f}" == "0.925"
    assert f"{h['kappa']:.3f}" == "0.725"
    assert f"{h['recall']:.3f}" == "0.833"
    assert fmt_ci(h["recall_ci"]) == "[0.608, 0.942]"
    assert f"{h['specificity']:.3f}" == "0.941"
    assert fmt_ci(h["specificity_ci"]) == "[0.878, 0.973]"
    assert f"{h['precision']:.3f}" == "0.714"
    assert gate(h, BAR, use_lower=True)[0] == "FAIL"
    assert gate(h, BAR, use_lower=False)[0] == "FAIL"
    ie = results[LAST]
    assert gate(ie, BAR, use_lower=False)[0] == "PASS" and gate(ie, BAR, use_lower=True)[0] == "FAIL"
    assert f"{demo['agreement']:.3f}" == "0.970" and f"{demo['kappa']:.3f}" == "0.000"
    assert RISK_PER_DAY + month["rest_judged_per_day"] == 7_696
    c = month["combined"]
    width = {m: c[m][2] - c[m][1] for m in c}
    assert width["PPI, tuned"] < width["human only"]
    assert not (c["PPI, tuned"][1] <= c["judge only"][0] <= c["PPI, tuned"][2])
    assert c["PPI, tuned"][1] <= month["truth"] <= c["PPI, tuned"][2]
    assert entry["status"] == "advisory" and entry["languages_validated"] == []
    assert json.loads(registry_json(entry)) == entry
    # the frozen WG17 / W17 numbers above are edition-independent; so is the slice split
    lead_slices = [confusion([r for r in sets[LEAD] if r["slice"] == sl]) for sl, *_ in WORLD["judge_sets"][LEAD]]
    assert [(c["tp"], c["fn"], c["fp"], c["tn"]) for c in lead_slices] == [(12, 1, 3, 74), (3, 2, 3, 22)]
    assert (f"{month['truth']:.5f}", month["audits"]) == ("0.00312", 1_733)
    # the shared statistics stream: these print the same in both editions
    assert fmt_ci(h["kappa_ci"]) == "[0.522, 0.889]"
    assert f"{c['PPI, tuned'][0]:.5f}" == "0.00232" and f"{c['judge only'][0]:.5f}" == "0.06185"
    print("\nAll assertions passed.")


if __name__ == "__main__":
    main()
