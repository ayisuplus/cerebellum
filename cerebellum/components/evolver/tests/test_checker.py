# tests/test_checker.py
"""Tests for QualityChecker — 8-dimension rubric and ratchet mechanism."""

from unittest.mock import MagicMock

from evolver.checker import QualityChecker
from evolver.models import EvalResult


# ── Minimal skills for testing ─────────────────────────────────────────────

_MINIMAL_SKILL = """---
name: test-skill
description: A test skill
version: 1
tags: []
---

## Steps
1. Do something
"""

_FULL_SKILL = """---
name: git-workflow
description: Standard git workflow for feature branches
version: 1
tags: [git, workflow]
generated_from: evolver
---

## Overview
Standard workflow for working with feature branches.

## Steps
1. Create a new branch from main
2. Make your changes
3. Write tests
4. Run the test suite
5. Commit with a clear message
   - Input: git checkout -b feature/my-feature
   - Output: Switched to a new branch 'feature/my-feature'
6. Push to remote
   - Verify: git push -u origin feature/my-feature

## Error Handling
- If merge conflict occurs, check git status for details
- Retry transient network errors up to 3 times
- For persistent failures, report the error and stop

## Common Pitfalls
- Do not force push to main
- Always pull before merge

## Checkpoints
> **Checkpoint:** Verify tests pass before committing.

## Example
```bash
git checkout -b feature/my-feature
git add .
git commit -m "feat: add new feature"
git push -u origin feature/my-feature
```

## See Also
- Refer to git documentation for advanced usage
"""


# ── Dimension scorers ────────────────────────────────────────────────────────

