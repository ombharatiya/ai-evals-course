# Lab: Check task success against CRM state

Module 8 (Task success and outbound outcomes). Diffs CRM state before and after each call against a gold end state per flow, reports the funnel with named denominators, and costs a six-class AMD confusion matrix.

`collections-task-checker.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/collections-task-checker
python3.11 collections-task-checker.py                    # global edition
python3.11 collections-task-checker.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Run the lab's checker logic on `data/<edition>/calls.jsonl` using `crm_before`, `crm_after` and `gold_end_state`, and compare your per-flow success with exercise 8.
2. Add T01-T10 from `data/<edition>/traces/` to the run and confirm T01 fails with the two diff lines the lab prints.
3. Rebuild the AMD matrix from `data/<edition>/production_sample.jsonl` and compare its lowest-recall class with the lab's.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/task-success-and-outbound
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/task-success-and-outbound
- Recipe page: https://www.aievals.co/cookbook/collections-task-checker
