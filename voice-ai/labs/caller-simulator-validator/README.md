# Lab: Validate a simulated caller

Module 9 (Simulating callers). Builds a pairwise scenario grid, runs three validators that reject bad simulated calls and regenerate them, compares simulated calls with real twins, and audits failures with two raters.

`caller-simulator-validator.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/caller-simulator-validator
python3.11 caller-simulator-validator.py                    # global edition
python3.11 caller-simulator-validator.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Check pair coverage of persona x flow in the 25 scenarios of `data/<edition>/calls.jsonl` and list the pairs a pairwise grid would add.
2. Write a validator that rejects a simulated call whose caller turns contradict its persona card (for example a third party who verifies as the borrower).
3. Compare simulated and production pass rates on C04, C08, C09 and C12 (exercise 9) and decide which check needs a simulator fix first.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-simulation
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-simulation
- Recipe page: https://www.aievals.co/cookbook/caller-simulator-validator
