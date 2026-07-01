# CrowdListen Eval Benchmark Design

Date: 2026-07-01

Scope: Fireworks AI entity, with Baseten and Modal as competitor entities.

## What Frontier-Quality Eval Sets Have In Common

Strong eval sets are not just JSONL files. They have:

1. A clear task contract.
   - Input fields are stable.
   - Output fields are explicit.
   - The model cannot pass by writing plausible prose.

2. Human-verified or execution-verified labels.
   - SWE-bench Verified uses human validation and executable tests.
   - Anthropic HH-RLHF uses chosen/rejected human preference pairs.
   - GPQA uses domain-expert questions plus non-expert validation.
   - METR time-horizon tasks use clear success criteria, self-contained environments, and human task-duration estimates.

3. Strong negatives.
   - Good evals include plausible wrong answers, not only easy examples.
   - For CrowdListen, the main hard negative is official marketing that sounds like market demand but is not user feedback.

4. Split discipline and leakage controls.
   - Train/dev/test are separated by source set, URL/text hash, entity, and cluster.
   - The test set should stay frozen.
   - Public web data needs contamination notes because models may have seen it.

5. Rubrics and calibration.
   - For model-graded evals, the grader rubric must itself be tested against human labels.
   - For CrowdListen, this means human-reviewed labels for source role, content type, evidence membership, cluster purity, and claim support.

6. Reproducibility.
   - The data package needs versioning, manifest counts, generation scripts, and a single command to run evals.

## Current Fireworks Eval Package

Location:

`eval_sets/fireworks/v1/`

Current eval-ready pack:

- 154 total records
- 67 partial-gold source provenance cases
- 12 audited SFT-style insight synthesis cases
- 9 audited DPO preference pairs
- 48 audited RFT/reward labels
- 10 cross-entity structural competitor cases
- 8 derived multi-turn workflow cases

Current full candidate pool:

- 4,540 candidate cases
- 792 source classification cases
- 3,560 opinion-unit quality cases
- 188 insight/cluster packets

Important limitation:

This is a good prototype eval pack, not a frontier-quality benchmark yet. The source provenance seed is partial gold, and the majority of opinion/insight records are not approved for training. The audit correctly blocklists many records because owned or employee marketing was converted into user-feedback-like opinion units.

## Representative Local Samples

### 1. Source Provenance Classification

Task: classify who posted a source and whether it contains actual user feedback.

Example source:

```json
{
  "author": "FireworksAI_HQ",
  "platform": "twitter",
  "url": "https://x.com/FireworksAI_HQ/status/2037222167642046626",
  "text": "\"We can bring down your TCO by 5-10x.\" Great insights from our founder & CEO Lin Qiao at @NVIDIAGTC Live last week on why 2026 is the year of customized inference."
}
```

Expected:

```json
{
  "source_role": "official_brand",
  "source_group": "owned_official",
  "feedback_type": ["none"]
}
```

Why it matters:

This catches the exact failure CrowdListen has had: official brand content should not become a pain point, opportunity, or feature request unless it quotes real external feedback.

### 2. Grounded Insight Synthesis

Task: rewrite a bad production insight using only the evidence.

Bad baseline:

```json
{
  "title": "Agentic workflow buyers want stable multi-tool orchestration and benchmarking",
  "category": "opportunity"
}
```

Evidence reality:

- Official Fireworks account posts about supporting builders.
- Employee/affiliated posts about recognition and community activity.
- No direct buyer complaint about orchestration or benchmarking.

Expected:

```json
{
  "category": "marketing_narrative",
  "title": "Fireworks AI gains industry recognition and developer community engagement",
  "split_recommended": false
}
```

Why it matters:

This tests evidence fidelity and source-role awareness, not just writing quality.

### 3. DPO Preference Pair

Task: choose the better synthesized insight.

Chosen:

- Separates official, employee, and creator evidence.
- Does not invent user demand.
- Labels the cluster as marketing narrative.

Rejected:

- Claims buyer demand for multi-tool orchestration.
- Uses official marketing as evidence of user pain.
- Adds unsupported product gaps.

This is useful for DPO only after the chosen/rejected pair is human-approved.

### 4. Reward Label / RFT Case

Task: score a candidate insight against a rubric.

Rubric dimensions:

- evidence fidelity
- category correctness
- source-role awareness
- specificity
- actionability

Hard-zero conditions:

- fabricated source, URL, author, or metric
- official-only evidence labeled as user pain
- top-engagement evidence does not support the insight
- unsupported competitor winner claim

### 5. Multi-Turn Workflow Eval

Task shape:

1. Retrieve sources for a topic.
2. Classify source role and content type.
3. Split evidence into official, affiliate, competitor, organic, creator.
4. Generate an insight.
5. Cite exact evidence IDs.
6. Refuse unsupported claims.

This is the closest match to how users want Claude Code, Codex, or another harness to use CrowdListen.

### 6. Cross-Entity Competitive Eval

Task: compare Fireworks against Baseten or Modal without conflating evidence roles.

Expected constraints:

```json
{
  "must_separate_roles": ["target", "competitor", "market"],
  "must_not_claim_winner_without_independent_evidence": true
}
```

Why it matters:

Competitor playbooks need to distinguish:

- what Baseten says about itself
- what Fireworks says about itself
- what independent users or buyers say
- what third-party benchmarks or discussion threads say

## CrowdListen Benchmark Suite Proposal

### Benchmark 1: Source Role and Source Group

Goal: determine who is speaking.

Labels:

- official_brand
- founder_exec
- employee
- affiliate_creator
- customer_user
- prospect_buyer
- independent_practitioner
- analyst_media
- competitor_official
- competitor_employee
- community_member
- unknown

