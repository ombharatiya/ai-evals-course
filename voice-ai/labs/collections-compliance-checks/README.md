# Lab: Collections compliance checks as code

Module 14 (Safety, privacy and compliance). Turns the lender's collections and telecom rules into deterministic checks with unit tests: calling windows, opening disclosures, verification before debt detail, voicemail content, stop requests, consent, caller ID and call frequency. Not legal advice.

`collections-compliance-checks.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/collections-compliance-checks
python3.11 collections-compliance-checks.py                    # global edition
python3.11 collections-compliance-checks.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Run the lab's checks on `data/<edition>/traces/*.json` and compare the failures and evidence turns with exercise 14.
2. Write a unit test for each policy in `world/<edition>/policies.yaml` that the lab does not cover yet.
3. Run the checks on the 200 simulated calls and list every call that fails a check but has no reviewer label.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/voice-safety-and-compliance
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/voice-safety-and-compliance
- Recipe page: https://www.aievals.co/cookbook/collections-compliance-checks
