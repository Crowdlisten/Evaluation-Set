#!/usr/bin/env python3
"""Package the safest Fireworks eval records for immediate testing.

This does not create new labels. It separates high-confidence eval material from
the larger candidate pool:

- partial source-provenance gold
- audited synthesis SFT records
- audited DPO preference pairs
- audited reward labels
- cross-entity structural challenge inputs
- multi-turn workflow checks derived from audited synthesis cases
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent


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


def load_blocklist(base_dir: Path) -> set[str]:
    return {
        row["case_id"]
        for row in read_jsonl(base_dir / "out_gold_review" / "training_blocklist.jsonl")
        if row.get("case_id")
    }


def package_source_provenance(base_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(base_dir / "out_gold_review" / "gold_seed.source_classification.jsonl")
    packaged = []
    for row in rows:
        ev = (row.get("evidence") or [{}])[0]
        packaged.append(
            {
                "eval_id": f"{row['case_id']}:source_provenance",
                "case_id": row["case_id"],
                "task_family": "source_provenance_classification",
                "input": {
                    "source": {
                        "platform": ev.get("platform"),
                        "url": ev.get("url"),
                        "author": ev.get("author"),
                        "title": ev.get("title"),
                        "text": ev.get("text"),
                        "metrics": ev.get("metrics"),
                    }
                },
                "expected": {
                    "source_role": row["labels"].get("source_role_gold"),
                    "source_group": row["labels"].get("source_group_gold"),
                    "feedback_type": row["labels"].get("feedback_type_gold"),
                },
                "assertions": [
                    "Do not infer user pain or feature requests from owned marketing.",
                    "Use URL/account provenance before interpreting content.",
                ],
                "quality": {
                    "status": "partial_gold",
                    "gold_fields": row["labels"].get("partial_gold_fields", []),
                    "content_type_gold": None,
                },
            }
        )
    return packaged


def package_sft(base_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(base_dir / "out_full" / "labels.sft.jsonl")
    out = []
    for row in rows:
        scores = row.get("rubric_scores") or {}
        if scores.get("overall", 0) < 88:
            continue
        out.append(
            {
                "eval_id": row["record_id"],
                "case_id": row["case_id"],
                "task_family": "grounded_insight_synthesis_sft",
                "messages": row.get("messages", []),
                "expected": row.get("assistant"),
                "rubric": {
                    "evidence_fidelity_min": 90,
                    "category_correctness_min": 90,
                    "source_role_awareness_min": 90,
                    "unsupported_claims_allowed": 0,
                },
                "quality": {
                    "status": "audited_model_output",
                    "gold_source": row.get("gold_source"),
                    "rubric_scores": scores,
                },
            }
        )
    return out


def package_preferences(base_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(base_dir / "out_full" / "labels.preference.jsonl")
    out = []
    for row in rows:
        if row.get("margin", 0) < 0.1:
            continue
        out.append(
            {
                "eval_id": row["record_id"],
                "case_id": row["case_id"],
                "task_family": "dpo_preference_pair",
                "messages": row.get("messages", []),
                "chosen": row.get("chosen"),
                "rejected": row.get("rejected"),
                "expected_preference": "chosen",
                "quality": {
                    "status": "audited_preference_pair",
                    "margin": row.get("margin"),
                    "chosen_scores": row.get("chosen_scores"),
                    "rejected_scores": row.get("rejected_scores"),
                    "preference_reason": row.get("preference_reason"),
                },
            }
        )
    return out


def package_reward(base_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(base_dir / "out_full" / "labels.reward.jsonl")
    out = []
    for row in rows:
        out.append(
            {
                "eval_id": row["record_id"],
                "case_id": row["case_id"],
                "task_family": "reward_model_scoring",
                "candidate_id": row.get("candidate_id"),
                "candidate_output": row.get("candidate_output"),
                "expected_reward": row.get("reward"),
                "expected_rubric_scores": row.get("rubric_scores"),
                "quality": {
                    "status": "audited_reward_label",
                    "violations": row.get("violations", []),
                    "grader_rationale": row.get("grader_rationale"),
                },
            }
        )
    return out


def package_cross_entity(base_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(base_dir / "out_cross_entity" / "cross_entity_competitive.jsonl")
    out = []
    for row in rows:
        out.append(
            {
                "eval_id": f"{row['case_id']}:cross_entity_structure",
                "case_id": row["case_id"],
                "task_family": "cross_entity_competitive_structure",
                "input": {
                    "target_entity": row.get("target_entity_name"),
                    "comparison_entities": row.get("comparison_entity_names"),
                    "comparison_scope": row.get("comparison_scope"),
                    "evidence": row.get("evidence"),
                },
                "expected": {
                    "must_separate_roles": ["target", "competitor", "market"],
                    "must_not_claim_winner_without_independent_evidence": True,
                    "comparison_axis": row.get("comparison_scope"),
                },
                "quality": {
                    "status": "structural_eval_not_gold_synthesis",
                    "note": "Evidence buckets are audited for structure, but final competitive synthesis still needs human review.",
                },
            }
        )
    return out


def package_multi_turn(sft_rows: list[dict[str, Any]], limit: int = 8) -> list[dict[str, Any]]:
    out = []
    for row in sft_rows[:limit]:
        expected = row.get("expected") or {}
        user_payload = {}
        messages = row.get("messages") or []
        if len(messages) >= 2:
            try:
                user_payload = json.loads(messages[1].get("content") or "{}")
            except json.JSONDecodeError:
                user_payload = {}
        out.append(
            {
                "eval_id": f"{row['case_id']}:multi_turn_grounded_insight",
                "case_id": row["case_id"],
                "task_family": "multi_turn_grounded_insight_workflow",
                "turns": [
                    {
                        "user": "Show the raw evidence and identify who is speaking in each source.",
                        "expected_checks": [
                            "Returns evidence IDs or URLs.",
                            "Separates official, employee, creator, competitor, and organic sources when present.",
                            "Does not summarize away source provenance.",
                        ],
                    },
                    {
                        "user": "Classify whether this is user feedback, marketing narrative, competitive evidence, or off-topic.",
                        "expected_checks": [
                            f"Final category should be compatible with: {expected.get('category')}",
                            "Official-only evidence must not become pain point or feature request.",
                        ],
                    },
                    {
                        "user": "Now write the final CrowdListen insight using only supported claims.",
                        "expected_output": expected,
                        "expected_checks": [
                            "No unsupported buyer/user claims.",
                            "Includes what not to claim or equivalent guardrails when evidence is promotional.",
                            "Keeps source-role awareness in the answer.",
                        ],
                    },
                ],
                "source_payload": user_payload,
                "quality": {
                    "status": "derived_from_audited_sft",
                    "note": "Multi-turn workflow eval derived from audited single-turn synthesis cases.",
                },
            }
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(SCRIPT_DIR))
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "out_eval_ready"))
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    out_dir = Path(args.out_dir)
    blocklist = load_blocklist(base_dir)

    source = package_source_provenance(base_dir)
    sft = package_sft(base_dir)
    pref = package_preferences(base_dir)
    reward = package_reward(base_dir)
    cross = package_cross_entity(base_dir)
    multi = package_multi_turn(sft)

    write_jsonl(out_dir / "source_provenance.partial_gold.jsonl", source)
    write_jsonl(out_dir / "insight_synthesis.audited_sft.jsonl", sft)
    write_jsonl(out_dir / "preference_pairs.audited_dpo.jsonl", pref)
    write_jsonl(out_dir / "reward_labels.audited_rft.jsonl", reward)
    write_jsonl(out_dir / "cross_entity.structural_eval.jsonl", cross)
    write_jsonl(out_dir / "multi_turn.workflow_eval.jsonl", multi)

    counts = {
        "source_provenance_partial_gold": len(source),
        "insight_synthesis_audited_sft": len(sft),
        "preference_pairs_audited_dpo": len(pref),
        "reward_labels_audited_rft": len(reward),
        "cross_entity_structural_eval": len(cross),
        "multi_turn_workflow_eval": len(multi),
    }
    manifest = {
        "version": "fireworks_eval_ready_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "counts": counts,
        "total_records": sum(counts.values()),
        "blocked_candidate_cases": len(blocklist),
        "task_families": dict(Counter(
            row["task_family"]
            for rows in [source, sft, pref, reward, cross, multi]
            for row in rows
        )),
        "quality_notes": [
            "This pack is for eval/testing, not blanket training.",
            "Source provenance records are partial gold only.",
            "SFT/DPO/RFT records come from audited synthesis outputs and rubric scores.",
            "Cross-entity records are structural challenge evals, not final synthesis gold.",
            "Multi-turn records are derived from audited single-turn synthesis cases.",
        ],
    }
    write_json(out_dir / "manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
