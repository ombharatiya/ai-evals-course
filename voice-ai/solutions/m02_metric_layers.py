"""Module 2 (voice-metric-layers) solution: a funnel with named denominators. Run: python3.11 solutions/m02_metric_layers.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
rows = v.jsonl(ed, "production_sample")
v.header(C, "Funnel metrics with named denominators")

dials = len(rows)
connects = [r for r in rows if r["connected"]]
human_true = [r for r in connects if r["human_answer"]]
human_pred = [r for r in connects if r["amd_pred"] == "human"]
rpc = [r for r in rows if r["rpc"]]
ptp = [r for r in rows if r["ptp"]]
verified = [r for r in ptp if r["ptp_verified"]]
kept = [r for r in ptp if r["kept"]]
print(f"Production sample: {dials} dial attempts on {rows[0]['call_date']}")
v.table([["dials", dials, ""], ["connects (answered by anything)", len(connects), v.pct(len(connects) / dials)],
         ["human answers (true)", len(human_true), v.pct(len(human_true) / len(connects)) + " of connects"],
         ["right-party contacts", len(rpc), v.pct(len(rpc) / len(human_true)) + " of human answers"],
         ["promises to pay", len(ptp), v.pct(len(ptp) / len(rpc)) + " of RPC"],
         ["verified PTP", len(verified), v.pct(len(verified) / len(ptp)) + " of PTP"],
         ["kept PTP", len(kept), v.pct(len(kept) / len(ptp)) + " of PTP (kept rate)"]],
        ["stage", "count", "rate"])
print()
print("The same promises over four denominators:")
for name, den in (("per dial", dials), ("per connect", len(connects)), ("per human answer", len(human_true)), ("per RPC", len(rpc))):
    print(f"  PTP {name:<17} {len(ptp) / den:.4f}")
print(f"  kept PTP per dial      {len(kept) / dials:.4f}")
print()
fh = [r for r in connects if r["amd_pred"] == "human" and not r["human_answer"]]
fm = [r for r in connects if r["human_answer"] and r["amd_pred"] != "human"]
print(f"AMD said human on {len(human_pred)} connects; {len(fh)} were machines (false human), "
      f"{len(fm)} humans were labelled machine (false machine).")
print(f"  trunk seconds spent on false humans at 21 s each: {21 * len(fh)}")
print(f"  PTP per AMD-human connect: {len(ptp) / len(human_pred):.4f} vs PTP per true human answer: {len(ptp) / len(human_true):.4f}")
print("  PTP per RPC does not move when only the AMD error rate changes; PTP per connect does.")
