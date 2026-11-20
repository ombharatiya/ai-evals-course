"""Module 12 (voice-load-cost) solution: the load knee and the eval budget. Run: python3.11 solutions/m12_voice_load_cost.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
cm = C["cost_model"]
v.header(C, "Load and cost")

bands = [(0, 1500), (1500, 1800), (1800, 10**6)]
rows = []
for lo, hi in bands:
    gaps = []
    for c in calls:
        if not lo <= c["concurrency_at_start"] < hi:
            continue
        ts = c["timings_summary"]
        gaps += [g for g, tool in zip(ts["turn_gap_ms"], ts["stage_ms"]["tool"]) if tool > 0]
    label = f"{lo}-{hi - 1}" if hi < 10**6 else f">= {lo}"
    rows.append([label, len(gaps), round(v.percentile(gaps, 0.5)), round(v.percentile(gaps, 0.95))])
v.table(rows, ["concurrent calls at start", "tool turns", "P50 gap ms", "P95 gap ms"])
print("The tail grows above the knee near 1,800 concurrent calls; a 50-call load test never sees it.")
print()
vol = C["volumes"]
days, nightly, commit_days = vol["calling_days_per_month"], C["ci"]["nightly"]["runs_per_month"], C["ci"]["per_commit"]["working_days"]
judged = C["world_rates"]["judged_calls_per_day"]
lines = {
    "checks": vol["connected_calls_per_day"] * days * cm["deterministic_check_per_call"],
    "judges": judged * days * (2 * cm["text_judge_per_call_per_dimension"] + cm["blueprint_judge_per_call"]),
    "stt": vol["connected_calls_per_day"] * cm["stt_retranscription_share"] * days * cm["stt_retranscription_per_call"],
    "human_audit": C["world_rates"]["human_audits_per_week"] * cm["human_audit_per_call"] * 52 / 12,
    "nightly_simulation": C["ci"]["nightly"]["audio_scenarios"] * C["ci"]["nightly"]["k"] * nightly * cm["simulated_audio_call"],
    "per_commit_text": C["ci"]["per_commit"]["text_scenarios"] * C["ci"]["per_commit"]["k"] * C["ci"]["per_commit"]["commits_per_day"] * commit_days * cm["text_scenario_run"],
    "load_tests": C["ci"]["pre_release_load_tests_per_month"] * cm["load_test_per_run"],
}
rows = [[k, v.major(C, x), v.major(C, cm["baseline_lines"][k])] for k, x in lines.items()]
total = sum(lines.values())
rows.append(["total", v.major(C, total), v.major(C, cm["baseline_total"])])
v.table(rows, ["line", "recomputed", "world bible"])
cap = cm["monthly_cap_today"]
print(f"Monthly cap today {v.major(C, cap, 0)}: {'inside' if total <= cap else 'over'}")
f = cm["capstone_volume_factor"]
scaled = total + (f - 1) * (lines["checks"] + lines["judges"] + lines["stt"])
cap2 = cm["monthly_cap_capstone"]
print(f"At {f}x volume the plan costs {v.major(C, scaled)} against a cap of {v.major(C, cap2, 0)}: "
      f"{'inside' if scaled <= cap2 else 'over by ' + v.major(C, scaled - cap2)}")
