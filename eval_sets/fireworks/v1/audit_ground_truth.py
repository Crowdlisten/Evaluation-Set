#!/usr/bin/env python3
"""Audit Fireworks eval packets for gold-standard readiness.

The generator outputs draft/predicted labels. This script is the quality gate:
it finds label-risk cases, builds a review queue, and emits a small
deterministic gold seed only where source provenance makes the label defensible
without subjective interpretation.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "out_gold_review"

STRONG_OFFICIAL_PATTERNS = (
    "x.com/fireworksai_hq/",
    "fireworks.ai/",
    "docs.fireworks.ai/",
    "fireworksai-docs.mintlify.app/",
    "fireworks ai youtube",
)
STRONG_EMPLOYEE_AUTHORS = {
    "lqiao",
    "lin qiao",
    "dzhulgakov",
    "pranavj09",
    "terryfireworks",
}
STRONG_COMPETITOR_PATTERNS = (
    "x.com/baseten/",
    "baseten.co/",
    "docs.baseten.co/",
    "x.com/modal_labs/",
    "modal.com/",
)
ORGANIC_PATTERNS = (
    "news.ycombinator.com/",
    "reddit.com/",
    "old.reddit.com/",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def evidence_text(ev: dict[str, Any]) -> str:
    return str(ev.get("text") or ev.get("snippet") or "").strip()


def provenance_blob(ev: dict[str, Any]) -> str:
    return " ".join(
        str(ev.get(key) or "")
        for key in ["url", "author", "title", "platform", "evidence_entity_name"]
    ).lower()


def is_only_url(text: str) -> bool:
    stripped = re.sub(r"https?://\\S+|t\\.co/\\S+", "", text).strip()
    return len(stripped) < 10


def has_market_evidence(case: dict[str, Any]) -> bool:
    for ev in case.get("evidence", []):
        group = ev.get("source_group_predicted")
        role = ev.get("source_role_predicted")
        if group in {"organic_market", "creator_analyst", "customer_proof"}:
            return True
        if role in {"customer_user", "prospect_buyer", "independent_practitioner", "community_member", "analyst_media"}:
            return True
    return False


def has_independent_evidence(case: dict[str, Any]) -> bool:
    for ev in case.get("evidence", []):
        if ev.get("evidence_entity_role") == "market":
            return True
        if ev.get("source_group_predicted") in {"organic_market", "creator_analyst", "customer_proof"}:
            return True
    return False


def deterministic_source_gold(case: dict[str, Any]) -> dict[str, Any] | None:
    if case.get("task_type") != "source_classification":
        return None
    evidence = case.get("evidence") or []
    if len(evidence) != 1:
        return None
    ev = evidence[0]
    blob = provenance_blob(ev)
    predicted = ev.get("source_role_predicted")
    labels: dict[str, Any] | None = None

    if any(pattern in blob for pattern in STRONG_OFFICIAL_PATTERNS):
        labels = {
            "source_role_gold": "official_brand",
            "source_group_gold": "owned_official",
            "feedback_type_gold": ["none"],
        }
    elif any(author in blob for author in STRONG_EMPLOYEE_AUTHORS):
        labels = {
            "source_role_gold": "employee",
            "source_group_gold": "affiliated_insider",
            "feedback_type_gold": ["none"],
        }
    elif any(pattern in blob for pattern in STRONG_COMPETITOR_PATTERNS):
        labels = {
            "source_role_gold": "competitor_official",
            "source_group_gold": "competitor_ecosystem",
            "feedback_type_gold": ["none"],
        }
    elif any(pattern in blob for pattern in ORGANIC_PATTERNS):
        labels = {
            "source_role_gold": "community_member",
            "source_group_gold": "organic_market",
        }

    if not labels:
        return None

    # If the predicted role conflicts with deterministic provenance, this is a
    # review item, not an auto-approved seed.
    if predicted and labels["source_role_gold"] != predicted:
        return None

    gold = json.loads(json.dumps(case))
    gold["labels"].update(labels)
    gold["labels"]["content_type_gold"] = None
    gold["labels"]["review_status"] = "reviewed"
    gold["labels"]["gold_source"] = "deterministic_provenance_audit_2026_07_01"
    gold["labels"]["partial_gold_fields"] = [
        "source_role_gold",
        "source_group_gold",
        "feedback_type_gold",
    ]
    gold["labels"]["rationale"] = "Partial gold: source provenance labels are deterministic; content type still requires human review."
    gold["training_views"]["sft_ready"] = False
    gold["training_views"]["eval_only"] = True
    gold["training_views"]["source_provenance_ready"] = True
    return gold


def audit_case(case: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    task = case.get("task_type")
    evidence = case.get("evidence") or []
    labels = case.get("labels") or {}

    if not evidence:
        issues.append("empty_evidence")

    source_ids = [ev.get("source_id") for ev in evidence if ev.get("source_id")]
    if len(source_ids) != len(set(source_ids)):
        issues.append("duplicate_source_ids")

    for ev in evidence:
        text = evidence_text(ev)
        role = ev.get("source_role_predicted")
        feedback = ev.get("feedback_type_predicted") or []
        if len(text) < 40 or is_only_url(text):
            issues.append("low_signal_text")
        if role in {None, "", "unknown"}:
            issues.append("unknown_source_role")
        if role in {"official_brand", "employee", "founder_exec", "competitor_official", "competitor_employee"}:
            if feedback and feedback != ["none"]:
                issues.append("owned_or_competitor_marketing_labeled_feedback")

    if task == "opinion_unit_quality":
        current = case.get("current_output") or {}
        opinion = str(current.get("opinion") or "")
        if len(opinion.split()) < 6:
            issues.append("opinion_too_short")
        parent_roles = {ev.get("source_role_predicted") for ev in evidence}
        if parent_roles & {"official_brand", "employee", "founder_exec", "competitor_official", "competitor_employee"}:
            issues.append("opinion_from_owned_or_competitor_source")
        if current.get("sentiment") == "positive" and parent_roles & {"official_brand", "employee", "founder_exec"}:
            issues.append("positive_marketing_claim_as_opinion")

    if task == "insight_synthesis":
        current = case.get("current_output") or {}
        category = str(current.get("category") or labels.get("insight_category_gold") or "").lower()
        title_desc = f"{current.get('title') or ''} {current.get('description') or ''}".lower()
        source_groups = {ev.get("source_group_predicted") for ev in evidence}
        content_types = {ev.get("content_type_predicted") for ev in evidence}
        if category in {"pain_point", "feature_request", "opportunity", "churn"}:
            if source_groups and source_groups <= {"owned_official", "affiliated_insider", None}:
                issues.append("market_insight_from_owned_only")
        if re.search(r"\\b(buyers?|users?|customers?|teams?)\\b.*\\b(want|need|complain|struggle|ask|request)", title_desc):
            if not has_market_evidence(case):
                issues.append("unsupported_buyer_inference_without_market_evidence")
        if len(content_types - {None}) > 3:
            issues.append("mixed_content_types")
        for mode in labels.get("failure_modes") or []:
            issues.append(f"existing_failure:{mode}")

    if task == "cross_entity_competitive_synthesis":
        role_by_source: dict[str, set[str]] = defaultdict(set)
        for ev in evidence:
            if ev.get("source_id"):
                role_by_source[str(ev["source_id"])].add(str(ev.get("evidence_entity_role")))
        if any(len(roles) > 1 for roles in role_by_source.values()):
            issues.append("same_source_assigned_multiple_evidence_roles")
        if not has_independent_evidence(case):
            issues.append("missing_independent_market_evidence")
        for ev in evidence:
            role = ev.get("evidence_entity_role")
            group = ev.get("source_group_predicted")
            if role == "target" and group not in {"owned_official", "affiliated_insider", "customer_proof"}:
                issues.append("target_bucket_contains_non_owned_evidence")
            if role == "competitor" and group not in {"competitor_ecosystem", "owned_official", "affiliated_insider"}:
                issues.append("competitor_bucket_contains_non_competitor_evidence")

    severity = 0
    severe = {
        "empty_evidence",
        "same_source_assigned_multiple_evidence_roles",
        "market_insight_from_owned_only",
        "unsupported_buyer_inference_without_market_evidence",
        "owned_or_competitor_marketing_labeled_feedback",
    }
    for issue in issues:
        severity += 3 if issue in severe or issue.startswith("existing_failure:") else 1

    return {
        "case_id": case.get("case_id"),
        "task_type": task,
        "severity": severity,
        "issues": sorted(set(issues)),
        "current_output": case.get("current_output"),
        "evidence_summary": [
            {
                "source_id": ev.get("source_id"),
                "url": ev.get("url"),
                "author": ev.get("author"),
                "platform": ev.get("platform"),
                "source_role_predicted": ev.get("source_role_predicted"),
                "source_group_predicted": ev.get("source_group_predicted"),
                "content_type_predicted": ev.get("content_type_predicted"),
                "evidence_entity_role": ev.get("evidence_entity_role"),
                "snippet": (ev.get("snippet") or evidence_text(ev))[:500],
            }
            for ev in evidence[:8]
        ],
    }


def load_cases(base_dir: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        "source_classification": read_jsonl(base_dir / "out_full" / "source_classification.jsonl"),
        "opinion_unit_quality": read_jsonl(base_dir / "out_full" / "opinion_unit_quality.jsonl"),
        "insight_synthesis": read_jsonl(base_dir / "out_full" / "insight_packets.jsonl"),
        "cross_entity_competitive_synthesis": read_jsonl(base_dir / "out_cross_entity" / "cross_entity_competitive.jsonl"),
    }


def build_review_queue(audits: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for audit in audits:
        if audit["severity"] > 0:
            by_task[audit["task_type"]].append(audit)
    for rows in by_task.values():
        rows.sort(key=lambda item: (item["severity"], len(item["issues"])), reverse=True)

    queue: list[dict[str, Any]] = []
    # Force task coverage first.
    for task in [
        "source_classification",
        "opinion_unit_quality",
        "insight_synthesis",
        "cross_entity_competitive_synthesis",
    ]:
        queue.extend(by_task.get(task, [])[: max(10, limit // 8)])

    seen = {row["case_id"] for row in queue}
    rest = sorted(
        [row for row in audits if row["severity"] > 0 and row["case_id"] not in seen],
        key=lambda item: (item["severity"], len(item["issues"])),
        reverse=True,
    )
    queue.extend(rest[: max(0, limit - len(queue))])
    return queue[:limit]


def render_markdown(report: dict[str, Any], queue: list[dict[str, Any]]) -> str:
    lines = [
        "# Fireworks Ground Truth Audit",
        "",
        f"Generated: {report['created_at']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issue Counts", ""])
    for issue, count in report["issue_counts"].items():
        lines.append(f"- {issue}: {count}")
    lines.extend(["", "## Task Risk", ""])
    for task, stats in report["task_risk"].items():
        lines.append(f"- {task}: {stats}")
    lines.extend(["", "## Review Queue Examples", ""])
    for item in queue[:20]:
        lines.append(f"### {item['case_id']} ({item['task_type']}, severity {item['severity']})")
        lines.append("")
        lines.append(f"Issues: {', '.join(item['issues'])}")
        current = item.get("current_output") or {}
        if current:
            lines.append(f"Current: {current.get('title') or current.get('opinion') or current.get('id')}")
        for ev in item.get("evidence_summary", [])[:3]:
            lines.append(
                f"- {ev.get('platform')} {ev.get('source_role_predicted')} {ev.get('url')}: {ev.get('snippet')}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(SCRIPT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--review-limit", type=int, default=160)
    parser.add_argument("--gold-source-limit", type=int, default=120)
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    out_dir = Path(args.out_dir)
    cases_by_task = load_cases(base_dir)
    all_cases = [case for rows in cases_by_task.values() for case in rows]

    audits = [audit_case(case) for case in all_cases]
    review_queue = build_review_queue(audits, args.review_limit)
    training_blocklist = [
        {
            "case_id": audit["case_id"],
            "task_type": audit["task_type"],
            "severity": audit["severity"],
            "issues": audit["issues"],
        }
        for audit in audits
        if audit["severity"] > 0
    ]

    source_gold: list[dict[str, Any]] = []
    seen_roles = Counter()
    for case in cases_by_task["source_classification"]:
        gold = deterministic_source_gold(case)
        if not gold:
            continue
        role = gold["labels"].get("source_role_gold") or "unknown"
        # Keep the deterministic seed stratified; the full queue still contains
        # everything for review.
        if seen_roles[role] >= max(10, args.gold_source_limit // 4):
            continue
        source_gold.append(gold)
        seen_roles[role] += 1
        if len(source_gold) >= args.gold_source_limit:
            break

    issue_counts = Counter(issue for audit in audits for issue in audit["issues"])
    task_risk: dict[str, Any] = {}
    for task, rows in cases_by_task.items():
        task_audits = [audit for audit in audits if audit["task_type"] == task]
        task_risk[task] = {
            "cases": len(rows),
            "flagged": sum(1 for audit in task_audits if audit["severity"] > 0),
            "max_severity": max((audit["severity"] for audit in task_audits), default=0),
            "avg_severity": round(sum(audit["severity"] for audit in task_audits) / max(len(task_audits), 1), 3),
        }

    report = {
        "version": "fireworks_ground_truth_audit_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "cases_total": len(all_cases),
            "review_queue": len(review_queue),
            "deterministic_source_gold_seed": len(source_gold),
            "training_blocklist": len(training_blocklist),
        },
        "task_counts": {task: len(rows) for task, rows in cases_by_task.items()},
        "issue_counts": dict(issue_counts.most_common()),
        "task_risk": task_risk,
        "gold_seed_role_counts": dict(seen_roles),
        "notes": [
            "Only deterministic source provenance fields are marked reviewed.",
            "Opinion, insight, and cross-entity cases remain review-required before training.",
            "Cases flagged for owned marketing as feedback or unsupported buyer inference should not enter training until corrected.",
        ],
    }

    write_json(out_dir / "audit_report.json", report)
    write_jsonl(out_dir / "audit_cases.jsonl", audits)
    write_jsonl(out_dir / "review_queue.jsonl", review_queue)
    write_jsonl(out_dir / "training_blocklist.jsonl", training_blocklist)
    write_jsonl(out_dir / "gold_seed.source_classification.jsonl", source_gold)
    write_json(out_dir / "gold_seed.manifest.json", {
        "created_at": report["created_at"],
        "records": len(source_gold),
        "role_counts": dict(seen_roles),
        "source": "deterministic provenance only; partial gold fields only",
    })
    (out_dir / "audit_report.md").write_text(render_markdown(report, review_queue), encoding="utf-8")

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
