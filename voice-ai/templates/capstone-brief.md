# Capstone brief: global edition

Steelyard Credit is a fictional lender; its numbers are illustrative. You may answer the capstone for either edition; this brief uses the global one, and the rubric's incident row scores against the T01-T10 log of the global world (`world/global/WORLD.md`, WG16). The India brief is in `capstone-brief.india.md`.

You are the staff engineer for evaluation at Steelyard Credit. Next quarter Hazel grows from 5 campaigns to 9 (a second PIL book, an SBL top-up campaign, and the first campaigns for Steelyard Credit UK Ltd and Steelyard Credit Espana S.L.). She grows from three language groups (English, Spanish-dominant, Spanglish) to five, with UK English and Spain Spanish handled by the bot for the first time, and from 2,400 to 6,000 peak concurrent calls. A speech-to-speech model, hazel-s2s-pilot, is being evaluated as a replacement for the cascade.

Dated rules to plan around (see WG10 of the world bible): the TCPA consent-revocation rule takes effect on 25 November 2026; on the Spain book, AI systems already on the market have until 2 December 2026 to mark synthetic audio under AI Act Article 50(2); CCD2's forbearance duty applies from 20 November 2026, with transposition still incomplete. Compliance wants evidence that no call reveals debt details before verification, that calling-window violations are zero, and that every stop request becomes a revocation event.

The CFO has capped eval spend at $75,000 a month. Today's plan costs about $45,673 and scales to about $75,698 at the new volume (WG20). Two vendors have pitched a managed testing platform. Write a design of no more than six pages plus an appendix of your memos (`eval-platform-design-doc.md`), and defend it in a 30-minute review with the head of engineering, the chief compliance officer and the CFO.

Cover:

1. Problem statement: the three incidents from T01-T10 that you consider most expensive, and why.
2. Data model: call, turn, span, audio segment, tool call, CRM diff, check result, label and judge score; the clock; versions; PII classes and retention per jurisdiction; how speech-to-speech traces differ.
3. Gold sets: contents, versioning, refresh and incident intake.
4. CI gates: per commit, nightly, pre-release and canary; gated metrics as interval rules; per-segment gating and multiplicity.
5. Simulation fleet: personas, audio-path parity, impairments, outbound coverage, simulator validation and audit rate, concurrency and cost.
6. Online sampling: checks on every call, strata and rates, human audit, how rates are reported, and rare-violation sizing for C07 and for the C04 judge backstop (C04's deterministic check reads every call).
7. Judge registry: fields, admission rule, status per language group (UK English and Spain Spanish included), revalidation triggers and ownership.
8. Cost budget: monthly cost by line from the WG20 unit costs, and cost per detected violation, inside the $75,000 cap.
9. Build vs buy for simulation, telephony impairment, load generation, judges, dashboards and labeling, with criteria (outbound support, Spanish and Spanglish fidelity, audio-path parity, UK and EU data handling, raw-result export, cost at volume) and exit terms.
10. Speech-to-speech: which evals disappear or must be rebuilt, and how you would run the comparison.
11. Incident coverage table: T01-T10, the component and gate that catch each one, and the expected time to detection.
12. Evidence from your own work: at least four outputs from the labs or exercises, for example your endpointing table from the endpointing lab or your judge registry entry from the judge validation lab.

Not legal advice: the compliance parts implement the fictional lender's reading of the rules.
