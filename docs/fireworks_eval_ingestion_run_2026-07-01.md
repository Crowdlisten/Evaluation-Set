# Fireworks Eval Ingestion Run - 2026-07-01

## What Ran

Parallel discovery agents inspected the existing CrowdListen ingestion surfaces,
current Fireworks workspace entities, and the eval design needed for
cross-entity competitor synthesis.

The successful ingestion command was:

```bash
python3 knowledge/research/fireworks_workspace_trends_collect.py --push --trigger
```

It pushed new source batches through the CrowdListen agent ingest endpoint and
triggered enrichment for Fireworks, Baseten, Modal, and the broader open-source
model training topic entity.

## Ingestion Result

```json
{
  "fireworks": {
    "inserted": 21,
    "pipeline_triggered": true
  },
  "baseten": {
    "inserted": 18,
    "pipeline_triggered": true
  },
  "modal": {
    "inserted": 20,
    "pipeline_triggered": true
  },
  "topic": {
    "inserted": 205,
    "pipeline_triggered": true
  }
}
```

The recursive X/LinkedIn browser collector was attempted against the same
workspace but returned zero post links from native search, browser web fallback,
and official page crawling in the current local browser session.

Local environment status during that attempt:

```text
CROWDLISTEN_API_KEY=True
AGENT_URL=True
SUPABASE_URL=True
SUPABASE_SERVICE_ROLE_KEY=True
TWITTER_BEARER_TOKEN=False
SCRAPECREATORS_API_KEY=False
```

That means browser-only discovery was the only available X/LinkedIn path, and no
Twitter API or LinkedIn enrichment fallback was available.

## Eval Set Output

The durable processing sequence is:

```text
content_store raw source
-> source enhancement
-> opinion_units atomic opinion splitting
-> opinion-unit embeddings
-> hierarchical clustering
-> entity_insights + insight_evidence
-> eval packets
```

For eval generation, `content_store` is used for provenance, raw text, URLs,
sender/source role, platform, and engagement. `opinion_units` is used for the
actual atomic clustering and synthesis cases because one source can contain
multiple distinct claims or user opinions.

Curated Fireworks eval set:

```json
{
  "cases_total": 300,
  "source_classification_cases": 120,
  "opinion_unit_quality_cases": 100,
  "insight_packet_cases": 80,
  "sft_records": 12,
  "preference_records": 9,
  "reward_records": 48
}
```

Full Fireworks candidate pool:

```json
{
  "cases_total": 4540,
  "source_classification_cases": 792,
  "opinion_unit_quality_cases": 3560,
  "insight_packet_cases": 188,
  "sft_records": 12,
  "preference_records": 9,
  "reward_records": 48
}
```

Cross-entity competitor eval set:

```json
{
  "cases_total": 10,
  "competitors": 2,
  "comparison_axes": 5
}
```

Axes covered:

- serving/deployment workflow
- latency/performance/reliability
- pricing/procurement/cost
- developer experience/docs/onboarding
- fine-tuning/post-training

Competitors covered:

- Baseten
- Modal

## Validation

The generated `out/`, `out_full/`, and `out_cross_entity/` outputs passed local
integrity checks:

- no duplicate case IDs
- no empty evidence arrays
- no missing source IDs or text fields in evidence items
- no train/dev/test split overlap
- cross-entity cases contain target, competitor, and market evidence roles

## Remaining Coverage Gap

For complete X and LinkedIn coverage, the current local recursive browser path
needs either:

- a working browser session that can expose post URLs while scrolling official
  accounts and search results, or
- API fallback credentials:
  - `TWITTER_BEARER_TOKEN` for X search, post lookup, and reply coverage
  - `SCRAPECREATORS_API_KEY` for LinkedIn post/comment enrichment

Until one of those is available, the eval set is useful for quality and
attribution testing, but it should not be treated as exhaustive coverage of
everything Fireworks, Baseten, and Modal posted on X/LinkedIn.
