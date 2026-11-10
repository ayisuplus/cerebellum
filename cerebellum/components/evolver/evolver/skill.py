import logging
import re
from evolver.models import SkillResult, RecallResult
from evolver.storage_base import BaseStorage

logger = logging.getLogger(__name__)

from evolver.artifact_writer import ArtifactWriter
from evolver.skill_prompts import SKILL_SYNTHESIS_PROMPT, SKILL_MERGE_PROMPT


class SkillEngine:
    def __init__(self, storage: BaseStorage, memory_engine, graph_engine,
                 llm_client=None, skill_library=None,
                 artifact_writer=None, quality_checker=None):
        self._storage = storage
        self._memory = memory_engine
        self._graph = graph_engine
        self._llm = llm_client
        self._library = skill_library  # backward-compat: SkillIndex or SkillLibrary
        self._artifact = artifact_writer or ArtifactWriter()
        self._checker = quality_checker  # may be wired in later (e.g. by Evolver)

    def generate(self, topic: str, output_dir: str = "./skills",
                 top_k: int = 20, executable: bool = True,
                 lang: str = "zh", _skip_dedup: bool = False) -> SkillResult | None:
        # Gather relevant memories
        memories = self._memory.recall(topic, top_k=top_k)
        if not memories:
            return None

        # Gather related graph nodes
        graph_nodes = self._graph.query(topic)
        name = self._slugify(topic)
        description = f"Auto-generated skill for: {topic}"

        # Check for similar skill in library (deduplication)
        if self._library and not _skip_dedup:
            similar_skill = self._library.find_similar_skill(topic, description)
            if similar_skill:
                logger.info("Found similar skill '%s', merging with new memories",
                           similar_skill.get("name"))
                return self._evolve_skill(
                    similar_skill, memories, graph_nodes,
                    output_dir=output_dir, executable=executable, lang=lang
                )

        # Try LLM synthesis first
        llm_content = self._synthesize_with_llm(topic, memories, graph_nodes, lang)

        # Delegate rendering to ArtifactWriter
        md_content, py_content = self._artifact.render(
            topic=topic, name=name, description=description,
            memories=memories, graph_nodes=graph_nodes,
            executable=executable, llm_content=llm_content,
        )
        if llm_content:
            logger.info("LLM synthesis succeeded for skill '%s'", name)
        else:
            logger.info("Template fallback for skill '%s'", name)

        # Delegate file writing to ArtifactWriter
        file_path, py_path = self._artifact.write(
            name=name, md_content=md_content, py_content=py_content,
            output_dir=output_dir,
        )
        if py_path:
            logger.info("Generated executable skill → %s", py_path)

        content_for_db = md_content
        if py_path:
            content_for_db += f"\n\n---\nExecutable: {py_path}"

        skill_id, actual_version = self._storage.upsert_skill(
            name=name, description=description,
            file_path=file_path, content=content_for_db,
        )

        if self._checker:
            try:
                improved_content, eval_result = self._checker.check_and_improve(
                    skill_id, md_content, topic,
                )
                if improved_content != md_content:
                    self._artifact.write(
                        name=name, md_content=improved_content, py_content=None,
                        output_dir=output_dir,
                    )
                    md_content = improved_content
                    improved_for_db = md_content
                    if py_path:
                        improved_for_db += f"\n\n---\nExecutable: {py_path}"
                    skill_id, actual_version = self._storage.upsert_skill(
                        name=name, description=description,
                        file_path=file_path, content=improved_for_db,
                    )
                    logger.info("Quality check: score=%.1f, status=%s",
                                eval_result.total_score, eval_result.status)
            except Exception:
                logger.warning("Quality check failed (non-fatal)", exc_info=True)

        self._storage.log_event("skillgen", {
            "topic": topic, "file": file_path,
            "py_file": py_path, "memories_used": len(memories),
        })

        logger.info("Generated skill '%s' v%d → %s", name, actual_version, file_path)
        return SkillResult(name=name, path=file_path, content=md_content, version=actual_version)

    def _evolve_skill(self, similar_skill: dict, memories: list[RecallResult],
                      graph_nodes: list, output_dir: str = "./skills",
                      executable: bool = True, lang: str = "zh") -> SkillResult | None:
        """Evolve an existing skill by merging with new memories.

        Args:
            similar_skill: Metadata of the similar skill found in library.
            memories: New memories to merge.
            graph_nodes: New graph nodes to merge.
            output_dir: Output directory.
            executable: Whether to generate executable Python skill.
            lang: Language for the skill.

        Returns:
            SkillResult or None if evolution fails.
        """
        skill_name = similar_skill.get("name")
        skill_topic = similar_skill.get("topic", "")
        current_version = similar_skill.get("version", 1)

        # Get existing skill content from library
        existing_content = self._library.get_skill_content(skill_name)
        if not existing_content:
            logger.warning("Cannot find content for skill '%s', generating new", skill_name)
            return self.generate(skill_topic, output_dir, executable=executable,
                                lang=lang, _skip_dedup=True)

        # Try LLM merge
        merged_content = self._merge_with_llm(
            existing_content, memories, graph_nodes, lang
        )

        if not merged_content:
            logger.warning("LLM merge failed for skill '%s', generating new", skill_name)
            return self.generate(skill_topic, output_dir, executable=executable,
                                lang=lang, _skip_dedup=True)

        # Update version
        new_version = current_version + 1

        # Update frontmatter version
        merged_content = re.sub(
            r'^(version:\s*)\d+',
            f'\\g<1>{new_version}',
            merged_content,
            count=1,
            flags=re.MULTILINE
        )

        # Write files via ArtifactWriter
        file_path, _ = self._artifact.write(
            name=skill_name, md_content=merged_content, py_content=None,
            output_dir=output_dir,
        )

        # Update library
        self._library.update_skill(
            skill_name, merged_content,
            memories_used=len(memories),
            graph_nodes_used=len(graph_nodes)
        )

        # Update storage
        skill_id, actual_version = self._storage.upsert_skill(
            name=skill_name,
            description=f"Evolved from {skill_name} v{current_version}",
            file_path=file_path, content=merged_content,
        )

        self._storage.log_event("skill_evolve", {
            "skill": skill_name,
            "old_version": current_version,
            "new_version": new_version,
            "memories_merged": len(memories),
        })

        logger.info("Evolved skill '%s' v%d → v%d", skill_name, current_version, new_version)
        return SkillResult(name=skill_name, path=file_path, content=merged_content, version=new_version)

    def _merge_with_llm(self, existing_content: str, memories: list[RecallResult],
                        graph_nodes: list, lang: str = "zh") -> str | None:
        """Use LLM to merge existing skill with new memories.

        Args:
            existing_content: Current skill content.
            memories: New memories to merge.
            graph_nodes: New graph nodes.
            lang: Language.

        Returns:
            Merged content or None if merge fails.
        """
        if not self._llm or not self._llm.available:
            return None

        # Build input
        lines = ["## Existing Skill:\n"]
        lines.append(existing_content[:3000])  # Limit size

        lines.append("\n\n## New Memories:\n")
        for m in memories[:10]:
            cat = f"[{m.category}]" if m.category else ""
            lines.append(f"{cat} {m.content[:200]}")

        if graph_nodes:
            lines.append("\n\n## New Knowledge Graph Nodes:\n")
            for n in graph_nodes[:10]:
                lines.append(f"[{n.node_type}] {n.label}")

        input_text = "\n".join(lines)
        prompt = SKILL_MERGE_PROMPT.get(lang, SKILL_MERGE_PROMPT["en"])

        try:
            result = self._llm.call_llm(input_text, prompt, max_tokens=3000)
            result = self._llm.strip_thinking(result)
            if result and len(result) > 200:
                return result
        except Exception as e:
            logger.warning("LLM skill merge failed: %s", e)

        return None

    def find_composable_pairs(self, min_shared_nodes: int = 3) -> list[tuple[str, str, list]]:
        """找出共享超过 N 个图谱节点的技能对。

        Args:
            min_shared_nodes: 最少共享节点数。

        Returns:
            list of (skill_a_name, skill_b_name, shared_node_labels)
        """
        skills = self._storage.list_skills()
        if len(skills) < 2:
            return []

        # For each skill, find its related graph nodes via content keywords
        skill_nodes = {}
        for skill in skills:
            content = skill.get("content", "") or ""
            name = skill.get("name", "")
            # Extract keywords from skill content
            keywords = self._memory._extract_tags(content) if hasattr(self._memory, '_extract_tags') else []
            # Query graph for each keyword
            node_labels = set()
            for kw in keywords[:10]:
                nodes = self._graph.query(kw)
                for n in nodes:
                    node_labels.add(n.label.lower())
            skill_nodes[name] = node_labels

        # Find pairs with sufficient overlap
        pairs = []
        names = list(skill_nodes.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                shared = skill_nodes[names[i]] & skill_nodes[names[j]]
                if len(shared) >= min_shared_nodes:
                    pairs.append((names[i], names[j], sorted(shared)))

        pairs.sort(key=lambda x: len(x[2]), reverse=True)
        logger.info("Found %d composable skill pairs", len(pairs))
        return pairs

    def compose(self, skill_a: str, skill_b: str, topic: str,
                output_dir: str = "./skills", lang: str = "zh") -> SkillResult | None:
        """组合两个相关技能为一个新技能。

        Args:
            skill_a: 第一个技能名称。
            skill_b: 第二个技能名称。
            topic: 组合技能的主题。
            output_dir: 输出目录。
            lang: 语言。

        Returns:
            SkillResult or None if composition fails.
        """
        # Read existing skills
        a_data = self._storage.get_skill_by_name(skill_a)
        b_data = self._storage.get_skill_by_name(skill_b)
        if not a_data or not b_data:
            logger.warning("Cannot compose: skill '%s' or '%s' not found", skill_a, skill_b)
            return None

        # Gather related memories for the topic
        memories = self._memory.recall(topic, top_k=15)

        # Try LLM synthesis
        if self._llm and self._llm.available:
            input_lines = [
                f"Topic: {topic}",
                f"\nSkill A ({skill_a}):\n{a_data.get('content', '')[:2000]}",
                f"\nSkill B ({skill_b}):\n{b_data.get('content', '')[:2000]}",
            ]
            if memories:
                input_lines.append("\nRelated memories:")
                for m in memories[:5]:
                    input_lines.append(f"  [{m.category}] {m.content[:200]}")

            compose_prompt = (
                "你是一个技能合成器。将以下两个相关技能组合为一个新的综合技能。\n\n"
                "要求：\n"
                "- 融合两个技能的核心步骤，去除重复\n"
                "- 补充两个技能之间的衔接逻辑\n"
                "- 保持具体、可执行的步骤\n"
                "- 输出纯Markdown格式\n\n"
                "输出格式：\n"
                "## 概述\n[一段话]\n\n## 步骤\n[编号步骤]\n\n## 关键洞察\n[列表]"
            ) if lang == "zh" else (
                "You are a skill composer. Combine the following two related skills "
                "into one comprehensive skill.\n\n"
                "Requirements:\n"
                "- Merge core steps from both skills, remove duplicates\n"
                "- Add bridging logic between the two skills\n"
                "- Keep steps specific and actionable\n"
                "- Output pure Markdown\n\n"
                "Output format:\n"
                "## Overview\n[one paragraph]\n\n## Steps\n[numbered steps]\n\n## Key Insights\n[list]"
            )

            try:
                content = self._llm.call_llm("\n".join(input_lines), compose_prompt, max_tokens=2000)
                content = self._llm.strip_thinking(content)
                if content and len(content) > 100:
                    name = self._slugify(topic)
                    frontmatter = (
                        f"---\nname: {name}\ndescription: Composed from {skill_a} + {skill_b}\n"
                        f"version: 1\ntags: [composed]\n"
                        f"composed_from: [{skill_a}, {skill_b}]\n---\n\n"
                        f"# {topic.replace('-', ' ').title()}\n\n"
                    )
                    md_content = frontmatter + content

                    file_path, _ = self._artifact.write(
                        name=name, md_content=md_content, py_content=None,
                        output_dir=output_dir,
                    )

                    skill_id, ver = self._storage.upsert_skill(
                        name=name, description=f"Composed from {skill_a} + {skill_b}",
                        file_path=file_path, content=md_content,
                    )
                    self._storage.log_event("compose", {
                        "topic": topic, "skill_a": skill_a, "skill_b": skill_b,
                        "file": file_path,
                    })
                    logger.info("Composed skill '%s' from '%s' + '%s'", name, skill_a, skill_b)
                    return SkillResult(name=name, path=file_path, content=md_content, version=ver)
            except Exception as e:
                logger.warning("LLM skill composition failed: %s", e)

        logger.warning("Skill composition failed for '%s' + '%s'", skill_a, skill_b)
        return None

    def _slugify(self, text: str) -> str:
        text = text.strip().lower()
        text = re.sub(r"\s+", "-", text)
        text = re.sub(r"[^\w一-鿿-]", "", text)
        return text

    def _synthesize_with_llm(self, topic: str, memories: list[RecallResult],
                             graph_nodes: list, lang: str = "zh") -> str | None:
        """Use LLM to synthesize high-quality skill content."""
        if not self._llm or not self._llm.available:
            return None

        # Build input text from memories and graph nodes
        lines = [f"Topic: {topic}\n"]
        lines.append("Memories:")
        for m in memories:
            cat = f"[{m.category}]" if m.category else ""
            lines.append(f"  {cat} {m.content}")
        if graph_nodes:
            lines.append("\nKnowledge Graph:")
            for n in graph_nodes[:10]:
                lines.append(f"  [{n.node_type}] {n.label}")
        input_text = "\n".join(lines)

        prompt = SKILL_SYNTHESIS_PROMPT.get(lang, SKILL_SYNTHESIS_PROMPT["en"])
        try:
            result = self._llm.call_llm(input_text, prompt, max_tokens=2000)
            # Use content field directly for skill synthesis (not reasoning)
            # Only strip thinking tags, don't extract final answer
            result = self._llm.strip_thinking(result)
            if result and len(result) > 100:
                return result
        except Exception as e:
            logger.warning("LLM skill synthesis failed: %s", e)
        return None
