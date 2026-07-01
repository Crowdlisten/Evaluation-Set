# Fireworks RLM Variant Eval

Generated: 2026-07-01T07:38:32.499678+00:00

This report tests RLM-style post-embedding synthesis behavior against the checked-in Fireworks case-study eval package.

## Judged Slice

- evaluated clusters: 12
- winner counts: `{'source_aware_recursive': 4, 'audit_rewrite': 3, 'flat_llm': 5}`

### baseline
- evidence_fidelity: `78.33`
- category_correctness: `70.42`
- specificity: `67.5`
- actionability: `43.33`
- source_role_awareness: `89.17`
- overall: `64.42`

### flat_llm
- evidence_fidelity: `88.33`
- category_correctness: `94.17`
- specificity: `83.33`
- actionability: `86.25`
- source_role_awareness: `95.0`
- overall: `88.75`

### audit_rewrite
- evidence_fidelity: `94.58`
- category_correctness: `95.42`
- specificity: `89.17`
- actionability: `89.58`
- source_role_awareness: `97.92`
- overall: `92.5`

### source_aware_recursive
- evidence_fidelity: `91.67`
- category_correctness: `93.33`
- specificity: `89.58`
- actionability: `86.67`
- source_role_awareness: `97.08`
- overall: `91.0`

## Full Insight Packet Proxy Eval

- packets evaluated: 188
- blocklisted insight packets: 129
- audited SFT overlap: 4

### baseline
- issue rate: `1.8138`
- packets with any issue: `129`
- actions: `{'keep': 188}`
- issue counts: `{'market_insight_from_owned_only': 96, 'demand_without_independent_market_evidence': 100, 'blocklisted_case_retained': 129, 'mixed_content_kept': 16}`
- category changes: `{}`
- audited category accuracy: `0.75` (3/4)

### flat_llm_proxy
- issue rate: `0.7713`
- packets with any issue: `129`
- actions: `{'keep': 188}`
- issue counts: `{'blocklisted_case_retained': 129, 'mixed_content_kept': 16}`
- category changes: `{'opportunity->marketing_narrative': 8, 'opportunity->product_launch': 17, 'opportunity->technical_proof': 15, 'pain_point->technical_proof': 10, 'pain_point->product_launch': 18, 'feature_request->product_launch': 14, 'feature_request->technical_proof': 6, 'feature_request->marketing_narrative': 3, 'pain_point->marketing_narrative': 9}`
- audited category accuracy: `0.75` (3/4)

### audit_rewrite_proxy
- issue rate: `0.6011`
- packets with any issue: `113`
- actions: `{'keep': 172, 'split': 16}`
- issue counts: `{'blocklisted_case_retained': 113}`
- category changes: `{'opportunity->marketing_narrative': 8, 'opportunity->product_launch': 17, 'opportunity->technical_proof': 15, 'pain_point->technical_proof': 10, 'pain_point->product_launch': 18, 'feature_request->product_launch': 14, 'feature_request->technical_proof': 6, 'feature_request->marketing_narrative': 3, 'pain_point->marketing_narrative': 9}`
- audited category accuracy: `0.75` (3/4)

### source_aware_recursive_proxy
- issue rate: `0.5319`
- packets with any issue: `100`
- actions: `{'keep': 159, 'split': 29}`
- issue counts: `{'blocklisted_case_retained': 100}`
- category changes: `{'opportunity->marketing_narrative': 8, 'opportunity->product_launch': 20, 'opportunity->technical_proof': 19, 'pain_point->technical_proof': 11, 'pain_point->product_launch': 18, 'feature_request->technical_proof': 7, 'feature_request->product_launch': 14, 'feature_request->marketing_narrative': 6, 'marketing_narrative->product_launch': 11, 'marketing_narrative->technical_proof': 18, 'visibility->marketing_narrative': 4, 'visibility->product_launch': 7, 'visibility->technical_proof': 7, 'pain_point->marketing_narrative': 9}`
- audited category accuracy: `0.5` (2/4)

## Interpretation

- The judged slice is the best quality comparison because it includes explicit LLM-judge scores.
- The full-packet proxy is a regression guardrail, not a substitute for human gold labels.
- A real RLM layer should be considered useful only if it preserves the judged-slice gains while reducing full-packet source-role and mixed-cluster failures.
