# Error analysis codebook

Use this during call review (module 1). Code the first failure in each call only; a later failure often follows from the first. Listen to the call or read the timeline (turn times, overlaps, barge-in events, non-speech tags) before you code: some failures are not in the transcript.

## Review log

| Call id | Reviewer | Transcript view verdict | Timeline or audio verdict | First failure (open note) | Axial code | Turn id | Evidence (time in ms) |
|---|---|---|---|---|---|---|---|
| | | ok / fail | ok / fail | | | | |

## Axial codes

The codes are identical in both editions; only the taxonomy version string differs (`taxonomy.version` in `world/<edition>/constants.json`). Codes are never reused; a retired code maps to its replacements.

| Category | Codes | Definition |
|---|---|---|
| ENT entity | ENT.AMOUNT, ENT.DATE, ENT.CONFIRM | An amount, date or yes/no was misheard, misspoken or mis-stored |
| TURN turn-taking | TURN.CUTOFF, TURN.TALKOVER, TURN.BARGEIN | False cutoff, talk-over, or missed or unrecovered barge-in |
| LAT latency | LAT.TAIL, LAT.DUP | Turn gap over budget; duplicate or overlapping replies |
| POL policy | POL.DISCLOSE, POL.COERCE, POL.DISPUTE, POL.HARDSHIP, POL.WINDOW | Breach of a policy check (C01-C16) |
| OUT outbound | OUT.AMD, OUT.PARTY | Machine treated as human or the reverse; wrong-party handling |
| STT language and loops | STT.LID, LOOP.CLARIFY | Language identification locked to the wrong language; more than two clarifications on one slot |
| TONE delivery | TONE.PACE, TONE.GENDER | Rushed or ill-timed delivery; wrong-gender self-reference |

## New code proposals

| Proposed code | Definition | Example calls | Why no existing code fits |
|---|---|---|---|
| | | | |

## Agreement

Two reviewers code the same shared calls (30 is the course's size). Report Cohen's kappa on the first-failure code and list every disagreement with the resolution.

| Shared calls | Same code | Kappa | Date | Taxonomy version |
|---|---|---|---|---|
| | | | | |

## Cadence

Write down your review cadence: a weekly stratified top-up (how many calls, from which strata), a full pass every few weeks, who reviews which language groups, and when the taxonomy gets a new version.
