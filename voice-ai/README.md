# Voice AI Evaluation: labs, data and exercises

Learner materials for the [Voice AI Evaluation course](https://www.aievals.co/courses/voice-ai-advanced). The course teaches how to evaluate voice agents where they fail: on phone audio, across languages, with entity error rate, endpointing curves, pass^k, validated judges and compliance gates. Its running example is an AI collections agent at a fictional lender.

Read the course in either edition:

- Global edition: [aievals.co/learn/voice-ai-evals](https://www.aievals.co/learn/voice-ai-evals). Steelyard Credit, a fictional US lender, and its agent Hazel. English, Spanish-dominant and Spanglish callers; US dollars; US, UK and EU rules.
- India edition: [aievals.co/learn/voice-ai-evals-india](https://www.aievals.co/learn/voice-ai-evals-india). Tarazu Finance, a fictional Indian lender, and its agent Asha; rupees; RBI, TRAI and DPDP rules.

Both editions share the same chapters, ids, code and computed numbers. Everything about both lenders is fictional and illustrative, the data is synthetic, and nothing here is legal advice.

## Setup

Python 3.11. Only two labs need numpy; everything else uses the standard library.

```bash
git clone https://github.com/ombharatiya/ai-evals-course.git
cd ai-evals-course/voice-ai
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt      # numpy==2.1.3
.venv/bin/python -m unittest discover -s tests -t . -v
```

The tests take a few minutes: the endpointing lab is the slow one.

## What is here

```
voice-ai/
  world/global/, world/india/   world bible, constants, tool and CRM schemas, policies
  data/                         generate.py, schemas, and the synthetic data of each edition
  labs/<slug>/                  the 12 lab scripts with their expected output in both editions
  exercises/                    one exercise per module
  solutions/                    worked solutions and their expected output
  templates/                    decision memo, codebook, judge registry entry, design doc, capstone brief and rubric
  tests/                        standard-library unittest suite
  tools/                        a small JSON Schema validator and a YAML reader (standard library)
```

Pick an edition with `--edition global` (the default) or `--edition india` on any lab, solution or the data generator.

## Labs and modules

| Module | Lab | Exercise |
|---|---|---|
| 1. Error analysis on real calls | - | [m01-call-review](exercises/m01-call-review.md) |
| 2. Metric design, layers and trade-offs | - | [m02-voice-metric-layers](exercises/m02-voice-metric-layers.md) |
| 3. STT evaluation beyond WER | [voice-entity-error-rate](labs/voice-entity-error-rate/) | [m03-stt-entities](exercises/m03-stt-entities.md) |
| 4. Testing on telephony audio | [telephony-degradation-pipeline](labs/telephony-degradation-pipeline/) (numpy) | [m04-phone-line-audio](exercises/m04-phone-line-audio.md) |
| 5. Measuring voice agent latency | [voice-latency-waterfall](labs/voice-latency-waterfall/) (numpy) | [m05-voice-latency-slos](exercises/m05-voice-latency-slos.md) |
| 6. Turn-taking, barge-in and recovery | [endpointing-operating-point](labs/endpointing-operating-point/) | [m06-endpointing-barge-in](exercises/m06-endpointing-barge-in.md) |
| 7. Evaluating speech output | [tts-round-trip-numerics](labs/tts-round-trip-numerics/) | [m07-speech-output-tts](exercises/m07-speech-output-tts.md) |
| 8. Task success and outbound outcomes | [collections-task-checker](labs/collections-task-checker/) | [m08-outbound-task-success](exercises/m08-outbound-task-success.md) |
| 9. Simulating callers | [caller-simulator-validator](labs/caller-simulator-validator/) | [m09-caller-simulation](exercises/m09-caller-simulation.md) |
| 10. Judges for audio | [voice-judge-validation](labs/voice-judge-validation/) | [m10-audio-judges](exercises/m10-audio-judges.md) |
| 11. Statistics and reliability | [voice-pass-k-planner](labs/voice-pass-k-planner/) | [m11-voice-reliability](exercises/m11-voice-reliability.md) |
| 12. Evals under load, and their cost | [voice-load-ramp-plan](labs/voice-load-ramp-plan/) | [m12-voice-load-cost](exercises/m12-voice-load-cost.md) |
| 13. Production monitoring | [rare-violation-sampling](labs/rare-violation-sampling/) | [m13-voice-monitoring](exercises/m13-voice-monitoring.md) |
| 14. Safety, privacy and compliance | [collections-compliance-checks](labs/collections-compliance-checks/) | [m14-collections-compliance](exercises/m14-collections-compliance.md) |
| 15. Capstone: design the eval platform | - | [m15-eval-platform-review](exercises/m15-eval-platform-review.md) |

Run a lab from its folder; two of them write files there (a pause CSV, phone-path WAVs):

```bash
cd labs/voice-latency-waterfall
../../.venv/bin/python voice-latency-waterfall.py                  # global edition
../../.venv/bin/python voice-latency-waterfall.py --edition india  # India edition
```

The lab scripts are copies of the scripts the site publishes and stay identical to them. Each is standalone: it generates its own synthetic data with a fixed seed and holds both editions' constants. The shared course data in `data/` is for the exercises and the stretch exercises in each lab's README.

## Data

`data/generate.py --edition <edition>` builds each edition's data from `world/<edition>/` with a fixed seed: ten incident traces T01-T10 on one clock, 200 simulated calls with timelines, transcripts, tool calls, stage timings and CRM before and after, entity reference and hypothesis pairs, endpointing pause events, judge labels with human labels, and a production sample. [data/README.md](data/README.md) documents every field.

## Written work

Each module ends with a decision memo in a 7-part format, and the course ends with a capstone: a design of the evaluation platform, defended in a review, for either edition. Templates are in [templates/](templates/). The course grades the module quizzes and the exam; the memos and the capstone are self-assessed against the rubric.
