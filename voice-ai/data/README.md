# Course data

Synthetic data for the Voice AI Evaluation course, one folder per edition. Every lender, agent, person, account and call is fictional. Steelyard Credit (global edition) and Tarazu Finance (India edition) are fictional lenders; their numbers are illustrative and are not industry rates.

```
data/
  generate.py          # writes data/<edition>/ from world/<edition>/ (standard library only)
  schemas/             # JSON Schemas for every record type below
  global/              # Steelyard Credit, seed 20261121
  india/               # Tarazu Finance, seed 20261120
```

Regenerate or verify an edition:

```bash
python3.11 data/generate.py --edition global           # rewrite data/global/
python3.11 data/generate.py --edition india --check    # rebuild in memory and compare with the files on disk
```

The same edition always produces byte-identical files; `tests/test_data.py` runs the `--check` comparison. `manifest.json` in each folder lists every file with its record count and SHA-256.

## Files

| File | Records | What it is | Used by |
|---|---|---|---|
| `traces/T01.json` ... `T10.json` | 10 | The incident log from the world bible (section 16), each as a full call on one clock | modules 1, 5, 7, 8, 14, 15 |
| `traces/S1.json`, `S2a.json`, `S2b.json` | 3 | Worked examples: a verified guarantor (S1), a compliant and a non-compliant voicemail (S2a, S2b) | module 14 |
| `calls.jsonl` | 200 | Simulated calls: 25 scenario cards x 8 trials, with timelines, transcripts, tool calls, stage timings and CRM before and after | modules 1, 5, 7, 8, 9, 11, 12, 14 |
| `entity_pairs.jsonl` | 600 | Reference transcripts with hypotheses from three STT systems under five audio conditions, and gold entities | modules 3, 4 |
| `pauses.jsonl` | 1,201 | Labelled caller pauses (hold or end) for endpointing, 400 per language group, plus T05's pause | module 6 |
| `judge_labels.jsonl` | 720 | 120 human-labelled calls per language group per judged dimension, with two raters and two judges | module 10 |
| `production_sample.jsonl` | 4,000 | Dial attempts from one production day, with AMD truth and prediction, funnel flags, strata and check results | modules 2, 8, 9, 13 |
| `manifest.json` | 1 | Edition, dataset name, seed, world version, generator version, file hashes and counts | tests |

## Calls and traces (`traces/*.json`, `calls.jsonl`)

Schema: `schemas/trace.schema.json` (voice-trace/1.3). One object per call. Every `*_ms` field is milliseconds since media start at the agent's ingress, so every event of a call sits on one clock. Tool arguments and CRM rows use the edition's field names and are checked against `world/<edition>/tools.schema.json` and `world/<edition>/crm.schema.json`.

| Field | Meaning |
|---|---|
| `call_id` | `SY-` (global) or `TZ-` (India), the call date and a 7-digit number |
| `schema_version` | Always `voice-trace/1.3` |
| `edition`, `dataset` | Edition name and dataset name with its seed |
| `campaign` | Campaign id from `world/<edition>/constants.json` (`campaigns`) |
| `account_id` | Fictional account, `A-` and 8 digits |
| `persona_or_real` | `sim` for the 200 simulated calls, `real` for the incident traces (real inside the fictional world) |
| `scenario` | For simulated calls: `scenario_id`, `trial` (1-8), `flow` (F01-F10), `persona` (P01-P13), `language_group`, `variant`. For traces: `incident`, `title`, `flow`, `persona`, `language_group` |
| `started_at_local`, `tz` | Local start time with UTC offset, and the IANA time zone |
| `location_signals` | Global edition only: the time zone implied by the area code and by the address (C01 uses both) |
| `dial` | Attempt context. Global: `attempts_7d_before`, `connect_outcome`, `counts_toward_cap`, `conversation`. India: `connected_calls_today_before`, `connected_calls_week_before`, `connect_outcome` |
| `cli`, `attestation` | Caller ID pattern; global edition adds the STIR/SHAKEN attestation level |
| `carrier`, `codec_chain` | Carrier leg and the codecs from the handset to the agent |
| `pipeline` | `cascade` (STT, LLM, TTS) or `s2s` |
| `concurrency_at_start` | Concurrent calls on the platform when the call started (module 12) |
| `versions` | Agent, prompt, STT, turn detector with threshold, LLM, TTS, policy pack, taxonomy, gold set |
| `silence_budget_ms` | The campaign's end-of-turn silence budget: `default` and `amount_or_date_asked` |
| `audio` | Recording URIs (placeholders, no audio ships), sample rate, and the carrier offset in ms |
| `amd` | Answering machine detection: `label` (what AMD said), `confidence`, `decided_at_ms`, `true_label` (what answered) |
| `turns` | Caller and agent turns in time order (below) |
| `timings_summary` | Per agent turn that answers a caller turn: `agent_turn_ids`, `turn_types`, `turn_gap_ms` (caller VAD end to agent audio start) and `stage_ms` lists for `eot_delay`, `llm_ttft`, `tool`, `tts_ttfb`, `playout` |
| `crm_before`, `crm_after` | CRM tables (table name -> list of rows) before and after the call |
| `gold_end_state` | What the CRM should show after the call: `new_rows` (table -> partial rows that must appear), `account` (account fields after the call), `call_attempt` (fields of the call-attempt row), optional `note` |
| `checks` | Check results the platform recorded (traces only; empty for simulated calls, which you score yourself): `id`, `result`, `evidence_turns` |
| `judge_scores` | Judge verdicts recorded on the call (T10) |
| `labels` | Reviewer labels: `labeler`, `taxonomy`, `code` (first failure, or `NONE`), `note`, `turn_id` |
| `review_set` | Simulated calls: `shared-30` when two reviewers labelled the call, else `single` |

