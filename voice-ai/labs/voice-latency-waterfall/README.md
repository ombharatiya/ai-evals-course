# Lab: A latency waterfall from turn spans and recordings

Module 5 (Measuring voice agent latency). Splits each turn into end-of-turn delay, LLM TTFT, tool time, TTS TTFB and playout, tests P95 by turn type against SLOs, rebuilds T04, and recovers what the caller heard from dual-channel recordings.

`voice-latency-waterfall.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs numpy (pinned in `requirements.txt`).

## Run it

```bash
cd labs/voice-latency-waterfall
python3.11 voice-latency-waterfall.py                    # global edition
python3.11 voice-latency-waterfall.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Point the span parser at `data/<edition>/calls.jsonl`: rebuild the turn gap of every agent turn from its spans and check it against `timings_summary.turn_gap_ms`.
2. Compute the P95 tool-turn gap per campaign from the calls and test it against each campaign's tool-turn SLO (silence budget + 2,200 ms).
3. Compare the calls above 1,800 concurrent calls with the rest: which stage's tail grows most?

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-latency
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-latency
- Recipe page: https://www.aievals.co/cookbook/voice-latency-waterfall
