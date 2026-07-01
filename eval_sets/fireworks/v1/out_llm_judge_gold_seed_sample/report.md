# Fireworks LLM Judge Gold Review

Generated: 2026-07-01T07:05:01.184316+00:00
Model: gpt-5.4-mini

## Counts

- reviewed: 12
- provisional_gold: 10
- needs_human_review: 2
- reject: 0

## By Task

- source_classification: 12

## Promotion Policy

- LLM-reviewed records are provisional, not final human gold.
- Promotion threshold is confidence >= 0.85 plus a provisional_gold decision.
- Cases with truncation, unclear provenance, or unsupported insight claims should remain needs_human_review.
- Training should use only human-approved or multi-judge consensus records.

## Sample Decisions

### fw_v1_source_classification_7d62543775a4 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is unambiguously from FireworksAI_HQ, the company's official account, and the content is promotional/event-related rather than user feedback. The predicted labels match the provenance and content, so this is suitable as gold.

### fw_v1_source_classification_9db4f727e274 (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The source is an official Fireworks AI account posting branded product/process content. The predicted labels align with provenance and content: official_brand, owned_official, technical_proof, and none for feedback type. No ambiguity requiring human review.

### fw_v1_source_classification_edf5e2495b2e (source_classification)

- decision: needs_human_review
- confidence: 0.97
- rationale: The provenance strongly indicates an official brand account, so the source-role/group labels are likely correct. But the post content is effectively absent (URL-only), making the thought_leadership/content_type label low-signal and not suitable for gold without human verification.
- human review: Source classification is plausible, but the content is too truncated to confidently gold-label content_type from text alone.

### fw_v1_source_classification_93d91dd24cef (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The provenance is clear: the post is authored by FireworksAI_HQ, an official brand account. That supports source_role=official_brand and source_group=owned_official. The content is company marketing about cost/performance and procurement-style value framing, so pricing_procurement is reasonable. No user feedback is present, so feedback_type=none is correct.

### fw_v1_source_classification_7199c4c0ca7b (source_classification)

- decision: needs_human_review
- confidence: 0.93
- rationale: The provenance is straightforward: the author is the official Fireworks AI account, so source_role and source_group are well supported. However, the case is explicitly flagged as requiring human review, and the content_type label is still a heuristic prelabel rather than a fully validated gold annotation. For benchmark gold, I prefer review when the case is not fully audited, even if the likely labels are correct.
- human review: Official-brand provenance is clear, but the case is only a heuristic prelabel and should be manually verified before promotion to gold.

### fw_v1_source_classification_4fd7e8be0d52 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is straightforward source classification: an official Fireworks AI account posts a launch announcement. There is no ambiguity about provenance or content type, and no user-feedback interpretation is needed.

### fw_v1_source_classification_8b3d65e76ec5 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The source is clearly the official Fireworks AI brand account, so source_role=official_brand and source_group=owned_official are well supported. The post is a community/event-style announcement referencing GTC and a CEO conversation, not user feedback. This is sufficiently unambiguous for gold.

### fw_v1_source_classification_0caaa5dbc83a (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The evidence is straightforward source classification: the author is the official Fireworks AI account, so source_role is official_brand and source_group is owned_official. The post is a product/technical methodology announcement with benchmark validation, fitting technical_proof. No user feedback is present, so feedback_type is none.

### fw_v1_source_classification_c1a884f9d346 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The provenance is unambiguous: the author is the official Fireworks AI account, so source_role is official_brand and source_group is owned_official. The post is company marketing with benchmark claims and product positioning, which fits technical_proof rather than user feedback. No correction is needed.

### fw_v1_source_classification_6ede02bf946d (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The post is from FireworksAI_HQ, an official brand account, and the content is a straightforward product launch announcement. No ambiguity or user-feedback interpretation is involved.

### fw_v1_source_classification_df9913b24072 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence clearly comes from an official brand account and is a product announcement. The predicted labels match the provenance and content: official_brand, owned_official, product_launch, and no feedback.

### fw_v1_source_classification_848123c3f1b5 (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The evidence clearly comes from the official Fireworks AI account and is a brand-authored promotional post citing benchmark performance. The predicted labels match the provenance and content. No ambiguity is present for source classification.
