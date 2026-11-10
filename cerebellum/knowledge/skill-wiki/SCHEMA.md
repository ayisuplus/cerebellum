# SCHEMA — Agent Engineering Skills Knowledge Base

Domain: **Agent Engineering Skills Knowledge Base** — a curated, interlinked
Markdown wiki (llm-wiki format) distilling structured agent-engineering
knowledge from a skill-graph into human-readable, search-indexable, and
training-data-ready pages.

## 1. Directory Layout

```
skill-wiki/
  index.md              — root index, lists all skills by category
  log.md                — changelog & state tracking
  SCHEMA.md             — this file
  entities/
    skills/             — one page per skill node (1230+ pages)
  concepts/
    workflows/          — workflow patterns, edge relationships, task maps
    patterns/           — (planned) task→workflow query mappings
```

## 2. File Naming Conventions

| Aspect | Rule |
|---|---|
| Format | `.md` only |
| Case | Lowercase-hyphens (`kebab-case`) |
| Pattern | `<entity-slug>.md`, `<concept-slug>.md` |
| Slug source | Lowercased, spaces→hyphens, strip non-alphanumeric |
| Max length | 80 chars (excluding `.md`) |
| Reserved names | `index`, `log`, `SCHEMA` |

Examples: `code-review-and-quality.md`, `workflow-patterns.md`, `llm-wiki.md`.

## 3. YAML Frontmatter

### Template (required and optional fields)

```yaml
---
title: <lowercase-hyphen-slug>
created: YYYY-MM-DD
updated: YYYY-MM-DD
type: <page-type>
tags: [<tag1>, <tag2>, …]
category: <category-name>
related: [<related-slug>, <related-slug>, …]
confidence: high | medium | low
sources:
  - <source-ref>
  - <source-ref>
---
```

### Field specs

| Field | Required | Type | Description |
|---|---|---|---|
| `title` | **yes** | string | Lowercase-hyphen slug matching filename (minus `.md`) |
| `created` | **yes** | string | ISO 8601 date (`YYYY-MM-DD`) — page creation date |
| `updated` | **yes** | string | ISO 8601 date — last significant content change |
| `type` | **yes** | enum | One of: `skill`, `concept`, `workflow`, `pattern`, `index`, `log`, `guide` |
| `tags` | **yes** | array[string] | 1–5 tags from the Tag Taxonomy (§4) |
| `category` | **yes** | string | Source category from the skill-graph (e.g. `agent-skills`, `Anthropic-Cybersecurity-Skills`, `research`). For concept pages, use the most specific applicable category. |
| `related` | no | array[string] | Wikilink slugs of directly related pages (edges from the graph or curated relations). Empty array if none. |
| `confidence` | **yes** | enum | `high` (curated/verified), `medium` (auto-exported), `low` (draft/unverified) |
| `sources` | no | array[string] | Origin references: file paths in the source graph, paper DOIs, URLs, or `skill-graph` for graph-derived nodes |

### Examples

**Skill page (auto-exported):**
```yaml
---
title: code-review-and-quality
created: 2026-07-04
updated: 2026-07-04
type: skill
tags: [agent-skills, review]
category: agent-skills
related: [requesting-code-review, code-simplification, receiving-code-review]
confidence: high
sources:
  - agent-skills/skills/code-review-and-quality/SKILL.md
---
```

**Workflow concept page:**
```yaml
---
title: parallel-review-pattern
created: 2026-07-03
updated: 2026-07-03
type: workflow
tags: [workflow, orchestration, review]
category: agent-skills
related: [code-review-and-quality, test-driven-development]
confidence: medium
sources:
  - skill-graph
---
```

## 4. Tag Taxonomy

20 tags for cross-cutting classification. Every page MUST have 1–5 tags from
this list. Tags are lowercase-hyphen and singular.

