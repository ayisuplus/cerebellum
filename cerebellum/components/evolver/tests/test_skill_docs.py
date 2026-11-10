"""Contract tests for project-level agent skills."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _frontmatter_keys(path: Path) -> list[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    keys = []
    for line in lines[1:end]:
        if ":" in line:
            keys.append(line.split(":", 1)[0])
    return keys


def _skill_text(name: str) -> str:
    return (ROOT / ".claude" / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def _frontmatter_description(name: str) -> str:
    lines = _skill_text(name).splitlines()
    end = lines.index("---", 1)
    for line in lines[1:end]:
        if line.startswith("description:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"{name} has no description frontmatter")


ACTIVE_SKILLS = ["evolver-study", "evolver-skill", "evolver-store", "evolver-query"]
OLD_SKILLS = ["evolver-learn", "evolver-summary", "evolver-memory", "evolver-skillcraft"]


def test_agent_facing_evolver_skills_are_four_storage_channels():
    skill_dir = ROOT / ".claude" / "skills"

    for name in ACTIVE_SKILLS:
        assert (skill_dir / name / "SKILL.md").exists()

    for name in OLD_SKILLS:
        assert not (skill_dir / name / "SKILL.md").exists()

    assert not (skill_dir / "evolver-engine.md").exists()


def test_agent_facing_evolver_skills_use_minimal_frontmatter():
    for name in ACTIVE_SKILLS:
        keys = _frontmatter_keys(ROOT / ".claude" / "skills" / name / "SKILL.md")

        assert keys == ["name", "description"]


def test_project_skill_descriptions_are_trigger_focused_and_compact():
    for name in ACTIVE_SKILLS:
        description = _frontmatter_description(name)

        assert description.startswith("Use when")
        assert len(description) <= 500
        assert "This is the" not in description
        assert "Do not under-trigger" not in description


def test_four_skills_keep_experience_and_data_tiers_separate():
    study = _skill_text("evolver-study")
    skill = _skill_text("evolver-skill")
    store = _skill_text("evolver-store")
    query = _skill_text("evolver-query")

    assert "SQLite experience tier" in study
    assert "SQLite experience tier" in skill
    assert "MySQL data tier" in store
    assert "MySQL data tier" in query
    assert "dead data" in store
    assert "verbatim" in query


def test_study_skill_documents_time_weighted_distillation():
    study = _skill_text("evolver-study")

    assert "time-weighted" in study
    assert "evergreen" in study
    assert "importance" in study
    assert "old memories become quieter" in study


def test_skill_skill_documents_quality_gate():
    skill = _skill_text("evolver-skill")

    assert "skillgen" in skill
    assert "evaluate" in skill
    assert "quality" in skill.lower()


def test_study_owns_recall_and_distill():
    study = _skill_text("evolver-study")

    assert "recall" in study
    assert "distill" in study
    assert "facts" in study


def test_skill_does_not_own_recall():
    skill = _skill_text("evolver-skill")

    lower = skill.lower()
    assert "recall" not in lower.split("##")[0]
