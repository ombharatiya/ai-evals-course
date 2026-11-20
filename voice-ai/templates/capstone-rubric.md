# Capstone rubric (100 points)

"Meets" is 70 points with no row at zero. "Strong" is 85. The capstone may be answered for either edition; the incident row scores against the T01-T10 log of the edition you pick, and the cost row against that edition's cap and unit costs.

| Row | Points | Meets | Strong |
|---|---|---|---|
| Incident coverage | 15 | Every trace in the chosen edition's log mapped to a component, a gate and a detection time | At least three caught by two independent components; detection times argued from cadence and sample size |
| Audio in the loop | 10 | STT, TTS, turn-taking and simulation evaluated on phone-path audio; wideband results never gate | A real 8 kHz holdout, live impairment tests, caller-heard latency taken from recordings |
| Entity and task metrics | 10 | Entity error rate on amounts and dates gated with intervals; CRM-diff task scoring per flow | Spoken checks kept apart from the diff; confirmation polarity; verified PTP |
| Latency and turn-taking | 10 | One vocabulary; P95 per turn type; an endpointing point per language group and campaign | Budgets per call state, consequence weighting, pinned SDKs, speech-to-speech implications |
| Statistics and gates | 10 | pass^k by the unbiased estimator; run counts from a power plan; paired gates per segment with Holm; clustered intervals | A canary that does not peek; zero-event bounds for compliance; no Wilson interval on differences or ratio metrics |
| Judge registry | 10 | Validation against human labels per language group and dimension; admission on the lower bound; revalidation triggers | Prevalence handled; gating vs advisory status; PPI for reported rates; no gating judge in a group not yet validated |
| Compliance as code | 10 | C01-C16 or an equivalent with types and inputs; cheap checks on every call; windows that know the product and location | Evidence of express requests, voice threat tests, a redaction audit, dated legal assumptions per jurisdiction |
| Production and rare events | 10 | Stratified sampling with sizing; drift signals; incident-to-regression with fail-first cases | Sizing shown for a 1-in-2,000 violation within a week; seasonal noise and carrier drift |
| Cost and build vs buy | 10 | A line-item budget inside the chosen edition's capstone cap from its unit costs; a decision per component with criteria | Cost per detected violation; exit terms; a list of what is never cut |
| Clarity under review | 5 | Six pages; decisions with their trade-offs; open risks named | Every number carries an interval or an as-of date |

Automatic deductions, 5 points each, whatever else the design gets right:

- stating a claim the course corrects in its uncorrected form (for example pass^8 at 80% given as anything other than 0.8^8, about 17%);
- a latency number with no start and end point;
- a judge used for gating without validation per language group;
- a vendor number with no "self-reported" label or as-of date;
- a Wilson interval on a difference or on WER.

## Score sheet

| Row | Points available | Your score | Evidence (section or appendix) |
|---|---|---|---|
| Incident coverage | 15 | | |
| Audio in the loop | 10 | | |
| Entity and task metrics | 10 | | |
| Latency and turn-taking | 10 | | |
| Statistics and gates | 10 | | |
| Judge registry | 10 | | |
| Compliance as code | 10 | | |
| Production and rare events | 10 | | |
| Cost and build vs buy | 10 | | |
| Clarity under review | 5 | | |
| Deductions | | | |
| Total | 100 | | |
