"""Module 5 (voice-latency-slos) solution: turn gaps, stage P95s and SLOs. Run: python3.11 solutions/m05_voice_latency_slos.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
slo = C["slo"]
v.header(C, "Voice latency: turn gap by turn type")

seg = {"tool": [], "non-tool": []}
stages = {"tool": {k: [] for k in ("eot_delay", "llm_ttft", "tool", "tts_ttfb", "playout")},
          "non-tool": {k: [] for k in ("eot_delay", "llm_ttft", "tool", "tts_ttfb", "playout")}}
breach = {"tool": 0, "non-tool": 0}
for c in calls:
    ts = c["timings_summary"]
    budget = c["silence_budget_ms"]["default"]
    byid = {t["turn_id"]: t for t in c["turns"]}
    for i, tid in enumerate(ts["agent_turn_ids"]):
        turn = byid[tid]
        if turn["llm"] is None or turn["llm"].get("speculative"):
            continue
        kind = "tool" if ts["stage_ms"]["tool"][i] > 0 else "non-tool"
        gap = ts["turn_gap_ms"][i]
        seg[kind].append(gap)
        for k in stages[kind]:
            stages[kind][k].append(ts["stage_ms"][k][i])
        if gap > budget + slo["turn_gap_add_ms"]["tool" if kind == "tool" else "non_tool"]:
            breach[kind] += 1
rows = []
for kind, gaps in seg.items():
    rows.append([kind, len(gaps), round(v.percentile(gaps, 0.5)), round(v.percentile(gaps, 0.95)), round(v.percentile(gaps, 0.99)),
                 f"{breach[kind]} ({v.pct(breach[kind] / len(gaps))})"])
v.table(rows, ["turns", "n", "P50 ms", "P95 ms", "P99 ms", "over the SLO (budget + 1,500 / + 2,200 ms)"])
print()
for kind in ("tool", "non-tool"):
    p95s = {k: v.percentile(vals, 0.95) for k, vals in stages[kind].items()}
    hops = 10 * ((4 if kind == "tool" else 2))
    total = v.percentile(seg[kind], 0.95)
    print(f"{kind} turns: sum of stage P95s {round(sum(p95s.values()))} ms (+{hops} ms of hops) vs P95 of the turn gap {round(total)} ms")
print("Percentiles do not add: budget the total from spans, then allocate it to stages.")
print()
t04 = v.traces(ed)["T04"]
byid = {t["turn_id"]: t for t in t04["turns"]}
ts = t04["timings_summary"]
i = max(range(len(ts["turn_gap_ms"])), key=lambda j: ts["turn_gap_ms"][j])
turn = byid[ts["agent_turn_ids"][i]]
caller = byid[turn["responds_to"]]
parts = [("end-of-turn delay", caller["eot_commit_ms"] - caller["vad_end_ms"]),
         ("hop", turn["llm"]["request_ms"] - caller["eot_commit_ms"]),
         ("LLM TTFT", turn["llm"]["first_token_ms"] - turn["llm"]["request_ms"])]
cursor = turn["llm"]["first_token_ms"]
for tc in turn["tool_calls"]:
    parts.append(("hop", tc["start_ms"] - cursor))
    parts.append((f"tool {tc['name']}", tc["end_ms"] - tc["start_ms"]))
    cursor = tc["end_ms"]
parts += [("hop", turn["tts"]["request_ms"] - cursor), ("TTS TTFB", turn["tts"]["first_byte_ms"] - turn["tts"]["request_ms"]),
          ("playout", turn["play_start_ms"] - turn["tts"]["first_byte_ms"])]
print("T04 waterfall (the slowest turn):")
for name, ms in parts:
    print(f"  {name:<28} {ms:>5} ms")
stage = sum(ms for name, ms in parts if name != "hop")
hops = sum(ms for name, ms in parts if name == "hop")
print(f"  stages {stage} ms + hops {hops} ms = turn gap {stage + hops} ms (recorded {ts['turn_gap_ms'][i]} ms)")
