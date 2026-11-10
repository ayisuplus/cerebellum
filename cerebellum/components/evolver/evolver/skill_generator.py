"""SkillGenerator: SKILL.md generation from distilled experiences.

Wraps SkillEngine.generate() for core synthesis, adds SKILL.md export.
Layer: SkillGenerator (distilled experience -> SKILL.md)
        SkillEngine  (memories + graph -> skill content)
"""

import logging
import os
from evolver.models import SkillResult
from evolver.skill import SkillEngine
from evolver.storage_base import BaseStorage

logger = logging.getLogger(__name__)


class SkillGenerator:
    """Generates SKILL.md files from experiences.

    Delegates core skill synthesis to SkillEngine.generate(),
    then handles SKILL.md export and distilled-experience input.

    Usage::

        generator = SkillGenerator(skill_engine, storage)
        result = generator.generate("git workflow")
        generator.export(result.name)
    """

    def __init__(self, skill_engine: SkillEngine, storage: BaseStorage):
        self._engine = skill_engine
        self._storage = storage

    def generate(self, topic: str, output_dir: str = "./skills",
                 lang: str = "zh") -> SkillResult | None:
        """Generate a SKILL.md from experiences.

        Delegates core generation to SkillEngine.generate().
        Returns SkillResult or None if no relevant memories found.
        """
        return self._engine.generate(topic, output_dir=output_dir, lang=lang)

    def export(self, name: str, output_dir: str = "./skills") -> str | None:
        """Export a generated skill as SKILL.md file.

        Reads skill from storage and writes to disk.
        Returns file path or None if skill not found.

        Receipt: file path shown on success.
        """
        skill_data = self._storage.get_skill_by_name(name)
        if not skill_data:
            logger.warning("Skill '%s' not found in storage", name)
            return None

        content = skill_data.get("content", "")
        if not content:
            return None

        os.makedirs(output_dir, exist_ok=True)
        file_path = os.path.join(output_dir, f"{name}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info("Exported skill '%s' -> %s", name, file_path)
        return file_path
