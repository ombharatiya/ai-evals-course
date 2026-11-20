# Lab: A phone-path degradation pipeline in numpy

Module 4 (Testing on telephony audio). Band-passes to 300-3400 Hz, resamples to 8 kHz, round-trips mu-law, drops 20 ms frames in Gilbert-Elliott bursts and mixes noise at a set SNR, then writes WAV files to run an STT system on. It writes them to phone_path_out/ in the folder you run it from.

`telephony-degradation-pipeline.py` is the same standalone file the course site shows. It generates its own synthetic data with a fixed seed, holds the constants of both editions, and needs numpy (pinned in `requirements.txt`).

## Run it

```bash
cd labs/telephony-degradation-pipeline
python3.11 telephony-degradation-pipeline.py                    # global edition
python3.11 telephony-degradation-pipeline.py --edition india    # India edition
```

The output must match `expected_output.txt` (global) and `expected_output.india.txt` (India) byte for byte; `tests/test_labs.py` checks both.

## Your task

1. Run the lab in one edition and read the output top to bottom. For each table, write one sentence on what decision it supports.
2. Find the numbers marked as computed for the course in the world bible (`world/<edition>/WORLD.md`, section 17) and check that the lab prints the same values.
3. Change one input (a seed, a threshold or a rate) and predict the effect before you rerun. Then restore it: the tests compare against the original output.

## Stretch exercises with the course data

1. Run the lab with `--wav` on your own consented 16 kHz recording of a line from a promise template in `world/<edition>/phrases.json`, then score your STT output on each condition with the entity error rate lab.
2. Map the five conditions in `data/<edition>/entity_pairs.jsonl` to the lab's parameters (codec chain, loss, SNR) and write down which parameter you would vary first.
3. Change the Gilbert-Elliott parameters for 5% loss with a mean burst of 4 frames and check the realised rate and burst length over 10 seeds.

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/telephony-audio
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/telephony-audio
- Recipe page: https://www.aievals.co/cookbook/telephony-degradation-pipeline
