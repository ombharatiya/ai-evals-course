# Exercises

One exercise per module of the course. Each one uses the synthetic data in `data/<edition>/` and the world files in `world/<edition>/`. Work in either edition: pass the edition to your code and read every field name, keyword and window from `world/<edition>/constants.json`, so the same code runs on both.

Write your own code first. A worked solution for each exercise is in `solutions/`, with its output for both editions in `solutions/expected/`:

```bash
python3.11 solutions/m03_stt_entities.py                  # global edition
python3.11 solutions/m03_stt_entities.py --edition india  # India edition
```

`solutions/vacourse.py` holds the shared helpers the solutions use (loaders, WER, Wilson and Clopper-Pearson intervals, kappa, pass^k, the CRM diff and the checks).

| Module | Exercise | Lab |
|---|---|---|
| 1. Error analysis on real calls | [m01-call-review.md](m01-call-review.md) | - |
| 2. Metric design, layers and trade-offs | [m02-voice-metric-layers.md](m02-voice-metric-layers.md) | - |
| 3. STT evaluation beyond WER | [m03-stt-entities.md](m03-stt-entities.md) | [voice-entity-error-rate](../labs/voice-entity-error-rate/) |
| 4. Testing on telephony audio | [m04-phone-line-audio.md](m04-phone-line-audio.md) | [telephony-degradation-pipeline](../labs/telephony-degradation-pipeline/) |
| 5. Measuring voice agent latency | [m05-voice-latency-slos.md](m05-voice-latency-slos.md) | [voice-latency-waterfall](../labs/voice-latency-waterfall/) |
| 6. Turn-taking, barge-in and recovery | [m06-endpointing-barge-in.md](m06-endpointing-barge-in.md) | [endpointing-operating-point](../labs/endpointing-operating-point/) |
| 7. Evaluating speech output | [m07-speech-output-tts.md](m07-speech-output-tts.md) | [tts-round-trip-numerics](../labs/tts-round-trip-numerics/) |
| 8. Task success and outbound outcomes | [m08-outbound-task-success.md](m08-outbound-task-success.md) | [collections-task-checker](../labs/collections-task-checker/) |
| 9. Simulating callers | [m09-caller-simulation.md](m09-caller-simulation.md) | [caller-simulator-validator](../labs/caller-simulator-validator/) |
| 10. Judges for audio | [m10-audio-judges.md](m10-audio-judges.md) | [voice-judge-validation](../labs/voice-judge-validation/) |
| 11. Statistics and reliability | [m11-voice-reliability.md](m11-voice-reliability.md) | [voice-pass-k-planner](../labs/voice-pass-k-planner/) |
| 12. Evals under load, and their cost | [m12-voice-load-cost.md](m12-voice-load-cost.md) | [voice-load-ramp-plan](../labs/voice-load-ramp-plan/) |
| 13. Production monitoring | [m13-voice-monitoring.md](m13-voice-monitoring.md) | [rare-violation-sampling](../labs/rare-violation-sampling/) |
| 14. Safety, privacy and compliance | [m14-collections-compliance.md](m14-collections-compliance.md) | [collections-compliance-checks](../labs/collections-compliance-checks/) |
| 15. Capstone: design the eval platform | [m15-eval-platform-review.md](m15-eval-platform-review.md) | - |
