"""Plan a voice load test (aievals.co cookbook recipe R10).

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Python 3.11, standard library only, no network.
--edition india switches to the India edition's fictional lender and prices (its constants
block sits between the INDIA EDITION markers below). The stack model is the same in both
editions and runs on one seed, so every latency, rejection and amount-safe line matches.

A discrete-event model (heapq) of the agent's cascaded stack under load:
  - admission limits: trunk channels and STT streaming concurrency (rejected connections)
  - an LLM provider concurrency limit with 429s, exponential backoff and at most 3 retries
  - LLM TTFT that inflates, and whose tail widens, as the provider fills up
  - CRM latency that rises with concurrent calls (the T04 mechanism)
  - STT final delay that rises with stream utilisation (the amount-accuracy proxy)
  - a caller who says "hello?" after 3 s of dead air, which makes a duplicate reply (T04)
It runs the plan: ramp in 10% steps of today's 2,400 projected peak up to 1.5x, a sustained
hold at 1.0x, a 3x spike, and a cold burst for contrast. It reports, per step, P95 tool-turn
gap with a call-clustered bootstrap interval, rejected connections, an amount-accuracy proxy
and LLM cost per completed task, then applies stop conditions and the load gate.

Run:
    python3.11 voice-load-ramp-plan.py                    # global edition
    python3.11 voice-load-ramp-plan.py --edition india    # India edition
"""
from __future__ import annotations

import argparse
import heapq
import math
import random


# ---- GLOBAL constants (copied from the world bible, world-global-v1.1) ---------
GLOBAL = {
    "lender": "Steelyard Credit, Inc. (fictional US lender)",
    "dataset": "steelyard-calls (synthetic, seed 20261121)",
    "seed": 20261121,
    "products": {"AUTO": "Auto loan", "PIL": "Personal installment, digital",
                 "POS": "Retail point-of-sale", "SBL": "Small business (guarantor)",
                 "SDL": "Credit-builder and small-dollar"},
    "campaigns": {  # campaign: (book, default silence budget ms, amount/date-asked budget ms)
        "AUTO-early-nov": ("AUTO", 400, 600),   # 300 ms before T05's fix on 2026-11-17
        "PIL-digital-nov": ("PIL", 400, 600),
        "POS-short-nov": ("POS", 400, 600),
        "SBL-guar-nov": ("SBL", 450, 650),
        "SDL-biwk-nov": ("SDL", 600, 800),
    },
    "calling_window_local": ("08:00", "21:00"),
    "calling_window_sdl": ("09:00", "20:00"),
    "customer_advocate": {"name": "Ms Dana Brooks", "email": "advocate@steelyard.example",
                          "phone": "(520) 555-0199",
                          "address": "1200 Example Avenue, Tucson, AZ 85701"},
    "money_unit": "integer cents",
    "usd_1500_forms": ["fifteen hundred", "one thousand five hundred", "1,500", "1500",
                       "$1,500.00", "mil quinientos", "mil quinientos dolares",
                       "1.500 [es-ES]"],
    "turn_types": ["greeting", "verification", "amount-quote", "readback", "tool",
                   "objection", "closing"],
    "hop_ms": 10,                # orchestration hop, WG11
    "carrier_offset_ms": 212,    # WG13 example call
}
# WG1 volumes and WG20 prices [W]; everything derived from them below is [C]
GLOBAL.update({
    "lender_short": "Steelyard",
    "note": "Steelyard Credit is a fictional lender; its numbers are illustrative.",
    "stack_note": "The stack model is synthetic and edition-neutral (seed 20261120 in both editions).",
    "volumes": {"dials_per_day": 250000, "connect_rate": 0.52, "connected_s": 150,
                "attempt_s": 30, "day_hours": 16, "peak_today": 2400, "peak_capstone": 6000},
    "day_label": "the 16-hour dialing day (08:00 Eastern to 21:00 Pacific)",
    "mean_conc": 401,            # WG1: about 400 [C]
    "prices": {"input_tokens": 25000, "cached_share": 0.60, "output_tokens": 500,
               "per_m_input": 1.00, "per_m_cached": 0.25, "per_m_output": 4.00},
    "per_call": 0.01575,         # WG20 prices, 60% cached [C]
    "money": ("$", 1, 5),        # (symbol, display scale, decimals) for per-call cost
    "task_col": ("cents/task", 100, 3),   # (header, display scale, decimals) for the table
    "sms_tool": "send_disclosure_sms",
    "price_ref": "WG20",
})

EDITIONS = {"global": GLOBAL}

