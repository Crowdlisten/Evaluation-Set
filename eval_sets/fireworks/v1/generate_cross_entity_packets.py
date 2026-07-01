#!/usr/bin/env python3
"""Generate Fireworks cross-entity competitor eval packets.

This is read-only against Supabase. It pairs Fireworks evidence with Baseten and
Modal evidence by marketing/comparison axis so we can evaluate whether synthesis
keeps entity attribution straight.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]
GENERATOR_PATH = SCRIPT_DIR / "generate_eval_packets.py"
CONFIG_PATH = SCRIPT_DIR / "competitors.json"
INPUT_VERSION = "crowdlisten_fireworks_cross_entity_v1"


def _load_base_generator() -> Any:
    spec = importlib.util.spec_from_file_location("fireworks_eval_generator", GENERATOR_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {GENERATOR_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gen = _load_base_generator()


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str) + "\n")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, default=str) + "\n")


def source_blob(row: dict[str, Any]) -> str:
    values = [
        row.get("title"),
        gen.source_text(row),
        gen.source_url(row),
        gen.author(row),
        gen.platform(row),
    ]
    return " ".join(str(value or "") for value in values).lower()


def row_score(row: dict[str, Any], terms: list[str]) -> float:
    blob = source_blob(row)
    term_hits = sum(1 for term in terms if term.lower() in blob)
    role = gen.infer_source_role(row)
    role_bonus = {
        "official_brand": 2.5,
        "competitor_official": 2.5,
        "employee": 1.5,
        "competitor_employee": 1.5,
        "affiliate_creator": 1.0,
        "community_member": 0.75,
        "customer_user": 1.25,
        "prospect_buyer": 1.25,
    }.get(role, 0.0)
    return term_hits * 10 + min(gen.engagement(row), 100000) / 10000 + role_bonus


def select_axis_sources(rows: list[dict[str, Any]], terms: list[str], limit: int) -> list[dict[str, Any]]:
    scored = [(row_score(row, terms), row) for row in rows]
    candidates = [item for item in scored if item[0] > 0]
    if not candidates:
        candidates = scored
    candidates.sort(key=lambda item: item[0], reverse=True)

    selected: list[dict[str, Any]] = []
    seen_signatures: set[str] = set()
    for _, row in candidates:
        text = gen.source_text(row)
        if len(text) < 40:
            continue
        signature = gen.source_url(row) or gen.text_hash(text)
        if signature in seen_signatures:
            continue
        selected.append(row)
        seen_signatures.add(signature)
        if len(selected) >= limit:
            break
    return selected


def source_group(row: dict[str, Any]) -> str:
    return gen.infer_source_group(gen.infer_source_role(row))


def source_role(row: dict[str, Any]) -> str:
    return gen.infer_source_role(row)


def filter_rows_for_bucket(rows: list[dict[str, Any]], bucket: str) -> list[dict[str, Any]]:
    """Keep evidence buckets semantically clean.

    Target and competitor buckets should contain owned/insider claims from that
    entity. Market evidence should contain third-party/organic/customer sources.
    This prevents vendor claims and independent evidence from being conflated.
    """
    if bucket == "target":
        return [
            row
            for row in rows
            if source_group(row) in {"owned_official", "affiliated_insider", "customer_proof"}
        ]
    if bucket == "competitor":
        return [
            row
            for row in rows
            if source_group(row) in {"owned_official", "affiliated_insider", "competitor_ecosystem"}
            or source_role(row) in {"competitor_official", "competitor_employee"}
        ]
    if bucket == "market":
        return [
            row
            for row in rows
            if source_group(row) in {"organic_market", "creator_analyst", "customer_proof"}
        ]
    return rows


def entity_evidence_item(
    row: dict[str, Any],
    entity: dict[str, Any],
    role: str,
    target_entity_id: str,
) -> dict[str, Any]:
    ev = gen.evidence_item(row)
    native_role = ev.get("source_role_predicted")
    ev.update(
        {
            "evidence_entity_id": entity["entity_id"],
            "evidence_entity_name": entity["entity_name"],
            "evidence_entity_role": role,
            "relationship_to_target": "self" if entity["entity_id"] == target_entity_id else "competes_with",
            "native_source_role_predicted": native_role,
        }
    )
    if role == "competitor" and native_role in {"official_brand", "employee", "founder_exec"}:
        ev["source_role_predicted"] = "competitor_official" if native_role == "official_brand" else "competitor_employee"
        ev["source_group_predicted"] = "competitor_ecosystem"
    return ev


def make_case(
    target: dict[str, Any],
    competitor: dict[str, Any],
    axis: str,
    terms: list[str],
    target_rows: list[dict[str, Any]],
    competitor_rows: list[dict[str, Any]],
    market_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    for row in target_rows:
        evidence.append(entity_evidence_item(row, target, "target", target["entity_id"]))
    for row in competitor_rows:
        evidence.append(entity_evidence_item(row, competitor, "competitor", target["entity_id"]))
    for row in market_rows:
        evidence.append(entity_evidence_item(row, {"entity_id": target["entity_id"], "entity_name": target["entity_name"]}, "market", target["entity_id"]))

    source_ids = sorted({str(ev["source_id"]) for ev in evidence if ev.get("source_id")})
    current_output = {
        "id": f"{target['entity_id']}:{competitor['entity_id']}:{axis}",
        "title": f"{competitor['entity_name']} vs {target['entity_name']}: {axis.replace('_', ' ')}",
        "description": "Draft comparison packet. The model should identify what each entity is claiming, what independent market evidence supports, and where attribution is uncertain.",
        "category": "competitive",
        "comparison_axis": axis,
        "terms": terms,
    }
    payload_for_hash = {
        "task_type": "cross_entity_competitive_synthesis",
        "target": target,
        "competitor": competitor,
        "axis": axis,
        "source_ids": source_ids,
        "text_hashes": [gen.text_hash(ev.get("text")) for ev in evidence],
    }
    case = {
        "case_id": gen.make_case_id("cross_entity_competitive_synthesis", [target["entity_id"], competitor["entity_id"], axis, source_ids]),
        "entity_id": target["entity_id"],
        "entity_name": target["entity_name"],
        "task_type": "cross_entity_competitive_synthesis",
        "input_version": INPUT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_ids": source_ids,
        "target_entity_id": target["entity_id"],
        "target_entity_name": target["entity_name"],
        "comparison_entity_ids": [competitor["entity_id"]],
        "comparison_entity_names": [competitor["entity_name"]],
        "comparison_scope": axis,
        "evidence": evidence,
        "current_output": current_output,
        "labels": {
            "review_status": "draft",
            "insight_category_gold": "competitive",
            "cluster_action_gold": None,
            "cluster_purity_gold": None,
            "comparison_axis_gold": axis,
            "failure_modes": [],
            "gold_groups": [
                {
                    "group_id": "target_claims",
                    "title": f"{target['entity_name']} evidence",
                    "category": "target",
                    "evidence_ids": [ev["source_id"] for ev in evidence if ev.get("evidence_entity_role") == "target"],
                },
                {
                    "group_id": "competitor_claims",
                    "title": f"{competitor['entity_name']} evidence",
                    "category": "competitor",
                    "evidence_ids": [ev["source_id"] for ev in evidence if ev.get("evidence_entity_role") == "competitor"],
                },
                {
                    "group_id": "independent_market_evidence",
                    "title": "Independent market evidence",
                    "category": "market",
                    "evidence_ids": [ev["source_id"] for ev in evidence if ev.get("evidence_entity_role") == "market"],
                },
            ],
            "rationale": "Draft cross-entity case. Human review should verify entity attribution, source independence, and whether any comparative claim is supported.",
        },
        "training_views": {
            "sft_ready": False,
            "dpo_ready": False,
            "reward_ready": False,
            "eval_only": True,
        },
        "input_hash": gen.stable_hash(payload_for_hash),
        "source_set_hash": gen.stable_hash(source_ids),
        "hashes": {
            "source_text_hashes": gen.stable_hash([gen.text_hash(ev.get("text")) for ev in evidence]),
            "urls": gen.stable_hash(sorted(ev.get("url") for ev in evidence if ev.get("url"))),
        },
        "provenance": {
            "generator": "generate_cross_entity_packets.py",
            "target_entity": target,
            "comparison_entity": competitor,
        },
    }
    return case


def fetch_sources(sb: Any, entity_id: str) -> list[dict[str, Any]]:
    return gen.fetch_all(sb, "content_store", "*", [("eq", "entity_id", entity_id)])


def platform_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(gen.platform(row) or "unknown" for row in rows))


def build_cases(
    sb: Any,
    config: dict[str, Any],
    per_axis: int,
    include_market: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    target = config["target"]
    axes = config["comparison_axes"]
    target_sources = fetch_sources(sb, target["entity_id"])
    sources_by_entity = {target["entity_id"]: target_sources}
    for competitor in config["competitors"]:
        sources_by_entity[competitor["entity_id"]] = fetch_sources(sb, competitor["entity_id"])

    market_sources = target_sources
    cases: list[dict[str, Any]] = []
    selection_summary: dict[str, Any] = {
        target["entity_name"]: {
            "entity_id": target["entity_id"],
            "content_store_rows": len(target_sources),
            "platform_counts": platform_counts(target_sources),
        }
    }
    for competitor in config["competitors"]:
        competitor_sources = sources_by_entity[competitor["entity_id"]]
        selection_summary[competitor["entity_name"]] = {
            "entity_id": competitor["entity_id"],
            "content_store_rows": len(competitor_sources),
            "platform_counts": platform_counts(competitor_sources),
        }
        for axis, terms in axes.items():
            target_rows = select_axis_sources(
                filter_rows_for_bucket(target_sources, "target"),
                terms,
                per_axis,
            )
            competitor_rows = select_axis_sources(
                filter_rows_for_bucket(competitor_sources, "competitor"),
                terms,
                per_axis,
            )
            if not target_rows or not competitor_rows:
                continue
            market_rows = []
            if include_market:
                selected_ids = {str(row.get("id")) for row in [*target_rows, *competitor_rows]}
                market_pool = [
                    row
                    for row in filter_rows_for_bucket(market_sources, "market")
                    if str(row.get("id")) not in selected_ids
                ]
                market_rows = select_axis_sources(market_pool, terms, max(2, per_axis // 2))
            cases.append(
                make_case(
                    target=target,
                    competitor=competitor,
                    axis=axis,
                    terms=terms,
                    target_rows=target_rows,
                    competitor_rows=competitor_rows,
                    market_rows=market_rows,
                )
            )
    return cases, selection_summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default=str(SCRIPT_DIR / "out_cross_entity"))
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--dotenv", default=str(REPO_ROOT / ".env"))
    parser.add_argument("--per-axis", type=int, default=8)
    parser.add_argument("--include-market", action=argparse.BooleanOptionalAction, default=True)
    args = parser.parse_args()

    gen.load_dotenv(Path(args.dotenv))
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
    config = load_config(Path(args.config))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cases, selection_summary = build_cases(sb, config, per_axis=args.per_axis, include_market=args.include_market)
    splits = gen.assign_splits(cases)
    leakage = gen.leakage_index(cases)
    manifest = {
        "version": "fireworks_cross_entity_eval_set_v1",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "read_only_supabase": True,
        "target_entity_id": config["target"]["entity_id"],
        "target_entity_name": config["target"]["entity_name"],
        "comparison_entity_ids": [item["entity_id"] for item in config["competitors"]],
        "comparison_entity_names": [item["entity_name"] for item in config["competitors"]],
        "counts": {
            "cross_entity_competitive_cases": len(cases),
            "cases_total": len(cases),
            "competitors": len(config["competitors"]),
            "comparison_axes": len(config["comparison_axes"]),
        },
        "selection_summary": selection_summary,
        "axis_counts": dict(Counter(case.get("comparison_scope") or "unknown" for case in cases)),
        "competitor_counts": dict(Counter((case.get("comparison_entity_names") or ["unknown"])[0] for case in cases)),
        "case_hash": gen.stable_hash([case["input_hash"] for case in cases]),
        "notes": [
            "Draft cases intentionally pair target, competitor, and independent-market evidence.",
            "Human review should reject winner claims unless independent evidence supports them.",
            "Use this set to evaluate source-role awareness, entity attribution, and competitive synthesis quality.",
        ],
    }

    write_jsonl(out_dir / "cases.jsonl", cases)
    write_jsonl(out_dir / "cross_entity_competitive.jsonl", cases)
    write_json(out_dir / "manifest.json", manifest)
    write_json(out_dir / "splits.json", splits)
    write_json(out_dir / "leakage_index.json", leakage)
    print(json.dumps(manifest["counts"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
