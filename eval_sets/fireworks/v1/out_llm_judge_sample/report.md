# Fireworks LLM Judge Gold Review

Generated: 2026-07-01T07:03:53.272605+00:00
Model: gpt-5.4-mini

## Counts

- reviewed: 12
- provisional_gold: 0
- needs_human_review: 5
- reject: 7

## By Task

- cross_entity_competitive_synthesis: 3
- insight_synthesis: 3
- opinion_unit_quality: 3
- source_classification: 3

## Promotion Policy

- LLM-reviewed records are provisional, not final human gold.
- Promotion threshold is confidence >= 0.85 plus a provisional_gold decision.
- Cases with truncation, unclear provenance, or unsupported insight claims should remain needs_human_review.
- Training should use only human-approved or multi-judge consensus records.

## Sample Decisions

### fw_v1_cross_entity_competitive_synthesis_e77f748a8586 (cross_entity_competitive_synthesis)

- decision: needs_human_review
- confidence: 0.93
- rationale: This is a cross-entity competitive synthesis draft, but the provided evidence is overwhelmingly owned/official marketing from Fireworks AI. The case description explicitly asks for independent market evidence and attribution uncertainty, yet the visible evidence does not establish independent market feedback or competitor-side claims for Baseten. Because official marketing should not be treated as user feedback and the independent evidence is not verifiable from the supplied excerpts, the case is not gold-ready.
- human review: Need verification of the Baseten evidence set and the independent market evidence set; current excerpt only shows Fireworks-owned sources and does not prove balanced cross-entity synthesis.

### fw_v1_cross_entity_competitive_synthesis_e22f4a545871 (cross_entity_competitive_synthesis)

- decision: needs_human_review
- confidence: 0.93
- rationale: This is a cross-entity competitive synthesis draft, but the provided evidence is overwhelmingly owned/official marketing from Fireworks AI and the Baseten/independent evidence is not visible in the prompt beyond IDs. That makes attribution and comparative support impossible to verify at gold level. The case should not be promoted without checking the competitor and independent sources and ensuring claims are grounded in non-marketing evidence where required.
- human review: Need to verify the missing competitor and independent evidence, and confirm whether the comparison is supported by non-official sources rather than vendor marketing.

### fw_v1_cross_entity_competitive_synthesis_d615319d56e7 (cross_entity_competitive_synthesis)

- decision: needs_human_review
- confidence: 0.93
- rationale: The case is not gold-ready because the provided evidence is overwhelmingly official/owned Fireworks material, with no visible Baseten evidence in the supplied input and no clearly independent market evidence supporting comparative conclusions. The generated labels also appear to assume competitor and market groups without verifiable evidence in the prompt, which is an unsupported inference and source-role attribution problem. This should be human-reviewed before benchmark promotion.
- human review: Need verification of the missing Baseten evidence set and the claimed independent market evidence; current input only substantiates Fireworks official claims.

### fw_v1_insight_synthesis_b1caeb8665ed (insight_synthesis)

- decision: reject
- confidence: 0.98
- rationale: This cluster is built almost entirely from owned-official or affiliated marketing claims, with no independent customer/prospect evidence. The current label 'pain_point' is unsupported; the content is closer to competitive marketing claims, but even that should not be benchmark gold because the cluster is mixed and not valid feedback. The correct action is discard, not rename or keep.
- human review: None needed; the case is clearly invalid for gold due to provenance and cluster composition.

### fw_v1_insight_synthesis_94e4b4f9be3e (insight_synthesis)

- decision: reject
- confidence: 0.98
- rationale: The cluster is composed entirely of owned official and affiliated insider posts. It does not contain independent customer or market feedback, so the inferred 'pain_point' insight is unsupported. The proposed migration playbook need is an inference from marketing claims about global scaling, not evidence of buyer objections or workflow gaps. This is a mixed marketing cluster and should not be promoted to gold.

### fw_v1_insight_synthesis_0da1d1348d8a (insight_synthesis)

- decision: reject
- confidence: 0.98
- rationale: All evidence is owned-official marketing from Fireworks AI. The proposed insight infers a customer feature request and rollout pain from promotional posts, which is unsupported. This is not valid market feedback and should not be benchmark gold.

### fw_v1_opinion_unit_quality_eeea2f8c6ad5 (opinion_unit_quality)

- decision: reject
- confidence: 0.98
- rationale: This is official marketing content from the target company, not external feedback. The generated label treats a promotional performance claim as an opinion unit, but benchmark gold should not promote owned-brand marketing as user sentiment or feedback. The claim also lacks independent evidence and is too short to serve as a reliable opinion example.

### fw_v1_opinion_unit_quality_ed1803fa8c6a (opinion_unit_quality)

- decision: reject
- confidence: 0.98
- rationale: This is not a valid opinion-unit quality gold case because the quoted opinion comes from an official brand account and is part of marketing/technical explainer content. Benchmark gold should not treat owned-official promotional language as user opinion. The snippet is also too short and generic to serve as a robust opinion unit.

### fw_v1_opinion_unit_quality_d944aca34779 (opinion_unit_quality)

- decision: reject
- confidence: 0.98
- rationale: This is not benchmark-gold opinion-unit quality material because the source is an employee/affiliated insider and the statement is essentially technical commentary/marketing-adjacent opinion rather than independent market feedback. The generated label set is also incomplete for this task and the case is explicitly flagged as draft with issues. Better to reject than promote a noisy label.

### fw_v1_source_classification_faa3ce9b63db (source_classification)

- decision: reject
- confidence: 0.98
- rationale: The evidence is a company LinkedIn post announcing a product availability update. That makes the source an official brand/owned official source, not unknown. The generated labels misclassify both source role and source group, and the feedback label is unsupported because there is no user feedback in the post. This is not suitable as benchmark gold for source classification.

### fw_v1_source_classification_f5aa272896f7 (source_classification)

- decision: needs_human_review
- confidence: 0.94
- rationale: The provenance is clear: the post comes from the official Fireworks AI account, so source_role and source_group are well supported. However, the text is extremely low-signal ('@awscloud @AWSstartups') and the content_type label 'thought_leadership' is not strongly evidenced from the snippet alone. This is suitable for human review rather than benchmark gold.
- human review: Low-signal post; source classification is clear, but content-type assignment is weakly supported by the available text.

### fw_v1_source_classification_edf5e2495b2e (source_classification)

- decision: needs_human_review
- confidence: 0.97
- rationale: The source classification appears correct based on provenance: an official Fireworks AI account posting on X should map to official_brand and owned_official. But the content is effectively truncated to a link, so the content_type label is not reliably grounded. Because benchmark gold should avoid noisy labels, this should not be promoted without human review.
- human review: Need confirmation that the linked post content is actually thought leadership; current evidence only shows a URL and does not expose the substantive text.
