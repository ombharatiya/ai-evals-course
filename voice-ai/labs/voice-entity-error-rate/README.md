# Lab: Entity error rate for spoken amounts and dates

Module 3 (STT evaluation beyond WER). Canonicalizes spoken amounts to minor units and dates to ISO, scores STT by entity error rate with a speaker-clustered interval, and shows WER and amount accuracy ranking two systems differently.

`voice-entity-error-rate.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs only the Python 3.11 standard library.

## Run it

```bash
cd labs/voice-entity-error-rate
python3.11 voice-entity-error-rate.py                    # global edition
python3.11 voice-entity-error-rate.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Score `data/<edition>/entity_pairs.jsonl` with the lab's own canonicalizer: run its amount canonicalizer on each `reference` and each hypothesis, and compare with `ref_entities` and `hyp_entities`. Every disagreement is either a canonicalizer gap or a labelling error.
2. Recompute the speaker-clustered interval for amount entity error rate on the pairs file with 90 speakers, and compare its width with the lab's synthetic sets.
3. Slice the pairs by `condition` and report the amount entity error rate per system on the phone path only.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/entity-error-rate
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/entity-error-rate
- Global edition: https://www.aievals.co/learn/voice-ai-evals/stt-normalization-code-switching
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/stt-normalization-hinglish
- Recipe page: https://www.aievals.co/cookbook/voice-entity-error-rate
