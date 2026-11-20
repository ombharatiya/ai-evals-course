# Decision memo: <one line naming the decision>

Module: <number and title>. Edition: <global or India>. Author: <name>. Date: <YYYY-MM-DD>.

Keep it to one page. Every number carries an interval or an as-of date.

## 1. Decision

One sentence that states the number or the rule. Example shape: "Gate releases on the upper bound of the amount entity error rate per gated segment, at or below <threshold>, on the phone-path holdout."

## 2. Context

The flow, segment and traffic this applies to: campaigns, language groups, call states, volume per day, and the incident that prompted the decision (trace id if there is one).

## 3. Options considered

At least two options, each with the trade-off it makes.

| Option | What it buys | What it costs |
|---|---|---|
| A | | |
| B | | |

## 4. Evidence

What was measured, on what data, with intervals and the dataset or gold-set version. Name the lab or exercise output you used.

## 5. Owner and review cadence

Who owns the decision, and when it is reviewed (for example weekly, per release, or after a vendor change).

## 6. Tripwires

Observations that reopen the decision, each with a threshold and a window. Example shape: "false-cutoff rate in one language group above 4% at the chosen operating point for two weeks."

## 7. Dated facts

Every vendor or benchmark number used, with its as-of date, its source and whether it is self-reported.

| Fact | Value | As of | Source | Self-reported? |
|---|---|---|---|---|
| | | | | |
