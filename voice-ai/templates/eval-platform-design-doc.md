# Voice agent evaluation platform: design

Edition: <global or India>. Author: <name>. Date: <YYYY-MM-DD>. Status: draft for review.

At most six pages, plus an appendix with your decision memos. Every number carries an interval or an as-of date. Mark each vendor number as self-reported where it is.

## 1. Problem statement

The three incidents from T01-T10 you consider most expensive, and why (cost per occurrence, frequency, regulatory exposure, time to detection today).

## 2. Data model

Call, turn, span, audio segment, tool call, CRM diff, check result, label and judge score. The clock and how carrier-side times map onto it. Versions recorded per call. PII classes, redaction and retention (per jurisdiction where it differs). How a speech-to-speech trace differs from a cascade trace.

## 3. Gold sets

Contents and sizes per language group, versioning and lineage, refresh cadence, and how a production incident becomes a case that fails on the old agent first.

## 4. CI gates

| Stage | What runs | Size and k | Gated metric as an interval rule | Segments and multiplicity |
|---|---|---|---|---|
| Per commit | | | | |
| Nightly | | | | |
| Pre-release | | | | |
| Canary | | | | |

## 5. Simulation fleet

Personas and scenario cards, audio-path parity, impairments, outbound coverage (machines, wrong parties, callbacks), simulator validation and the audit rate, concurrency and cost.

## 6. Online sampling

Checks that run on every call. Strata and sampling rates. Human audit size and allocation. How rates are reported (which estimator). Rare-violation sizing for the coercion check and for the judge backstop of the verification-order check.

## 7. Judge registry

Fields, admission rule, status per language group, revalidation triggers and ownership. Attach one registry entry (templates/judge-registry-entry.json).

## 8. Cost budget

| Line | Unit cost | Volume | Monthly cost |
|---|---|---|---|
| | | | |
| Total | | | |

State the cap, the total, the cost per detected violation, and what is never cut.

## 9. Build versus buy

| Component | Build or buy | Criteria that decided it | Exit terms |
|---|---|---|---|
| Simulation | | | |
| Telephony impairment | | | |
| Load generation | | | |
| Judges | | | |
| Dashboards | | | |
| Labeling | | | |

## 10. Speech-to-speech

Which evals disappear or must be rebuilt, and how you would run the paired comparison against the cascade.

## 11. Incident coverage

| Trace | Component and gate that catch it | Second, independent catch | Expected time to detection |
|---|---|---|---|
| T01 | | | |
| T02 | | | |
| T03 | | | |
| T04 | | | |
| T05 | | | |
| T06 | | | |
| T07 | | | |
| T08 | | | |
| T09 | | | |
| T10 | | | |

## 12. Evidence from your own work

At least four outputs from the labs or exercises (for example your endpointing table, your judge registry entry, your budget table, your incident coverage table), each with the command that produced it.

## Open risks

| Risk | Owner | What would tell us it is happening |
|---|---|---|
| | | |

## Appendix: decision memos

One memo per module you worked through (templates/decision-memo.md).