Caller turn:

| Field | Meaning |
|---|---|
| `turn_id`, `speaker` | Position in the call; `caller` |
| `source` | `human`, or `machine` for voicemail greetings, call-screening assistants, intercepts, announcements and IVRs |
| `vad_start_ms`, `vad_end_ms` | Voice activity start and end; `vad_end_ms` is stored back-dated by the hangover |
| `vad_hangover_ms` | VAD hangover the pipeline subtracted |
| `stt_partials`, `stt_final` | Streaming STT output; the final has `t_ms`, `text`, per-word `lang_tags` and `confidence` |
| `eot_commit_ms` | When the turn detector committed end of turn (`null` for machine audio) |
| `reference_text` | What the caller said (human transcription) |
| `gloss` | English meaning of a Spanish line (global edition) |
| `ref_intent` | Reference label of what the caller did: for example `promise`, `confirm_yes`, `backchannel`, `already_paid`, `dispute`, `hardship`, `third_party`, `callback_request`, `complaint`, `hangup` |
| `ref_entities` | Gold entities in the reference text: `type` (`amount` in minor units, `date` as ISO, `confirmation`, `postal_code`) and `value` |
| `stt_entities` | The same entities as extracted from the STT text; a difference from `ref_entities` is a misheard entity |
| `tags` | Non-speech tags, for example `crying, 4 s` |
| `pauses` | Hold pauses inside the turn: `start_ms`, `end_ms`, `label`, `content_tag` |

Agent turn:

