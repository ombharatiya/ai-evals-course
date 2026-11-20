# Lab: Round-trip TTS numbers and dates

Module 7 (Evaluating speech output). Verbalizes amounts and dates, round-trips them through TTS and STT (a constructed fixture stands in for real engines), exact-matches each entity type, and gates on an exact binomial bound.

`tts-round-trip-numerics.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/tts-round-trip-numerics
python3.11 tts-round-trip-numerics.py                    # global edition
python3.11 tts-round-trip-numerics.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Take every read-back line in `data/<edition>/calls.jsonl` (acts `readback` or `inform_ptp`) and check the TTS text against its `entities` with the lab's parse-back scorer.
2. Use T06 (`data/<edition>/traces/T06.json`) as a regression case: write the assertion that would have failed before the words-for-dates rule.
3. Compute how many error-free amount lines you need for an upper bound of 0.5%.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/tts-for-agents
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/tts-for-agents
- Recipe page: https://www.aievals.co/cookbook/tts-round-trip-numerics
