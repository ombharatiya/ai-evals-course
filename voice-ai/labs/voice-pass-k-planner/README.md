# Lab: pass^k and a run-count planner

Module 11 (Statistics and reliability). Estimates every-trial success from repeated runs with the unbiased estimator, sizes paired and unpaired runs for a 5-point drop, and gates 12 segments with paired bootstrap deltas and Holm.

`voice-pass-k-planner.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/voice-pass-k-planner
python3.11 voice-pass-k-planner.py                    # global edition
python3.11 voice-pass-k-planner.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Feed the 25 scenarios x 8 trials of `data/<edition>/calls.jsonl` to the lab's suite estimator (a trial passes when the task diff is empty and no check fails).
2. Group the scenarios into the 12 gated segments and report which segments have too few scenarios to gate.
3. Measure discordant cells by splitting the 8 trials into two runs of 4 and rerun the paired sample size.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-reliability-statistics
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-reliability-statistics
- Recipe page: https://www.aievals.co/cookbook/voice-pass-k-planner
