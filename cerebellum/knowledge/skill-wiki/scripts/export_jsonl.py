#!/usr/bin/env python3
"""
export_jsonl.py — 从 skill-graph.yaml 蒸馏 4 种 JSONL 训练数据。

Output (data/training/):
  skill_desc.jsonl     — "what does X do?" → description
  skill_rel.jsonl      — "what skills work with X?" → related via edges
  workflow_rec.jsonl   — "skills for category X?" → sorted by score
  skill_comp.jsonl     — "compare X and Y?" → diff of two skills

每行: {"prompt": …, "completion": …, "metadata": {…}}
"""

from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# 0. paths
# ---------------------------------------------------------------------------
GRAPH = Path(os.environ.get("SKILL_GRAPH", "E:/projects/skill-graph/data/skill-graph.yaml"))
OUT   = Path("data/training")
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. load
# ---------------------------------------------------------------------------
with open(GRAPH, "r", encoding="utf-8") as f:
    raw = yaml.safe_load(f)

nodes: list[dict]      = raw["nodes"]
edges: list[dict]      = raw["edges"]
workflows: list[dict]  = raw.get("workflows", [])
meta: dict             = raw.get("meta", {})

# index by id
node_by_id: dict[str, dict] = {n["id"]: n for n in nodes}

# category -> [nodes]
cat_nodes: dict[str, list[dict]] = defaultdict(list)
for n in nodes:
    cat_nodes[n["category"]].append(n)

# node_id -> edge list (outgoing)
out_edges: dict[str, list[dict]] = defaultdict(list)
for e in edges:
    out_edges[e["from"]].append(e)

# node_id -> related node ids (all directions, deduped)
related_ids: dict[str, set[str]] = defaultdict(set)
for e in edges:
    related_ids[e["from"]].add(e["to"])
    related_ids[e["to"]].add(e["from"])

# ---------------------------------------------------------------------------
# 2. helpers
# ---------------------------------------------------------------------------

def jl(prompt: str, completion: str, metadata: dict) -> str:
    """One JSONL line."""
    return json.dumps(
        {"prompt": prompt, "completion": completion, "metadata": metadata},
        ensure_ascii=False,
    )


def skill_summary(n: dict) -> str:
    """Short summary string for a skill node."""
    return f"{n['name']} (score={n.get('score', 0.0)}, category={n['category']})"


# ---------------------------------------------------------------------------
# 3. skill_desc.jsonl  —  Q: "what does X do?"  A: description
# ---------------------------------------------------------------------------
def gen_skill_desc() -> list[str]:
    lines: list[str] = []
    for n in nodes:
        prompt = f"What does {n['name']} do?"
        completion = n["description"]
        md = {"id": n["id"], "category": n["category"], "score": n.get("score", 0.0)}
        lines.append(jl(prompt, completion, md))
    return lines


# ---------------------------------------------------------------------------
# 4. skill_rel.jsonl  —  Q: "what skills work with X?"  A: related from edges
# ---------------------------------------------------------------------------
def gen_skill_rel() -> list[str]:
    lines: list[str] = []
    for n in nodes:
        rels = related_ids.get(n["id"], set())
        if not rels:
            continue
        # resolve their descriptions
        parts: list[str] = []
        for rid in sorted(rels):
            rn = node_by_id.get(rid)
            if rn:
                parts.append(f"- {rn['name']}: {rn['description']}")
        if not parts:
            continue

        prompt = f"What skills work with {n['name']}?"
        completion = "\n".join(parts)
        md = {
            "id": n["id"],
            "relation_count": len(rels),
            "edge_types": list(
                {e["type"] for e in edges if e["from"] == n["id"] or e["to"] == n["id"]}
            ),
        }
        lines.append(jl(prompt, completion, md))
    return lines


# ---------------------------------------------------------------------------
# 5. workflow_rec.jsonl  —  Q: "skills for category X?"  A: sorted by score
# ---------------------------------------------------------------------------
def gen_workflow_rec() -> list[str]:
    lines: list[str] = []
    for cat, c_nodes in sorted(cat_nodes.items()):
        # sort by score descending, tie-break by name
        sorted_nodes = sorted(c_nodes, key=lambda x: (-x.get("score", 0.0), x["name"]))
        parts: list[str] = []
        for cn in sorted_nodes:
            parts.append(
                f"- {cn['name']}: score={cn.get('score', 0.0)}, {cn['description']}"
            )
        prompt = f"What skills are available for category {cat}?"
        completion = "\n".join(parts)
        md = {"category": cat, "skill_count": len(sorted_nodes)}
        lines.append(jl(prompt, completion, md))
    return lines


