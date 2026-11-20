"""Module 7 (speech-output-tts) solution: test what the borrower hears. Run: python3.11 solutions/m07_speech_output_tts.py [--edition india]"""
import vacourse as v

ed = v.edition_arg(__doc__)
C = v.constants(ed)
calls = v.calls(ed)
v.header(C, "Speech output: spoken entities and the acceptance gate")

print("Exact one-sided 95% upper bound on the error rate after k errors in n spoken lines:")
for k, n in ((0, 400), (1, 400), (0, 100), (2, 1000)):
    print(f"  {k} of {n}: {v.cp_upper(k, n):.4f}")
print()
lines = errors = 0
examples = []
for c in calls:
    caller_amount = None
    for t in c["turns"]:
        if t["speaker"] == "caller":
            for e in t["ref_entities"]:
                if e["type"] == "amount":
                    caller_amount = e["value"]
        elif t.get("tts") and ({"readback", "inform_ptp"} & set(t["acts"])):
            spoken = [e for e in t["tts"]["entities"] if e["type"] == "amount"]
            if spoken and caller_amount is not None:
                lines += 1
                if spoken[0]["value"] != caller_amount:
                    errors += 1
                    examples.append((c["call_id"], t["turn_id"], caller_amount, spoken[0]["value"]))
print(f"Read-back lines in the simulated calls: {lines}; amount differs from what the caller said: {errors}")
for cid, tid, said, spoken in examples[:3]:
    print(f"  {cid} turn {tid}: caller said {v.money(C, said)}, agent read back {v.money(C, spoken)}")
print(f"Upper bound on the read-back amount error rate: {v.cp_upper(errors, lines):.4f}")
print()
dues_ok = dues_n = 0
for c in calls:
    dues = [tc["result"][C["fields"]["past_due"]] for t in c["turns"] for tc in t.get("tool_calls", []) if tc["name"] == "get_dues"]
    for t in c["turns"]:
        if t.get("tts") and "inform_dues" in t["acts"] and dues:
            for e in t["tts"]["entities"]:
                if e["type"] == "amount":
                    dues_n += 1
                    dues_ok += e["value"] == dues[0]
print(f"C13 (amount stated equals get_dues): {dues_ok} of {dues_n} dues statements match")
print()
t06 = v.traces(ed)["T06"]
turn = next(t for t in t06["turns"] if t["speaker"] == "agent" and t.get("tts") and t["tts"].get("audio_reading"))
print("T06: the text was right and the audio was wrong")
print(f"  TTS input text : {turn['tts']['text']}")
print(f"  audio reading  : {turn['tts']['audio_reading']}")
ptp = [tc for t in t06["turns"] for tc in t.get("tool_calls", []) if tc["name"] == "record_promise_to_pay"][0]
heard = [e["value"] for t in t06["turns"] if t["speaker"] == "caller" for e in t["ref_entities"] if e["type"] == "date"]
print(f"  stored ptp_date {ptp['args_redacted']['ptp_date']}; the date the borrower heard {heard[-1]}")
