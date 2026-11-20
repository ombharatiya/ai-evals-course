# Module 5: Measuring voice agent latency

Measure the turn gap by turn type, test it against the SLOs, and show that stage P95s do not add up to the P95 of the turn.

## Data

- `data/<edition>/calls.jsonl` (`timings_summary`, `silence_budget_ms`)
- `data/<edition>/traces/T04.json`
- `world/<edition>/constants.json` (`slo`)

## Tasks

1. Split agent turns into tool turns and non-tool turns (a turn is a tool turn when its tool time before TTS is above zero). Skip turns whose `llm.speculative` is true.
2. Report P50, P95 and P99 of the platform turn gap for each group, and the share of turns over the SLO: silence budget + 1,500 ms for non-tool turns and + 2,200 ms for tool turns.
3. Compare the sum of stage P95s with the P95 of the turn gap for each group.
4. Rebuild the T04 waterfall from its spans: end-of-turn delay, hops, LLM TTFT, two tool calls, TTS TTFB and playout. The parts must add up to the recorded turn gap.

## What a good answer shows

The latency table, the sum-of-P95s comparison and the T04 waterfall adding up to 3,990 ms.

## Check your work

```bash
python3.11 solutions/m05_voice_latency_slos.py
python3.11 solutions/m05_voice_latency_slos.py --edition india
```

Compare with `solutions/expected/m05_voice_latency_slos.txt` and `solutions/expected/m05_voice_latency_slos.india.txt`.

The lab for this module is [voice-latency-waterfall](../labs/voice-latency-waterfall/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-latency
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-latency
- Course module: https://www.aievals.co/courses/voice-ai-advanced