# ---- INDIA EDITION START --------------------------------------------------------
# ---- TARAZU constants (copied from the world bible, world-v1.1) ----------------
TARAZU = {
    "lender": "Tarazu Finance Ltd (fictional NBFC)",
    "dataset": "tarazu-calls (synthetic, seed 20261120)",
    "seed": 20261120,
    "products": {"TW": "Two-wheeler", "PL": "Personal, digital", "CD": "Consumer durable",
                 "SBL": "Small business", "MFI": "Microfinance"},
    "campaigns": {  # campaign: (book, default silence budget ms, amount/date-asked budget ms)
        "TW-early-nov": ("TW", 400, 600),     # 300 ms before T05's fix on 2026-11-17
        "PL-digital-nov": ("PL", 400, 600),
        "CD-short-nov": ("CD", 400, 600),
        "SBL-guar-nov": ("SBL", 450, 650),
        "MFI-fort-nov": ("MFI", 600, 800),
    },
    "calling_window_local": ("08:00", "19:00"),
    "calling_window_mfi": ("09:00", "18:00"),
    "grievance_officer": {"name": "Ms Neha Kulkarni", "email": "grievance@tarazu.example",
                          "phone": "020-4000-0000",
                          "address": "Tarazu House, Baner Road, Pune 411045"},
    "money_unit": "integer paise",
    "rs_150000_forms": ["dedh lakh", "1.5 lakh", "1,50,000", "150000", "150,000",
                        "ek lakh pachaas hazaar", "one lakh fifty thousand"],
    "turn_types": ["greeting", "verification", "amount-quote", "readback", "tool",
                   "objection", "closing"],
    "hop_ms": 10,                # orchestration hop, W11
    "carrier_offset_ms": 212,    # W13 example call
}
# W1 volumes and W20 prices [W]; everything derived from them below is [C]
TARAZU.update({
    "lender_short": "Tarazu",
    "note": "Tarazu Finance is a fictional lender; its numbers are illustrative.",
    "stack_note": "The stack model is synthetic.",
    "volumes": {"dials_per_day": 250000, "connect_rate": 0.52, "connected_s": 150,
                "attempt_s": 30, "day_hours": 11, "peak_today": 2400, "peak_capstone": 6000},
    "day_label": "08:00-19:00",
    "mean_conc": 583,            # W1: about 580 [C]
    "prices": {"input_tokens": 25000, "cached_share": 0.60, "output_tokens": 500,
               "per_m_input": 20.0, "per_m_cached": 5.0, "per_m_output": 80.0},
    "per_call": 0.315,
    "money": ("Rs ", 1, 3),
    "task_col": ("Rs/task", 1, 3),
    "sms_tool": "send_grievance_sms",
    "price_ref": "W20",
})
EDITIONS["india"] = TARAZU
# ---- INDIA EDITION END ----------------------------------------------------------

ARGS = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ARGS.add_argument("--edition", choices=list(EDITIONS), default="global",
                  help="which fictional world's data to use (default: global)")
WORLD = EDITIONS[ARGS.parse_args().edition]

VOL = WORLD["volumes"]
PRICES = WORLD["prices"]
LEAD = list(WORLD["campaigns"])[0]                 # the first campaign in the block: AUTO-early-nov
_, BUDGET_MS, BUDGET_AMOUNT_MS = WORLD["campaigns"][LEAD]   # 400 and 600 ms in both editions
SLO_TOOL_GAP_MS = BUDGET_MS + 2200    # WG11/W11: lead campaign budget 400 ms + 2,200 ms on tool turns
SLO_NONTOOL_GAP_MS = BUDGET_MS + 1500
HELLO_AFTER_MS = 3000             # T04: "hello? hello?" came after 2,990 ms of dead air

