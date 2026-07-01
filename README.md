# CrowdListen Evaluation Set

Versioned evaluation artifacts for CrowdListen.

## Fireworks v1

The current package lives under `eval_sets/fireworks/v1/` and includes:

- source classification cases
- opinion-unit quality cases
- insight and cluster packets
- cross-entity competitor packets
- audited SFT, DPO, and reward-label views
- LLM-judge adjudication outputs
- provisional gold source-classification records

The candidate pool is not gold by default. Use `out_gold_v1/` for the current
LLM-provisional gold pack, and use `out_gold_review/` plus the LLM judge outputs
as review backlogs.

Key docs:

- `eval_sets/fireworks/v1/README.md`
- `eval_sets/fireworks/v1/gold_adjudication_protocol.md`
- `eval_sets/fireworks/v1/ground_truth_protocol.md`
- `docs/crowdlisten_eval_benchmark_design_2026-07-01.md`

## Current Counts

As of the Fireworks v1 package:

- 4,550 candidate cases
- 154 eval-ready records
- 44 LLM-provisional source-classification gold records
- 3,266 blocklisted training candidates pending correction/review

## Safety

Generated labels are not automatically training labels. Training should use only
human-approved or multi-judge consensus records.