| # | Tag | Scope |
|---|---|---|
| 1 | `agent-skills` | First-party agent-engineering skills (from `agent-skills` category) |
| 2 | `cybersecurity` | Offensive/defensive security, threat intel, forensics |
| 3 | `development` | Software engineering, coding patterns, frameworks |
| 4 | `ai-ml` | AI/ML skills, LLM ops, model development |
| 5 | `review` | Code review, design review, quality assurance |
| 6 | `automation` | CI/CD, pipelines, devops, orchestration |
| 7 | `testing` | Test strategies, TDD, test frameworks |
| 8 | `data` | Data engineering, analysis, pipelines |
| 9 | `design` | UI/UX, architecture, system design |
| 10 | `research` | Academic research, literature, investigation |
| 11 | `workflow` | Multi-step patterns, orchestration, agent pipelines |
| 12 | `package` | Third-party packages, libraries, CLI tools |
| 13 | `productivity` | Personal/dev workflow optimization |
| 14 | `creative` | Content generation, media, writing |
| 15 | `devops` | Infrastructure, deployment, operations |
| 16 | `mobile` | Mobile development (iOS, Android, cross-platform) |
| 17 | `frontend` | Web frontend, UI frameworks, browser |
| 18 | `backend` | Server-side, APIs, databases |
| 19 | `obsidian` | Obsidian-related skills and vault management |
| 20 | `documentation` | Docs, ADRs, wiki writing, knowledge management |

## 5. Page Lifecycle

### Creation

- **Auto-exported pages** (bulk from `scripts/export.py`): created all at once
  with `confidence: medium` and `sources: [skill-graph]`.
- **Curated pages** (human-written): set `confidence: high`, add proper
  `sources` and `related` links.
- **New skill pages** added manually: match file naming conventions, include
  all required frontmatter fields, add `related` links to known neighbors.

### Update

- **Threshold**: update `updated` date when:
  - Content changes substantively (description, related links, workflow refs).
  - Confidence level changes.
  - Tags or category are corrected.
- **DO NOT** update for formatting-only changes, whitespace fixes, or
  auto-generated index regeneration.
- Auto-exported pages MAY be overwritten by pipeline re-runs; curated edits
  SHOULD be migrated back into the source graph if they represent new knowledge.

### Split / Merge

- **Split threshold**: a page exceeding ~200 lines of body content or covering
  >20 `related` links SHOULD be split into sub-pages under a subdirectory
  (e.g. `entities/skills/soc/` for SOC skill variants).
- **Merge threshold**: duplicate or near-identical pages (same source ID,
  overlapping description >80%) MUST be merged, keeping the older `created`
  date and the higher `confidence` level.

## 6. Entity Page Format (skills)

```markdown
---
<frontmatter>
---

<One-paragraph description. Trigger conditions. Use cases.>

## Metadata

- **ID:** `<graph-node-id>`
- **Source:** `<path-in-source-repo-or-external-ref>`
- **Score:** `<float>`
- **Edges:** `<int>`

## Related Skills

- [[<related-slug>]] *(<relation-type>)* — <short description>
- [[<related-slug>]] *(<relation-type>)* — <short description>

## Appears In Workflows

- [<workflow-name>](workflow-patterns.md#<workflow-anchor>)
- [<workflow-name>](workflow-patterns.md#<workflow-anchor>)
```

**Relation types**: `complement`, `similar`, `predecessor`, `successor`, `conflict`.

## 7. Concept / Workflow Page Format

```markdown
---
<frontmatter>
---

# <Title>

<One-paragraph concept description.>

## <Section>

<Body content with wikilinks to entity pages.>

- [[<related-skill>]] — <role in this workflow>
- [[<related-skill>]] — <role in this workflow>
```

Workflow pages SHOULD include sections for:
- **Complementary Skills** — skill pairs commonly used together
- **Sequences** — ordered skill chains for common tasks
- **Decision Gates** — branching points where skill selection matters

## 8. Training Export Format

Training data exported via `scripts/export_jsonl.py` follows this schema:

```jsonl
{"prompt": "...", "completion": "...", "metadata": {…}}
```

| File | Prompt pattern | Use case |
|---|---|---|
| `skill_desc.jsonl` | "What does X do?" | Skill description lookup |
| `skill_rel.jsonl` | "What skills work with X?" | Related skill recommendation |
| `workflow_rec.jsonl` | "Skills for category X?" | Category-based skill search |
| `skill_comp.jsonl` | "Compare X and Y?" | Skill comparison reasoning |

## 9. Index and Log

- `index.md` — auto-generated: lists all pages grouped by category; frontmatter
  uses `type: index`.
- `log.md` — curated changelog; frontmatter uses `type: log`. Entries are
  reverse-chronological. Each entry records the date, event, and key stats.
