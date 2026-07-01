#!/usr/bin/env python3
"""Offline tests for RLM-style post-embedding insight refinement.

This script evaluates the RLM variants that were previously designed for the
Fireworks case study:

- flat_llm
- audit_rewrite
- source_aware_recursive

It has two parts:

1. Re-summarize the existing judged slice from
   docs/fireworks_rlm_synthesis_eval_2026-06-30.json.
2. Run a deterministic proxy of each strategy across every checked-in
   insight_synthesis packet to measure label/provenance failure rates.

The proxy is not a learned RLM. It is a reproducible guardrail test for the
same behaviors the RLM layer is supposed to improve: source-role awareness,
cluster splitting, and avoiding fake market demand from owned marketing.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
DOCS_DIR = REPO_ROOT / "docs"
DEFAULT_OUT_DIR = SCRIPT_DIR / "out_rlm_eval"

INSIGHT_PACKETS = SCRIPT_DIR / "out_full" / "insight_packets.jsonl"
AUDITED_SFT = SCRIPT_DIR / "out_eval_ready" / "insight_synthesis.audited_sft.jsonl"
BLOCKLIST = SCRIPT_DIR / "out_gold_review" / "training_blocklist.jsonl"
JUDGED_SLICE = DOCS_DIR / "fireworks_rlm_synthesis_eval_2026-06-30.json"

DEMAND_CATEGORIES = {"pain_point", "feature_request", "opportunity", "churn"}
OWNED_GROUPS = {"owned_official", "affiliated_insider", ""}
INDEPENDENT_GROUPS = {"organic_market", "customer_user", "creator_analyst"}
ROLE_GROUP_CATEGORY = {
    "owned_official": "marketing_narrative",
    "affiliated_insider": "technical_proof",
    "competitor_ecosystem": "competitive",
    "organic_market": "opportunity",
    "customer_user": "customer_success",
    "creator_analyst": "marketing_narrative",
}
CONTENT_TYPE_CATEGORY = {
    "product_launch": "product_launch",
    "technical_proof": "technical_proof",
    "customer_story": "customer_success",
    "competitive_claim": "competitive",
    "comparison": "competitive",
    "tutorial": "marketing_narrative",
    "thought_leadership": "marketing_narrative",
}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def normalize(value: Any) -> str:
    return str(value or "").strip()


def evidence(packet: dict[str, Any]) -> list[dict[str, Any]]:
    return list(packet.get("evidence") or [])


def group_counts(packet: dict[str, Any]) -> Counter[str]:
    return Counter(normalize(ev.get("source_group_predicted")) for ev in evidence(packet))


def role_counts(packet: dict[str, Any]) -> Counter[str]:
    return Counter(normalize(ev.get("source_role_predicted")) for ev in evidence(packet))


def content_counts(packet: dict[str, Any]) -> Counter[str]:
    return Counter(normalize(ev.get("content_type_predicted")) for ev in evidence(packet))


def current_category(packet: dict[str, Any]) -> str:
    return normalize((packet.get("current_output") or {}).get("category"))


def current_title(packet: dict[str, Any]) -> str:
    return normalize((packet.get("current_output") or {}).get("title"))


def majority(counter: Counter[str]) -> str:
    for key, _ in counter.most_common():
        if key:
            return key
    return ""


def owned_only(packet: dict[str, Any]) -> bool:
    groups = set(group_counts(packet))
    return bool(groups) and groups <= OWNED_GROUPS


def has_independent_market_evidence(packet: dict[str, Any]) -> bool:
    return bool(set(group_counts(packet)) & INDEPENDENT_GROUPS)


def mixed_content(packet: dict[str, Any]) -> bool:
    return len({key for key in content_counts(packet) if key}) > 3


def low_signal_ratio(packet: dict[str, Any]) -> float:
    rows = evidence(packet)
    if not rows:
        return 1.0
    low = 0
    for ev in rows:
        text = normalize(ev.get("text") or ev.get("snippet"))
        text_without_urls = " ".join(part for part in text.split() if not part.startswith(("http://", "https://", "t.co/")))
        if len(text_without_urls) < 30:
            low += 1
    return low / len(rows)


def category_from_evidence(packet: dict[str, Any], fallback: str) -> str:
    content_type = majority(content_counts(packet))
    if content_type in CONTENT_TYPE_CATEGORY:
        return CONTENT_TYPE_CATEGORY[content_type]
    group = majority(group_counts(packet))
    return ROLE_GROUP_CATEGORY.get(group, fallback)


def baseline(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "category": current_category(packet),
        "action": "keep",
        "split_recommended": False,
        "discard_recommended": False,
        "notes": [],
    }


def flat_llm_proxy(packet: dict[str, Any]) -> dict[str, Any]:
    category = current_category(packet)
    notes: list[str] = []
    if category in DEMAND_CATEGORIES and owned_only(packet):
        category = category_from_evidence(packet, "marketing_narrative")
        notes.append("relabel_owned_only_demand")
    if category in DEMAND_CATEGORIES and not has_independent_market_evidence(packet):
        category = category_from_evidence(packet, "marketing_narrative")
        notes.append("relabel_no_independent_market_evidence")
    return {
        "category": category,
        "action": "keep",
        "split_recommended": False,
        "discard_recommended": False,
        "notes": notes,
    }


def audit_rewrite_proxy(packet: dict[str, Any]) -> dict[str, Any]:
    result = flat_llm_proxy(packet)
    notes = list(result["notes"])
    action = "keep"
    if low_signal_ratio(packet) >= 0.5:
        action = "discard"
        notes.append("discard_low_signal_cluster")
    elif mixed_content(packet):
        action = "split"
        notes.append("split_mixed_content_types")
    return {
        "category": result["category"],
        "action": action,
        "split_recommended": action == "split",
        "discard_recommended": action == "discard",
        "notes": notes,
    }


def source_aware_recursive_proxy(packet: dict[str, Any]) -> dict[str, Any]:
    result = flat_llm_proxy(packet)
    notes = list(result["notes"])
    action = "keep"
    groups = {key for key in group_counts(packet) if key}
    contents = {key for key in content_counts(packet) if key}
    if low_signal_ratio(packet) >= 0.5:
        action = "discard"
        notes.append("discard_low_signal_cluster")
    elif len(groups) > 2 or len(contents) > 3:
        action = "split"
        notes.append("split_by_source_group_and_content_type")
    category = category_from_evidence(packet, result["category"])
    if result["category"] in {"competitive", "customer_success", "technical_proof"}:
        category = result["category"]
    return {
        "category": category,
        "action": action,
        "split_recommended": action == "split",
        "discard_recommended": action == "discard",
        "notes": notes,
    }


VARIANTS = {
    "baseline": baseline,
    "flat_llm_proxy": flat_llm_proxy,
    "audit_rewrite_proxy": audit_rewrite_proxy,
    "source_aware_recursive_proxy": source_aware_recursive_proxy,
}


def load_expected_categories() -> dict[str, str]:
    rows = read_jsonl(AUDITED_SFT)
    return {row["case_id"]: normalize((row.get("expected") or {}).get("category")) for row in rows}


def load_blocklist() -> set[str]:
    return {row["case_id"] for row in read_jsonl(BLOCKLIST)}


def evaluate_prediction(packet: dict[str, Any], prediction: dict[str, Any], blocklisted: set[str]) -> list[str]:
    issues: list[str] = []
    category = prediction["category"]
    action = prediction["action"]
    if category in DEMAND_CATEGORIES and owned_only(packet):
        issues.append("market_insight_from_owned_only")
    if category in DEMAND_CATEGORIES and not has_independent_market_evidence(packet):
        issues.append("demand_without_independent_market_evidence")
    if mixed_content(packet) and action == "keep":
        issues.append("mixed_content_kept")
    if low_signal_ratio(packet) >= 0.5 and action != "discard":
        issues.append("low_signal_not_discarded")
    if packet["case_id"] in blocklisted and action == "keep":
        issues.append("blocklisted_case_retained")
    return issues


def summarize_judged_slice() -> dict[str, Any]:
    if not JUDGED_SLICE.exists():
        return {"available": False}
    data = read_json(JUDGED_SLICE)
    results = data.get("results") or []
    strategy_scores: dict[str, dict[str, float]] = {}
    winner_counts: Counter[str] = Counter()
    for row in results:
        winner_counts[row.get("winner") or "unknown"] += 1
        for strategy, scores in (row.get("scores") or {}).items():
            bucket = strategy_scores.setdefault(strategy, Counter())
            for metric, value in scores.items():
                if isinstance(value, (int, float)):
                    bucket[metric] += float(value)
            bucket["_n"] += 1
    averages: dict[str, dict[str, float]] = {}
    for strategy, scores in strategy_scores.items():
        n = scores.pop("_n", 0) or 1
        averages[strategy] = {metric: round(value / n, 2) for metric, value in scores.items()}
    return {
        "available": True,
        "evaluated_clusters": len(results),
        "winner_counts": dict(winner_counts),
        "average_scores": averages,
    }


def evaluate_full_packet_proxies() -> dict[str, Any]:
    packets = read_jsonl(INSIGHT_PACKETS)
    blocklisted = load_blocklist()
    expected_categories = load_expected_categories()
    variant_reports: dict[str, Any] = {}

    for name, predict in VARIANTS.items():
        issue_counts: Counter[str] = Counter()
        action_counts: Counter[str] = Counter()
        category_changes: Counter[str] = Counter()
        gold_overlap = 0
        gold_category_matches = 0
        examples: list[dict[str, Any]] = []
        for packet in packets:
            prediction = predict(packet)
            issues = evaluate_prediction(packet, prediction, blocklisted)
            issue_counts.update(issues)
            action_counts[prediction["action"]] += 1
            before = current_category(packet)
            after = prediction["category"]
            if before != after:
                category_changes[f"{before}->{after}"] += 1
            expected = expected_categories.get(packet["case_id"])
            if expected:
                gold_overlap += 1
                if after == expected:
                    gold_category_matches += 1
            if issues and len(examples) < 8:
                examples.append(
                    {
                        "case_id": packet["case_id"],
                        "title": current_title(packet),
                        "current_category": before,
                        "predicted_category": after,
                        "action": prediction["action"],
                        "issues": issues,
                        "source_groups": dict(group_counts(packet)),
                        "content_types": dict(content_counts(packet)),
                    }
                )

        total_issue_count = sum(issue_counts.values())
        denominator = max(1, len(packets))
        variant_reports[name] = {
            "packets_evaluated": len(packets),
            "issue_counts": dict(issue_counts),
            "issue_rate": round(total_issue_count / denominator, 4),
            "packets_with_any_issue": sum(
                1 for packet in packets if evaluate_prediction(packet, predict(packet), blocklisted)
            ),
            "action_counts": dict(action_counts),
            "category_changes": dict(category_changes),
            "gold_overlap": gold_overlap,
            "gold_category_matches": gold_category_matches,
            "gold_category_accuracy": round(gold_category_matches / gold_overlap, 4) if gold_overlap else None,
            "examples": examples,
        }

    return {
        "packets_evaluated": len(packets),
        "blocklisted_insight_packets": sum(1 for packet in packets if packet["case_id"] in blocklisted),
        "audited_sft_overlap": len(expected_categories),
        "variants": variant_reports,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Fireworks RLM Variant Eval",
        "",
        f"Generated: {report['created_at']}",
        "",
        "This report tests RLM-style post-embedding synthesis behavior against the checked-in Fireworks case-study eval package.",
        "",
        "## Judged Slice",
        "",
    ]
    judged = report["judged_slice"]
    if not judged.get("available"):
        lines.append("No judged slice found.")
    else:
        lines.append(f"- evaluated clusters: {judged['evaluated_clusters']}")
        lines.append(f"- winner counts: `{judged['winner_counts']}`")
        lines.append("")
        for strategy, scores in judged["average_scores"].items():
            lines.append(f"### {strategy}")
            for metric, value in scores.items():
                lines.append(f"- {metric}: `{value}`")
            lines.append("")

    lines.extend(["## Full Insight Packet Proxy Eval", ""])
    full = report["full_packet_proxy_eval"]
    lines.append(f"- packets evaluated: {full['packets_evaluated']}")
    lines.append(f"- blocklisted insight packets: {full['blocklisted_insight_packets']}")
    lines.append(f"- audited SFT overlap: {full['audited_sft_overlap']}")
    lines.append("")
    for name, result in full["variants"].items():
        lines.append(f"### {name}")
        lines.append(f"- issue rate: `{result['issue_rate']}`")
        lines.append(f"- packets with any issue: `{result['packets_with_any_issue']}`")
        lines.append(f"- actions: `{result['action_counts']}`")
        lines.append(f"- issue counts: `{result['issue_counts']}`")
        lines.append(f"- category changes: `{result['category_changes']}`")
        if result["gold_category_accuracy"] is not None:
            lines.append(
                f"- audited category accuracy: `{result['gold_category_accuracy']}` "
                f"({result['gold_category_matches']}/{result['gold_overlap']})"
            )
        lines.append("")

    lines.extend(["## Interpretation", ""])
    lines.extend(
        [
            "- The judged slice is the best quality comparison because it includes explicit LLM-judge scores.",
            "- The full-packet proxy is a regression guardrail, not a substitute for human gold labels.",
            "- A real RLM layer should be considered useful only if it preserves the judged-slice gains while reducing full-packet source-role and mixed-cluster failures.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "judged_slice": summarize_judged_slice(),
        "full_packet_proxy_eval": evaluate_full_packet_proxies(),
    }
    DEFAULT_OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_json(DEFAULT_OUT_DIR / "rlm_variant_report.json", report)
    (DEFAULT_OUT_DIR / "rlm_variant_report.md").write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {DEFAULT_OUT_DIR / 'rlm_variant_report.json'}")
    print(f"wrote {DEFAULT_OUT_DIR / 'rlm_variant_report.md'}")


if __name__ == "__main__":
    main()
