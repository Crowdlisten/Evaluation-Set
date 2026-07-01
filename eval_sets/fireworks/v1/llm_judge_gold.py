#!/usr/bin/env python3
"""LLM-as-judge adjudication for the Fireworks eval candidate pool.

This script does not mutate generated cases. It reads candidate cases, asks a
strict judge to review labels case by case, and writes an adjudication layer
under out_llm_judge/.

Gold policy:
- "provisional_gold" means one LLM judge says the labels are evidence-grounded.
- "needs_human_review" means the case is useful but not safe to promote.
- "reject" means the case should stay out of training/eval gold.

True frontier-grade gold should combine this output with human review or
multi-judge consensus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUT_DIR = SCRIPT_DIR / "out_llm_judge"
DEFAULT_MODEL = os.getenv("CROWDLISTEN_JUDGE_MODEL", "gpt-5.4-mini")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


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


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clamp_text(text: str | None, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "\n[TRUNCATED_FOR_JUDGE_INPUT]"


def compact_evidence(case: dict[str, Any], max_evidence: int, max_chars: int) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for ev in (case.get("evidence") or [])[:max_evidence]:
        items.append(
            {
                "source_id": ev.get("source_id"),
                "opinion_unit_id": ev.get("opinion_unit_id"),
                "platform": ev.get("platform"),
                "url": ev.get("url"),
                "title": ev.get("title"),
                "author": ev.get("author"),
                "sender_type_current": ev.get("sender_type_current"),
                "source_group_current": ev.get("source_group_current"),
                "source_role_predicted": ev.get("source_role_predicted"),
                "source_group_predicted": ev.get("source_group_predicted"),
                "content_type_predicted": ev.get("content_type_predicted"),
                "feedback_type_predicted": ev.get("feedback_type_predicted"),
                "evidence_entity_name": ev.get("evidence_entity_name"),
                "evidence_entity_role": ev.get("evidence_entity_role"),
                "relationship_to_target": ev.get("relationship_to_target"),
                "metrics": ev.get("metrics") or {},
                "engagement": ev.get("engagement"),
                "text": clamp_text(ev.get("text") or ev.get("snippet"), max_chars),
            }
        )
    return items


def load_cases(base_dir: Path) -> list[dict[str, Any]]:
    files = [
        base_dir / "out_full" / "source_classification.jsonl",
        base_dir / "out_full" / "opinion_unit_quality.jsonl",
        base_dir / "out_full" / "insight_packets.jsonl",
        base_dir / "out_cross_entity" / "cross_entity_competitive.jsonl",
    ]
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for path in files:
        for case in read_jsonl(path):
            case_id = str(case.get("case_id") or "")
            if not case_id or case_id in seen:
                continue
            seen.add(case_id)
            cases.append(case)
    return cases


def load_audit_index(base_dir: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(base_dir / "out_gold_review" / "audit_cases.jsonl")
    return {str(row.get("case_id")): row for row in rows if row.get("case_id")}


def select_cases(
    cases: list[dict[str, Any]],
    audit_index: dict[str, dict[str, Any]],
    limit: int | None,
    per_task_limit: int | None,
    case_ids: set[str] | None,
) -> list[dict[str, Any]]:
    if case_ids:
        return [case for case in cases if case.get("case_id") in case_ids]

    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_task[str(case.get("task_type"))].append(case)

    selected: list[dict[str, Any]] = []
    for task in sorted(by_task):
        rows = by_task[task]
        rows.sort(
            key=lambda c: (
                audit_index.get(str(c.get("case_id")), {}).get("severity", 0),
                len(audit_index.get(str(c.get("case_id")), {}).get("issues", [])),
                str(c.get("case_id")),
            ),
            reverse=True,
        )
        selected.extend(rows[:per_task_limit] if per_task_limit else rows)

    if limit:
        selected = selected[:limit]
    return selected


def allowed_labels(taxonomy: dict[str, Any], key: str) -> list[str]:
    return sorted((taxonomy.get(key, {}).get("labels") or {}).keys())


def build_prompt(
    case: dict[str, Any],
    taxonomy: dict[str, Any],
    audit: dict[str, Any] | None,
    max_evidence: int,
    max_chars: int,
) -> str:
    task = case.get("task_type")
    payload = {
        "case_id": case.get("case_id"),
        "entity_name": case.get("entity_name"),
        "task_type": task,
        "current_output": case.get("current_output"),
        "generated_labels": case.get("labels"),
        "audit_flags": audit or {},
        "evidence": compact_evidence(case, max_evidence=max_evidence, max_chars=max_chars),
        "allowed_labels": {
            "source_role": allowed_labels(taxonomy, "source_role"),
            "source_group": allowed_labels(taxonomy, "source_group"),
            "content_type": allowed_labels(taxonomy, "content_type"),
            "feedback_type": allowed_labels(taxonomy, "feedback_type"),
            "insight_category": allowed_labels(taxonomy, "insight_category"),
            "cluster_action": allowed_labels(taxonomy, "cluster_action"),
            "failure_mode": allowed_labels(taxonomy, "failure_mode"),
        },
        "judge_policy": [
            "Use provenance before interpreting content.",
            "Do not treat official, employee, or competitor marketing as user feedback unless it quotes or summarizes external users.",
            "Do not infer buyer demand from absence of detail.",
            "For clusters, each claim must map to evidence IDs.",
            "For competitor synthesis, separate target, competitor, and independent market evidence.",
            "If evidence is truncated or insufficient, mark needs_human_review.",
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)


JUDGE_SCHEMA = {
    "name": "crowdlisten_eval_judgment",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "case_id",
            "task_type",
            "decision",
            "confidence",
            "corrected_labels",
            "failure_modes",
            "evidence_checks",
            "rationale",
            "human_review_reason",
            "training_use",
        ],
        "properties": {
            "case_id": {"type": "string"},
            "task_type": {"type": "string"},
            "decision": {
                "type": "string",
                "enum": ["provisional_gold", "needs_human_review", "reject"],
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "corrected_labels": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "source_role_gold",
                    "source_group_gold",
                    "content_type_gold",
                    "feedback_type_gold",
                    "quality_gold",
                    "insight_category_gold",
                    "cluster_action_gold",
                    "cluster_purity_gold",
                    "supports_cluster",
                    "gold_groups",
                ],
                "properties": {
                    "source_role_gold": {"type": ["string", "null"]},
                    "source_group_gold": {"type": ["string", "null"]},
                    "content_type_gold": {"type": ["string", "null"]},
                    "feedback_type_gold": {"type": "array", "items": {"type": "string"}},
                    "quality_gold": {"type": ["string", "null"]},
                    "insight_category_gold": {"type": ["string", "null"]},
                    "cluster_action_gold": {"type": ["string", "null"]},
                    "cluster_purity_gold": {"type": ["string", "null"]},
                    "supports_cluster": {"type": ["boolean", "null"]},
                    "gold_groups": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["group_id", "title", "category", "evidence_ids"],
                            "properties": {
                                "group_id": {"type": "string"},
                                "title": {"type": "string"},
                                "category": {"type": "string"},
                                "evidence_ids": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                },
            },
            "failure_modes": {"type": "array", "items": {"type": "string"}},
            "evidence_checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["source_id", "role", "supports_case", "notes"],
                    "properties": {
                        "source_id": {"type": ["string", "null"]},
                        "role": {"type": ["string", "null"]},
                        "supports_case": {"type": "boolean"},
                        "notes": {"type": "string"},
                    },
                },
            },
            "rationale": {"type": "string"},
            "human_review_reason": {"type": ["string", "null"]},
            "training_use": {
                "type": "object",
                "additionalProperties": False,
                "required": ["eval_ready", "sft_ready", "dpo_ready", "reward_ready"],
                "properties": {
                    "eval_ready": {"type": "boolean"},
                    "sft_ready": {"type": "boolean"},
                    "dpo_ready": {"type": "boolean"},
                    "reward_ready": {"type": "boolean"},
                },
            },
        },
    },
    "strict": True,
}


SYSTEM_PROMPT = """You are a strict CrowdListen benchmark adjudicator.
Your job is to decide whether a generated eval case can become benchmark gold.
Prefer rejecting or human-reviewing uncertain cases over promoting noisy labels.
Return only valid JSON matching the schema.
"""


def call_openai(model: str, prompt: str, timeout: int) -> dict[str, Any]:
    from openai import OpenAI

    client = OpenAI(timeout=timeout)
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_schema", "json_schema": JUDGE_SCHEMA},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    content = response.choices[0].message.content or "{}"
    return json.loads(content)


def safe_case_stub(case: dict[str, Any], audit: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "case_id": case.get("case_id"),
        "task_type": case.get("task_type"),
        "source_ids": case.get("source_ids"),
        "source_set_hash": case.get("source_set_hash"),
        "generated_labels": case.get("labels"),
        "current_output": case.get("current_output"),
        "audit": audit or {},
    }


def make_adjudication(
    case: dict[str, Any],
    judgment: dict[str, Any],
    audit: dict[str, Any] | None,
    model: str,
    prompt_hash: str,
) -> dict[str, Any]:
    decision = judgment.get("decision")
    confidence = float(judgment.get("confidence") or 0)
    training_use = judgment.get("training_use") or {}

    if decision == "provisional_gold" and confidence < 0.85:
        decision = "needs_human_review"
        judgment["decision"] = decision
        judgment["human_review_reason"] = judgment.get("human_review_reason") or "Confidence below promotion threshold."
        training_use = {"eval_ready": False, "sft_ready": False, "dpo_ready": False, "reward_ready": False}
        judgment["training_use"] = training_use

    return {
        "case_id": case.get("case_id"),
        "task_type": case.get("task_type"),
        "decision": decision,
        "confidence": confidence,
        "model": model,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "prompt_hash": prompt_hash,
        "judgment": judgment,
        "case_stub": safe_case_stub(case, audit),
        "provenance": {
            "judge": "llm_judge_gold.py",
            "gold_status": "provisional_one_judge" if decision == "provisional_gold" else decision,
            "requires_human_or_consensus_for_training_gold": decision == "provisional_gold",
        },
    }


def render_report(manifest: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    by_task = Counter(row.get("task_type") for row in rows)
    by_decision = Counter(row.get("decision") for row in rows if row.get("decision"))
    lines = [
        "# Fireworks LLM Judge Gold Review",
        "",
        f"Generated: {manifest['created_at']}",
        f"Model: {manifest['model']}",
        "",
        "## Counts",
        "",
        f"- reviewed: {manifest['reviewed_cases']}",
        f"- provisional_gold: {by_decision.get('provisional_gold', 0)}",
        f"- needs_human_review: {by_decision.get('needs_human_review', 0)}",
        f"- reject: {by_decision.get('reject', 0)}",
        "",
        "## By Task",
        "",
    ]
    for task, count in by_task.most_common():
        lines.append(f"- {task}: {count}")
    lines.extend(["", "## Promotion Policy", ""])
    lines.extend(
        [
            "- LLM-reviewed records are provisional, not final human gold.",
            "- Promotion threshold is confidence >= 0.85 plus a provisional_gold decision.",
            "- Cases with truncation, unclear provenance, or unsupported insight claims should remain needs_human_review.",
            "- Training should use only human-approved or multi-judge consensus records.",
            "",
            "## Sample Decisions",
            "",
        ]
    )
    for row in rows[:20]:
        judgment = row.get("judgment") or {}
        lines.append(f"### {row['case_id']} ({row['task_type']})")
        lines.append("")
        if "decision" in row:
            lines.append(f"- decision: {row['decision']}")
            lines.append(f"- confidence: {row['confidence']}")
            lines.append(f"- rationale: {judgment.get('rationale')}")
        else:
            lines.append(f"- prompt_hash: {row.get('prompt_hash')}")
        if judgment.get("human_review_reason"):
            lines.append(f"- human review: {judgment.get('human_review_reason')}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-dir", default=str(SCRIPT_DIR))
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR))
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--limit", type=int, default=40)
    parser.add_argument("--per-task-limit", type=int, default=10)
    parser.add_argument("--case-id", action="append", default=[])
    parser.add_argument("--max-evidence", type=int, default=8)
    parser.add_argument("--max-chars-per-evidence", type=int, default=3500)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--sleep", type=float, default=0.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    base_dir = Path(args.base_dir)
    out_dir = Path(args.out_dir)
    load_dotenv(base_dir.parents[2] / ".env")
    load_dotenv(Path.cwd() / ".env")

    taxonomy = read_json(base_dir / "taxonomy.json")
    cases = load_cases(base_dir)
    audit_index = load_audit_index(base_dir)
    selected = select_cases(
        cases,
        audit_index,
        limit=args.limit,
        per_task_limit=args.per_task_limit,
        case_ids=set(args.case_id) if args.case_id else None,
    )

    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    if args.dry_run:
        for case in selected:
            audit = audit_index.get(str(case.get("case_id")))
            prompt = build_prompt(case, taxonomy, audit, args.max_evidence, args.max_chars_per_evidence)
            rows.append(
                {
                    "case_id": case.get("case_id"),
                    "task_type": case.get("task_type"),
                    "prompt_hash": stable_hash(prompt),
                    "prompt_preview": prompt[:5000],
                }
            )
    else:
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set; run with --dry-run or configure a key.")
        for index, case in enumerate(selected, start=1):
            case_id = str(case.get("case_id"))
            audit = audit_index.get(case_id)
            prompt = build_prompt(case, taxonomy, audit, args.max_evidence, args.max_chars_per_evidence)
            prompt_hash = stable_hash(prompt)
            try:
                judgment = call_openai(args.model, prompt, args.timeout)
                rows.append(make_adjudication(case, judgment, audit, args.model, prompt_hash))
                print(f"[{index}/{len(selected)}] judged {case_id}")
            except Exception as exc:  # noqa: BLE001
                failures.append(
                    {
                        "case_id": case_id,
                        "task_type": case.get("task_type"),
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                    }
                )
                print(f"[{index}/{len(selected)}] failed {case_id}: {type(exc).__name__}: {exc}")
            if args.sleep:
                time.sleep(args.sleep)

    created_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "version": "fireworks_llm_judge_gold_v1",
        "created_at": created_at,
        "model": args.model,
        "dry_run": args.dry_run,
        "candidate_cases_available": len(cases),
        "selected_cases": len(selected),
        "reviewed_cases": len(rows),
        "failed_cases": len(failures),
        "counts_by_task": dict(Counter(row.get("task_type") for row in rows)),
        "counts_by_decision": dict(Counter(row.get("decision") for row in rows if row.get("decision"))),
        "promotion_policy": {
            "provisional_gold_confidence_threshold": 0.85,
            "human_or_multi_judge_required_for_final_training_gold": True,
        },
    }

    suffix = "dry_run" if args.dry_run else "adjudications"
    write_json(out_dir / "manifest.json", manifest)
    write_jsonl(out_dir / f"{suffix}.jsonl", rows)
    write_jsonl(out_dir / "failures.jsonl", failures)
    (out_dir / "report.md").write_text(render_report(manifest, rows), encoding="utf-8")
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
