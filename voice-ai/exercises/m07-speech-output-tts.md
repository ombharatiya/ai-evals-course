# Module 7: Evaluating speech output

Test the spoken output: compare what the agent read back with what the caller said, and set an acceptance gate with an exact binomial bound.

## Data

- `data/<edition>/calls.jsonl (agent `tts.entities`, caller `ref_entities`)`
- `data/<edition>/traces/T06.json (`tts.audio_reading`)`

## Tasks

1. Write the exact (Clopper-Pearson) one-sided 95% upper bound for k errors in n lines. Check that 0 of 400 gives about 0.0075.
2. For every read-back or PTP confirmation turn, compare the amount in `tts.entities` with the amount the caller said in the reference transcript. Count the mismatches and bound the error rate.
3. Run C13: every dues statement must state the amount that get_dues returned.
4. In T06, compare the TTS input text with `audio_reading`, and the stored PTP date with the date the borrower heard.

## What a good answer shows

The gate numbers, the mismatch count with its bound, and why a transcript review passes T06.

## Check your work

```bash
python3.11 solutions/m07_speech_output_tts.py
python3.11 solutions/m07_speech_output_tts.py --edition india
```

Compare with `solutions/expected/m07_speech_output_tts.txt` and `solutions/expected/m07_speech_output_tts.india.txt`.

The lab for this module is [tts-round-trip-numerics](../labs/tts-round-trip-numerics/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/tts-for-agents
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/tts-for-agents
- Course module: https://www.aievals.co/courses/voice-ai-advanced
