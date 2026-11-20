# Lab: Validate a voice judge per language group

Module 10 (Judges for audio). Checks a judge against human labels one language group at a time: confusion matrix, kappa, Wilson intervals on the violation class, lower-bound admission, the prevalence trap, a prediction-powered estimate and a registry entry.

`voice-judge-validation.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/voice-judge-validation
python3.11 voice-judge-validation.py                    # global edition
python3.11 voice-judge-validation.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Run the lab's functions on `data/<edition>/judge_labels.jsonl`; the C07 transcript judge in the edition's validation group reproduces agreement 0.925 and kappa 0.725.
2. Validate the blueprint judge on TONE.PACE per language group and fill a registry entry from templates/judge-registry-entry.json.
3. Compute how many more labelled violations each group needs before a recall lower bound of 0.90 is possible.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/audio-judges
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/audio-judges
- Recipe page: https://www.aievals.co/cookbook/voice-judge-validation
