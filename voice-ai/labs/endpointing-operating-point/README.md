# Lab: Choose an endpointing operating point

Module 6 (Turn-taking, barge-in and recovery). Sweeps a turn detector's silence budget over labelled pauses, reads false cutoffs against dead air per language group, and picks a budget per campaign and call state by expected cost. It writes a pause CSV in the folder you run it from.

`endpointing-operating-point.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/endpointing-operating-point
python3.11 endpointing-operating-point.py                    # global edition
python3.11 endpointing-operating-point.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Run the lab's sweep on `data/<edition>/pauses.jsonl` instead of its generated pauses, and compare the chosen points.
2. Add `model_b_hold_prob` as a second detector and report its false cutoffs at the same dead air as model A.
3. Find the shortest budget that does not cut T05's pause (`pause_id` T05-p1) and price it in dead air on every end pause.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/turn-taking-and-barge-in
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/turn-taking-and-barge-in
- Recipe page: https://www.aievals.co/cookbook/endpointing-operating-point
