"""Tests for the extracted skill_prompts module."""

from evolver.skill_prompts import SKILL_SYNTHESIS_PROMPT, SKILL_MERGE_PROMPT


def test_both_constants_are_dicts_with_zh_and_en():
    assert isinstance(SKILL_SYNTHESIS_PROMPT, dict)
    assert isinstance(SKILL_MERGE_PROMPT, dict)
    for constant in (SKILL_SYNTHESIS_PROMPT, SKILL_MERGE_PROMPT):
        assert "zh" in constant
        assert "en" in constant


def test_zh_and_en_values_are_non_empty_strings():
    for constant in (SKILL_SYNTHESIS_PROMPT, SKILL_MERGE_PROMPT):
        for lang in ("zh", "en"):
            assert isinstance(constant[lang], str)
            assert constant[lang].strip() != ""


def test_synthesis_en_contains_yaml_frontmarker():
    assert "YAML Frontmatter" in SKILL_SYNTHESIS_PROMPT["en"]


def test_merge_zh_contains_skill_evolver():
    assert "技能进化器" in SKILL_MERGE_PROMPT["zh"]
