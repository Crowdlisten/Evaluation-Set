# Fireworks Eval and Training Plan

## What To Optimize First

Start with evaluation and SFT before RFT or DPO.

Reason: the biggest observed Fireworks failures are deterministic taxonomy and grounding errors:

- official marketing mislabeled as pain point or feature request
- product launches mislabeled as user feedback
- unsupported gaps inferred from missing launch details
- mixed clusters with multiple unrelated product or marketing themes

These are best fixed first with clearer labels, better prompts, and SFT-style structured examples.

## Stage 1: Frozen Eval

Use `out/cases.jsonl` as the frozen case source.

Primary evals:

1. Source classification
   - source role accuracy
   - source group accuracy
   - content type accuracy
   - feedback false-positive rate on official/employee content

2. Opinion-unit quality
   - atomicity
   - sentiment correctness
   - dimension usefulness
   - no fake feedback from marketing copy

3. Cluster membership
   - evidence membership F1
   - engagement-weighted precision
   - split/merge action accuracy
   - top-engagement misfit rate

4. Insight synthesis
   - category correctness
   - evidence fidelity
   - source-role awareness
   - unsupported claim rate
   - actionability

## Stage 2: Human Review

Review order:

1. `source_classification.jsonl`
2. `insight_packets.jsonl`
3. `opinion_unit_quality.jsonl`

Promote a record only when:

- `labels.review_status = "approved"`
- the reviewer agrees with source role, source group, content type, and feedback labels
- cluster packets have an explicit keep/rename/split/merge/discard decision
- every generated claim can be traced to evidence IDs

## Stage 3: SFT

Use SFT for structured tasks where there is one best answer:

- source classification JSON
- content type and feedback labels
- cluster action JSON
- grounded insight rewrite JSON

Good SFT target:

```json
{
  "source_role": "official_brand",
  "source_group": "owned_official",
  "content_type": "product_launch",
  "feedback_type": ["none"],
  "rationale": "Official product availability post; no direct user feedback."
}
```

SFT should use approved records only. Draft and predicted labels are for review queues, not training.

## Stage 4: DPO

Use DPO after the review set has enough plausible rejected answers.

Best DPO pairs:

- chosen: grounded, specific, source-aware, correctly categorized
- rejected: plausible but unsupported, over-broad, or source-role blind

Example rejected pattern:

- source evidence is official launch posts
- rejected answer says users are frustrated or requesting clearer workflow
- chosen answer classifies it as product launch or marketing narrative

DPO is useful for preference shaping, but it should not be the first fix because weak labels would teach style preferences without fixing taxonomy.

## Stage 5: RFT / Reward Training

Use RFT only after the rubric is stable and there are enough reviewed reward labels.

Reward should heavily penalize:

- unsupported claims
- official marketing treated as user feedback
- wrong source role
- wrong category
- missing evidence IDs
- split-worthy clusters treated as clean

Initial reward formula:

```text
0.25 * evidence_fidelity
+ 0.20 * category_correctness
+ 0.20 * source_role_awareness
+ 0.20 * cluster_membership
+ 0.15 * actionability
```

Hard-zero conditions:

- fabricated URL, source, author, or metric
- pain point or feature request from official-only evidence without quoted user feedback
- top-engagement evidence does not support the cluster

## Recommended Path

For the Fireworks case:

1. Use this eval set to quantify the current pipeline.
2. Fix taxonomy and prompt contracts.
3. Run SFT on approved structured examples.
4. Add DPO pairs from the audited synthesis variants.
5. Add RFT only after the grader reliably matches human review.

