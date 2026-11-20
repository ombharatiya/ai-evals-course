# Module 3: STT evaluation beyond WER

Score three STT systems by WER and by amount entity error rate, with an interval clustered by speaker, and show that the two metrics rank them differently.

## Data

- `data/<edition>/entity_pairs.jsonl (600 reference and hypothesis pairs, three systems, gold entities)`

## Tasks

1. Write a word-level Levenshtein alignment that returns substitutions, deletions and insertions. Check it on pair T01: one substitution in 12 words.
2. Compute corpus WER per system (sum of edits over sum of reference words).
3. Compute amount entity error rate per system from `ref_entities` and `hyp_entities`, with a 95% bootstrap interval that resamples speakers, not utterances (1,000 resamples).
4. Count the pairs where WER is under 10% and the amount is wrong.

## What a good answer shows

A table with corpus WER and amount entity error rate with intervals per system, and a sentence on which system you would ship for a collections agent and why.

## Check your work

```bash
python3.11 solutions/m03_stt_entities.py
python3.11 solutions/m03_stt_entities.py --edition india
```

Compare with `solutions/expected/m03_stt_entities.txt` and `solutions/expected/m03_stt_entities.india.txt`.

The lab for this module is [voice-entity-error-rate](../labs/voice-entity-error-rate/).

## Read

- Global edition: https://www.aievals.co/learn/voice-ai-evals/entity-error-rate
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/entity-error-rate
- Global edition: https://www.aievals.co/learn/voice-ai-evals/stt-normalization-code-switching
- India edition: https://www.aievals.co/learn/voice-ai-evals-india/stt-normalization-hinglish
- Course module: https://www.aievals.co/courses/voice-ai-advanced
