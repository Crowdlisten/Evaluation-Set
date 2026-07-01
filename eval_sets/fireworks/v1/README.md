# Fireworks Case Study Package v1

This package defines the first versioned CrowdListen case-study corpus. It uses
the Fireworks entity and the surrounding open-model inference market as a sample
for evaluating the broader CrowdListen benchmark suite.

The immediate goal is to test and improve:

- source categorization: who posted it and where it belongs in the UI
- content categorization: what kind of source it is
- feedback detection: whether the source actually contains pain, requests, objections, praise, or no feedback
- cluster quality: whether evidence inside a cluster is truly about the same thing
- insight synthesis: whether the generated insight is grounded, source-aware, and useful

The dataset is local and read-only against production. Generation pulls from Supabase but only writes local JSONL files.

## Pipeline Shape

The production entity pipeline is:

```text
raw content_store row
-> source enhancement
-> opinion_units atomic opinion splitting
-> opinion-unit embeddings
-> hierarchical clustering
-> entity_insights + insight_evidence
-> eval packets
```

Use `content_store` for source provenance, raw context, URLs, sender role,
platform, and metrics. Use `opinion_units` for clustering and synthesis evals:
one post, thread, or video can contain multiple distinct claims, and those
should be judged independently before they are clustered.

## Entity

- Entity: Fireworks AI
- Entity ID: `86e21e31-35d9-46a9-9999-527e6c227dfa`
- Primary current corpus: X/Twitter official, employee, creator, competitor, organic, LinkedIn, Hacker News, and web sources

## Files

- `taxonomy.json`: versioned label system and decision rules
- `schema.json`: JSON Schema for canonical eval cases
- `competitors.json`: target/competitor entity map for Fireworks, Baseten, and Modal
- `generate_eval_packets.py`: read-only Supabase exporter and draft labeler
- `generate_cross_entity_packets.py`: read-only exporter for competitor attribution and synthesis evals
- `audit_ground_truth.py`: eval audit, blocklist, review queue, and partial gold seed generator
- `package_eval_ready.py`: packages the safest records for immediate eval runs
- `ground_truth_protocol.md`: criteria for promoting draft labels to gold
- `out/cases.jsonl`: generated canonical cases
- `out_cross_entity/cases.jsonl`: generated cross-entity competitor cases
- `out_gold_review/review_queue.jsonl`: prioritized human review queue
- `out_gold_review/training_blocklist.jsonl`: cases excluded from training until corrected
- `out_gold_review/gold_seed.source_classification.jsonl`: partial source-provenance gold seed
- `out_eval_ready/`: high-confidence eval pack for immediate testing
- `out/source_classification.jsonl`: generated source-role eval cases
- `out/opinion_unit_quality.jsonl`: generated opinion-unit eval cases
- `out/insight_packets.jsonl`: generated cluster/synthesis eval cases
- `out/labels.sft.jsonl`: audited or draft supervised examples
- `out/labels.preference.jsonl`: preference pairs derived from audited synthesis runs
- `out/labels.reward.jsonl`: reward labels derived from audited synthesis runs
- `out/manifest.json`: generation counts, hashes, and source corpus stats
- `out/splits.json`: case-level train/dev/test split
- `out/leakage_index.json`: source/text/url hashes used to block leakage

The `out/` files are generated artifacts. Regenerate them from the current database when the corpus changes.

## Eval Tasks

### 1. Source Classification

Input: one `content_store` item with raw text, URL, author, metadata, and metrics.

Gold labels:

- `source_role_gold`
- `source_group_gold`
- `content_type_gold`
- `feedback_type_gold`

Critical failure:

- Official or employee launch content labeled as user pain or feature request without direct user feedback.

### 2. Opinion Unit Quality

Input: one `opinion_units` row plus its parent source.

Gold labels:

- whether the extracted opinion is atomic
- whether sentiment is correct
- whether the dimension is useful
- whether the parent source should have produced an opinion at all

Critical failure:

- Turning pure marketing copy into fake user feedback.

### 3. Cluster Membership

Input: one `entity_insights` row plus linked evidence.

Gold labels:

- `cluster_action_gold`: keep, rename, split, merge, discard
- `cluster_purity_gold`
- `insight_category_gold`
- `gold_groups`
- evidence-level membership and failure modes

Critical failure:

- A cluster whose top-engagement evidence is unrelated to the title or category.

### 4. Insight Synthesis

Input: same cluster packet, plus current production insight.

Gold output:

- a grounded title
- corrected category
- concise description
- source-aware rationale
- optional recommended action

Critical failure:

- Unsupported claims, absence-as-evidence, or collapsing official messaging into user demand.

### 5. Preference and Reward Labels

Use the prior Fireworks synthesis audit to derive:

- SFT records from high-scoring audited outputs
- DPO pairs from chosen vs rejected synthesis outputs
- reward labels from rubric scores

These are derived views over the same `case_id`. Splits are by case, not by label file.

### 6. Cross-Entity Competitive Synthesis

Input: paired Fireworks, competitor, and independent market evidence across one
comparison axis.

Gold labels:

- `comparison_axis_gold`
- entity-aware evidence groups for target, competitor, and market evidence
- source-role and entity-attribution failure modes

Critical failure:

- Treating Baseten or Modal owned marketing as independent market evidence, or
  making a winner claim without independent support.

