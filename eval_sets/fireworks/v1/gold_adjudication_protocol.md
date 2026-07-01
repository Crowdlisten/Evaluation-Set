# Fireworks Gold Adjudication Protocol

Date: 2026-07-01

## Goal

Turn the Fireworks candidate eval pool into a frontier-quality benchmark without
silently promoting noisy generated labels.

The candidate pool is not gold by default. It is a review backlog.

Current candidate pool:

- 4,550 total cases
- 792 source classification cases
- 3,560 opinion-unit cases
- 188 insight/cluster cases
- 10 cross-entity competitor cases

Current issue:

Many cases are useful for finding failures, but not safe for training or
benchmark gold. In particular, official/employee marketing is often converted
into feedback-like opinion units or user-demand insights.

## Gold Status Levels

### generated

Produced by the exporter or pipeline. Not reviewed.

### deterministic_partial_gold

Provenance-only labels are safe because URL/account/author is unambiguous.

Allowed fields:

- source_role_gold
- source_group_gold
- feedback_type_gold when provenance makes feedback impossible, e.g. official
  brand launch post with no quoted external feedback

Not automatically allowed:

- content_type_gold
- opinion quality
- cluster purity
- insight synthesis

### llm_provisional_gold

One LLM judge reviewed the case with the rubric and found it safe.

This is useful for regression testing, but not final training gold unless
paired with human approval or multi-judge consensus.

### consensus_gold

Two or more independent judges agree, or one LLM judge and one human reviewer
agree, with no critical failure modes.

This is acceptable for eval gold.

### human_gold

Human reviewer approved the labels and rationale.

This is acceptable for eval and training.

### needs_human_review

Potentially useful, but not safe to promote because the source is low-signal,
truncated, ambiguous, or needs external context.

### reject

Do not use as benchmark gold or training data. Keep it only as a failure example
or blocklist record.

## LLM Judge Runner

Script:

```bash
python3 eval_sets/fireworks/v1/llm_judge_gold.py \
  --limit 40 \
  --per-task-limit 10 \
  --out-dir eval_sets/fireworks/v1/out_llm_judge
```

Dry run:

```bash
python3 eval_sets/fireworks/v1/llm_judge_gold.py \
  --dry-run \
  --limit 8 \
  --per-task-limit 2 \
  --out-dir eval_sets/fireworks/v1/out_llm_judge_dry_run
```

The runner writes:

- `manifest.json`
- `adjudications.jsonl`
- `failures.jsonl`
- `report.md`

It does not mutate generated cases.

## Judge Rubric

The judge must:

1. Use provenance before interpreting text.
2. Separate official, employee, affiliate, competitor, organic, and customer
   evidence.
3. Reject official/employee/competitor marketing as user feedback unless the
   evidence quotes or summarizes external users.
4. Reject insights that infer buyer demand from missing product detail.
5. Require claim-to-evidence support.
6. Keep competitor claims separate from target claims and independent market
   evidence.
7. Mark truncated or URL-only cases as human review unless only source-role
   provenance is being evaluated.

Promotion threshold:

- decision must be `provisional_gold`
- confidence must be at least 0.85
- no hard failure mode

Hard failure modes:

- official_marketing_as_feedback
- source_role_blindness
- unsupported_inference
- competitor_marketing_as_market_feedback
- winner_claim_without_independent_evidence
- mixed_entity_cluster
- fabricated source, URL, author, or metric

## Actual Sample Runs

### High-risk stratified sample

Command:

```bash
python3 eval_sets/fireworks/v1/llm_judge_gold.py \
  --limit 12 \
  --per-task-limit 3 \
  --out-dir eval_sets/fireworks/v1/out_llm_judge_sample
```

Result:

- 12 reviewed
- 0 provisional gold
- 5 needs human review
- 7 rejected

Interpretation:

This confirms the candidate pool contains real failure cases. The riskiest
opinion and insight candidates should not be promoted. They are useful as
negative evals, review tasks, and regression failures.

### Deterministic source-provenance seed sample

Command:

```bash
python3 - <<'PY'
import json, pathlib, subprocess, sys
base = pathlib.Path("eval_sets/fireworks/v1")
ids = []
for line in (base / "out_gold_review/gold_seed.source_classification.jsonl").read_text().splitlines():
    if line.strip():
        ids.append(json.loads(line)["case_id"])
cmd = [sys.executable, str(base / "llm_judge_gold.py"), "--out-dir", str(base / "out_llm_judge_gold_seed_sample")]
for cid in ids[:12]:
    cmd += ["--case-id", cid]
raise SystemExit(subprocess.call(cmd))
PY
```

Result:

- 12 reviewed
- 10 provisional gold
- 2 needs human review
- 0 rejected

Interpretation:

The judge can promote clean source-provenance cases while refusing low-signal
content-type labels. This is the right behavior for frontier-quality data.

## Frontier-Quality Build Plan

### Phase 1: Freeze a small gold benchmark

Create `out_gold_v1/` from adjudicated records:

- 200 source role/source group cases
- 200 content type cases
- 150 feedback detection cases
- 50 opinion splitting cases
- 50 cluster membership cases
- 50 insight synthesis cases
- 20 competitor playbook cases
- 10 multi-turn agent workflow cases

### Phase 2: Add consensus

Run at least two independent judge passes:

- strict provenance judge
- market-insight judge
- optional human reviewer for disagreements

Promote only when labels agree or a human resolves the disagreement.

### Phase 3: Human review the hard cases

Prioritize:

1. high-engagement organic market sources
2. LinkedIn posts with full comment context
3. HN/Reddit threads with discussion depth
4. competitor official posts
5. mixed clusters with high business value

### Phase 4: Build negative evals deliberately

Do not discard all rejected cases. Keep a negative benchmark for:

- official launch mislabeled as feature request
- employee post mislabeled as user pain
- competitor marketing treated as independent market evidence
- mixed clusters kept as pure
- unsupported winner claims

### Phase 5: Training readiness

Use records only when:

- human_gold or consensus_gold
- evidence IDs are preserved
- labels have reviewer notes
- train/dev/test leakage is blocked by URL/text/source-set hash

Recommended training order:

1. SFT for source role, source group, content type, feedback detection.
2. SFT for grounded insight JSON only after cluster gold exists.
3. DPO for chosen/rejected insight pairs where the rejected answer is a known
   failure.
4. RFT only after the reward grader has been calibrated against human labels.

## What This Means For The Current Pool

The current candidate pool cannot be declared gold case by case yet. It can be
processed case by case, but the first LLM pass shows:

- clean provenance cases are goldable
- high-risk insight and opinion cases are mostly not goldable
- cross-entity competitor cases need fuller evidence visibility before golding
- low-signal URL-only posts should not receive content-type gold

The next practical step is to run the judge over all 67 deterministic source
gold seed cases, then expand into organic-market and competitor cases with
multi-judge consensus.

