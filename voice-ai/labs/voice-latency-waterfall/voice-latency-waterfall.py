"""A latency waterfall from turn spans and recordings (aievals.co recipe R3).

Steelyard Credit is a fictional lender; its numbers are illustrative.
Dataset: steelyard-calls (synthetic, seed 20261121). Python 3.11, numpy only, no network.
--edition india switches to the India edition's fictional lender and data set
(its constants block sits between the INDIA EDITION markers below).

Run:
    python3.11 -m venv .venv && .venv/bin/pip install numpy==2.1.3
    .venv/bin/python voice-latency-waterfall.py                    # global edition
    .venv/bin/python voice-latency-waterfall.py --edition india    # India edition
"""
from __future__ import annotations

import argparse

import numpy as np

# ---- GLOBAL constants (copied from the world bible, world-global-v1.1) ---------
GLOBAL = {
    "lender": "Steelyard Credit, Inc. (fictional US lender)",
    "lender_short": "Steelyard",
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
TARAZU["lender_short"] = "Tarazu"
EDITIONS["india"] = TARAZU
# ---- INDIA EDITION END ----------------------------------------------------------

ARGS = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ARGS.add_argument("--edition", choices=list(EDITIONS), default="global",
                  help="which fictional world's data to use (default: global)")
WORLD = EDITIONS[ARGS.parse_args().edition]

SEED = WORLD["seed"]
HOP = WORLD["hop_ms"]
LEAD = list(WORLD["campaigns"])[0]          # first campaign in the block: AUTO-early-nov
LEAD_BOOK = WORLD["campaigns"][LEAD][0]     # its book: AUTO
MODEL_SEED = 2026  # Step 4 teaching model: one seed for both editions, so its [C] lines match
Z95 = 1.6448536269514722  # standard normal 95th percentile


# ---- SLOs (WG11), derived from the campaign's silence budget ----------------------
def budget_ms(campaign: str, state: str) -> int:
    _, default, entity_state = WORLD["campaigns"][campaign]
    return entity_state if state in ("amount-asked", "date-asked") else default


def slos(campaign: str, state: str, tool_turn: bool, budget: int | None = None) -> dict:
    b = budget_ms(campaign, state) if budget is None else budget
    return {
        "end_of_turn": b + 150, "stt_final": 300, "llm_ttft": 900 if tool_turn else 700,
        "tool_time": 600, "tts_ttfb": 250, "playout": 60,
        "turn_gap": b + (2200 if tool_turn else 1500), "filler_deadline": b + 800,
    }


# ---- span parser for the voice-trace/1.3 schema (WG13) --------------------------
def parse_turns(trace: dict) -> list[dict]:
    """Pair each agent turn with the caller turn before it and split the turn gap."""
    rows, caller = [], None
    for turn in trace["turns"]:
        if turn["speaker"] == "caller":
            caller = turn
            continue
        llm, tts, tools = turn["llm"], turn["tts"], turn.get("tool_calls", [])
        hops = llm["request_ms"] - caller["eot_commit_ms"]
        last_end = llm["first_token_ms"]
        for call in tools:
            hops += call["start_ms"] - last_end
            last_end = call["end_ms"]
        hops += tts["request_ms"] - last_end
        row = {
            "call_id": trace["call_id"], "campaign": trace["campaign"],
            "turn_type": turn["turn_type"], "state": turn.get("state", "default"),
            "n_tools": len(tools), "cache_hit": llm["cached_tokens"] > 0,
            "end_of_turn": caller["eot_commit_ms"] - caller["vad_end_ms"],
            "stt_final": (caller["stt_final"]["t_ms"] - caller["vad_end_ms"]
                          if "stt_final" in caller else None),
            "llm_ttft": llm["first_token_ms"] - llm["request_ms"],
            "tool_time": sum(c["end_ms"] - c["start_ms"] for c in tools),
            "tts_ttfb": tts["first_byte_ms"] - tts["request_ms"],
            "playout": turn["play_start_ms"] - tts["first_byte_ms"],
            "orchestration": hops, "n_hops": 2 + len(tools),
            "turn_gap": turn["play_start_ms"] - caller["vad_end_ms"],
        }
        stage_sum = sum(row[k] for k in ("end_of_turn", "llm_ttft", "tool_time",
                                         "tts_ttfb", "playout", "orchestration"))
        assert stage_sum == row["turn_gap"], (trace["call_id"], stage_sum, row["turn_gap"])
        rows.append(row)
    return rows


def waterfall(caller: dict, agent: dict) -> list[tuple[str, int, int]]:
    """Ordered (label, start, end) bars from caller speech end to agent audio at egress."""
    bars = [("end-of-turn delay", caller["vad_end_ms"], caller["eot_commit_ms"]),
            ("hop", caller["eot_commit_ms"], agent["llm"]["request_ms"]),
            ("LLM TTFT", agent["llm"]["request_ms"], agent["llm"]["first_token_ms"])]
    last = agent["llm"]["first_token_ms"]
    for call in agent.get("tool_calls", []):
        bars += [("hop", last, call["start_ms"]),
                 (f"tool {call['name']}", call["start_ms"], call["end_ms"])]
        last = call["end_ms"]
    bars += [("hop", last, agent["tts"]["request_ms"]),
             ("TTS TTFB", agent["tts"]["request_ms"], agent["tts"]["first_byte_ms"]),
             ("playout", agent["tts"]["first_byte_ms"], agent["play_start_ms"])]
    return bars


def duplicate_risk(trace: dict) -> list[tuple[int, int]]:
    """A caller eot_commit that lands while an agent reply is still pending (LAT.DUP)."""
    hits, pending_until = [], None
    for turn in trace["turns"]:
        if turn["speaker"] == "agent":
            pending_until = turn["play_start_ms"]
        elif pending_until is not None and turn["eot_commit_ms"] < pending_until:
            hits.append((turn["eot_commit_ms"], pending_until))
    return hits


# ---- T04 verbatim (WG16): two sequential tools, cold prefix, peak load -----------
# The spans are identical in both editions; only the campaign name differs.
T04 = {
    "call_id": "T04", "schema_version": "voice-trace/1.3", "campaign": LEAD,
    "started_on": "2026-11-13", "pipeline": "cascade", "silence_budget_ms": 300,
    "turns": [
        {"turn_id": 1, "speaker": "caller", "vad_end_ms": 40210, "vad_hangover_ms": 200,
         "eot_commit_ms": 40590},
        {"turn_id": 2, "speaker": "agent", "turn_type": "tool",
         "llm": {"request_ms": 40600, "first_token_ms": 41820, "cached_tokens": 0},
         "tool_calls": [{"name": "get_dues", "start_ms": 41830, "end_ms": 42690},
                        {"name": "check_payment_status", "start_ms": 42700, "end_ms": 43950}],
         "tts": {"request_ms": 43960, "first_byte_ms": 44150}, "play_start_ms": 44200},
        {"turn_id": 3, "speaker": "caller", "vad_start_ms": 43200, "eot_commit_ms": 43580},
    ],
}

# ---- synthetic generator: 300 calls, 8 agent turns each --------------------------
# Generator parameters (median, P95) in ms. Invented for this synthetic data set;
# they are not the lender's SLOs and not measurements of any vendor.
GEN = {
    "detector_wait": (55, 115),      # end-of-turn delay minus the silence budget
    "stt_final": (170, 280),
    "ttft_plain": (360, 540), "ttft_tool": (560, 940), "cache_miss_factor": 1.45,
    "tool_call": (430, 900),         # one CRM or payments call
    "tts_ttfb": (160, 230), "playout": (45, 57),
}
LAYOUT = [  # (turn_type, state of the caller turn before it, is tool turn)
    ("greeting", "default", False), ("verification", "default", False),
    ("tool", "default", True), ("amount-quote", "default", False),
    ("objection", "default", False), ("readback", "date-asked", False),
    ("tool", "default", True), ("closing", "default", False),
]
# calls per campaign, in the campaign order of the edition's constants block
CALLS = dict(zip(WORLD["campaigns"], (120, 60, 45, 45, 30)))
CACHE_MISS = 0.30


def draw(z: float, p50: float, p95: float) -> int:
    return int(round(p50 * np.exp(z * np.log(p95 / p50) / Z95)))


def make_traces(rng: np.random.Generator, shared_load_rho: float = 0.0) -> list[dict]:
    """shared_load_rho > 0 ties the LLM and CRM tails together on each tool turn (T04)."""
    traces = []
    for campaign, n in CALLS.items():
        for i in range(n):
            t, turns = 2000, []
            for k, (ttype, state, is_tool) in enumerate(LAYOUT):
                start = t + int(rng.integers(300, 900))
                end = start + int(rng.integers(700, 2200))
                eot = end + budget_ms(campaign, state) + draw(rng.normal(), *GEN["detector_wait"])
                turns.append({"turn_id": 2 * k + 1, "speaker": "caller", "state": state,
                              "vad_start_ms": start, "vad_end_ms": end, "vad_hangover_ms": 200,
                              "stt_final": {"t_ms": end + draw(rng.normal(), *GEN["stt_final"])},
                              "eot_commit_ms": eot})
                load = rng.normal()
                own = lambda: rng.normal()  # noqa: E731
                mix = lambda: shared_load_rho * load + np.sqrt(1 - shared_load_rho**2) * own()  # noqa: E731
                hit = rng.random() >= CACHE_MISS
                req = eot + HOP
                ttft = draw(mix() if is_tool else own(),
                            *(GEN["ttft_tool"] if is_tool else GEN["ttft_plain"]))
                if not hit:
                    ttft = int(round(ttft * GEN["cache_miss_factor"]))
                cursor, tool_calls = req + ttft, []
                for name in (["get_dues", "check_payment_status"] if k == 2 else
                             ["record_promise_to_pay", "send_payment_link"])[: int(rng.integers(1, 3)) if is_tool else 0]:
                    s = cursor + HOP
                    e = s + draw(mix(), *GEN["tool_call"])
                    tool_calls.append({"name": name, "start_ms": s, "end_ms": e})
                    cursor = e
                tts_req = cursor + HOP
                fb = tts_req + draw(own(), *GEN["tts_ttfb"])
                play = fb + draw(own(), *GEN["playout"])
                turns.append({"turn_id": 2 * k + 2, "speaker": "agent", "turn_type": ttype,
                              "state": state,
                              "llm": {"request_ms": req, "first_token_ms": req + ttft,
                                      "cached_tokens": 1840 if hit else 0},
                              "tool_calls": tool_calls,
                              "tts": {"request_ms": tts_req, "first_byte_ms": fb},
                              "play_start_ms": play})
                t = play + int(rng.integers(1200, 3200))
            traces.append({"call_id": f"{campaign}-{i:03d}", "campaign": campaign,
                           "schema_version": "voice-trace/1.3", "pipeline": "cascade",
                           "turns": turns})
    return traces


# ---- percentiles with a call-clustered bootstrap --------------------------------
def by_call(rows: list[dict], key: str, keep) -> list[np.ndarray]:
    calls: dict[str, list[int]] = {}
    for r in rows:
        if keep(r):
            calls.setdefault(r["call_id"], []).append(r[key])
    return [np.array(v) for v in calls.values()]


def clustered_ci(groups: list[np.ndarray], q: float, rng, b: int = 1000) -> tuple[float, float, float]:
    pooled = np.concatenate(groups)
    stats = np.empty(b)
    for j in range(b):
        pick = rng.integers(0, len(groups), len(groups))
        stats[j] = np.percentile(np.concatenate([groups[i] for i in pick]), q)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return float(np.percentile(pooled, q)), float(lo), float(hi)


def verdict(lo: float, hi: float, slo: float) -> str:
    return "BREACH" if lo > slo else ("pass" if hi <= slo else "unclear")


# ---- recordings: dual-channel tones and noise bursts at 8 kHz -------------------
SR, FRAME = 8000, 80  # 10 ms analysis frames


def energy_vad(x: np.ndarray, thr_db: float = -30.0, bridge_ms: int = 150) -> list[tuple[int, int]]:
    n = len(x) // FRAME
    rms = np.sqrt(np.mean(x[: n * FRAME].reshape(n, FRAME) ** 2, axis=1) + 1e-12)
    active = 20 * np.log10(rms) > thr_db
    segs, start = [], None
    for i, a in enumerate(active):
        if a and start is None:
            start = i
        if not a and start is not None:
            segs.append([start * 10, i * 10])
            start = None
    if start is not None:
        segs.append([start * 10, n * 10])
    merged = []
    for s in segs:
        if merged and s[0] - merged[-1][1] < bridge_ms:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [(s, e) for s, e in merged if e - s >= 100]


def render_call(trace: dict, truth: dict, rng) -> tuple[np.ndarray, np.ndarray]:
    """Carrier-side stereo recording. rec_ms = t_ms + offset; caller audio is heard at the
    carrier leg_in ms before agent ingress, agent audio leg_out ms after media egress."""
    off, lin, lout = truth["offset"], truth["leg_in"], truth["leg_out"]
    last = trace["turns"][-1]["play_start_ms"] + 4000 + off + lout
    caller = rng.normal(0, 0.003, last * SR // 1000)
    agent = rng.normal(0, 0.003, last * SR // 1000)
    t = np.arange(len(agent)) / SR

    def put(ch, s_ms, e_ms, kind):
        a, b = s_ms * SR // 1000, e_ms * SR // 1000
        if kind == "noise":
            ch[a:b] += rng.normal(0, 0.25, b - a)
        else:
            ch[a:b] += 0.3 * np.sin(2 * np.pi * 440 * t[a:b]) + 0.2 * np.sin(2 * np.pi * 1210 * t[a:b])

    for seg in truth["caller_segments"]:  # true speech at agent ingress
        put(caller, seg[0] - lin + off, seg[1] - lin + off, "noise")
    for p, dur in truth["agent_plays"]:
        put(agent, p + lout + off, p + lout + off + dur, "tone")
    return caller, agent


def make_recorded_calls(rng, n_calls: int = 50) -> list[tuple[dict, dict]]:
    """Lead-campaign calls from a pipeline variant that writes vad_end_ms WITHOUT back-dating."""
    out = []
    for i in range(n_calls):
        truth = {"offset": WORLD["carrier_offset_ms"], "leg_in": int(rng.integers(72, 89)),
                 "leg_out": int(rng.integers(92, 109)), "hangover": 200,
                 "caller_segments": [], "agent_plays": [], "talk_over": []}
        t, turns = 1500, []
        for k, (ttype, state, is_tool) in enumerate(LAYOUT):
            start = t + int(rng.integers(300, 900))
            end = start + int(rng.integers(700, 2200))
            gap = budget_ms(LEAD, state) + 600 + int(rng.integers(0, 900 if is_tool else 500))
            play = end + gap
            truth["caller_segments"].append((start, end))
            if rng.random() < 0.08:  # early jump-in: caller paused 720 ms and resumed
                resume = end + 720  # the turn was already committed, as in T05
                truth["caller_segments"].append((resume, play + int(rng.integers(400, 900))))
                truth["talk_over"].append(k)
            dur = int(rng.integers(1200, 3000))
            truth["agent_plays"].append((play, dur))
            turns.append({"speaker": "caller", "vad_start_ms": start,
                          "vad_end_ms": end + truth["hangover"],  # not back-dated
                          "vad_hangover_ms": truth["hangover"]})
            turns.append({"speaker": "agent", "turn_type": ttype, "play_start_ms": play})
            t = max(play + dur, truth["caller_segments"][-1][1]) + int(rng.integers(300, 900))
        out.append(({"call_id": f"REC-{i:02d}", "turns": turns}, truth))
    return out


def reconcile(trace: dict, caller_segs, agent_segs) -> dict:
    vad_starts = [x["vad_start_ms"] for x in trace["turns"] if x["speaker"] == "caller"]
    vad_ends = [x["vad_end_ms"] for x in trace["turns"] if x["speaker"] == "caller"]
    plays = [x["play_start_ms"] for x in trace["turns"] if x["speaker"] == "agent"]
    assert len(agent_segs) == len(plays), (trace["call_id"], len(agent_segs), len(plays))
    a = float(np.median([seg[0] - p for seg, p in zip(agent_segs, plays)]))  # offset + leg_out
    onsets = np.array([s for s, _ in caller_segs])
    b = float(np.median([v - onsets[np.argmin(np.abs(onsets - (v + a)))] for v in vad_starts]))
    gaps_rec, gaps_span = [], []
    for (ao, _), p, ve in zip(agent_segs, plays, vad_ends):
        before = [seg for seg in caller_segs if seg[0] < ao]
        gaps_rec.append(ao - before[-1][1])  # negative: caller still talking at agent onset
        gaps_span.append(p - ve)
    return {"offset": (a - b) / 2, "round_trip": a + b,
            "rec": np.array(gaps_rec), "span": np.array(gaps_span)}


def main() -> None:
    rng = np.random.default_rng(SEED)
    print(f"{WORLD['dataset']}; {WORLD['lender']}; numbers are illustrative.\n")

    # Step 1: the T04 waterfall
    row = parse_turns(T04)[0]
    print(f"Step 1. T04 waterfall ({LEAD}, 2026-11-13, budget then 300 ms)")
    for name, start, end in waterfall(T04["turns"][0], T04["turns"][1]):
        ms = end - start
        print(f"  {name:<26}{start:>6} -> {end:<6}{ms:>5} ms  {'#' * max(1, round(ms / 50))}")
    stages = row["turn_gap"] - row["orchestration"]
    print(f"  turn gap {row['turn_gap']} ms = {stages} ms of stages + "
          f"{row['n_hops']} hops x {HOP} ms")
    s = slos(LEAD, "default", True, budget=T04["silence_budget_ms"])
    for k in ("end_of_turn", "llm_ttft", "tool_time", "tts_ttfb", "playout", "turn_gap"):
        print(f"  {k:<14}{row[k]:>6} ms  SLO {s[k]:>5}  {'over' if row[k] > s[k] else 'ok'}")
    print(f"  filler deadline {s['filler_deadline']} ms; no filler played")
    for commit, pending in duplicate_risk(T04):
        print(f"  LAT.DUP: caller eot_commit at {commit} while the reply was pending until {pending}")
    assert row["turn_gap"] == 3990 and stages == 3950 and row["orchestration"] == 40
    assert row["n_hops"] == 4 and duplicate_risk(T04) == [(43580, 44200)]

    # Step 2: synthetic spans, per-stage P95 against the SLO table
    traces = make_traces(rng)
    rows = [r for tr in traces for r in parse_turns(tr)]
    print(f"\nStep 2. Parsed {len(traces)} calls, {len(rows)} agent turns; every turn's stages "
          f"plus hops equal its turn gap")
    lead_rows = [r for r in rows if r["campaign"] == LEAD]
    print(f"  {LEAD} per-stage P95, call-clustered 95% CI (1,000 resamples)")
    print(f"  {'stage':<13}{'turns':<15}{'n':>4}{'P50':>6}{'P95':>6}{'  95% CI':<14}{'P99':>6}{'SLO':>6}")
    stage_checks = [
        ("end_of_turn", "default", lambda r: r["state"] == "default", False),
        ("end_of_turn", "date-asked", lambda r: r["state"] == "date-asked", False),
        ("stt_final", "all", lambda r: r["stt_final"] is not None, False),
        ("llm_ttft", "non-tool", lambda r: r["n_tools"] == 0, False),
        ("llm_ttft", "tool", lambda r: r["n_tools"] > 0, True),
        ("tool_time", "1 call", lambda r: r["n_tools"] == 1, True),
        ("tool_time", "2 sequential", lambda r: r["n_tools"] == 2, True),
        ("tts_ttfb", "all", lambda r: True, False),
        ("playout", "all", lambda r: True, False),
    ]
    results = {}
    for key, label, keep, is_tool in stage_checks:
        groups = by_call(lead_rows, key, keep)
        p50 = float(np.percentile(np.concatenate(groups), 50))
        p95, lo, hi = clustered_ci(groups, 95, rng)
        p99 = float(np.percentile(np.concatenate(groups), 99))
        slo = slos(LEAD, "date-asked" if label == "date-asked" else "default", is_tool)[key]
        results[(key, label)] = verdict(lo, hi, slo)
        n = sum(len(g) for g in groups)
        print(f"  {key:<13}{label:<15}{n:>4}{p50:>6.0f}{p95:>6.0f}  [{lo:>4.0f}, {hi:>4.0f}]"
              f"{p99:>7.0f}{slo:>6}  {results[(key, label)]}")
    assert results[("tool_time", "2 sequential")] == "BREACH"
    assert results[("end_of_turn", "default")] == "pass"

    # Step 3: platform turn gap by turn type at the lead campaign's 400 ms budget
    print(f"\nStep 3. {LEAD} platform turn gap by turn type (budget 400 ms, 600 ms when "
          "an amount or date was asked)")
    print(f"  {'turn type':<14}{'n':>4}{'P50':>6}{'P95':>6}{'  95% CI':<14}{'SLO':>6}")
    gap_verdicts = {}
    for ttype in ["greeting", "verification", "amount-quote", "objection", "readback",
                  "closing", "non-tool (all)", "tool"]:
        keep = (lambda r: r["n_tools"] == 0) if ttype == "non-tool (all)" else \
            (lambda r, tt=ttype: r["turn_type"] == tt)
        groups = by_call(lead_rows, "turn_gap", keep)
        p95, lo, hi = clustered_ci(groups, 95, rng)
        state = "date-asked" if ttype == "readback" else "default"
        slo = slos(LEAD, state, ttype == "tool")["turn_gap"]
        if ttype == "non-tool (all)":  # each turn against its own budget's SLO
            for r in lead_rows:
                r["over_slo"] = r["turn_gap"] - slos(LEAD, r["state"], False)["turn_gap"]
            worst, lo, hi = clustered_ci(by_call(lead_rows, "over_slo", keep), 95, rng)
            gap_verdicts[ttype] = verdict(lo, hi, 0)
            print(f"  {ttype:<14}{sum(1 for r in lead_rows if keep(r)):>4}  P95 of gap minus own SLO "
                  f"{worst:.0f} [{lo:.0f}, {hi:.0f}]  {gap_verdicts[ttype]}")
            continue
        gap_verdicts[ttype] = verdict(lo, hi, slo)
        p50 = float(np.percentile(np.concatenate(groups), 50))
        n = sum(len(g) for g in groups)
        print(f"  {ttype:<14}{n:>4}{p50:>6.0f}{p95:>6.0f}  [{lo:>4.0f}, {hi:>4.0f}]{slo:>6}  "
              f"{gap_verdicts[ttype]}")
    late = sum(1 for r in lead_rows if r["n_tools"] and r["turn_gap"] > slos(LEAD, "default", True)["filler_deadline"])
    n_tool = sum(1 for r in lead_rows if r["n_tools"])
    print(f"  tool turns past the 1,200 ms filler deadline: {late} of {n_tool}")
    assert gap_verdicts["tool"] == "BREACH"
    assert all(v == "pass" for k, v in gap_verdicts.items() if k != "tool")

    print("\n  Tool-turn P95 by campaign (SLO = budget + 2,200 ms)")
    for campaign in CALLS:
        groups = by_call([r for r in rows if r["campaign"] == campaign], "turn_gap",
                         lambda r: r["n_tools"] > 0)
        p95, lo, hi = clustered_ci(groups, 95, rng)
        slo = slos(campaign, "default", True)["turn_gap"]
        print(f"  {campaign:<16}{p95:>6.0f}  [{lo:>4.0f}, {hi:>4.0f}]  SLO {slo}  {verdict(lo, hi, slo)}")

    # Step 4: why stage P95s do not add up
    print("\nStep 4. Sum of stage P95s vs P95 of the total")
    n = 400_000
    model = [(450, 800), (566, 2246), (250, 450)]  # generic teaching model, WG17
    model_rng = np.random.default_rng(MODEL_SEED)
    for label, rho in (("independent", 0.0), ("correlated 0.8", 0.8), ("comonotone", 1.0)):
        common = model_rng.normal(size=n)
        zs = [rho * common + np.sqrt(1 - rho**2) * model_rng.normal(size=n) for _ in model]
        total = sum(p50 * np.exp(z * np.log(p95 / p50) / Z95) for z, (p50, p95) in zip(zs, model))
        p50t, p95t = np.percentile(total, [50, 95])
        print(f"  teaching model, {label:<15} total P50 {p50t:>5.0f}  P95 {p95t:>5.0f}  "
              f"sum of P95s {sum(p for _, p in model)}")
        if rho == 0.0:
            assert abs(p50t - 1340) < 25 and abs(p95t - 3000) < 60
        if rho == 1.0:
            assert abs(p95t - 3496) < 15
    gaps = {}
    for label, rho in (("independent", 0.0), ("shared load", 0.9)):
        t_rows = [r for rep in range(1, 9) for tr in make_traces(np.random.default_rng(SEED + rep), rho)
                  for r in parse_turns(tr) if r["n_tools"] == 2]
        parts = ["end_of_turn", "orchestration", "llm_ttft", "tool_time", "tts_ttfb", "playout"]
        sum95 = sum(np.percentile([r[k] for r in t_rows], 95) for k in parts)
        tot95 = np.percentile([r["turn_gap"] for r in t_rows], 95)
        gaps[label] = sum95 - tot95
        print(f"  {WORLD['lender_short']} two-tool turns, {label:<12} sum of stage P95s {sum95:>5.0f}  "
              f"P95 of turn gap {tot95:>5.0f}  gap {sum95 - tot95:>4.0f}")
    assert gaps["independent"] > gaps["shared load"] > 0

    # Step 5: what the caller heard, from the stereo recording
    print(f"\nStep 5. 50 recorded {LEAD_BOOK} calls (spans written without back-dating vad_end_ms)")
    rec_rng = np.random.default_rng(SEED + 2)
    offs, rts, d_all, rec_all, span_all, overs, flagged, injected = [], [], [], [], [], 0, 0, []
    for trace, truth in make_recorded_calls(rec_rng):
        caller, agent = render_call(trace, truth, rec_rng)
        res = reconcile(trace, energy_vad(caller), energy_vad(agent))
        offs.append(res["offset"])
        rts.append(res["round_trip"])
        clean = np.array([k not in truth["talk_over"] for k in range(len(LAYOUT))])
        d_all.extend((res["rec"] - res["span"])[clean])
        rec_all.extend(res["rec"])
        span_all.extend(res["span"])
        overs += len(truth["talk_over"])
        injected.append(truth["hangover"] + truth["leg_in"] + truth["leg_out"])
        flagged += int(np.sum(res["rec"] < 0))
        assert set(np.flatnonzero(res["rec"] < 0)) == set(truth["talk_over"])
    off_hat, rt_hat, under = float(np.median(offs)), float(np.median(rts)), float(np.median(d_all))
    print(f"  recovered carrier offset {off_hat:.0f} ms (injected 212; per-call "
          f"{min(offs):.0f} to {max(offs):.0f})")
    print(f"  recovered carrier round trip {rt_hat:.0f} ms")
    rec_all, span_all = np.array(rec_all), np.array(span_all)
    print(f"  turn gap from spans:     P50 {np.percentile(span_all, 50):>5.0f}  "
          f"P95 {np.percentile(span_all, 95):>5.0f}  min {span_all.min():>5.0f}")
    print(f"  caller-heard (recording): P50 {np.percentile(rec_all, 50):>5.0f}  "
          f"P95 {np.percentile(rec_all, 95):>5.0f}  min {rec_all.min():>5.0f}")
    print(f"  spans understate the caller-heard gap by {under:.0f} ms (median, clean turns)")
    print(f"  minus the round trip leaves {under - rt_hat:.0f} ms: the VAD hangover the "
          f"pipeline never subtracted")
    print(f"  negative caller-heard gaps (agent started over the caller): {flagged} of "
          f"{len(rec_all)}, {int(np.sum(rec_all < -300))} of them past the 300 ms talk-over line; "
          f"the spans show every one as a positive gap")
    assert abs(off_hat - WORLD["carrier_offset_ms"]) <= 20
    assert all(abs(o - WORLD["carrier_offset_ms"]) <= 20 for o in offs)
    assert abs(under - float(np.median(injected))) <= 20
    assert abs((under - rt_hat) - 200) <= 20 and flagged == overs and span_all.min() > 0


if __name__ == "__main__":
    main()