## Metrics

Recommended gates for a clustering/synthesis run:

- evidence membership F1 >= 0.88
- engagement-weighted precision >= 0.92
- split/merge action accuracy >= 0.80
- category macro F1 >= 0.84
- critical category confusion rate <= 0.05
- claim support precision >= 0.90
- unsupported claim rate <= 0.10
- role-compatible category rate >= 0.95
- no top-engagement source is a clear misfit

Overall gate:

```text
0.25 * membership_f1
+ 0.20 * split_merge_f1
+ 0.20 * category_macro_f1
+ 0.25 * claim_support_precision
+ 0.10 * role_compatible_rate
>= 0.88
```

## Generation

From the repo root:

```bash
python3 eval_sets/fireworks/v1/generate_eval_packets.py \
  --out-dir eval_sets/fireworks/v1/out
```

The curated v1 set intentionally defaults to 300 cases for fast review. To
generate the full candidate pool from every currently available Fireworks source,
opinion unit, and insight packet:

```bash
python3 eval_sets/fireworks/v1/generate_eval_packets.py \
  --source-target 10000 \
  --opinion-target 10000 \
  --insight-target 10000 \
  --out-dir eval_sets/fireworks/v1/out_full
```

As of the 2026-07-01 run, the full existing-corpus ceiling is:

- 4,540 total cases
- 792 unique source classification cases after URL/text dedupe
- 3,560 opinion-unit quality cases
- 188 insight/cluster packets
- 12 audited SFT records
- 9 audited DPO preference records
- 48 audited reward records

The source-side ceiling is lower than the raw `content_store` count because some
rows share a URL or normalized text. The full candidate pool is best treated as a
review backlog; use the curated `out/` set for fast regression checks.

To generate cross-entity competitor eval cases from Fireworks plus the ingested
Baseten and Modal entities:

```bash
python3 eval_sets/fireworks/v1/generate_cross_entity_packets.py \
  --out-dir eval_sets/fireworks/v1/out_cross_entity
```

As of the 2026-07-01 run, `out_cross_entity/` contains 10 draft cases: Baseten
and Modal across serving/deployment workflow, latency/performance/reliability,
pricing/procurement/cost, developer experience/docs/onboarding, and
fine-tuning/post-training.

To audit ground-truth readiness and generate the review queue/blocklist:

```bash
python3 eval_sets/fireworks/v1/audit_ground_truth.py \
  --out-dir eval_sets/fireworks/v1/out_gold_review
```

As of the 2026-07-01 audit:

- 4,550 cases audited
- 160 cases in the review queue
- 3,266 cases blocklisted from training until corrected
- 67 partial source-provenance gold records

The partial gold seed only approves deterministic provenance fields
(`source_role_gold`, `source_group_gold`, `feedback_type_gold`). It does not
approve content type, opinion quality, cluster membership, or synthesis labels.

To package the safest eval records for immediate testing:

```bash
python3 eval_sets/fireworks/v1/package_eval_ready.py \
  --out-dir eval_sets/fireworks/v1/out_eval_ready
```

As of the 2026-07-01 blocklist-filtered package, `out_eval_ready/` contains 100
records and zero case IDs from `out_gold_review/training_blocklist.jsonl`:

- 64 partial-gold source provenance checks
- 4 audited SFT-style grounded insight synthesis checks
- 2 audited DPO-style preference pairs
- 16 audited RFT/reward-style labels
- 10 cross-entity structural competitor checks
- 4 derived multi-turn workflow checks

50 records from the earlier eval-ready candidate pack were excluded because
their `case_id` appears in the training blocklist. Those exclusions are written
to `out_eval_ready/excluded_blocklisted.jsonl` for inspection.

## Latest Ingestion Run

The latest successful ingestion path was the Fireworks workspace trends
collector:

```bash
python3 knowledge/research/fireworks_workspace_trends_collect.py --push --trigger
```

It pushed 21 Fireworks, 18 Baseten, 20 Modal, and 205 topic-level sources through
the agent ingest endpoint and triggered enrichment. The recursive X/LinkedIn
browser collector was also attempted, but the current local browser session
returned zero discoverable post links from native search, web fallback, and
official pages. The missing local API keys at that point were
`TWITTER_BEARER_TOKEN` and `SCRAPECREATORS_API_KEY`, so X reply/comment coverage
and LinkedIn post/comment enrichment were not available through API fallback.

The script loads `.env` by default and expects:

```bash
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

It does not write to Supabase.

## Labeling Workflow

1. Generate draft packets from production data.
2. Review `source_classification.jsonl` first to fix source-role and content-type labels.
3. Review `insight_packets.jsonl` next, starting with records that have `failure_modes`.
4. Promote reviewed records by setting `labels.review_status` to `approved`.
5. Export only approved records for SFT/DPO/RFT.
6. Keep frozen test case IDs out of training.

## Training Use

Use SFT first for deterministic structured outputs:

- source classification JSON
- cluster action JSON
- grounded insight rewrite JSON

Use DPO second when we have high-quality chosen/rejected pairs:

- chosen is grounded, source-aware, correctly categorized
- rejected is plausible but unsupported, over-broad, or category-blind

Use RFT/reward training after the rubric is stable:

- reward should penalize unsupported claims and source-role mistakes heavily
- do not optimize directly on unreviewed draft labels