class TestFrontmatterScorer:
    def test_empty_content(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        assert checker._score_frontmatter("") == 0

    def test_missing_frontmatter(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        assert checker._score_frontmatter("## Steps\n1. Step one") == 0

    def test_partial_frontmatter(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_frontmatter("---\nname: test\n---\n## Steps\n1. Step")
        assert 0 < score < 10

    def test_full_frontmatter(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_frontmatter(_FULL_SKILL)
        assert score == 10


class TestWorkflowScorer:
    def test_no_steps(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        assert checker._score_workflow("No steps here") == 1

    def test_minimal_steps(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_workflow("## Steps\n1. Step one")
        assert score == 4  # 2 base + 1 numbered + 1 enough lines

    def test_rich_steps(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_workflow(_FULL_SKILL)
        assert score >= 9  # near-max, exact score depends on content analysis


class TestEdgeCasesScorer:
    def test_empty(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        assert checker._score_edge_cases("Just some text") == 2

    def test_with_error_keywords(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_edge_cases(
            "If an operation fails, check the logs. Retry on error."
        )
        assert score >= 7

    def test_with_retry_keywords(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_edge_cases(
            "Use retry with timeout. Rollback on failure."
        )
        assert score >= 7


class TestCheckpointsScorer:
    def test_empty(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        # None of the checkpoint keywords are present
        assert checker._score_checkpoints("nothing to see here at all") == 2

    def test_with_confirm_verify(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_checkpoints(
            "Verify results before proceeding. Ask user to confirm."
        )
        assert score >= 7


class TestSpecificityScorer:
    def test_empty(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        # Short words (avg <= 4), no code, no file paths, no tools
        score = checker._score_specificity("a b c d e")
        assert score == 2

    def test_with_code_block(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_specificity("```bash\nnpm install\n```")
        assert score >= 4


class TestResourcesScorer:
    def test_empty(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        assert checker._score_resources("Just text") == 3

    def test_with_related_section(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_resources("See also related docs\nhttps://example.com")
        assert score >= 8


class TestArchitectureScorer:
    def test_empty(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        assert checker._score_architecture("Short text") == 2

    def test_multiple_sections(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_architecture(_FULL_SKILL)
        assert score >= 5


class TestEffectivenessScorer:
    def test_no_topic_overlap(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_effectiveness(
            "completely unrelated content about gardening",
            "git workflow"
        )
        assert score == 3  # base only

    def test_high_topic_coverage(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        score = checker._score_effectiveness(
            "git workflow: git commit, git push, git merge",
            "git workflow"
        )
        assert score >= 5


# ── evaluate() ─────────────────────────────────────────────────────────────

class TestEvaluate:
    def test_returns_eval_result(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        result = checker.evaluate(_MINIMAL_SKILL, "testing skill")
        assert isinstance(result, EvalResult)
        assert 0 <= result.total_score <= 100
        assert len(result.dim_scores) == 8
        assert result.round == 1

    def test_dimensions_present(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        result = checker.evaluate(_MINIMAL_SKILL, "testing skill")
        for dim in ("frontmatter", "workflow", "edge_cases", "checkpoints",
                    "specificity", "resources", "architecture", "effectiveness"):
            assert dim in result.dim_scores

    def test_scores_in_range(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        result = checker.evaluate(_FULL_SKILL, "git workflow")
        for dim, score in result.dim_scores.items():
            assert 0 <= score <= 10, f"{dim} score out of range: {score}"


# ── fix_dimension() ─────────────────────────────────────────────────────────

class TestFixDimension:
    def _make_checker(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        return checker

    def test_fix_frontmatter_adds_missing_fields(self):
        checker = self._make_checker()
        result = checker._fix_frontmatter(
            "No frontmatter here", EvalResult(total_score=0, dim_scores={}, round=1)
        )
        assert result.startswith("---\nname:")

    def test_fix_workflow_adds_steps_when_missing(self):
        checker = self._make_checker()
        result = checker._fix_workflow(
            "Just text", EvalResult(total_score=0, dim_scores={}, round=1)
        )
        assert "## Steps" in result

    def test_fix_edge_cases_adds_section(self):
        checker = self._make_checker()
        result = checker._fix_edge_cases(
            "No error handling", EvalResult(total_score=0, dim_scores={}, round=1)
        )
        assert "## Error Handling" in result

    def test_fix_checkpoints_adds_checkpoint(self):
        checker = self._make_checker()
        result = checker._fix_checkpoints(
            "## Steps\n1. Do it", EvalResult(total_score=0, dim_scores={}, round=1)
        )
        assert "Checkpoint" in result

    def test_fix_specificity_adds_example(self):
        checker = self._make_checker()
        result = checker._fix_specificity(
            "Some content", EvalResult(total_score=0, dim_scores={}, round=1)
        )
        assert "## Example" in result

    def test_fix_resources_adds_related(self):
        checker = self._make_checker()
        result = checker._fix_resources(
            "Content without related", EvalResult(total_score=0, dim_scores={}, round=1)
        )
        assert "## See Also" in result

    def test_fix_architecture_adds_overview(self):
        checker = self._make_checker()
        result = checker._fix_architecture(
            "---\nname: test\n---\n## Steps\n1. Do it",
            EvalResult(total_score=0, dim_scores={}, round=1),
        )
        assert "## Overview" in result

    def test_fix_effectiveness_adds_quick_reference(self):
        checker = self._make_checker()
        result = checker._fix_effectiveness(
            "Original content", EvalResult(total_score=0, dim_scores={"effectiveness": 3}, round=1)
        )
        assert "Quick Reference" in result
        assert result.startswith("Original content")

    def test_fix_effectiveness_high_score_unchanged(self):
        checker = self._make_checker()
        result = checker._fix_effectiveness(
            "Original content", EvalResult(total_score=0, dim_scores={"effectiveness": 8}, round=1)
        )
        assert result == "Original content"


# ── check_and_improve() ratchet ────────────────────────────────────────────

class TestRatchet:
    def test_improves_minimal_skill(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        improved, result = checker.check_and_improve(1, _MINIMAL_SKILL, "testing")
        assert isinstance(improved, str)
        assert isinstance(result, EvalResult)
        # Improved content should differ from input
        assert improved != _MINIMAL_SKILL
        # Result should reflect the final state
        assert result.status in ("improved", "reverted")

    def test_does_not_degrade_high_quality_skill(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        original_score = checker.evaluate(_FULL_SKILL, "git").total_score
        improved, result = checker.check_and_improve(1, _FULL_SKILL, "git")
        assert result.total_score >= original_score

    def test_max_rounds_respected(self):
        checker = QualityChecker.__new__(QualityChecker)
        checker._storage = None
        checker.MAX_ROUNDS = 3
        _, result = checker.check_and_improve(1, _MINIMAL_SKILL, "testing")
        assert result.round <= 3


# ── _log_evaluation() ────────────────────────────────────────────────────────

class TestLogEvaluation:
    def test_log_evaluation_swallows_storage_errors(self):
        """If storage write fails, log_evaluation must not propagate."""
        mock_storage = MagicMock()
        mock_storage.insert_skill_evaluation.side_effect = RuntimeError("DB down")
        checker = QualityChecker(mock_storage)
        # Should NOT raise — errors are caught and logged as warning
        checker._log_evaluation(1, 1, EvalResult(0, {}, 1, "pass"), "improved")
        # If we get here without raising, the test passes