# ---- The stack model. Invented generator parameters for this synthetic test, ----
# ---- the same in both editions; not measurements of either fictional lender ----
# ---- and not any vendor's limits. Replace with yours.                          ----
GEN = {
    "trunk_channels": 5000,          # SIP channels
    "stt_streams": 4500,             # STT streaming concurrency limit (binds before the trunk)
    "llm_concurrency": 450,          # in-flight requests the LLM provider accepts, then 429
    "llm_retries": 3, "llm_backoff_ms": 250,     # 250, 500, 1000 ms, each x U(0.5, 1.5)
    "llm_gen_hold_ms": 500,          # slot held this long after the first token
    "ttft_median_ms": {"tool": 520, "nontool": 430}, "ttft_sigma": 0.33,
    "ttft_inflate": 2.0, "ttft_sigma_widen": 0.60,   # median x (1 + 2 u^2), sigma + 0.6 u^2
    "cold_prefix_ms": 700, "cache_warmup_s": 30,     # cold prefix cache after traffic starts
    "crm_median_ms": 200, "crm_sigma": 0.45, "crm_knee_calls": 1950, "crm_power": 3,
    "stt_final_median_ms": 160, "stt_sigma": 0.40, "stt_inflate": 4.0, "stt_power": 6,
    "stt_wait_cap_ms": 250,          # orchestrator waits this long for the final, then uses the partial
    "detector_median_ms": 60, "detector_sigma": 0.5,
    "tts_ttfb_median_ms": 170, "tts_sigma": 0.30, "playout_ms": 50,
    "caller_speech_median_s": 5.2, "caller_sigma": 0.45,
    "agent_play_median_s": 12.0, "agent_sigma": 0.35,
    "amd_ms": 2380,                  # WG13/W13 example call
    "hello_prob": 0.6,               # caller says "hello?" once dead air passes 3 s
}

# Agent turns of one F01-style call: (turn type, CRM tool calls in sequence, state before it)
CALL_PLAN = [
    ("greeting", 0, "open"),           # scripted opener: no LLM request
    ("verification", 1, "default"),    # verify_identity
    ("amount-quote", 2, "default"),    # get_dues -> check_payment_status, sequential as in T04
    ("objection", 0, "default"),
    ("readback", 0, "amount-asked"),   # acts on the caller's amount: the amount turn
    ("tool", 2, "default"),            # record_promise_to_pay -> send_payment_link
    ("tool", 1, "default"),            # the disclosure SMS (WORLD["sms_tool"])
    ("closing", 0, "default"),
]
LLM_TURNS = sum(1 for t in CALL_PLAN if t[2] != "open")
AMOUNT_TURN = 4

# The plan. Stop conditions and gate thresholds are this recipe's choices; set your own.
PLAN = {
    "peak": VOL["peak_today"], "step_frac": 0.10, "max_mult": 1.5, "spike_mult": 3.0,
    "step_s": 300, "measure_last_s": 150, "hold_s": 600, "spike_s": 180, "settle_s": 300,
    "stop_p95_mult": 2.0,            # stop if P95 tool-turn gap > 2x SLO
    "stop_reject": 0.01,             # stop if more than 1% of connections are rejected (not in the spike)
    "stop_turn_fail": 0.005,         # stop if more than 0.5% of calls drop on exhausted retries
    "gate_amount_safe": 0.99,        # gate: amount-safe share at least 99%
    "gate_reject": 0.001,            # gate: rejected connections at most 0.1% at 1.0x and 1.5x
}
# The stack model and its seed are edition-neutral: both editions run the same synthetic
# stack, so the ramp, knee, gate, spike and burst lines match and only labels and money differ.
SEED = 20261120
HOP = WORLD["hop_ms"]


def lognorm(rng: random.Random, median: float, sigma: float) -> float:
    return median * math.exp(sigma * rng.gauss(0.0, 1.0))


