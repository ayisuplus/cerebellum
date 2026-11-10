#!/usr/bin/env python3
"""
skill-graph → wiki markdown exporter (llm-wiki format).

Reads skill-graph.yaml, generates one markdown page per skill with:
- Frontmatter (title, created, updated, type, tags, category, related, confidence)
- Description
- Metadata (ID, Source, Score, Edges)
- Related Skills section ([[wikilinks]] from edges)
- Appears In Workflows section (if in any workflow)
- See Also section (backlinks + same-category peers)
- Generates index.md, log.md, and workflow-patterns.md
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# 0. paths
# ---------------------------------------------------------------------------
GRAPH = Path(os.environ.get("SKILL_GRAPH", "E:/projects/skill-graph/data/skill-graph.yaml"))
WIKI  = Path("skill-wiki")
OUT_SKILLS = WIKI / "entities" / "skills"
OUT_CONCEPTS = WIKI / "concepts" / "workflows"

OUT_SKILLS.mkdir(parents=True, exist_ok=True)
OUT_CONCEPTS.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# 1. load
# ---------------------------------------------------------------------------
with open(GRAPH, "r", encoding="utf-8") as f:
    raw = yaml.safe_load(f)

nodes: list[dict]       = raw["nodes"]
edges: list[dict]       = raw["edges"]
workflows: list[dict]   = raw.get("workflows", [])

node_by_id: dict[str, dict] = {n["id"]: n for n in nodes}

# category -> [nodes]
cat_nodes: dict[str, list[dict]] = defaultdict(list)
for n in nodes:
    cat_nodes[n["category"]].append(n)

# node_id -> outgoing edge list
out_edges: dict[str, list[dict]] = defaultdict(list)
for e in edges:
    out_edges[e["from"]].append(e)

# node_id -> incoming edge list (backlinks — skills that link TO this one)
in_edges: dict[str, list[dict]] = defaultdict(list)
for e in edges:
    in_edges[e["to"]].append(e)

# node_id -> related node ids (all directions, deduped)
related_ids: dict[str, set[str]] = defaultdict(set)
for e in edges:
    related_ids[e["from"]].add(e["to"])
    related_ids[e["to"]].add(e["from"])

# workflow node sets indexed by node_id
workflow_ids_by_node: dict[str, list[dict]] = defaultdict(list)
for wf in workflows:
    for nid in wf.get("nodes", []):
        workflow_ids_by_node[nid].append(wf)

# ---------------------------------------------------------------------------
# 2. helpers
# ---------------------------------------------------------------------------

TODAY = date.today().isoformat()


def confidence_from_score(score: float) -> str:
    if score >= 70:
        return "high"
    elif score >= 40:
        return "medium"
    return "low"


def edge_label(e: dict) -> str:
    """Human-readable label for an edge type."""
    t = e["type"]
    if t == "similar":
        return "similar"
    elif t == "complement":
        return "complement"
    elif t == "bridge":
        return "bridge"
    elif t == "extends":
        return "extends"
    elif t == "requires":
        return "requires"
    elif t == "sequence":
        return "sequence"
    elif t == "ecosystem":
        return "ecosystem"
    return t


def fmt_related_edge(nid: str, e: dict) -> str:
    """Format a related skill from an edge in either direction."""
    other = e["to"] if e["from"] == nid else e["from"]
    tgt = node_by_id.get(other)
    desc = (tgt.get("description", "") or "") if tgt else ""
    label = edge_label(e)
    line = f"- [[{other}]] *({label})*"
    if desc:
        line += f" — {desc}"
    return line


def fmt_backlink(from_id: str) -> str:
    """Format an incoming reference as a See Also item."""
    src = node_by_id.get(from_id)
    if not src:
        return f"- [[{from_id}]]"
    cat = src.get("category", "")
    return f"- [[{from_id}]] — {cat}"


# ---------------------------------------------------------------------------
# 3. page generation
# ---------------------------------------------------------------------------

def generate_skill_page(n: dict) -> str:
    nid = n["id"]
    cat = n["category"]
    score = n.get("score", 0.0)
    desc = n.get("description", "").strip()
    rel_ids = related_ids.get(nid, set())

    # All edges connected to this node (both directions)
    all_edges = out_edges.get(nid, []) + in_edges.get(nid, [])

    # tags from category
    cat_tag = cat.lower().replace(" ", "-").replace("--", "-")
    tags = [cat_tag]

    # frontmatter
    fields = [
        "---",
        f"title: {nid}",
        f"created: {TODAY}",
        f"updated: {TODAY}",
        "type: skill",
        f"tags: [{', '.join(tags)}]",
        f"category: {cat}",
    ]
    if rel_ids:
        fields.append(f"related: [{', '.join(sorted(rel_ids))}]")
    fields.append(f"confidence: {confidence_from_score(score)}")
    fields.append("---")
    fields.append("")

    # description
    fields.append(desc)
    fields.append("")

    # metadata
    src_path = n.get("path", f"{cat}/skills/{nid}/SKILL.md")
    fields.append("## Metadata")
    fields.append("")
    fields.append(f"- **ID:** `{nid}`")
    fields.append(f"- **Source:** `{src_path}`")
    fields.append(f"- **Score:** {score}")
    fields.append(f"- **Edges:** {len(rel_ids)}")
    fields.append("")

    # Related Skills (from all connected edges)
    if all_edges:
        fields.append("## Related Skills")
        fields.append("")
        # Sort: outgoing first, then incoming; within each group by type then target
        edges_sorted = sorted(all_edges, key=lambda e: (0 if e["from"] == nid else 1, e["type"], e["to"] if e["from"] == nid else e["from"]))
        for e in edges_sorted:
            fields.append(fmt_related_edge(nid, e))
        fields.append("")

    # Appears In Workflows
    wfs_for_node = workflow_ids_by_node.get(nid, [])
    if wfs_for_node:
        fields.append("## Appears In Workflows")
        fields.append("")
        for wf in sorted(wfs_for_node, key=lambda w: w["name"]):
            wf_name = wf["name"]
            fields.append(f"- [{wf_name}](workflow-patterns.md#{wf_name})")
        fields.append("")

    # See Also — same-category peers not already in related edges
    covered_ids = {nid}
    for e in all_edges:
        covered_ids.add(e["to"] if e["from"] == nid else e["from"])

    cat_peers = [m["id"] for m in cat_nodes.get(cat, []) if m["id"] not in covered_ids]
    if cat_peers:
        fields.append("## See Also")
        fields.append("")
        for sid in sorted(cat_peers[:10]):
            fields.append(fmt_backlink(sid))
        fields.append("")

    return "\n".join(fields)


def generate_index() -> str:
    """Generate/update skill-wiki/index.md."""
    cat_order = sorted(cat_nodes.keys(), key=lambda c: (-len(cat_nodes[c]), c))

    lines = [
        "---",
        "title: skill-wiki",
        f"created: {TODAY}",
        "type: index",
        "confidence: high",
        "---",
        "",
        "# Skill Wiki",
        "",
        "Knowledge graph distilled from the skill-graph into interlinked Markdown pages.",
        "",
        f"- **Nodes:** {len(nodes)}",
        f"- **Edges:** {len(edges)}",
        f"- **Workflows:** {len(workflows)}",
        "",
        "## Categories",
        "",
    ]
    for cat in cat_order:
        count = len(cat_nodes[cat])
        lines.append(f"- **{cat}** ({count})")

    lines.extend(["", "## All Skills", ""])
    all_sorted = sorted(nodes, key=lambda n: (n["category"], n["id"]))
    for n in all_sorted:
        nid = n["id"]
        cat = n["category"]
        lines.append(f"- [[{nid}]] — {cat}")

    lines.extend(["", "## Workflows", ""])
    for wf in sorted(workflows, key=lambda w: w["name"]):
        wf_name = wf["name"]
        lines.append(f"- [{wf_name}](concepts/workflows/workflow-patterns.md#{wf_name})")

    lines.extend([
        "",
        "---",
        "",
        f"*Generated by `scripts/export.py` on {TODAY}.*",
        "",
    ])
    return "\n".join(lines)


def generate_log() -> str:
    """Generate/update skill-wiki/log.md."""
    # Count categories
    cat_counts = [(cat, len(ns)) for cat, ns in sorted(cat_nodes.items(), key=lambda x: -len(x[1]))]

    lines = [
        "---",
        "title: changelog",
        f"created: {TODAY}",
        "type: log",
        "confidence: high",
        "---",
        "",
        "# Changelog",
        "",
        f"## {TODAY} — Export with Wikilinks",
        "",
        f"Re-export from `skill-graph.yaml` via `scripts/export.py`.",
        "",
        "- Added [[wikilinks]] cross-references in Related Skills section",
        "- Added See Also section (backlinks + same-category peers)",
        "",
        "### Stats",
        "",
    ]
    for cat, count in cat_counts:
        lines.append(f"- **{cat}:** {count} skills")
    lines.append("")
    return "\n".join(lines)


def generate_workflow_patterns() -> str:
    """Generate concepts/workflows/workflow-patterns.md."""
    lines = [
        "---",
        "title: workflow-patterns",
        f"created: {TODAY}",
        "type: concept",
        "tags: [workflow, pattern]",
        "confidence: high",
        "---",
        "",
        "# Workflow Patterns",
        "",
        "Derived from the skill-graph edge relationships and pipeline workflows.",
        "",
    ]

    # Complementary pairs (complement edges, bidirectional)
    comp_pairs: set[tuple[str, str]] = set()
    for e in edges:
        if e["type"] == "complement":
            a, b = e["from"], e["to"]
            pair = tuple(sorted([a, b]))
            comp_pairs.add(pair)

    if comp_pairs:
        lines.append("## Complementary Skills")
        lines.append("")
        lines.append("These skills are designed to work together — one feeds into or enhances the other.")
        lines.append("")
        for a, b in sorted(comp_pairs):
            lines.append(f"- [[{a}]] ↔ [[{b}]]")
        lines.append("")

    # Bridge connections
    bridge_edges = [e for e in edges if e["type"] == "bridge"]
    if bridge_edges:
        lines.append("## Bridge Connections")
        lines.append("")
        lines.append("These skills bridge between different domains or attack phases.")
        lines.append("")
        for e in sorted(bridge_edges, key=lambda x: (x["from"], x["to"])):
            a, b = e["from"], e["to"]
            label = e.get("label", "bridge")
            lines.append(f"- [[{a}]] → [[{b}]] *({label})*")
        lines.append("")

    # Workflows
    if workflows:
        lines.append("## Workflows")
        lines.append("")
        for wf in sorted(workflows, key=lambda w: w["name"]):
            wf_name = wf["name"]
            wf_desc = wf.get("source", wf_name)
            wf_nodes = wf.get("nodes", [])

            lines.append(f"### {wf_name}")
            lines.append("")
            lines.append(f"_{wf_desc}_")
            lines.append("")
            lines.append("**Pipeline:**")
            lines.append("")
            for nid in wf_nodes:
                n = node_by_id.get(nid)
                desc = ""
                if n:
                    desc = n.get("description", "")[:60]
                    if len(n.get("description", "")) > 60:
                        desc += "…"
                entry = f"- [[{nid}]]"
                if desc:
                    entry += f" — {desc}"
                lines.append(entry)
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. write
# ---------------------------------------------------------------------------

def write_skills() -> int:
    count = 0
    for n in nodes:
        nid = n["id"]
        page = generate_skill_page(n)
        path = OUT_SKILLS / f"{nid}.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(page)
        count += 1
    return count


def write_index() -> int:
    path = WIKI / "index.md"
    content = generate_index()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return len(content)


def write_log() -> int:
    path = WIKI / "log.md"
    content = generate_log()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return len(content)


def write_workflow_patterns() -> int:
    path = OUT_CONCEPTS / "workflow-patterns.md"
    content = generate_workflow_patterns()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return len(content)


# ---------------------------------------------------------------------------
# 5. main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"Loading {GRAPH} …")
    print(f"  nodes: {len(nodes)}, edges: {len(edges)}, workflows: {len(workflows)}")

    print("Generating skill pages …")
    skill_count = write_skills()
    print(f"  → {skill_count} skill pages")

    print("Generating index …")
    idx_len = write_index()
    print(f"  → {idx_len} bytes")

    print("Generating log …")
    log_len = write_log()
    print(f"  → {log_len} bytes")

    print("Generating workflow patterns …")
    wf_len = write_workflow_patterns()
    print(f"  → {wf_len} bytes")

    # Sample verification
    samples = ["writing-skills", "writing-plans", "academic-paper", "detecting-email-account-compromise"]
    print("\nSample pages:")
    for sid in samples:
        fpath = OUT_SKILLS / f"{sid}.md"
        if fpath.exists():
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            # Count wikilinks
            import re
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            see_also = "## See Also" in content
            print(f"  {sid}: {len(links)} wikilinks, See Also={'yes' if see_also else 'no'}")

    print("\nDone.")


if __name__ == "__main__":
    main()
