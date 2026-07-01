# Fireworks Ground Truth Protocol

## Principle

Gold data must separate provenance facts from interpretive labels.

Provenance labels can be deterministic when the URL, author, or account clearly
identifies the speaker. Opinion quality, insight category, cluster membership,
and competitive synthesis require evidence-level review before training.

## Current Gold State

Generated files:

- `out_gold_review/audit_report.md`: human-readable audit summary
- `out_gold_review/audit_report.json`: machine-readable audit summary
- `out_gold_review/audit_cases.jsonl`: every eval case with risk flags
- `out_gold_review/review_queue.jsonl`: 160 prioritized cases for human review
- `out_gold_review/training_blocklist.jsonl`: cases excluded from training until corrected
- `out_gold_review/gold_seed.source_classification.jsonl`: partial gold seed for deterministic source provenance

The source-classification seed is partial gold only:

- approved fields: `source_role_gold`, `source_group_gold`, `feedback_type_gold`
- not approved: `content_type_gold`
- training flag: `source_provenance_ready=true`
- `sft_ready=false` until full label review is complete

## What Is Blocked

Do not train on any case in `training_blocklist.jsonl`.

Primary blockers found in the Fireworks pass:

- owned or employee marketing converted into user-feedback opinion units
- positive company claims treated as independent sentiment
- insight clusters with only official evidence framed as market demand
- unknown LinkedIn speaker roles
- low-signal X rows where only a t.co link was captured

## Promotion Rules

A case can move to `approved` only when:

1. The speaker/source role is verified from URL, account, or author.
2. The source group is verified independently from the content interpretation.
3. For opinion units, the opinion is atomic, faithful, non-duplicative, and not
   merely vendor marketing unless the task is explicitly marketing narrative.
4. For insight clusters, every evidence item supports the title and category.
5. For competitive synthesis, target, competitor, and market evidence are not
   conflated, and winner claims require independent evidence.
6. Any corrected labels are written back into the eval JSONL with
   `labels.review_status="approved"` and a reviewer note.

## Training Policy

Use these gates:

- source-role classifier: may use records with `source_provenance_ready=true`
  only for source role/source group supervision.
- content-type classifier: requires reviewed `content_type_gold`.
- opinion splitter/quality model: requires reviewed opinion-unit labels.
- clustering/synthesis/RFT: requires approved insight or cross-entity cases.
- DPO/RFT: use only approved chosen/rejected pairs or approved rubric scores.

Draft, predicted, or blocklisted cases are evaluation/review material only.