def pctl(values: list[float], q: float) -> float:
    """Linear-interpolated percentile (numpy's default method)."""
    s = sorted(values)
    if not s:
        return float("nan")
    pos = (len(s) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cluster_boot_p95(by_call: list[list[float]], rng: random.Random, b: int = 200):
    """95% interval for P95, resampling whole calls (turns in one call share its load)."""
    n = len(by_call)
    stats = []
    for _ in range(b):
        pool: list[float] = []
        for i in rng.choices(range(n), k=n):
            pool.extend(by_call[i])
        stats.append(pctl(pool, 0.95))
    return pctl(stats, 0.025), pctl(stats, 0.975)


def llm_request_cost(cached: bool) -> float:
    """Edition prices, one LLM request: 25,000 input tokens and 500 output tokens per call."""
    inp = PRICES["input_tokens"] / LLM_TURNS
    out = PRICES["output_tokens"] / LLM_TURNS
    if cached:
        c = inp * (1 - PRICES["cached_share"]) * PRICES["per_m_input"] + \
            inp * PRICES["cached_share"] * PRICES["per_m_cached"]
    else:
        c = inp * PRICES["per_m_input"]
    return (c + out * PRICES["per_m_output"]) / 1e6


# ---- Discrete-event simulation ---------------------------------------------------
class Sim:
    """Open-loop arrivals (dials connect at a scheduled rate), one event heap, one clock in ms."""

    def __init__(self, phases: list[tuple[str, float, float]], seed: int, warm_at_ms: float = 0.0):
        self.rng = random.Random(seed)
        self.phases = phases          # (label, duration s, target concurrency)
        self.heap: list = []
        self.seq = 0
        self.active = 0               # admitted calls holding a trunk channel and an STT stream
        self.llm_inflight = 0
        self.warm_at = warm_at_ms     # traffic start for the prefix-cache warm-up
        self.calls: dict[int, dict] = {}
        self.rejected: list[float] = []
        self.attempts: list[float] = []
        self.samples: list[tuple[float, int]] = []

    def push(self, t: float, kind: str, data) -> None:
        self.seq += 1
        heapq.heappush(self.heap, (t, self.seq, kind, data))

    def schedule_arrivals(self) -> None:
        t = 0.0
        for _label, dur_s, conc in self.phases:
            end = t + dur_s * 1000
            rate = conc / VOL["connected_s"] / 1000          # Little's law: arrivals per ms
            if rate > 0:
                nxt = t + self.rng.expovariate(rate)
                while nxt < end:
                    self.push(nxt, "arrive", None)
                    nxt += self.rng.expovariate(rate)
            t = end
        self.end_ms = t
        for s in range(0, int(t // 1000) + 1):
            self.push(s * 1000.0, "sample", None)

    def cache_hit(self, t: float) -> bool:
        warm = min(1.0, max(0.0, (t - self.warm_at) / (GEN["cache_warmup_s"] * 1000)))
        return self.rng.random() < warm

    def run(self) -> "Sim":
        self.schedule_arrivals()
        while self.heap:
            t, _, kind, data = heapq.heappop(self.heap)
            getattr(self, "on_" + kind)(t, data)
        return self

    # events
    def on_sample(self, t, _):
        self.samples.append((t, self.active))

    def on_arrive(self, t, _):
        self.attempts.append(t)
        if self.active >= min(GEN["trunk_channels"], GEN["stt_streams"]):
            self.rejected.append(t)
            return
        self.active += 1
        cid = len(self.calls)
        self.calls[cid] = {"start": t, "turns": [], "dropped": None, "cost": 0.0,
                           "partial_amount": False, "dup": set(), "end": None}
        # scripted opener after AMD, then the caller answers
        play = GEN["amd_ms"] + lognorm(self.rng, GEN["tts_ttfb_median_ms"], GEN["tts_sigma"])
        play_end = t + play + 1000 * lognorm(self.rng, 6.0, 0.2)
        self.push(play_end + 1000 * lognorm(self.rng, GEN["caller_speech_median_s"],
                                            GEN["caller_sigma"]), "caller_end", (cid, 1))

    def on_caller_end(self, t, data):
        cid, ti = data
        call = self.calls[cid]
        _ttype, _ntools, state = CALL_PLAN[ti]
        budget = BUDGET_AMOUNT_MS if state == "amount-asked" else BUDGET_MS
        eot = budget + lognorm(self.rng, GEN["detector_median_ms"], GEN["detector_sigma"])
        u_stt = self.active / GEN["stt_streams"]
        stt = lognorm(self.rng, GEN["stt_final_median_ms"] *
                      (1 + GEN["stt_inflate"] * u_stt ** GEN["stt_power"]), GEN["stt_sigma"])
        wait = min(max(0.0, stt - eot), GEN["stt_wait_cap_ms"])
        if ti == AMOUNT_TURN and stt > eot + GEN["stt_wait_cap_ms"]:
            call["partial_amount"] = True          # the LLM acted on a partial transcript
        turn = {"ti": ti, "t0": t, "eot": eot, "retries": 0}
        self.push(t + eot + wait + HOP, "llm_request", (cid, turn))

    def on_llm_request(self, t, data):
        cid, turn = data
        call = self.calls[cid]
        if self.llm_inflight >= GEN["llm_concurrency"]:
            if turn["retries"] >= GEN["llm_retries"]:
                call["dropped"] = t
                self.end_call(t, cid)
                return
            back = GEN["llm_backoff_ms"] * 2 ** turn["retries"] * self.rng.uniform(0.5, 1.5)
            turn["retries"] += 1
            self.push(t + back, "llm_request", (cid, turn))
            return
        self.llm_inflight += 1
        u = self.llm_inflight / GEN["llm_concurrency"]
        ttype, ntools, _ = CALL_PLAN[turn["ti"]]
        tool = ntools > 0
        med = GEN["ttft_median_ms"]["tool" if tool else "nontool"] * (1 + GEN["ttft_inflate"] * u ** 2)
        cached = self.cache_hit(t)
        ttft = lognorm(self.rng, med, GEN["ttft_sigma"] + GEN["ttft_sigma_widen"] * u ** 2)
        if not cached:
            ttft += GEN["cold_prefix_ms"]
        call["cost"] += llm_request_cost(cached)
        first_token = t + ttft
        self.push(first_token + GEN["llm_gen_hold_ms"], "llm_release", None)
        # tools run in sequence; CRM latency rises with concurrent calls
        crm_med = GEN["crm_median_ms"] * (1 + (self.active / GEN["crm_knee_calls"]) ** GEN["crm_power"])
        tt = first_token
        crm = []
        for _ in range(ntools):
            d = lognorm(self.rng, crm_med, GEN["crm_sigma"])
            crm.append(d)
            tt += HOP + d
        tts = lognorm(self.rng, GEN["tts_ttfb_median_ms"], GEN["tts_sigma"])
        play_start = tt + HOP + tts + GEN["playout_ms"]
        gap = play_start - turn["t0"]
        turn.update(gap=gap, ttft=ttft, crm=crm, tool=tool, t_play=play_start)
        call["turns"].append(turn)
        if gap > HELLO_AFTER_MS and self.rng.random() < GEN["hello_prob"]:
            call["dup"].add(turn["ti"])            # "hello?" -> a second LLM request and reply
            call["cost"] += llm_request_cost(cached)
        play_end = play_start + 1000 * lognorm(self.rng, GEN["agent_play_median_s"], GEN["agent_sigma"])
        if turn["ti"] + 1 < len(CALL_PLAN):
            nxt = play_end + 1000 * lognorm(self.rng, GEN["caller_speech_median_s"], GEN["caller_sigma"])
            self.push(nxt, "caller_end", (cid, turn["ti"] + 1))
        else:
            self.push(play_end, "hangup", cid)

    def on_llm_release(self, t, _):
        self.llm_inflight -= 1

    def on_hangup(self, t, cid):
        self.end_call(t, cid)

    def end_call(self, t, cid):
        self.calls[cid]["end"] = t
        self.active -= 1


# ---- Measuring a window ----------------------------------------------------------
def anchor(call: dict) -> float:
    """Call-level metrics belong to the moment of the amount turn (or the drop)."""
    for tr in call["turns"]:
        if tr["ti"] == AMOUNT_TURN:
            return tr["t0"]
    return call["dropped"] if call["dropped"] is not None else call["start"]


def amount_safe(call: dict) -> bool:
    return (call["dropped"] is None and not call["partial_amount"]
            and not ({AMOUNT_TURN, AMOUNT_TURN + 1} & call["dup"]))


def completed(call: dict) -> bool:
    return call["dropped"] is None and amount_safe(call) and not call["dup"] and call["end"] is not None


def measure(sim: Sim, t0: float, t1: float, rng: random.Random, boot: int = 200) -> dict:
    tool_by_call, nontool, crm, ttft_tool = [], [], [], []
    for call in sim.calls.values():
        g = [tr["gap"] for tr in call["turns"] if tr["tool"] and t0 <= tr["t0"] < t1]
        if g:
            tool_by_call.append(g)
        for tr in call["turns"]:
            if t0 <= tr["t0"] < t1:
                if tr["tool"]:
                    crm.extend(tr["crm"])
                    ttft_tool.append(tr["ttft"])
                else:
                    nontool.append(tr["gap"])
    tool = [x for g in tool_by_call for x in g]
    anchored = [c for c in sim.calls.values() if t0 <= anchor(c) < t1]
    att = sum(1 for a in sim.attempts if t0 <= a < t1)
    rej = sum(1 for a in sim.rejected if t0 <= a < t1)
    done = [c for c in anchored if completed(c)]
    conc = [a for (t, a) in sim.samples if t0 <= t < t1]
    lo, hi = cluster_boot_p95(tool_by_call, rng, boot)
    return {
        "conc": sum(conc) / len(conc), "p95_tool": pctl(tool, 0.95), "ci": (lo, hi),
        "p95_nontool": pctl(nontool, 0.95), "crm_p95": pctl(crm, 0.95),
        "ttft_p95": pctl(ttft_tool, 0.95), "attempts": att, "rejected": rej,
        "reject_rate": rej / att if att else 0.0,
        "drop_rate": sum(1 for c in anchored if c["dropped"] is not None) / max(1, len(anchored)),
        "amount_safe": sum(1 for c in anchored if amount_safe(c)) / max(1, len(anchored)),
        "dup_rate": sum(1 for c in anchored if c["dup"]) / max(1, len(anchored)),
        "partial_amount": sum(1 for c in anchored if c["partial_amount"]) / max(1, len(anchored)),
        "dup_amount": sum(1 for c in anchored if {AMOUNT_TURN, AMOUNT_TURN + 1} & c["dup"])
        / max(1, len(anchored)),
        "cost_per_task": sum(c["cost"] for c in anchored) / max(1, len(done)),
        "n_calls": len(anchored), "n_tool_turns": len(tool),
    }


# ---- Step 1: the plan from the world constants -----------------------------------
def step1_plan() -> list[tuple[str, float, float]]:
    print(f"Part 1. The plan, from {WORLD['lender_short']}'s volumes and prices")
    w = VOL
    connects = w["dials_per_day"] * w["connect_rate"]
    call_s = connects * w["connected_s"] + (w["dials_per_day"] - connects) * w["attempt_s"]
    mean_conc = call_s / (w["day_hours"] * 3600)
    assert connects == 130000 and round(mean_conc) == WORLD["mean_conc"]   # [C]
    print(f"  mean concurrency over {WORLD['day_label']}: {mean_conc:.0f} calls; peak today {w['peak_today']:,}"
          f" ({w['peak_today'] / mean_conc:.1f}x the mean)")
    per_call = LLM_TURNS * llm_request_cost(True)
    assert abs(per_call - WORLD["per_call"]) < 1e-9              # WG20/W20 prices [C]
    sym, scale, dec = WORLD["money"]
    print(f"  agent LLM cost per connected call at {WORLD['price_ref']} prices (60% cached): {sym}{per_call * scale:.{dec}f}")
    peak = PLAN["peak"]
    steps = [round(peak * PLAN["step_frac"] * k) for k in range(1, round(PLAN["max_mult"] / PLAN["step_frac"]) + 1)]
    assert steps[0] == 240 and steps[9] == 2400 and steps[-1] == 3600 and len(steps) == 15
    spike = round(peak * PLAN["spike_mult"])
    assert spike == 7200
    phases = []
    for c in steps[:10]:
        phases.append((f"ramp {c / peak:.1f}x", PLAN["step_s"], c))
    phases.append(("hold 1.0x", PLAN["hold_s"], peak))
    for c in steps[10:]:
        phases.append((f"ramp {c / peak:.1f}x", PLAN["step_s"], c))
    phases.append(("settle 1.0x", PLAN["settle_s"], peak))
    phases.append(("spike 3.0x", PLAN["spike_s"], spike))
    phases.append(("recover 1.0x", PLAN["settle_s"], peak))
    total_s = sum(p[1] for p in phases)
    offered = sum(p[1] * p[2] / VOL["connected_s"] for p in phases)
    print(f"  ramp steps of {int(peak * PLAN['step_frac'])} calls: {steps[0]:,} .. {steps[-1]:,} "
          f"(1.5x of {peak:,}); hold {PLAN['hold_s'] // 60} min at {peak:,}; spike to {spike:,} (3x)")
    print(f"  {len(phases)} phases, {total_s / 60:.0f} minutes, about {offered:,.0f} call attempts")
    return phases


# ---- Step 2 and 3: run the ramp, read the table ---------------------------------
def step2_run(phases) -> tuple[Sim, list[dict]]:
    sim = Sim(phases, SEED).run()
    rng = random.Random(SEED + 1)
    rows, t = [], 0.0
    for label, dur, target in phases:
        t1 = t + dur * 1000
        if not label.startswith(("settle", "recover")):
            t0 = t if label.startswith("spike") else t1 - PLAN["measure_last_s"] * 1000
            if label.startswith("hold"):
                t0 = t + 150_000
            m = measure(sim, t0, t1, rng)
            m.update(label=label, target=target)
            rows.append(m)
        t = t1
    return sim, rows


def verdict(m: dict) -> str:
    if m["ci"][1] <= SLO_TOOL_GAP_MS:
        return "pass"
    if m["ci"][0] > SLO_TOOL_GAP_MS:
        return "BREACH"
    return "unclear"


def step3_table(rows: list[dict]) -> dict:
    print()
    print("Part 2. Ramp, hold and spike (P95 tool-turn gap SLO 2,600 ms; interval = call-clustered bootstrap)")
    head, tscale, tdec = WORLD["task_col"]
    print(f"  phase         target   conc  P95 tool gap [95% CI]    CRM P95  TTFT P95  reject  amount-safe  {head}  verdict")
    for m in rows:
        print(f"  {m['label']:<12} {m['target']:>6,} {m['conc']:>6,.0f}  {m['p95_tool']:>6,.0f} "
              f"[{m['ci'][0]:>6,.0f}, {m['ci'][1]:>6,.0f}]  {m['crm_p95']:>6,.0f}  {m['ttft_p95']:>8,.0f}"
              f"  {100 * m['reject_rate']:>5.1f}%  {100 * m['amount_safe']:>10.1f}%  {m['cost_per_task'] * tscale:>{len(head)}.{tdec}f}"
              f"  {verdict(m)}")
    ramp = [m for m in rows if m["label"].startswith("ramp")]
    base = ramp[0]
    # knee: the first step whose whole P95 interval sits above the tool-turn SLO
    knee = next(m for m in ramp if verdict(m) == "BREACH")
    prev = ramp[ramp.index(knee) - 1]
    crm_x = {m["target"]: m["crm_p95"] / base["crm_p95"] for m in ramp}
    ttft_x = {m["target"]: m["ttft_p95"] / base["ttft_p95"] for m in ramp}
    print()
    print(f"  knee: P95 tool-turn gap is flat to about 1,200 calls ({base['p95_tool']:,.0f} -> "
          f"{ramp[4]['p95_tool']:,.0f} ms), then leaves the SLO between {prev['target']:,} "
          f"({verdict(prev)}, {prev['p95_tool']:,.0f}) and {knee['target']:,} ({verdict(knee)}, "
          f"{knee['p95_tool']:,.0f})")
    print(f"  CRM P95 vs the {base['target']} step:  x{crm_x[1440]:.2f} at 1,440, x{crm_x[1680]:.2f} at 1,680, "
          f"x{crm_x[1920]:.2f} at 1,920, x{crm_x[2400]:.2f} at 2,400")
    print(f"  TTFT P95 vs the {base['target']} step: x{ttft_x[1440]:.2f} at 1,440, x{ttft_x[1680]:.2f} at 1,680, "
          f"x{ttft_x[1920]:.2f} at 1,920, x{ttft_x[2400]:.2f} at 2,400")
    for lbl in ("hold 1.0x", "ramp 1.2x", "ramp 1.5x"):
        m = next(r for r in rows if r["label"] == lbl)
        print(f"  why amounts go unsafe at {lbl:<9}: duplicate reply on the amount turns "
              f"{100 * m['dup_amount']:4.1f}% of calls, LLM acted on an STT partial {100 * m['partial_amount']:4.1f}%")
    hold = next(r for r in rows if r["label"] == "hold 1.0x")
    assert hold["partial_amount"] < 0.005 and hold["dup_amount"] > 0.10    # at peak: duplicates, not STT
    assert next(r for r in rows if r["label"] == "ramp 1.5x")["partial_amount"] > 0.01
    assert prev["target"] == 1680 and verdict(prev) == "pass"                 # knee near 1,800 [W19]
    assert knee["target"] == 1920
    assert crm_x[1680] < 2.0 <= crm_x[1920]                                  # CRM P95 doubles near 1,800 [W]
    assert ttft_x[2400] > ttft_x[1440] > 1.0                                 # the LLM tail widens with it
    assert base["p95_tool"] < SLO_TOOL_GAP_MS and verdict(base) == "pass"
    # frozen across editions (same stack, same seed): the knee and the hold
    assert (round(prev["p95_tool"]), round(knee["p95_tool"]), round(hold["p95_tool"])) == (2549, 2787, 3451)

    # W19: a load test at 50 concurrent calls never sees T04
    small = Sim([("50 calls", 600, 50)], SEED + 3).run()
    s = measure(small, 300_000, 600_000, random.Random(SEED + 4))
    print(f"  a 50-call test for 10 minutes: P95 tool gap {s['p95_tool']:,.0f} ms "
          f"[{s['ci'][0]:,.0f}, {s['ci'][1]:,.0f}] on {s['n_tool_turns']} tool turns: {verdict(s)}")
    assert verdict(s) == "pass"
    return {"knee": knee, "prev": prev}


def step4_stop_and_gate(rows: list[dict]) -> None:
    print()
    print("Part 3. Stop conditions and the load gate")
    stop = None
    for m in rows:
        if m["label"].startswith("spike"):
            continue
        reasons = []
        if m["p95_tool"] > PLAN["stop_p95_mult"] * SLO_TOOL_GAP_MS:
            reasons.append(f"P95 tool gap {m['p95_tool']:,.0f} > {PLAN['stop_p95_mult'] * SLO_TOOL_GAP_MS:,.0f}")
        if m["reject_rate"] > PLAN["stop_reject"]:
            reasons.append(f"rejections {100 * m['reject_rate']:.1f}% > 1%")
        if m["drop_rate"] > PLAN["stop_turn_fail"]:
            reasons.append(f"calls dropped on exhausted LLM retries {100 * m['drop_rate']:.2f}% > 0.5%")
        if reasons and stop is None:
            stop = (m, reasons)
    if stop:
        print(f"  a real run stops at '{stop[0]['label']}' ({stop[0]['target']:,} calls): " + "; ".join(stop[1]))
    else:
        print("  no stop condition fired on the ramp")
    for lbl in ("hold 1.0x", "ramp 1.5x"):
        m = next(r for r in rows if r["label"] == lbl)
        checks = {
            "P95 tool gap <= 2,600 (upper CI)": m["ci"][1] <= SLO_TOOL_GAP_MS,
            "amount-safe >= 99%": m["amount_safe"] >= PLAN["gate_amount_safe"],
            "rejections <= 0.1%": m["reject_rate"] <= PLAN["gate_reject"],
        }
        res = "PASS" if all(checks.values()) else "FAIL"
        bad = [k for k, v in checks.items() if not v]
        print(f"  gate at {lbl:<9} ({m['target']:,}): {res}" + (f"  failed: {', '.join(bad)}" if bad else ""))
    hold = next(r for r in rows if r["label"] == "hold 1.0x")
    assert verdict(hold) == "BREACH"          # T04 is a peak-load failure: today's stack fails at 1.0x

    spike = next(r for r in rows if r["label"].startswith("spike"))
    lo, hi = wilson(spike["rejected"], spike["attempts"])
    limit = min(GEN["trunk_channels"], GEN["stt_streams"])
    print(f"  spike to 7,200 for {PLAN['spike_s']} s: {spike['rejected']:,} of {spike['attempts']:,} connections "
          f"rejected ({100 * spike['reject_rate']:.1f}%, Wilson {100 * lo:.1f}-{100 * hi:.1f}%); "
          f"admitted calls capped at the {limit:,} STT streams")
    ramp15 = next(r for r in rows if r["label"] == "ramp 1.5x")
    assert spike["rejected"] > 0 and ramp15["rejected"] == 0
    assert (spike["rejected"], spike["attempts"]) == (3389, 8583)     # frozen across editions


# ---- Step 4: cold burst vs the sustained phase ------------------------------------
def step5_burst(rows: list[dict]) -> None:
    print()
    print("Part 4. A cold burst to 2,400 vs the sustained phase at 2,400")
    # 2,400 calls connect in 10 s from idle, with a cold prefix cache; measure the first 150 s
    burst_rate_conc = 2400 / 10 * VOL["connected_s"]          # concurrency-equivalent arrival rate
    sim = Sim([("burst", 10, burst_rate_conc), ("after", 290, 0)], SEED + 7).run()
    m = measure(sim, 0, 150_000, random.Random(SEED + 8))
    retries = sum(tr["retries"] for c in sim.calls.values() for tr in c["turns"])
    llm_req = sum(len(c["turns"]) for c in sim.calls.values())
    hold = next(r for r in rows if r["label"] == "hold 1.0x")
    print(f"  cold burst  : {len(sim.calls):,} calls, P95 tool gap {m['p95_tool']:,.0f} ms "
          f"[{m['ci'][0]:,.0f}, {m['ci'][1]:,.0f}], TTFT P95 {m['ttft_p95']:,.0f}, "
          f"{100 * retries / max(1, llm_req):.1f}% of LLM requests retried after a 429, "
          f"amount-safe {100 * m['amount_safe']:.1f}%")
    print(f"  sustained   : P95 tool gap {hold['p95_tool']:,.0f} ms [{hold['ci'][0]:,.0f}, {hold['ci'][1]:,.0f}], "
          f"TTFT P95 {hold['ttft_p95']:,.0f}, amount-safe {100 * hold['amount_safe']:.1f}%")
    print(f"  the burst reports {m['p95_tool'] - hold['p95_tool']:+,.0f} ms on P95: cold caches and "
          f"synchronised first turns, not the steady state a peak hour runs in")
    assert m["p95_tool"] > hold["p95_tool"]


def main() -> None:
    print(f"{WORLD['lender']}: load-test plan, {WORLD['dataset']}")
    print(f"{WORLD['note']} {WORLD['stack_note']}")
    print()
    phases = step1_plan()
    _sim, rows = step2_run(phases)
    step3_table(rows)
    step4_stop_and_gate(rows)
    step5_burst(rows)
    print()
    print("All assertions passed.")


if __name__ == "__main__":
    main()
