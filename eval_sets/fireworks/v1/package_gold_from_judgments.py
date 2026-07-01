#!/usr/bin/env python3
"""Package LLM-adjudicated records into a clean provisional gold eval pack."""

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
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True, ensure_ascii=False, default=str) + "\n")


def load_case_index(base_dir: Path) -> dict[str, dict[str, Any]]:
    paths = [
        base_dir / "out_full" / "source_classification.jsonl",
        base_dir / "out_full" / "opinion_unit_quality.jsonl",
        base_dir / "out_full" / "insight_packets.jsonl",
        base_dir / "out_cross_entity" / "cross_entity_competitive.jsonl",
    ]
    index: dict[str, dict[str, Any]] = {}
    for path in paths:
        for case in read_jsonl(path):
            if case.get("case_id"):
                index[str(case["case_id"])] = case
    return index


def promote_case(case: dict[str, Any], adjudication: dict[str, Any]) -> dict[str, Any]:
    promoted = json.loads(json.dumps(case))
    judgment = adjudication["judgment"]
    corrected = judgment.get("corrected_labels") or {}
    promoted["labels"].update({k: v for k, v in corrected.items() if v is not None})
    promoted["labels"]["review_status"] = "reviewed"
    promoted["labels"]["gold_status"] = "llm_provisional_gold"
    promoted["labels"]["gold_source"] = "llm_judge_gold.py"
    promoted["labels"]["judge_model"] = adjudication.get("model")
    promoted["labels"]["judge_confidence"] = adjudication.get("confidence")
    promoted["labels"]["rationale"] = judgment.get("rationale")
    promoted["labels"]["human_notes"] = judgment.get("human_review_reason")
    promoted["labels"]["failure_modes"] = judgment.get("failure_modes") or []
    promoted["training_views"].update(
        {
            "eval_only": not bool((judgment.get("training_use") or {}).get("sft_ready")),
            "sft_ready": False,
            "dpo_ready": False,
            "reward_ready": False,
            "llm_provisional_eval_ready": bool((judgment.get("training_use") or {}).get("eval_ready")),
            "requires_human_or_consensus_for_training": True,
        }
    )
    promoted["provenance"]["gold_adjudication"] = {
        "adjudication_prompt_hash": adjudication.get("prompt_hash"),
        "adjudicated_at": adjudication.get("created_at"),
        "decision": adjudication.get("decision"),
        "confidence": adjudication.get("confidence"),
    }
    return promoted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(SCRIPT_DIR))
    parser.add_argument("--judgments-dir", default=str(SCRIPT_DIR / "out_llm_judge_source_seed_full"))
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "out_gold_v1"))
    parser.add_argument("--min-confidence", type=float, default=0.85)
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    judgments_dir = Path(args.judgments_dir)
    out_dir = Path(args.out_dir)

    cases = load_case_index(base_dir)
    adjudications = read_jsonl(judgments_dir / "adjudications.jsonl")

    promoted: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    missing_cases: list[str] = []

    for adj in adjudications:
        case_id = str(adj.get("case_id"))
        case = cases.get(case_id)
        if not case:
            missing_cases.append(case_id)
            continue
        if adj.get("decision") == "provisional_gold" and float(adj.get("confidence") or 0) >= args.min_confidence:
            promoted.append(promote_case(case, adj))
        elif adj.get("decision") == "reject":
            rejected.append(adj)
        else:
            review_queue.append(adj)

    by_task = Counter(row.get("task_type") for row in promoted)
    by_role = Counter((row.get("labels") or {}).get("source_role_gold") for row in promoted)
    by_content = Counter((row.get("labels") or {}).get("content_type_gold") for row in promoted)

    write_jsonl(out_dir / "source_classification.provisional_gold.jsonl", promoted)
    write_jsonl(out_dir / "needs_human_review.jsonl", review_queue)
    write_jsonl(out_dir / "rejected.jsonl", rejected)
    write_json(
        out_dir / "manifest.json",
        {
            "version": "fireworks_gold_v1_provisional",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_judgments_dir": str(judgments_dir),
            "min_confidence": args.min_confidence,
            "counts": {
                "promoted": len(promoted),
                "needs_human_review": len(review_queue),
                "rejected": len(rejected),
                "missing_cases": len(missing_cases),
            },
            "promoted_by_task": dict(by_task),
            "promoted_source_role_counts": dict(by_role),
            "promoted_content_type_counts": dict(by_content),
            "quality_notes": [
                "This pack is LLM-provisional gold, not human_gold.",
                "Use for eval regression and reviewer bootstrapping.",
                "Do not use for final training until human or multi-judge consensus promotion.",
            ],
        },
    )
    print(json.dumps(read_jsonl(out_dir / "source_classification.provisional_gold.jsonl")[:1], indent=2, ensure_ascii=False, default=str))
    print(f"promoted={len(promoted)} review={len(review_queue)} rejected={len(rejected)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
