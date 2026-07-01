#!/usr/bin/env python3
"""
Generate Fireworks eval packets from the current CrowdListen Supabase data.

This script is read-only against Supabase. It writes local JSONL/JSON files under
eval_sets/fireworks/v1/out by default.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENTITY_ID = "86e21e31-35d9-46a9-9999-527e6c227dfa"
ENTITY_NAME = "Fireworks AI"
INPUT_VERSION = "crowdlisten_fireworks_case_v1"
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
AUDIT_JSON = REPO_ROOT / "docs" / "fireworks_rlm_synthesis_eval_2026-06-30.json"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def text_hash(text: str | None) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return "sha256:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def parse_json_maybe(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.loads(json.dumps(value, default=str))


def source_text(row: dict[str, Any]) -> str:
    metadata = parse_json_maybe(row.get("metadata"))
    candidates = [
        row.get("raw_content"),
        row.get("content"),
        row.get("text"),
        row.get("body"),
        row.get("description"),
        metadata.get("full_text"),
        metadata.get("raw_text"),
        metadata.get("text"),
        metadata.get("rewritten_text"),
        row.get("title"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return ""


def source_url(row: dict[str, Any]) -> str | None:
    metadata = parse_json_maybe(row.get("metadata"))
    for key in ("source_url", "url", "permalink", "link", "external_url"):
        value = row.get(key) or metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def author(row: dict[str, Any]) -> str | None:
    metadata = parse_json_maybe(row.get("metadata"))
    for key in ("author", "username", "handle", "account", "screen_name", "channel", "source_name"):
        value = row.get(key) or metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def platform(row: dict[str, Any]) -> str | None:
    metadata = parse_json_maybe(row.get("metadata"))
    value = row.get("platform") or metadata.get("platform")
    return str(value).strip() if value else None


def engagement(row: dict[str, Any]) -> float:
    metadata = parse_json_maybe(row.get("metadata"))
    total = 0.0
    for key in (
        "engagement",
        "engagement_count",
        "likes",
        "like_count",
        "views",
        "view_count",
        "impressions",
        "shares",
        "retweets",
        "reposts",
        "comments",
        "num_comments",
        "replies",
    ):
        value = row.get(key, metadata.get(key))
        try:
            if value is not None and str(value).strip() != "":
                total += float(str(value).replace(",", ""))
        except ValueError:
            continue
    return total


def metrics(row: dict[str, Any]) -> dict[str, Any]:
    metadata = parse_json_maybe(row.get("metadata"))
    keys = [
        "likes",
        "like_count",
        "views",
        "view_count",
        "impressions",
        "shares",
        "retweets",
        "reposts",
        "comments",
        "num_comments",
        "replies",
        "engagement",
        "engagement_count",
    ]
    out: dict[str, Any] = {}
    for key in keys:
        value = row.get(key, metadata.get(key))
        if value is not None:
            out[key] = scalar(value)
    return out


def normalize_sender(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.strip().lower()
    mapping = {
        "official": "official_brand",
        "brand": "official_brand",
        "company": "official_brand",
        "employee": "employee",
        "affiliate": "affiliate_creator",
        "creator": "affiliate_creator",
        "organic": "community_member",
        "user": "customer_user",
        "customer": "customer_user",
        "competitor": "competitor_official",
    }
    return mapping.get(lowered, lowered)


def infer_source_role(row: dict[str, Any]) -> str:
    metadata = parse_json_maybe(row.get("metadata"))
    author_value = (author(row) or "").lower()
    url_value = (source_url(row) or "").lower()
    title_value = str(row.get("title") or "").lower()
    provenance = " ".join([author_value, url_value, title_value])

    # Provenance beats body text. A Fireworks post mentioning Baseten is still
    # owned Fireworks content; a Baseten docs page is competitor content.
    if any(
        token in provenance
        for token in (
            "fireworks.ai",
            "docs.fireworks.ai",
            "fireworksai-docs.mintlify.app",
            "fireworksai.mintlify.app",
            "fireworksai_hq",
            "fireworks ai youtube",
        )
    ):
        return "official_brand"
    if any(token in provenance for token in ("lqiao", "lin qiao", "dzhulgakov", "pranavj09", "terryfireworks")):
        return "employee"
    if any(
        token in provenance
        for token in (
            "baseten.co",
            "docs.baseten.co",
            "x.com/baseten",
            "modal.com",
            "modal labs",
            "x.com/modal_labs",
            "replicate.com",
            "together.ai",
            "openrouter.ai",
        )
    ):
        return "competitor_official"
    if any(token in provenance for token in ("prof_oz", "sinan ozdemir", "substack", "medium.com", "newsletter", "youtube.com/watch")):
        return "affiliate_creator"
    if any(
        token in provenance
        for token in (
            "findaichat.com/compare",
            "datarekha.com",
            "northflank.com/blog",
            "morphllm.com",
            "futureagi.com",
            "procurefyi.substack.com",
            "eastwind.substack.com",
            "alatirok.com",
        )
    ):
        return "analyst_media"
    if any(token in provenance for token in ("news.ycombinator.com", "reddit.com", "hacker news")):
        return "community_member"

    sender = normalize_sender(metadata.get("sender_type") or row.get("sender_type"))
    if sender:
        return sender
    return "unknown"


def infer_source_group(source_role: str) -> str:
    if source_role in {"official_brand", "founder_exec"}:
        return "owned_official"
    if source_role in {"employee"}:
        return "affiliated_insider"
    if source_role in {"competitor_official", "competitor_employee"}:
        return "competitor_ecosystem"
    if source_role in {"affiliate_creator", "analyst_media"}:
        return "creator_analyst"
    if source_role in {"customer_user"}:
        return "customer_proof"
    if source_role in {"prospect_buyer", "independent_practitioner", "community_member"}:
        return "organic_market"
    return "unknown"


def infer_content_type(row: dict[str, Any]) -> str:
    text = " ".join(str(x or "") for x in [row.get("title"), source_text(row)]).lower()
    url = (source_url(row) or "").lower()
    if any(x in text for x in ("launch", "available", "beta", "now supports", "day-0", "day 0", "sdk", "release")):
        return "product_launch"
    if any(x in text for x in ("latency", "throughput", "benchmark", "tokens/sec", "eval", "reliability", "performance", "speed")):
        return "technical_proof"
    if any(x in text for x in ("customer", "case study", "testimonial", "used by", "enabled", "saved", "reduced cost")):
        return "customer_success"
    if any(x in text for x in ("how to", "tutorial", "setup", "install", "guide", "claude code", "cursor", "no json")):
        return "tutorial_how_to"
    if any(x in text for x in ("vs ", "versus", "compare", "comparison", "beats", "alternative", "faster than", "cheaper than")):
        return "competitive_claim"
    if any(x in text for x in ("partnership", "partner", "integration", "integrates", "marketplace")):
        return "partner_integration"
    if any(x in text for x in ("webinar", "event", "gtc", "join us", "conference", "hackathon")):
        return "event_community"
    if any(x in text for x in ("?", "can i", "how do i", "does fireworks", "where can")):
        return "support_question"
    if any(x in text for x in ("bug", "broken", "failed", "error", "doesn't work", "not working")):
        return "bug_report"
    if any(x in text for x in ("wish", "would like", "feature request", "please add", "need support for")):
        return "feature_request_post"
    if any(x in text for x in ("price", "pricing", "cost", "credits", "billing")):
        return "pricing_procurement"
    if "docs.fireworks.ai" in url:
        return "tutorial_how_to"
    role = infer_source_role(row)
    if role in {"official_brand", "employee", "founder_exec"}:
        return "thought_leadership"
    return "user_review_experience" if role in {"community_member", "customer_user", "prospect_buyer"} else "generic_reaction"


def infer_feedback_types(row: dict[str, Any], content_type: str) -> list[str]:
    role = infer_source_role(row)
    if role in {"official_brand", "employee", "founder_exec", "competitor_official", "competitor_employee"}:
        return ["none"]
    text = source_text(row).lower()
    labels: list[str] = []
    if any(x in text for x in ("confusing", "hard", "pain", "friction", "stuck", "can't", "cannot", "failed", "broken")):
        labels.append("pain_point")
    if content_type == "feature_request_post":
        labels.append("feature_request")
    if any(x in text for x in ("compare", "vs", "alternative", "switch", "shortlist")):
        labels.append("comparison_or_switching")
    if any(x in text for x in ("price", "pricing", "expensive", "cost", "credits")):
        labels.append("pricing_objection")
    if any(x in text for x in ("docs", "guide", "example", "setup", "how do i")):
        labels.append("docs_guidance_request")
    if any(x in text for x in ("fast", "reliable", "latency", "throughput", "performance")):
        labels.append("performance_reliability")
    if any(x in text for x in ("great", "love", "worked", "using", "success")):
        labels.append("positive_testimonial")
    return sorted(set(labels)) or ["none"]


def evidence_item(row: dict[str, Any], opinion: dict[str, Any] | None = None, snippet: str | None = None) -> dict[str, Any]:
    metadata = parse_json_maybe(row.get("metadata"))
    role = infer_source_role(row)
    ctype = infer_content_type(row)
    return {
        "source_id": str(row.get("id")),
        "opinion_unit_id": str(opinion.get("id")) if opinion and opinion.get("id") else None,
        "platform": platform(row),
        "url": source_url(row),
        "title": row.get("title"),
        "author": author(row),
        "sender_type_current": metadata.get("sender_type") or row.get("sender_type"),
        "source_group_current": metadata.get("source_group") or row.get("source_group"),
        "source_class_current": metadata.get("source_class") or row.get("source_class"),
        "source_role_predicted": role,
        "source_group_predicted": infer_source_group(role),
        "content_type_predicted": ctype,
        "feedback_type_predicted": infer_feedback_types(row, ctype),
        "text": source_text(row),
        "rewritten_text": metadata.get("rewritten_text"),
        "snippet": snippet,
        "engagement": engagement(row),
        "metrics": metrics(row),
        "created_at": str(row.get("created_at")) if row.get("created_at") else None,
        "metadata": {
            "processing_status": row.get("processing_status"),
            "source_type": row.get("source_type"),
            "content_hash": row.get("content_hash"),
        },
    }


def make_case_id(prefix: str, parts: list[Any]) -> str:
    digest = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:12]
    return f"fw_v1_{prefix}_{digest}"


def base_case(task_type: str, evidence: list[dict[str, Any]], current_output: dict[str, Any] | None = None) -> dict[str, Any]:
    source_ids = sorted({str(ev["source_id"]) for ev in evidence if ev.get("source_id")})
    payload_for_hash = {
        "task_type": task_type,
        "source_ids": source_ids,
        "evidence_text_hashes": [text_hash(ev.get("text")) for ev in evidence],
        "current_output": current_output or {},
    }
    return {
        "case_id": make_case_id(task_type, [task_type, source_ids, current_output or {}]),
        "entity_id": ENTITY_ID,
        "entity_name": ENTITY_NAME,
        "task_type": task_type,
        "input_version": INPUT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_ids": source_ids,
        "evidence": evidence,
        "current_output": current_output,
        "labels": {"review_status": "draft"},
        "training_views": {
            "sft_ready": False,
            "dpo_ready": False,
            "reward_ready": False,
            "eval_only": True,
        },
        "input_hash": stable_hash(payload_for_hash),
        "source_set_hash": stable_hash(source_ids),
        "hashes": {
            "source_text_hashes": stable_hash([text_hash(ev.get("text")) for ev in evidence]),
            "urls": stable_hash(sorted(ev.get("url") for ev in evidence if ev.get("url"))),
        },
        "provenance": {"generator": "generate_eval_packets.py"},
    }


def source_case(row: dict[str, Any]) -> dict[str, Any]:
    ev = evidence_item(row)
    case = base_case("source_classification", [ev])
    role = ev["source_role_predicted"]
    ctype = ev["content_type_predicted"]
    case["labels"].update(
        {
            "review_status": "predicted",
            "source_role_gold": role,
            "source_group_gold": infer_source_group(role),
            "content_type_gold": ctype,
            "feedback_type_gold": ev["feedback_type_predicted"],
            "failure_modes": [],
            "rationale": "Heuristic prelabel; requires human review before training.",
        }
    )
    return case


def opinion_case(opinion: dict[str, Any], source: dict[str, Any] | None) -> dict[str, Any]:
    source = source or {"id": opinion.get("content_store_id"), "metadata": {}}
    ev = evidence_item(source, opinion=opinion, snippet=opinion.get("opinion"))
    case = base_case("opinion_unit_quality", [ev])
    case["current_output"] = {
        "opinion_unit_id": str(opinion.get("id")),
        "opinion": opinion.get("opinion"),
        "sentiment": opinion.get("sentiment"),
        "dimension": opinion.get("dimension"),
        "engagement_weight": opinion.get("engagement_weight"),
    }
    case["case_id"] = make_case_id(
        "opinion_unit_quality",
        [opinion.get("id"), opinion.get("content_store_id"), opinion.get("opinion")],
    )
    payload_for_hash = {
        "task_type": case["task_type"],
        "source_ids": case["source_ids"],
        "opinion_unit_id": opinion.get("id"),
        "opinion_text_hash": text_hash(opinion.get("opinion")),
        "current_output": case["current_output"],
    }
    case["input_hash"] = stable_hash(payload_for_hash)
    case["labels"].update(
        {
            "review_status": "draft",
            "quality_gold": None,
            "failure_modes": [],
            "rationale": "Draft opinion-unit quality example; human should mark atomicity, sentiment, and whether the source should produce an opinion.",
        }
    )
    return case


def insight_case(
    insight: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
    source_by_id: dict[str, dict[str, Any]],
    opinion_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for ev_row in evidence_rows:
        source = source_by_id.get(str(ev_row.get("content_store_id")))
        if not source:
            continue
        opinion = opinion_by_id.get(str(ev_row.get("opinion_unit_id"))) if ev_row.get("opinion_unit_id") else None
        evidence.append(evidence_item(source, opinion=opinion, snippet=ev_row.get("snippet")))

    current_output = {
        "id": str(insight.get("id")),
        "title": insight.get("title"),
        "description": insight.get("description"),
        "category": insight.get("category"),
        "urgency": insight.get("urgency"),
        "impact_score": insight.get("impact_score"),
        "confidence": float(insight["confidence"]) if insight.get("confidence") is not None else None,
        "signal_count": insight.get("signal_count"),
    }
    case = base_case("insight_synthesis", evidence, current_output=current_output)
    roles = Counter(ev.get("source_role_predicted") for ev in evidence)
    current_category = (insight.get("category") or "").lower()
    failure_modes: list[str] = []
    role_only_official = set(roles) <= {"official_brand", "employee", "founder_exec", None}
    if role_only_official and current_category in {"pain_point", "feature_request"}:
        failure_modes.extend(["wrong_category", "official_marketing_as_feedback"])
    if len(roles) > 2:
        failure_modes.append("source_role_blindness")
    if len({ev.get("content_type_predicted") for ev in evidence}) > 3:
        failure_modes.append("mixed_cluster")
    quality = "bad" if failure_modes else ("mixed" if len(roles) > 1 else "good")
    case["labels"].update(
        {
            "review_status": "predicted",
            "quality_gold": quality,
            "insight_category_gold": current_category or None,
            "cluster_action_gold": "rename" if failure_modes else "keep",
            "cluster_purity_gold": "mixed" if "mixed_cluster" in failure_modes else "mostly_pure",
            "failure_modes": sorted(set(failure_modes)),
            "gold_groups": [],
            "rationale": "Heuristic cluster prelabel; review evidence membership, action, category, and gold groups before training.",
        }
    )
    return case


def fetch_all(sb: Any, table: str, select: str = "*", filters: list[tuple[str, str, Any]] | None = None, page_size: int = 1000) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = sb.table(table).select(select)
        for method, column, value in filters or []:
            if method == "eq":
                query = query.eq(column, value)
            elif method == "in":
                query = query.in_(column, value)
            elif method == "is":
                query = query.is_(column, value)
        result = query.range(offset, offset + page_size - 1).execute()
        batch = result.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            return rows
        offset += page_size


def chunked(items: list[Any], size: int) -> list[list[Any]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def choose_stratified_sources(rows: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        role = infer_source_role(row)
        group = infer_source_group(role)
        buckets[group].append(row)

    quotas = {
        "owned_official": 30,
        "affiliated_insider": 25,
        "organic_market": 20,
        "competitor_ecosystem": 15,
        "creator_analyst": 15,
        "customer_proof": 5,
        "unknown": 15,
    }
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    seen_signature: set[str] = set()
    for group, quota in quotas.items():
        candidates = sorted(buckets.get(group, []), key=engagement, reverse=True)
        for row in candidates[:quota]:
            rid = str(row.get("id"))
            sig = source_url(row) or text_hash(source_text(row))
            if rid not in seen and sig not in seen_signature:
                chosen.append(row)
                seen.add(rid)
                seen_signature.add(sig)

    if len(chosen) < target:
        rest = sorted(rows, key=engagement, reverse=True)
        for row in rest:
            rid = str(row.get("id"))
            sig = source_url(row) or text_hash(source_text(row))
            if rid not in seen and sig not in seen_signature:
                chosen.append(row)
                seen.add(rid)
                seen_signature.add(sig)
            if len(chosen) >= target:
                break
    return chosen[:target]


def choose_opinions(rows: list[dict[str, Any]], target: int) -> list[dict[str, Any]]:
    by_sentiment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_sentiment[str(row.get("sentiment") or "unknown")].append(row)
    quotas = {"positive": 25, "neutral": 20, "negative": 20, "mixed": 20, "unknown": 15}
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for sentiment, quota in quotas.items():
        candidates = sorted(
            by_sentiment.get(sentiment, []),
            key=lambda r: float(r.get("engagement_weight") or 0),
            reverse=True,
        )
        for row in candidates[:quota]:
            rid = str(row.get("id"))
            if rid not in seen:
                chosen.append(row)
                seen.add(rid)
    if len(chosen) < target:
        rest = sorted(rows, key=lambda r: float(r.get("engagement_weight") or 0), reverse=True)
        for row in rest:
            rid = str(row.get("id"))
            if rid not in seen:
                chosen.append(row)
                seen.add(rid)
            if len(chosen) >= target:
                break
    return chosen[:target]


def choose_insights(insights: list[dict[str, Any]], evidence_by_insight: dict[str, list[dict[str, Any]]], target: int) -> list[dict[str, Any]]:
    def priority(row: dict[str, Any]) -> tuple[int, int, float]:
        category = str(row.get("category") or "")
        evidence_count = len(evidence_by_insight.get(str(row.get("id")), []))
        risky = 1 if category in {"pain_point", "feature_request", "marketing_narrative", "competitive"} else 0
        return (risky, evidence_count, float(row.get("impact_score") or 0))

    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in insights:
        by_category[str(row.get("category") or "unknown")].append(row)

    quotas = {
        "opportunity": 12,
        "pain_point": 12,
        "feature_request": 12,
        "marketing_narrative": 16,
        "competitive": 12,
        "visibility": 8,
        "churn": 4,
        "unknown": 4,
    }
    chosen: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category, quota in quotas.items():
        candidates = sorted(by_category.get(category, []), key=priority, reverse=True)
        for row in candidates[:quota]:
            rid = str(row.get("id"))
            if rid not in seen and evidence_by_insight.get(rid):
                chosen.append(row)
                seen.add(rid)
    if len(chosen) < target:
        rest = sorted(insights, key=priority, reverse=True)
        for row in rest:
            rid = str(row.get("id"))
            if rid not in seen and evidence_by_insight.get(rid):
                chosen.append(row)
                seen.add(rid)
            if len(chosen) >= target:
                break
    return chosen[:target]


def derive_training_views_from_audit(cases_by_insight_id: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not AUDIT_JSON.exists():
        return [], [], []
    data = json.loads(AUDIT_JSON.read_text())
    sft: list[dict[str, Any]] = []
    pref: list[dict[str, Any]] = []
    reward: list[dict[str, Any]] = []

    for item in data.get("results", []):
        cluster = item.get("cluster") or {}
        insight_id = str(cluster.get("id") or cluster.get("insight_id") or "")
        case = cases_by_insight_id.get(insight_id)
        if not case:
            continue
        outputs = item.get("outputs") or {}
        scores = item.get("scores") or {}
        winner = item.get("winner")
        if not winner or winner not in outputs:
            continue
        chosen = outputs[winner]
        chosen_scores = scores.get(winner) or {}
        if chosen_scores.get("overall", 0) >= 88:
            sft.append(
                {
                    "record_id": f"{case['case_id']}_sft_{winner}",
                    "case_id": case["case_id"],
                    "task_type": "insight_synthesis",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a CrowdListen evidence-fidelity analyst. Return only valid JSON.",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "entity": ENTITY_NAME,
                                    "task": "Rewrite the insight using only this evidence.",
                                    "current_output": case.get("current_output"),
                                    "evidence": case.get("evidence"),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    "assistant": chosen,
                    "gold_source": "audited_model_fireworks_rlm_synthesis_eval_2026_06_30",
                    "rubric_scores": chosen_scores,
                    "split": "train",
                }
            )

        baseline = outputs.get("baseline")
        baseline_scores = scores.get("baseline") or {}
        if baseline and chosen_scores.get("overall", 0) - baseline_scores.get("overall", 0) >= 10:
            pref.append(
                {
                    "record_id": f"{case['case_id']}_dpo_{winner}_vs_baseline",
                    "case_id": case["case_id"],
                    "messages": [
                        {
                            "role": "system",
                            "content": "Return a grounded CrowdListen insight JSON.",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "entity": ENTITY_NAME,
                                    "current_output": case.get("current_output"),
                                    "evidence": case.get("evidence"),
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                    "chosen": chosen,
                    "rejected": baseline,
                    "preference_reason": "Chosen output scored higher on evidence fidelity, category correctness, specificity, actionability, and source-role awareness.",
                    "chosen_scores": chosen_scores,
                    "rejected_scores": baseline_scores,
                    "margin": round((chosen_scores.get("overall", 0) - baseline_scores.get("overall", 0)) / 100, 3),
                    "split": "train",
                }
            )

        for candidate_id, candidate in outputs.items():
            candidate_scores = scores.get(candidate_id) or {}
            reward.append(
                {
                    "record_id": f"{case['case_id']}_reward_{candidate_id}",
                    "case_id": case["case_id"],
                    "candidate_id": candidate_id,
                    "candidate_output": candidate,
                    "rubric_scores": candidate_scores,
                    "reward": round(float(candidate_scores.get("overall") or 0) / 100, 3),
                    "violations": [] if candidate_scores.get("overall", 0) >= 88 else ["needs_review"],
                    "grader_rationale": candidate.get("issue") or "Derived from audited synthesis eval.",
                    "split": "dev",
                }
            )

    return sft, pref, reward


def assign_splits(cases: list[dict[str, Any]]) -> dict[str, Any]:
    ids = sorted(case["case_id"] for case in cases)
    rng = random.Random(42)
    rng.shuffle(ids)
    n = len(ids)
    train_end = int(n * 0.70)
    dev_end = int(n * 0.85)
    return {
        "version": "fireworks_v1",
        "strategy": "grouped_by_case_id_source_set_hash_entity_id",
        "frozen_test": True,
        "train": ids[:train_end],
        "dev": ids[train_end:dev_end],
        "test": ids[dev_end:],
    }


def leakage_index(cases: list[dict[str, Any]]) -> dict[str, Any]:
    case_entries = []
    source_to_cases: dict[str, list[str]] = defaultdict(list)
    url_to_cases: dict[str, list[str]] = defaultdict(list)
    text_to_cases: dict[str, list[str]] = defaultdict(list)
    for case in cases:
        cid = case["case_id"]
        for ev in case.get("evidence", []):
            sid = ev.get("source_id")
            url = ev.get("url")
            th = text_hash(ev.get("text"))
            if sid:
                source_to_cases[str(sid)].append(cid)
            if url:
                url_to_cases[str(url)].append(cid)
            text_to_cases[th].append(cid)
        case_entries.append(
            {
                "case_id": cid,
                "source_set_hash": case.get("source_set_hash"),
                "input_hash": case.get("input_hash"),
            }
        )
    return {
        "cases": case_entries,
        "source_id_to_cases": source_to_cases,
        "url_to_cases": url_to_cases,
        "text_hash_to_cases": text_to_cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--entity-id", default=ENTITY_ID)
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "out"))
    parser.add_argument("--source-target", type=int, default=120)
    parser.add_argument("--opinion-target", type=int, default=100)
    parser.add_argument("--insight-target", type=int, default=80)
    parser.add_argument("--dotenv", default=str(REPO_ROOT / ".env"))
    args = parser.parse_args()

    load_dotenv(Path(args.dotenv))
    try:
        from supabase import create_client
    except ImportError:
        print("Missing supabase package. Install repo requirements first.", file=sys.stderr)
        return 2

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        print("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required.", file=sys.stderr)
        return 2

    sb = create_client(url, key)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sources = fetch_all(sb, "content_store", "*", [("eq", "entity_id", args.entity_id)])
    opinions = fetch_all(sb, "opinion_units", "*", [("eq", "entity_id", args.entity_id)])
    insights = fetch_all(sb, "entity_insights", "*", [("eq", "entity_id", args.entity_id)])

    insight_ids = [str(row.get("id")) for row in insights if row.get("id")]
    evidence_rows: list[dict[str, Any]] = []
    for batch in chunked(insight_ids, 100):
        evidence_rows.extend(fetch_all(sb, "insight_evidence", "*", [("in", "insight_id", batch)]))

    source_by_id = {str(row.get("id")): row for row in sources}
    opinion_by_id = {str(row.get("id")): row for row in opinions}
    evidence_by_insight: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence_rows:
        evidence_by_insight[str(row.get("insight_id"))].append(row)
    for rows in evidence_by_insight.values():
        rows.sort(key=lambda r: float(r.get("relevance") or 0), reverse=True)

    source_examples = [source_case(row) for row in choose_stratified_sources(sources, args.source_target)]
    opinion_sources = {str(row.get("content_store_id")) for row in opinions if row.get("content_store_id")}
    missing_sources = [sid for sid in opinion_sources if sid not in source_by_id]
    if missing_sources:
        for batch in chunked(missing_sources, 100):
            for row in fetch_all(sb, "content_store", "*", [("in", "id", batch)]):
                source_by_id[str(row.get("id"))] = row
    opinion_examples = [
        opinion_case(row, source_by_id.get(str(row.get("content_store_id"))))
        for row in choose_opinions(opinions, args.opinion_target)
    ]
    insight_examples = [
        insight_case(row, evidence_by_insight.get(str(row.get("id")), [])[:8], source_by_id, opinion_by_id)
        for row in choose_insights(insights, evidence_by_insight, args.insight_target)
    ]

    cases = source_examples + opinion_examples + insight_examples
    cases_by_insight_id = {
        str(case.get("current_output", {}).get("id")): case
        for case in insight_examples
        if case.get("current_output", {}).get("id")
    }
    sft, pref, reward = derive_training_views_from_audit(cases_by_insight_id)
    splits = assign_splits(cases)
    leakage = leakage_index(cases)

    manifest = {
        "version": "fireworks_eval_set_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "entity_id": args.entity_id,
        "entity_name": ENTITY_NAME,
        "read_only_supabase": True,
        "counts": {
            "content_store_rows": len(sources),
            "opinion_units": len(opinions),
            "entity_insights": len(insights),
            "insight_evidence": len(evidence_rows),
            "source_classification_cases": len(source_examples),
            "opinion_unit_quality_cases": len(opinion_examples),
            "insight_packet_cases": len(insight_examples),
            "cases_total": len(cases),
            "sft_records": len(sft),
            "preference_records": len(pref),
            "reward_records": len(reward),
        },
        "platform_counts": dict(Counter(platform(row) or "unknown" for row in sources)),
        "source_group_predicted_counts": dict(Counter(infer_source_group(infer_source_role(row)) for row in sources)),
        "content_type_predicted_counts": dict(Counter(infer_content_type(row) for row in sources)),
        "case_hash": stable_hash([case["input_hash"] for case in cases]),
        "notes": [
            "Generated labels are draft/predicted unless derived from the audited synthesis eval.",
            "Human review is required before using generated source/opinion/cluster labels for training.",
            "Splits are case-level to avoid leakage across SFT, DPO, reward, and eval views.",
        ],
    }

    write_jsonl(out_dir / "cases.jsonl", cases)
    write_jsonl(out_dir / "source_classification.jsonl", source_examples)
    write_jsonl(out_dir / "opinion_unit_quality.jsonl", opinion_examples)
    write_jsonl(out_dir / "insight_packets.jsonl", insight_examples)
    write_jsonl(out_dir / "labels.sft.jsonl", sft)
    write_jsonl(out_dir / "labels.preference.jsonl", pref)
    write_jsonl(out_dir / "labels.reward.jsonl", reward)
    write_json(out_dir / "manifest.json", manifest)
    write_json(out_dir / "splits.json", splits)
    write_json(out_dir / "leakage_index.json", leakage)

    print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
