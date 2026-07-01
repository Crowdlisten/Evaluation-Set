#!/usr/bin/env python3
"""Static label consistency checks for the Fireworks case-study package.

This is not a gold-label reviewer. It catches contradictions that should be
addressed before a record is promoted, such as official sources carrying
feedback labels or cross-entity packets missing visible competitor evidence.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_REPORT = SCRIPT_DIR / "out_quality_review" / "label_consistency_report.json"
DEFAULT_MD = SCRIPT_DIR / "out_quality_review" / "label_consistency_report.md"

OWNED_ROLES = {
    "official_brand",
    "founder_exec",
    "employee",
    "competitor_official",
    "competitor_employee",
}
CREATOR_ANALYST_ROLES = {
    "affiliate_creator",
    "analyst_media",
}
MARKET_ROLES = {
    "affiliate_creator",
    "customer_user",
    "prospect_buyer",
    "independent_practitioner",
    "analyst_media",
    "community_member",
}
FEEDBACK_LABELS = {
    "pain_point",
    "feature_request",
    "buying_objection",
    "comparison_or_switching",
    "pricing_objection",
    "workflow_gap",
    "performance_reliability",
    "docs_guidance_request",
    "positive_testimonial",
    "success_metric",
    "question_request",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def source_text(ev: dict[str, Any]) -> str:
    return str(ev.get("text") or ev.get("snippet") or "").strip()


def text_too_short(ev: dict[str, Any]) -> bool:
    text = re.sub(r"https?://\S+|t\.co/\S+", "", source_text(ev)).strip()
    return len(text) < 30


def has_first_person_or_user_evidence(ev: dict[str, Any]) -> bool:
    text = source_text(ev).lower()
    return bool(
        re.search(r"\b(i|we|our team|my team|using|used|migrated|switched|customer|buyer|user|developer)\b", text)
        and re.search(r"\b(fireworks|baseten|modal|openrouter|inference|model|fine[- ]?tuning|deploy|latency|cost)\b", text)
    )


def has_feedback(labels: list[str] | None) -> bool:
    values = set(labels or [])
    return bool(values & FEEDBACK_LABELS) and values != {"none"}


def iter_cases() -> list[dict[str, Any]]:
    # Use canonical case-shaped files only. Derived eval-ready views can have
    # different schemas, such as `input.source` instead of top-level `evidence`.
    paths = [
        SCRIPT_DIR / "out_full" / "source_classification.jsonl",
        SCRIPT_DIR / "out_full" / "opinion_unit_quality.jsonl",
        SCRIPT_DIR / "out_full" / "insight_packets.jsonl",
        SCRIPT_DIR / "out_cross_entity" / "cross_entity_competitive.jsonl",
        SCRIPT_DIR / "out_gold_v1" / "source_classification.provisional_gold.jsonl",
    ]
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for path in paths:
        for row in read_jsonl(path):
            key = (str(row.get("case_id")), str(path.relative_to(SCRIPT_DIR)))
            if key in seen:
                continue
            seen.add(key)
            row["_audit_file"] = str(path.relative_to(SCRIPT_DIR))
            rows.append(row)
    return rows


def evidence_roles(case: dict[str, Any]) -> set[str]:
    return {str(ev.get("source_role_predicted") or "") for ev in case.get("evidence") or []}


def evidence_groups(case: dict[str, Any]) -> set[str]:
    return {str(ev.get("source_group_predicted") or "") for ev in case.get("evidence") or []}


def audit_case(case: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    task = case.get("task_type")
    labels = case.get("labels") or {}
    evidence = case.get("evidence") or []

    if not evidence:
        issues.append({"severity": "critical", "code": "empty_evidence"})

    for ev in evidence:
        role = ev.get("source_role_predicted")
        feedback = ev.get("feedback_type_predicted") or []
        if role in OWNED_ROLES and has_feedback(feedback):
            issues.append(
                {
                    "severity": "critical",
                    "code": "owned_source_has_feedback_labels",
                    "source_id": ev.get("source_id"),
                    "source_role": role,
                    "feedback_type_predicted": feedback,
                }
            )
        if role in CREATOR_ANALYST_ROLES and has_feedback(feedback) and not has_first_person_or_user_evidence(ev):
            issues.append(
                {
                    "severity": "review",
                    "code": "creator_or_analyst_feedback_needs_explicit_user_evidence",
                    "source_id": ev.get("source_id"),
                    "source_role": role,
                    "feedback_type_predicted": feedback,
                }
            )
        if role in {None, "", "unknown"} and ev.get("platform") == "linkedin":
            issues.append(
                {
                    "severity": "review",
                    "code": "linkedin_unknown_role_parseable_from_text",
                    "source_id": ev.get("source_id"),
                    "title": ev.get("title"),
                }
            )
        if text_too_short(ev):
            issues.append(
                {
                    "severity": "review",
                    "code": "low_signal_or_url_only_source",
                    "source_id": ev.get("source_id"),
                    "source_role": role,
                }
            )

    if task == "source_classification" and len(evidence) == 1:
        ev = evidence[0]
        label_role = labels.get("source_role_gold")
        label_group = labels.get("source_group_gold")
        predicted_role = ev.get("source_role_predicted")
        predicted_group = ev.get("source_group_predicted")
        if label_role and predicted_role and label_role != predicted_role:
            issues.append(
                {
                    "severity": "review",
                    "code": "source_role_label_differs_from_predicted",
                    "source_role_gold": label_role,
                    "source_role_predicted": predicted_role,
                }
            )
        if label_group and predicted_group and label_group != predicted_group:
            issues.append(
                {
                    "severity": "review",
                    "code": "source_group_label_differs_from_predicted",
                    "source_group_gold": label_group,
                    "source_group_predicted": predicted_group,
                }
            )

    if task == "opinion_unit_quality":
        roles = evidence_roles(case)
        current = case.get("current_output") or {}
        if roles & OWNED_ROLES:
            issues.append(
                {
                    "severity": "review",
                    "code": "opinion_from_owned_or_competitor_source",
                    "roles": sorted(roles),
                    "opinion": current.get("opinion"),
                }
            )

    if task == "insight_synthesis":
        groups = evidence_groups(case)
        current = case.get("current_output") or {}
        category = str(current.get("category") or labels.get("insight_category_gold") or "")
        if category in {"pain_point", "feature_request", "opportunity", "churn"}:
            if groups and groups <= {"owned_official", "affiliated_insider", ""}:
                issues.append(
                    {
                        "severity": "critical",
                        "code": "market_insight_from_owned_only",
                        "category": category,
                        "groups": sorted(groups),
                    }
                )
        if len({ev.get("content_type_predicted") for ev in evidence if ev.get("content_type_predicted")}) > 3:
            issues.append({"severity": "review", "code": "mixed_content_types"})

    if task == "cross_entity_competitive_synthesis":
        entity_roles = {ev.get("evidence_entity_role") for ev in evidence}
        if "competitor" not in entity_roles:
            issues.append({"severity": "critical", "code": "cross_entity_missing_competitor_evidence"})
        if "market" not in entity_roles:
            issues.append({"severity": "review", "code": "cross_entity_missing_market_evidence"})

    return issues


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Fireworks Label Consistency Report",
        "",
        f"Generated: {report['created_at']}",
        "",
        "## Summary",
        "",
    ]
    for key, value in report["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Issue Counts", ""])
    for code, count in report["issue_counts"].items():
        lines.append(f"- {code}: {count}")
    lines.extend(["", "## By Task", ""])
    for task, stats in report["task_counts"].items():
        lines.append(f"- {task}: {stats}")
    lines.extend(["", "## Highest Priority Examples", ""])
    for row in report["examples"][:20]:
        lines.append(f"### {row['case_id']} ({row['task_type']})")
        lines.append(f"- file: `{row['file']}`")
        lines.append(f"- issues: {', '.join(issue['code'] for issue in row['issues'])}")
        if row.get("title"):
            lines.append(f"- title: {row['title']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    cases = iter_cases()
    issue_counts: Counter[str] = Counter()
    severity_counts: Counter[str] = Counter()
    task_counts: dict[str, Counter[str]] = defaultdict(Counter)
    flagged: list[dict[str, Any]] = []

    for case in cases:
        issues = audit_case(case)
        task = str(case.get("task_type"))
        task_counts[task]["cases"] += 1
        if issues:
            task_counts[task]["flagged"] += 1
        for issue in issues:
            issue_counts[issue["code"]] += 1
            severity_counts[issue["severity"]] += 1
        if issues:
            current = case.get("current_output") or {}
            flagged.append(
                {
                    "case_id": case.get("case_id"),
                    "task_type": task,
                    "file": case.get("_audit_file"),
                    "title": current.get("title") or current.get("opinion"),
                    "issues": issues,
                }
            )

    def priority(row: dict[str, Any]) -> tuple[int, int]:
        severity = {"critical": 3, "review": 2}.get(row["issues"][0]["severity"], 1)
        return (max({"critical": 3, "review": 2}.get(issue["severity"], 1) for issue in row["issues"]), len(row["issues"]))

    flagged.sort(key=priority, reverse=True)
    report = {
        "version": "fireworks_label_consistency_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "cases_checked": len(cases),
            "cases_flagged": len(flagged),
            "critical_issues": severity_counts.get("critical", 0),
            "review_issues": severity_counts.get("review", 0),
        },
        "issue_counts": dict(issue_counts.most_common()),
        "task_counts": {task: dict(counter) for task, counter in sorted(task_counts.items())},
        "examples": flagged[:100],
        "notes": [
            "This is static validation, not final gold review.",
            "Critical issues should be fixed or blocklisted before promotion.",
            "Review issues may be acceptable for generated candidate pools but not for final training gold.",
        ],
    }
    write_json(DEFAULT_REPORT, report)
    DEFAULT_MD.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_MD.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report["counts"], indent=2, sort_keys=True))
    return 1 if report["counts"]["critical_issues"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
