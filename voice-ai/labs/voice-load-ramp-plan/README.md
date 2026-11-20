# Lab: Plan a voice load test

Module 12 (Evals under load, and their cost). Models the voice stack under load with a discrete-event simulation, ramps in 10% steps to 1.5x of projected peak, holds, spikes to 3x, and reports P95 tool-turn gap, rejections, an amount-accuracy proxy and cost per completed task.

`voice-load-ramp-plan.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/voice-load-ramp-plan
python3.11 voice-load-ramp-plan.py                    # global edition
python3.11 voice-load-ramp-plan.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Compare the lab's knee with the tool-turn gaps by concurrency band in `data/<edition>/calls.jsonl` (exercise 12).
2. Re-plan for 6,000 concurrent calls, the capstone peak, and price the pre-release load tests with `world/<edition>/constants.json` (`cost_model.load_test_per_run`).
3. Add a stop condition on the P95 tool-turn gap SLO of the slowest campaign.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-load-and-cost
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-load-and-cost
- Recipe page: https://www.aievals.co/cookbook/voice-load-ramp-plan
