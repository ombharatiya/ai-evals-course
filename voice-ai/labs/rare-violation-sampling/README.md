# Lab: Size samples for rare violations

Module 13 (Production monitoring). Computes how many calls you must judge to see a rare violation, bounds the rate when you see none, and stratifies the judge toward the paths where violations live.

`rare-violation-sampling.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/rare-violation-sampling
python3.11 rare-violation-sampling.py                    # global edition
python3.11 rare-violation-sampling.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Use the stratum shares from `data/<edition>/production_sample.jsonl` (exercise 13) as the lab's stratum sizes and recompute the stratified plan.
2. Size the human audit so that a 1-in-2,000 violation is seen within a week with 95% probability, and price it with the human audit unit cost in `world/<edition>/constants.json`.
3. Replay T09 with the judge reading every angry-path call from the day the prompt patch went live.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-production-monitoring
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-production-monitoring
- Recipe page: https://www.aievals.co/cookbook/rare-violation-sampling
