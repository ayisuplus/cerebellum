"""Artifact writer: renders and writes SKILL.md and optional skill.py files.

Owns frontmatter construction, Jinja template loading, and the file-system
side effects of skill generation. Has no knowledge of the storage layer,
the library, or the quality checker.
"""
import logging
import os
from pathlib import Path
from typing import Any, Optional, Sequence

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


def _default_env() -> Environment:
    template_dir = Path(__file__).parent / "templates"
    return Environment(loader=FileSystemLoader(str(template_dir)))


class ArtifactWriter:
    """Render SKILL.md and skill.py bodies, then write them to disk."""

    def __init__(self, jinja_env: Optional[Environment] = None,
                 output_dir: str = "./skills"):
        self._env = jinja_env or _default_env()
        self._default_output_dir = output_dir

    def render(
        self,
        topic: str,
        name: str,
        description: str,
        memories: Sequence[Any],
        graph_nodes: Sequence[Any],
        executable: bool = True,
        llm_content: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Return (md_content, py_content_or_none) without touching disk."""
        all_tags: set[str] = set()
        for m in memories:
            cat = getattr(m, "category", None)
            if cat:
                all_tags.add(cat)
        for n in graph_nodes:
            ntype = getattr(n, "node_type", None)
            if ntype:
                all_tags.add(ntype)

        title = topic.replace("-", " ").title()
        tags = sorted(all_tags)
        memory_count = len(memories)
        node_count = len(graph_nodes)

        if llm_content:
            frontmatter = (
                f"---\nname: {name}\ndescription: {description}\n"
                f"version: 1\ntags: [{', '.join(tags)}]\n"
                f"generated_from: {memory_count} memories, "
                f"{node_count} graph nodes\n"
                f"synthesis: llm\n---\n\n"
                f"# {title}\n\n"
            )
            md_content = frontmatter + llm_content
        else:
            groups = self._group_categories(memories, graph_nodes)
            summary = (
                f"Based on {memory_count} memories and "
                f"{node_count} knowledge graph nodes."
            )
            md_template = self._env.get_template("skill.md.j2")
            md_content = md_template.render(
                name=name, description=description, version=1,
                tags=tags, memory_count=memory_count,
                node_count=node_count, title=title,
                summary=summary, steps=groups["steps"],
                success_cases=groups["success_cases"],
                failure_lessons=groups["failure_lessons"],
                insights=groups["insights"], related_skills=groups["related"],
            )

        py_content: Optional[str] = None
        if executable and not llm_content:
            py_content = self._render_python(
                name=name, description=description, version=1,
                tags=tags, memory_count=memory_count,
                node_count=node_count, title=title,
                groups=groups,
            )
        elif executable and llm_content:
            py_content = self._render_python_wrapper(
                name=name, description=description,
            )

        return md_content, py_content

    def write(
        self,
        name: str,
        md_content: str,
        py_content: Optional[str],
        output_dir: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Write md (and optional py) into output_dir. Returns (md_path, py_path)."""
        target_dir = output_dir or self._default_output_dir
        os.makedirs(target_dir, exist_ok=True)
        md_path = os.path.join(target_dir, f"{name}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        py_path: Optional[str] = None
        if py_content is not None:
            py_path = os.path.join(target_dir, f"{name}.py")
            with open(py_path, "w", encoding="utf-8") as f:
                f.write(py_content)
        return md_path, py_path

    def _group_categories(
        self, memories: Sequence[Any], graph_nodes: Sequence[Any],
    ) -> dict[str, list[str]]:
        """Extract and group memory contents by category, returning a dict
        with keys success_cases, failure_lessons, insights, steps, and related.
        Each list is capped at 5 (steps capped at 10)."""
        success_cases = [m.content for m in memories
                         if getattr(m, "category", None) == "success"]
        failure_lessons = [m.content for m in memories
                           if getattr(m, "category", None) == "failure"]
        insights = [m.content for m in memories
                    if getattr(m, "category", None) == "insight"]
        steps = self._extract_steps(success_cases)
        related = [f"{n.label} ({getattr(n, 'node_type', '')})"
                   for n in graph_nodes[:5]]
        return {
            "success_cases": success_cases[:5],
            "failure_lessons": failure_lessons[:5],
            "insights": insights[:5],
            "steps": steps,
            "related": related,
        }

    @staticmethod
    def _extract_steps(success_cases: list[str]) -> list[str]:
        steps: list[str] = []
        for case in success_cases:
            for line in case.split("\n"):
                line = line.strip()
                if line and len(line) > 5:
                    steps.append(line)
        return steps[:10]

    def _render_python(
        self, *, name: str, description: str, version: int, tags: list[str],
        memory_count: int, node_count: int, title: str,
        groups: dict[str, list[str]],
    ) -> str:
        py_template = self._env.get_template("skill.py.j2")
        return py_template.render(
            name=name, description=description, version=version,
            tags=tags, memory_count=memory_count, node_count=node_count,
            title=title, steps=groups["steps"],
            success_cases=groups["success_cases"],
            failure_lessons=groups["failure_lessons"],
            insights=groups["insights"], related_skills=groups["related"],
        )

    @staticmethod
    def _render_python_wrapper(*, name: str, description: str) -> str:
        _esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
        return (
            f'"""{_esc(name)}: {_esc(description)}"""\n'
            f'\nNAME = "{_esc(name)}"\n'
            f'DESCRIPTION = "{_esc(description)}"\n'
            f'\n\ndef run(*args, **kwargs):\n'
            f'    """See SKILL.md for the full workflow."""\n'
            f'    raise NotImplementedError("LLM-synthesized skill; see SKILL.md")\n'
        )