Metric:

- macro F1
- critical confusion rate
- official/employee-as-user false positive rate

Gold target:

- 1,000 reviewed cases across Fireworks, Baseten, Modal, OpenRouter, Together, Groq, and Hugging Face.

### Benchmark 2: Content Type

Goal: identify what kind of content this is.

Labels:

- product_launch
- technical_proof
- customer_success
- tutorial_how_to
- competitive_claim
- thought_leadership
- event_community
- partner_integration
- user_review_experience
- support_question
- bug_report
- feature_request_post
- pricing_procurement
- generic_reaction
- off_topic

Metric:

- macro F1
- launch-vs-feedback confusion rate
- feedback false-positive rate on official content

Gold target:

- 1,500 reviewed single-source cases.

### Benchmark 3: Feedback Detection

Goal: decide whether a source actually contains market feedback.

Labels:

- pain_point
- feature_request
- buying_objection
- comparison_or_switching
- pricing_objection
- workflow_gap
- performance_reliability
- docs_guidance_request
- positive_testimonial
- success_metric
- question_request
- none

Metric:

- multi-label F1
- false positive rate on official content
- false negative rate on organic/user content

Gold target:

- 1,000 reviewed examples, balanced to include hard negatives.

### Benchmark 4: Opinion Splitting

Goal: split long threads, videos, posts, and comments into atomic claims.

Outputs:

- atomic opinion unit
- source span
- speaker
- sentiment
- dimension
- whether the unit should exist

Metric:

- atomicity agreement
- duplicate rate
- unsupported extraction rate
- span grounding score

Gold target:

- 300 sources with human-marked spans, including videos/transcripts and long HN/Reddit threads.

### Benchmark 5: Cluster Membership and Purity

Goal: decide whether evidence belongs together.

Outputs:

- keep, rename, split, merge, discard
- evidence-level include/exclude labels
- gold group IDs when a split is needed

Metric:

- evidence membership F1
- engagement-weighted precision
- split/merge action accuracy
- top-engagement misfit rate

Gold target:

- 200 clusters, each with 5-25 evidence items.

### Benchmark 6: Insight Synthesis

Goal: produce concise, source-aware, evidence-grounded insights.

Required output:

- title
- category
- description
- claim-to-evidence map
- source-role breakdown
- confidence
- unsupported claim check

Metric:

- claim support precision
- source-role awareness
- category correctness
- actionability
- unsupported claim rate

Gold target:

- 300 reviewed insight packets.

### Benchmark 7: Competitor Playbook Synthesis

Goal: summarize what competitors are trying to own in the market.

Required output:

- competitor entity
- official narrative
- employee/affiliate narrative
- organic market response
- topics they rank well on
- recent high-performing posts
- proof/evidence IDs
- implications for Fireworks

Metric:

- entity attribution precision
- evidence role separation
- unsupported winner-claim rate
- topic specificity

Gold target:

- 100 cross-entity packets covering Fireworks vs Baseten, Modal, OpenRouter, Together, Groq, and Hugging Face.

### Benchmark 8: Agent Workflow

Goal: evaluate the actual customer workflow, not only isolated labels.

Example task:

> For Fireworks, find the top X topics this week where Fireworks should show up, separate competitor-owned claims from organic market discussion, identify three posts to respond to, and cite raw source IDs.

Metric:

- task completion
- correct API/harness usage
- evidence coverage
- citation correctness
- unsupported claim rate
- latency/cost

Gold target:

- 50 multi-turn workflows with expected final artifacts and hidden checks.

## What To Build Next

### Phase 1: Freeze a Small Gold Set

Create `eval_sets/fireworks/v1_gold/` with:

- 200 source-role cases
- 200 content-type cases
- 150 feedback-detection cases
- 50 opinion-splitting cases
- 50 cluster packets
- 50 insight-synthesis packets
- 20 competitor packets
- 10 multi-turn workflow tasks

This is enough to prevent regressions and compare methods.

### Phase 2: Add Review Tooling

Build a small reviewer flow that shows:

- raw source
- rendered preview if available
- author/account metadata
- existing labels
- suggested labels
- reviewer decision
- evidence spans
- reason code

The review output should write JSONL patches, not mutate generated data silently.

### Phase 3: Add Baselines

Every benchmark needs baseline scores:

- current production pipeline
- prompt-only improved taxonomy
- embedding clustering only
- RLM/post-embedding refinement
- LLM-as-judge with calibrated rubric
- human-reviewed gold ceiling

### Phase 4: Use Training Only After Gold Exists

Training path:

1. SFT for source role, content type, feedback labels, and grounded insight JSON.
2. DPO for plausible synthesis pairs where the rejected answer is a known failure.
3. RFT only after the reward grader matches human labels reliably.

Do not train from the full candidate pool yet. Use it as a review backlog.

## Quality Bar

CrowdListen should treat an eval release as ready only if:

- every record has stable IDs and raw source provenance
- labels have review status and reviewer notes
- train/dev/test splits have no source/hash/entity leakage
- unsupported-claim failures are explicitly represented
- official/employee/competitor/organic source-role confusion is measured
- there is a benchmark card documenting collection method, known limits, and intended use
- the eval can run from one command and produce a score report

## Immediate Gap Against Frontier Benchmarks

The current Fireworks eval set is directionally right, but frontier-level quality requires:

- more human gold labels
- more adversarial hard negatives
- more independent organic-market data
- verified X/LinkedIn source completeness or a clear coverage caveat
- executable agent workflow evals through the CrowdListen API/harness
- a benchmark card and score report for every run