| Field | Meaning |
|---|---|
| `turn_id`, `speaker` | Position in the call; `agent` |
| `turn_type` | `greeting`, `verification`, `amount-quote`, `readback`, `tool`, `objection` or `closing` |
| `responds_to` | The caller turn this turn answers (`null` for scripted turns such as the opener or a voicemail message) |
| `llm` | `request_ms`, `first_token_ms`, `first_answer_token_ms`, `cached_tokens`; `speculative` is true when the request started before the end-of-turn commit. `null` for scripted turns |
| `tool_calls` | `name`, `args_redacted` (arguments without account and contact ids, phone numbers, verification values and free-text statements), `start_ms`, `end_ms`, `result`. Calls that start after playback are listed after it |
| `tts` | `text` sent to synthesis, optional `gloss`, `request_ms`, `first_byte_ms`, `entities` (what the text states: `amount`, `date`, `product`, `dpd`), optional `audio_reading` (what the audio said, when it differs; T06), optional `audio_entities` (the entities the audio stated where they differ from `entities`; T06's heard date) |
| `play_start_ms`, `play_end_ms` | Agent audio at media egress |
| `speaking_rate_sps` | Syllables per second |
| `barge_in` | `null`, or `t_ms`, `tts_stop_ms`, `stop_latency_ms` when the caller interrupted |
| `acts` | What the turn did, from the orchestrator: for example `ai_disclosure`, `recording_notice`, `inform_dues`, `ask_payment`, `readback`, `disclosure`, `callback_number`, `consequence_statement` |

Turn gap of an agent turn = its `play_start_ms` minus the `vad_end_ms` of the turn in `responds_to`. For simulated, non-speculative turns it equals end-of-turn delay + LLM TTFT + tool time + TTS TTFB + playout + 10 ms per orchestration hop (two hops plus one per tool call before speech); `tests/test_data.py` checks this.

## Entity pairs (`entity_pairs.jsonl`)

Schema: `schemas/entity_pair.schema.json`.

| Field | Meaning |
|---|---|
| `pair_id` | `T01` (the incident utterance) or `EP001`-`EP599` |
| `speaker_id` | Speaker, for clustered intervals (90 speakers plus T01's) |
| `language_group` | One of the edition's three language groups |
| `condition` | `wideband_16k`, `g711_clean`, `amr_g711`, `amr_g711_loss5` (5% burst loss) or `noise_10db` |
| `call_date` | Date used to resolve relative dates |
| `kind` | `promise` (amount and date) or `confirm` (yes or a backchannel) |
| `reference` | Human reference transcript |
| `hyps` | Hypotheses from `sys_a`, `sys_b` and `sys_c` |
| `ref_entities` | Gold entities of the reference (amounts in minor units, ISO dates, confirmations) |
| `hyp_entities` | The entities each hypothesis states, per system |

## Pauses (`pauses.jsonl`)

Schema: `schemas/pause.schema.json`.

| Field | Meaning |
|---|---|
| `pause_id`, `call_id`, `turn_id` | Ids; `T05-p1` is T05's 720 ms pause |
| `language_group`, `campaign` | Segment of the pause |
| `call_state` | `default`, `amount_asked` or `date_asked` |
| `content_tag` | What comes next: `date`, `amount`, `dispute`, `small_talk` or `none` |
| `label` | `hold` (the caller had not finished) or `end` (the turn was over) |
| `pause_ms` | Silence length. For an `end` pause, how long the caller would stay silent if nobody spoke |
| `model_a_hold_prob`, `model_b_hold_prob` | Two turn detectors' probability that the caller is holding the floor |

## Judge labels (`judge_labels.jsonl`)

Schema: `schemas/judge_label.schema.json`.

| Field | Meaning |
|---|---|
| `call_id` | Validation call id |
| `language_group` | One of the three language groups |
| `dimension` | `C07` (coercion and consequence misstatement) or `TONE.PACE` (pacing and empathy after hardship) |
| `rater_a`, `rater_b` | Two human raters (true = violation) |
| `human_label` | Adjudicated human label |
| `transcript_judge`, `blueprint_judge` | Verdicts of a transcript-only judge and a judge that reads a text blueprint of the audio (speaking rate, overlaps, pauses, non-speech tags) |

The C07 transcript judge in the edition's validation group (`judge_validation_group` in `constants.json`) has 18 violations, 15 caught and 6 false alarms in 120 calls, as in the world bible.

## Production sample (`production_sample.jsonl`)

Schema: `schemas/production_row.schema.json`. One dial attempt per line from one calling day.

| Field | Meaning |
|---|---|
| `attempt_id`, `call_date`, `campaign`, `product`, `language_group`, `local_time` | Attempt identity and segment |
| `connect_outcome` | `answered`, `voicemail`, `unanswered`, `busy` or `out_of_service` |
| `connected` | Answered by anything (human or machine) |
| `amd_true`, `amd_pred` | What answered and what AMD said (one of the edition's six `amd_classes`); `null` when not connected |
| `human_answer`, `rpc` | A human answered; the right party was reached and verified |
| `flow` | The call flow on human answers |
| `stratum` | Sampling stratum on human answers: `angry`, `complaint`, `dispute`, `hardship`, `stop_request`, `window_edge` or `other` |
| `ptp`, `ptp_verified`, `kept` | A promise to pay was recorded; its stored amount and date match what the borrower confirmed; it was kept (checked two weeks later) |
| `call_seconds` | Connected call length |
| `checks` | On human answers: results of C04, C08, C09, C12 (`pass`, `fail` or `n/a`) |
| `violation` | The first failed check, or `null` |
| `judge_sampled` | The call was sent to the judge under the stratified plan |
| `concurrency` | Concurrent calls when the attempt started |
