# CrowdListen Evaluation Set

Evaluation datasets, benchmark artifacts, and adjudication scripts for
CrowdListen.

CrowdListen turns raw market evidence into structured marketing intelligence:
source attribution, feedback labels, opinion units, clusters, insights,
competitor playbooks, and agent workflow outputs. This repository contains the
Fireworks v1 benchmark package used to test whether that pipeline is grounded,
source-aware, and safe to train against.

## What This Is

The Fireworks v1 package evaluates whether CrowdListen can:

- identify who is speaking: official, employee, affiliate, competitor, organic,
  creator, customer, or unknown
- classify what kind of content a source contains
- detect real user or market feedback without confusing it with owned marketing
- judge whether opinion units are atomic and faithful to their source
- test whether clusters are coherent or should be split, merged, renamed, or
  discarded
- synthesize insights that cite evidence instead of inventing buyer demand
- compare competitor playbooks while separating target, competitor, and
  independent market evidence
- support multi-turn agent workflows that retrieve evidence and produce
  marketing actions

The primary entity is **Fireworks AI**. Baseten and Modal are included as
competitor entities for cross-entity benchmark cases.

## Current Status

The candidate pool is **not gold by default**. It is a review backlog.

| Pack | Path | Count | Status |
| --- | --- | ---: | --- |
| Full candidate pool | `eval_sets/fireworks/v1/out_full/` | 4,540 cases | generated, not gold |
| Eval-ready pack | `eval_sets/fireworks/v1/out_eval_ready/` | 154 records | safe for eval/testing, not blanket training |
| Provisional gold | `eval_sets/fireworks/v1/out_gold_v1/` | 44 records | LLM-provisional source-classification gold |
| Human review backlog | `eval_sets/fireworks/v1/out_gold_review/` | 160 priority cases | review queue |
| Training blocklist | `eval_sets/fireworks/v1/out_gold_review/training_blocklist.jsonl` | 3,266 cases | do not train |

Generated labels should not be used as training labels unless they are promoted
to human-approved gold or multi-judge consensus gold.

## Repository Layout

```text
eval_sets/fireworks/v1/
  README.md                         # detailed package notes
  taxonomy.json                     # label taxonomy and decision rules
  schema.json                       # canonical eval case schema
  generate_eval_packets.py          # read-only exporter from CrowdListen data
  generate_cross_entity_packets.py  # competitor/market comparison exporter
  audit_ground_truth.py             # rule-based audit and blocklist builder
  llm_judge_gold.py                 # LLM-as-judge adjudication runner
  package_eval_ready.py             # curated eval-ready pack builder
  package_gold_from_judgments.py    # packages provisional gold records
  ground_truth_protocol.md          # promotion criteria
  gold_adjudication_protocol.md     # LLM/human/consensus gold policy
  training_plan.md                  # SFT, DPO, and RFT plan
  out/                              # curated generated cases
  out_full/                         # full generated candidate pool
  out_eval_ready/                   # safer eval/testing subset
  out_gold_review/                  # audit report, review queue, blocklist
  out_gold_v1/                      # current LLM-provisional gold pack
```

Additional design notes live in `docs/`.

## Task Families

### Source Classification

Input: one source with raw text, URL, author, platform, metrics, and current
metadata.

Output labels:

- `source_role_gold`
- `source_group_gold`
- `content_type_gold`
- `feedback_type_gold`

Critical failure: official or employee launch content labeled as user pain,
feature request, or organic market feedback without direct external feedback.

### Opinion-Unit Quality

Input: one extracted opinion unit plus its parent source.

Output labels:

- whether the opinion is atomic
- whether the sentiment and dimension are correct
- whether the parent source should have produced an opinion at all

Critical failure: turning owned marketing copy into fake user feedback.

### Cluster and Insight Synthesis

Input: a production insight plus linked evidence.

Output labels:

- `cluster_action_gold`: keep, rename, split, merge, discard
- `cluster_purity_gold`
- `insight_category_gold`
- evidence-level membership notes
- grounded rewritten insight where applicable

Critical failure: unsupported claims, source-role blindness, or a cluster whose
top-engagement evidence does not support the title.

### Cross-Entity Competitive Synthesis

Input: Fireworks evidence, competitor evidence, and independent market evidence.

Output requirements:

- separate target, competitor, and market evidence
- avoid winner claims without independent support
- cite evidence IDs for every material claim

Critical failure: treating Baseten or Modal owned marketing as independent
market evidence.

### Agent Workflow Evals

Input: a multi-turn task, such as finding trends Fireworks should respond to and
retrieving the supporting evidence.

Output requirements:

- retrieve relevant sources
- classify source roles
- separate official, affiliate, competitor, organic, and creator evidence
- produce a grounded recommendation with cited source IDs

## Quickstart

From the repository root:

```bash
python3 eval_sets/fireworks/v1/audit_ground_truth.py
```

Run an LLM-judge dry run:

```bash
python3 eval_sets/fireworks/v1/llm_judge_gold.py \
  --dry-run \
  --limit 8 \
  --per-task-limit 2 \
  --out-dir eval_sets/fireworks/v1/out_llm_judge_dry_run
```

Run a small real adjudication pass:

```bash
python3 eval_sets/fireworks/v1/llm_judge_gold.py \
  --limit 12 \
  --per-task-limit 3 \
  --out-dir eval_sets/fireworks/v1/out_llm_judge_sample
```

Package provisional gold from adjudications:

```bash
python3 eval_sets/fireworks/v1/package_gold_from_judgments.py \
  --judgments-dir eval_sets/fireworks/v1/out_llm_judge_source_seed_full \
  --out-dir eval_sets/fireworks/v1/out_gold_v1
```

The exporter scripts require CrowdListen database credentials. Generated JSONL
artifacts are already checked in for reproducible inspection.

## Gold Policy

This repository uses explicit gold status levels:

- `generated`: produced by the exporter or pipeline; not reviewed
- `deterministic_partial_gold`: provenance-only labels are deterministic
- `llm_provisional_gold`: one LLM judge approved the case
- `consensus_gold`: multiple judges agree, or one judge plus a human reviewer
  agree
- `human_gold`: human-reviewed and approved
- `needs_human_review`: useful but not safe to promote
- `reject`: keep only as a negative or blocklisted example

Use `llm_provisional_gold` for regression testing and reviewer bootstrapping.
Use only `human_gold` or `consensus_gold` for training.

## Known Limitations

- The full candidate pool includes noisy generated labels.
- Source coverage is strongest for existing Fireworks corpus rows and weaker for
  exhaustive X/LinkedIn history.
- Many opinion-unit candidates come from owned or employee marketing and should
  not be treated as independent user feedback.
- Cross-entity competitor cases are structural challenge evals, not final
  competitive-synthesis gold.
- LLM judge outputs are provisional and require human review or multi-judge
  consensus before final training use.

## Design References

This README follows common benchmark-package conventions used by established
eval repositories: clear task scope, dataset layout, quickstart commands, split
and gold-status notes, intended use, and limitations.

Useful reference projects:

- [SWE-bench](https://github.com/SWE-bench/SWE-bench)
- [OpenAI Evals](https://github.com/openai/evals)
- [Anthropic HH-RLHF](https://github.com/anthropics/hh-rlhf)
- [HELM](https://github.com/stanford-crfm/helm)

