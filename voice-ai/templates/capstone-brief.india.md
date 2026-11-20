# Capstone brief: India edition

Tarazu Finance is a fictional lender; its numbers are illustrative. You may answer the capstone for either edition; this brief uses the India one, and the rubric's incident row scores against the T01-T10 log of the India world (`world/india/WORLD.md`, W16). The global brief is in `capstone-brief.md`.

You are the staff engineer for evaluation at Tarazu Finance. Next quarter Asha goes from 5 campaigns to 9 (adding a second PL book, an SBL top-up campaign, a larger MFI book and a Marathi pilot), from Hinglish, Hindi and Indian English to five languages (Marathi and Kannada handled by the bot for the first time), and from 2,400 to 6,000 peak concurrent calls. A speech-to-speech model (asha-s2s-pilot) is under evaluation as a replacement for the cascade. The RBI recovery amendments take effect on 1 January 2027 and DPDP Rule 6 around May 2027. Compliance wants evidence that no call discloses dues before verification and that calling-window violations are zero.

The CFO has capped eval spend at Rs 15,00,000 a month; today's plan costs about Rs 9.1 lakh and scales to about Rs 15.1 lakh at the new volume (W20). Two vendors have pitched a managed testing platform. Write a design of at most six pages plus an appendix of your memos (`eval-platform-design-doc.md`), and defend it in a 30-minute review with the head of engineering, the chief compliance officer and the CFO.

Cover:

1. Problem statement: the three incidents from T01-T10 you consider most expensive, and why.
2. Data model: call, turn, span, audio segment, tool call, CRM diff, check result, label, judge score; the clock; versions; PII classes and retention; how speech-to-speech traces differ.
3. Gold sets: contents, versioning, refresh, incident intake.
4. CI gates: per commit, nightly, pre-release, canary; gated metrics as interval rules; per-segment gating and multiplicity.
5. Simulation fleet: personas, audio-path parity, impairments, outbound coverage, simulator validation and audit rate, concurrency and cost.
6. Online sampling: checks on every call, strata and rates, human audit, how rates are reported, rare-violation sizing for C07 and for the C04 judge backstop (C04's deterministic check runs on every call).
7. Judge registry: fields, admission rule, per-language status (including Marathi and Kannada), revalidation triggers, ownership.
8. Cost budget: monthly cost by line from the W20 unit costs and cost per detected violation, inside the Rs 15 lakh cap.
9. Build vs buy for simulation, telephony impairment, load generation, judges, dashboards and labelling, with criteria (outbound support, Hinglish fidelity, audio-path parity, Indian data residency and DPDP processor terms, raw-result export, cost at volume) and exit terms.
10. Speech-to-speech: which evals disappear or must be rebuilt, and how you would run the comparison.
11. Incident coverage table: T01-T10, the component and gate that catches each, and the expected time to detection.
12. Evidence from your own work: at least four outputs from the labs or exercises (for example your endpointing table from the endpointing lab, your judge registry entry from the judge validation lab).

Not legal advice: the compliance parts implement the fictional lender's reading of the rules.
