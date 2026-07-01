# Fireworks LLM Judge Gold Review

Generated: 2026-07-01T07:09:38.183545+00:00
Model: gpt-5.4-mini

## Counts

- reviewed: 67
- provisional_gold: 44
- needs_human_review: 20
- reject: 3

## By Task

- source_classification: 67

## Promotion Policy

- LLM-reviewed records are provisional, not final human gold.
- Promotion threshold is confidence >= 0.85 plus a provisional_gold decision.
- Cases with truncation, unclear provenance, or unsupported insight claims should remain needs_human_review.
- Training should use only human-approved or multi-judge consensus records.

## Sample Decisions

### fw_v1_source_classification_7d62543775a4 (source_classification)

- decision: needs_human_review
- confidence: 0.98
- rationale: The source classification is straightforward: the author is the official Fireworks AI account, so source_role should be official_brand and source_group should be owned_official. However, the content is promotional/event-related marketing, not feedback from external users. Because the benchmark policy says not to treat official marketing as user feedback, this case should not be promoted as gold without human confirmation of the intended labeling scheme.
- human review: Official brand marketing post; content_type is plausible, but the case is not suitable for automatic gold promotion because it is not user feedback and the label set may be intended for feedback-oriented classification.

### fw_v1_source_classification_9db4f727e274 (source_classification)

- decision: provisional_gold
- confidence: 0.96
- rationale: The evidence is a post from the company's official X account promoting a blog about TDD for AI agents and evals. This cleanly supports source_role=official_brand and source_group=owned_official. The content is technical proof/marketing content, not user feedback, so feedback_type=none is appropriate.

### fw_v1_source_classification_edf5e2495b2e (source_classification)

- decision: needs_human_review
- confidence: 0.97
- rationale: The provenance strongly supports official brand / owned official classification. But the content itself is effectively unreadable beyond a link, so while the predicted labels are likely correct, this is not ideal benchmark gold without human verification of the underlying post content.
- human review: Truncated low-signal post text makes content-type labeling less robust than source classification; verify the linked content before promoting to gold.

### fw_v1_source_classification_93d91dd24cef (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The provenance is clear: the post is authored by FireworksAI_HQ, an official brand account, so source_role_gold=official_brand and source_group_gold=owned_official are correct. The content is a marketing/proof-point post about pricing/performance comparisons and procurement-style value framing, so pricing_procurement fits. No evidence suggests user feedback or another source class.

### fw_v1_source_classification_7199c4c0ca7b (source_classification)

- decision: needs_human_review
- confidence: 0.93
- rationale: The provenance is clear: the author is FireworksAI_HQ, an official brand account, so source_role=official_brand and source_group=owned_official are well supported. However, the content_type label partner_integration is somewhat heuristic because the post mentions partners but is not a concrete integration announcement or product documentation. This is suitable for human review rather than gold promotion.
- human review: Content type is borderline: the post references partners but does not clearly announce or describe a partner integration in a way that is unambiguous for benchmark gold.

### fw_v1_source_classification_4fd7e8be0d52 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is straightforward: an official Fireworks AI account posts about a product launch collaboration. Source role and group are unambiguous, and the content type is correctly labeled as product_launch. No user feedback is present, so feedback_type none is appropriate.

### fw_v1_source_classification_8b3d65e76ec5 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The post is authored by FireworksAI_HQ, an official brand account, so the source role is official_brand and source group is owned_official. The content is a public event/community post rather than user feedback, and the generated labels match the evidence cleanly.

### fw_v1_source_classification_0caaa5dbc83a (source_classification)

- decision: needs_human_review
- confidence: 0.93
- rationale: The source classification appears correct: the author is the official Fireworks AI account, so source_role_gold=official_brand and source_group_gold=owned_official are well supported. However, the case is flagged for human review because the content is promotional marketing/technical proof and should not be over-interpreted as feedback. Since benchmark gold should be conservative, this is better reviewed before promotion.
- human review: Official-brand marketing content is correctly classified, but the case is promotional and may be noisy for benchmark gold without additional context.

### fw_v1_source_classification_c1a884f9d346 (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The evidence is straightforward source classification: an official Fireworks AI account posting benchmark/performance claims about its own product. This supports official_brand and owned_official with high confidence. Content type is technical_proof rather than user feedback, and feedback_type is none.

### fw_v1_source_classification_6ede02bf946d (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is unambiguous: the author is the official Fireworks AI account, the sender type is official, and the post is a product announcement rather than user feedback. The predicted labels match the provenance and content, so this is suitable as benchmark gold.

### fw_v1_source_classification_df9913b24072 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is a direct post from FireworksAI_HQ, an official brand account, announcing a product launch. The predicted source role and group are correct, and the content type is clearly product_launch. No ambiguity or conflicting evidence is present.

### fw_v1_source_classification_848123c3f1b5 (source_classification)

- decision: provisional_gold
- confidence: 0.96
- rationale: The evidence is clearly from Fireworks AI's official account and is self-promotional marketing about its own product. The source role and group are unambiguous, and the content is best labeled technical_proof rather than user feedback.

### fw_v1_source_classification_5c89da8574c8 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The post is from FireworksAI_HQ, an official brand account, and the content is promotional/tutorial guidance for FireConnect. The source classification is unambiguous: official_brand within owned_official. No user feedback is being inferred.

### fw_v1_source_classification_e15c1f0c4e54 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is straightforward: an official Fireworks AI account posted a short brand statement on X. The predicted labels match the provenance and content type. No ambiguity or conflicting evidence is present.

### fw_v1_source_classification_b392c60bd272 (source_classification)

- decision: provisional_gold
- confidence: 0.96
- rationale: The evidence is straightforward: the author is FireworksAI_HQ, which maps to official_brand and owned_official. The post presents benchmark/performance claims and product rollout information, fitting technical_proof. No ambiguity or conflicting evidence is present.

### fw_v1_source_classification_7134e1e327bd (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The evidence is unambiguous: the author is the official Fireworks AI account, so source_role is official_brand and source_group is owned_official. The post is promotional/announcement-style content, fitting product_launch rather than user feedback. No correction is needed.

### fw_v1_source_classification_83cb552a1605 (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The provenance is unambiguous: the author is the official Fireworks AI account, and the content is branded commentary plus a link to a company blog. The predicted labels match the evidence, and there is no indication of external user feedback or mixed attribution.

### fw_v1_source_classification_e42c8472909a (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The evidence is clearly from the target company’s official account and is promotional/educational company content, not external user feedback. The predicted labels match the provenance and content well, with no ambiguity requiring review.

### fw_v1_source_classification_87f8baee9bbf (source_classification)

- decision: provisional_gold
- confidence: 0.97
- rationale: The evidence is clearly an official Fireworks AI account posting company-authored technical content. The predicted labels match the provenance and content type, and there is no ambiguity requiring human review.

### fw_v1_source_classification_a9016be4e834 (source_classification)

- decision: provisional_gold
- confidence: 0.98
- rationale: The source is unambiguously an official brand account for Fireworks AI. The content is promotional/announcement-style and fits product_launch better than technical_proof because it advertises an event and upcoming product updates rather than presenting evidence or a technical demonstration. Source role and group are correct as given.
