# Module 4: Testing on telephony audio

Rank STT systems per audio condition and show that a ranking on wideband audio does not carry over to the phone path.

## Data

- `data/<edition>/entity_pairs.jsonl (`condition`: wideband_16k, g711_clean, amr_g711, amr_g711_loss5, noise_10db)`

## Tasks

1. For each condition and system, compute the amount entity error rate.
2. Rank the systems per condition, then pool every phone-path condition and rank again.
3. Name the system that wins on wideband audio and where it places on the phone path.

## What a good answer shows

A condition-by-system table and the gating rule you would write: which columns gate a release, and which are reported only.

## Check your work

```bash
python3.11 solutions/m04_phone_line_audio.py
python3.11 solutions/m04_phone_line_audio.py --edition india
```

Compare with `solutions/expected/m04_phone_line_audio.txt` and `solutions/expected/m04_phone_line_audio.india.txt`.

The lab for this module is [telephony-degradation-pipeline](../labs/telephony-degradation-pipeline/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/telephony-audio
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/telephony-audio
- Course module: https://www.aievals.co/courses/voice-ai-advanced