# ---------------------------------------------------------------------------
# 6. skill_comp.jsonl  —  Q: "compare X and Y?"  A: diff
# ---------------------------------------------------------------------------
def gen_skill_comp() -> list[str]:
    """Generate compare pairs.

    Strategy: for each node, pair it with up to 3 peers:
      1. Same-category (most comparable)
      2. Edge-related (different category, linked by graph)
      3. Random high-score (diverse)

    Keep comparisons symmetric (A-B vs B-A deduped).
    """
    lines: list[str] = []
    seen: set[tuple[str, str]] = set()
    nids = [n["id"] for n in nodes]

    for n in nodes:
        candidates: list[str] = []

        # same-category peers
        same_cat = [m["id"] for m in cat_nodes.get(n["category"], []) if m["id"] != n["id"]]
        candidates.extend(same_cat[:2])

        # edge-related
        rels = list(related_ids.get(n["id"], set()))
        candidates.extend(rels[:2])

        # random high-score (top 20% by score)
        high_score = [
            m["id"] for m in nodes
            if m["id"] != n["id"]
            and m.get("score", 0.0) >= 70
            and m["id"] not in candidates
            and m["id"] not in rels
        ]
        if high_score:
            candidates.append(random.choice(high_score))

        for peer_id in candidates:
            a_id, b_id = n["id"], peer_id
            if a_id == b_id:
                continue
            key = tuple(sorted((a_id, b_id)))
            if key in seen:
                continue
            seen.add(key)

            a = node_by_id[a_id]
            b = node_by_id[b_id]

            prompt = f"Compare {a['name']} and {b['name']}."

            # Build a structured comparison
            lines_comp: list[str] = []
            lines_comp.append(f"=== {a['name']} ===")
            lines_comp.append(f"Category: {a['category']}")
            lines_comp.append(f"Score: {a.get('score', 0.0)}")
            lines_comp.append(f"Description: {a['description']}")
            lines_comp.append("")
            lines_comp.append(f"=== {b['name']} ===")
            lines_comp.append(f"Category: {b['category']}")
            lines_comp.append(f"Score: {b.get('score', 0.0)}")
            lines_comp.append(f"Description: {b['description']}")
            lines_comp.append("")
            lines_comp.append("=== Differences ===")
            if a["category"] != b["category"]:
                lines_comp.append(
                    f"- Category: {a['category']} vs {b['category']}"
                )
            score_diff = a.get("score", 0.0) - b.get("score", 0.0)
            if abs(score_diff) > 0.5:
                lines_comp.append(
                    f"- Score: {score_diff:+.1f} ({a['name']} is {'higher' if score_diff > 0 else 'lower'})"
                )
            else:
                lines_comp.append("- Score: similar")
            lines_comp.append(f"- Description: each serves its own purpose")

            completion = "\n".join(lines_comp)
            md = {
                "id_a": a_id,
                "id_b": b_id,
                "category_a": a["category"],
                "category_b": b["category"],
                "score_a": a.get("score", 0.0),
                "score_b": b.get("score", 0.0),
            }
            lines.append(jl(prompt, completion, md))

    return lines


# ---------------------------------------------------------------------------
# 7. write & stats
# ---------------------------------------------------------------------------
def write_jsonl(name: str, lines: list[str]) -> int:
    path = OUT / name
    with open(path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    return len(lines)


def main() -> None:
    print(f"Loading {GRAPH} …")
    print(f"  nodes={len(nodes)}  edges={len(edges)}  workflows={len(workflows)}")
    print()

    random.seed(42)

    stats: dict[str, int] = {}

    print("Generating skill_desc.jsonl …")
    stats["skill_desc"] = write_jsonl("skill_desc.jsonl", gen_skill_desc())

    print("Generating skill_rel.jsonl …")
    stats["skill_rel"] = write_jsonl("skill_rel.jsonl", gen_skill_rel())

    print("Generating workflow_rec.jsonl …")
    stats["workflow_rec"] = write_jsonl("workflow_rec.jsonl", gen_workflow_rec())

    print("Generating skill_comp.jsonl …")
    stats["skill_comp"] = write_jsonl("skill_comp.jsonl", gen_skill_comp())

    print()
    print(f"{'='*50}")
    print(f"{'File':<25} {'Lines':>8}")
    print(f"{'-'*35}")
    for name, count in stats.items():
        print(f"{name:<25} {count:>8}")
    print(f"{'-'*35}")
    total = sum(stats.values())
    print(f"{'TOTAL':<25} {total:>8}")

    # brief quality check
    sample_file = OUT / "skill_desc.jsonl"
    with open(sample_file, "r", encoding="utf-8") as f:
        first = json.loads(f.readline())
    print()
    print("Sample line (skill_desc.jsonl, first):")
    print(f"  prompt:     {first['prompt'][:80]}…" if len(first["prompt"]) > 80 else f"  prompt:     {first['prompt']}")
    print(f"  completion: {first['completion'][:80]}…" if len(first["completion"]) > 80 else f"  completion: {first['completion']}")
    print(f"  metadata:   {first['metadata']}")


if __name__ == "__main__":
    main()
