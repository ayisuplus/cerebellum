import re
import logging
from evolver.models import EvalResult
from evolver.utils import nonempty_lines

logger = logging.getLogger(__name__)


class QualityChecker:
    MAX_ROUNDS = 3

    DIMENSIONS = {
        "frontmatter":   8,
        "workflow":      15,
        "edge_cases":    10,
        "checkpoints":    7,
        "specificity":   15,
        "resources":      5,
        "architecture":  15,
        "effectiveness": 25,
    }

    def __init__(self, storage):
        self._storage = storage

    def evaluate(self, skill_content: str, topic: str) -> EvalResult:
        """Evaluate skill content across 8 dimensions."""
        scores = {}
        scores["frontmatter"] = self._score_frontmatter(skill_content)
        scores["workflow"] = self._score_workflow(skill_content)
        scores["edge_cases"] = self._score_edge_cases(skill_content)
        scores["checkpoints"] = self._score_checkpoints(skill_content)
        scores["specificity"] = self._score_specificity(skill_content)
        scores["resources"] = self._score_resources(skill_content)
        scores["architecture"] = self._score_architecture(skill_content)
        scores["effectiveness"] = self._score_effectiveness(skill_content, topic)

        total = sum(scores[d] * self.DIMENSIONS[d] / 10.0 for d in scores)
        return EvalResult(
            total_score=round(total, 1),
            dim_scores=scores,
            round=1,
            status="pass",
        )

    def check_and_improve(self, skill_id: int, skill_content: str,
                          topic: str) -> tuple[str, EvalResult]:
        """Evaluate, fix weakest dimension, ratchet.

        Evaluates only once per round (on the improved version) instead of
        twice, by comparing against the best score from the previous iteration.
        """
        best_content = skill_content
        best_eval = self.evaluate(skill_content, topic)
        best_score = best_eval.total_score
        current_eval = best_eval  # score to beat this round

        for round_num in range(1, self.MAX_ROUNDS + 1):
            weakest = min(current_eval.dim_scores, key=current_eval.dim_scores.get)

            improved = self._fix_dimension(best_content, weakest, current_eval)
            new_eval = self.evaluate(improved, topic)

            if new_eval.total_score > best_score:
                best_content = improved
                best_score = new_eval.total_score
                best_eval = EvalResult(
                    total_score=new_eval.total_score,
                    dim_scores=new_eval.dim_scores,
                    round=round_num,
                    status="improved",
                )
                current_eval = new_eval
                self._log_evaluation(skill_id, round_num, new_eval, "improved")
            else:
                self._log_evaluation(skill_id, round_num, new_eval, "reverted")
                break

        return best_content, best_eval

    # --- Dimension scorers (each returns 1-10) ---

    def _score_frontmatter(self, content: str) -> int:
        score = 0
        if re.search(r'^---\s*\n', content):
            score += 2
        if re.search(r'^name:\s*\S+', content, re.MULTILINE):
            score += 2
        if re.search(r'^description:\s+.+', content, re.MULTILINE):
            score += 2
        if re.search(r'^version:\s*\d+', content, re.MULTILINE):
            score += 1
        if re.search(r'^tags:\s*\[', content, re.MULTILINE):
            score += 1
        if re.search(r'^generated_from:', content, re.MULTILINE):
            score += 1
        if content.count('---') >= 2:
            score += 1
        return min(score, 10)

    def _score_workflow(self, content: str) -> int:
        steps_match = re.search(r'## Steps\s*\n(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if not steps_match:
            return 1
        steps_text = steps_match.group(1).strip()
        if not steps_text:
            return 1
        score = 2
        numbered = re.findall(r'^\d+\.', steps_text, re.MULTILINE)
        if len(numbered) >= 3:
            score += 3
        elif len(numbered) >= 1:
            score += 2
        bullets = re.findall(r'^[-*]\s', steps_text, re.MULTILINE)
        if bullets:
            score += 1
        lines = nonempty_lines(steps_text)
        if len(lines) >= 3:
            score += 2
        if any(kw in steps_text.lower() for kw in ['input', 'output', 'result', 'return']):
            score += 2
        return min(score, 10)

    def _score_edge_cases(self, content: str) -> int:
        score = 2
        lower = content.lower()
        if any(kw in lower for kw in ['error', 'exception', 'fail', 'fallback']):
            score += 3
        if re.search(r'if.*fail|when.*error|handle', lower):
            score += 2
        if any(kw in lower for kw in ['retry', 'timeout', 'rollback', 'recover']):
            score += 2
        if 'pitfall' in lower or 'warning' in lower or 'caution' in lower:
            score += 1
        return min(score, 10)

    def _score_checkpoints(self, content: str) -> int:
        score = 2
        lower = content.lower()
        if any(kw in lower for kw in ['confirm', 'verify', 'check', 'review']):
            score += 3
        if any(kw in lower for kw in ['ask', 'pause', 'wait', 'before proceeding']):
            score += 2
        if any(kw in lower for kw in ['approve', 'user', 'human']):
            score += 2
        return min(score, 10)

    def _score_specificity(self, content: str) -> int:
        score = 2
        if re.search(r'```', content):
            score += 2
        if re.search(r'[\w/]+\.\w+', content):
            score += 1
        if re.search(r'=\d+|=\w+|:\s*\d+', content):
            score += 1
        words = re.findall(r'\w+', content)
        if words and sum(len(w) for w in words) / len(words) > 4:
            score += 2
        if re.search(r'\b(git|docker|npm|pip|curl|ssh)\b', content, re.IGNORECASE):
            score += 1
        return min(score, 10)

    def _score_resources(self, content: str) -> int:
        score = 3
        if 'related' in content.lower() or 'see also' in content.lower():
            score += 3
        if re.search(r'https?://', content):
            score += 2
        if re.search(r'tags:', content):
            score += 1
        return min(score, 10)

    def _score_architecture(self, content: str) -> int:
        score = 2
        sections = re.findall(r'^## ', content, re.MULTILINE)
        if len(sections) >= 3:
            score += 3
        elif len(sections) >= 2:
            score += 2
        if 'overview' in content.lower() or 'summary' in content.lower():
            score += 2
        if 500 < len(content) < 5000:
            score += 1
        if re.search(r'^### ', content, re.MULTILINE):
            score += 1
        return min(score, 10)

    def _score_effectiveness(self, content: str, topic: str) -> int:
        score = 3
        topic_words = set(re.findall(r'\w+', topic.lower()))
        content_words = set(re.findall(r'\w+', content.lower()))
        overlap = topic_words & content_words
        if topic_words:
            coverage = len(overlap) / len(topic_words)
            if coverage > 0.7:
                score += 4
            elif coverage > 0.4:
                score += 2
        if re.search(r'^\d+\.\s', content, re.MULTILINE):
            score += 2
        if len(content) > 300:
            score += 1
        return min(score, 10)

    # --- Fix strategies ---

    def _fix_dimension(self, content: str, dimension: str,
                       eval_result: EvalResult) -> str:
        fixers = {
            "frontmatter": self._fix_frontmatter,
            "workflow": self._fix_workflow,
            "edge_cases": self._fix_edge_cases,
            "checkpoints": self._fix_checkpoints,
            "specificity": self._fix_specificity,
            "resources": self._fix_resources,
            "architecture": self._fix_architecture,
            "effectiveness": self._fix_effectiveness,
        }
        fixer = fixers.get(dimension)
        if fixer:
            return fixer(content, eval_result)
        return content

    def _fix_frontmatter(self, content: str, eval_result: EvalResult) -> str:
        if not re.search(r'^---\s*\n', content):
            content = "---\nname: generated-skill\ndescription: Auto-generated\nversion: 1\ntags: []\n---\n" + content
        lines = content.split('\n')
        insert_idx = 1  # default: right after opening ---
        for i, line in enumerate(lines):
            if line.strip() == '---' and i > 0:
                insert_idx = i
                break
        additions = []
        if not re.search(r'^version:', content, re.MULTILINE):
            additions.append('version: 1')
        if not re.search(r'^tags:', content, re.MULTILINE):
            additions.append('tags: []')
        if not re.search(r'^generated_from:', content, re.MULTILINE):
            additions.append('generated_from: evolver')
        for a in additions:
            lines.insert(insert_idx, a)
        return '\n'.join(lines)

    def _fix_workflow(self, content: str, eval_result: EvalResult) -> str:
        # Skip if content is LLM-synthesized (has synthesis: llm marker)
        if 'synthesis: llm' in content:
            return content
        steps_match = re.search(r'(## Steps\s*\n)(.*?)(?=\n## |\Z)', content, re.DOTALL)
        if not steps_match:
            content += "\n\n## Steps\n1. Review the task requirements\n2. Execute the main action\n3. Verify the result\n"
            return content
        header, steps_text = steps_match.group(1), steps_match.group(2)
        lines = nonempty_lines(steps_text)
        numbered = []
        for i, line in enumerate(lines, 1):
            if re.match(r'^\d+\.', line):
                numbered.append(line)
            else:
                numbered.append(f"{i}. {line}")
        return content.replace(steps_match.group(0), header + '\n'.join(numbered) + '\n')

    def _fix_edge_cases(self, content: str, eval_result: EvalResult) -> str:
        if 'synthesis: llm' in content:
            return content
        if '## Error Handling' not in content and '## Common Pitfalls' not in content:
            content += "\n\n## Error Handling\n- If an operation fails, check the logs for details\n- Retry transient errors up to 3 times\n- For persistent failures, report the error and stop\n"
        return content

    def _fix_checkpoints(self, content: str, eval_result: EvalResult) -> str:
        if 'synthesis: llm' in content:
            return content
        if 'confirm' not in content.lower() and 'verify' not in content.lower():
            content = re.sub(
                r'(## Steps\s*\n)',
                r'\1> **Checkpoint:** Verify results before proceeding.\n\n',
                content,
            )
        return content

    def _fix_specificity(self, content: str, eval_result: EvalResult) -> str:
        if 'synthesis: llm' in content:
            return content
        if '```' not in content:
            content += "\n\n## Example\n```\n# Example usage\n# Input: <describe input>\n# Output: <describe expected output>\n```\n"
        return content

    def _fix_resources(self, content: str, eval_result: EvalResult) -> str:
        if 'synthesis: llm' in content:
            return content
        if '## Related' not in content and '## See Also' not in content:
            content += "\n\n## See Also\n- Refer to project documentation for advanced usage\n"
        return content

    def _fix_architecture(self, content: str, eval_result: EvalResult) -> str:
        if '## Overview' not in content:
            content = re.sub(
                r'(---\s*\n)',
                r'\1\n## Overview\nThis skill was auto-generated and optimized by evolver.\n\n',
                content,
                count=1,
            )
        return content

    def _fix_effectiveness(self, content: str, eval_result: EvalResult) -> str:
        topic_score = eval_result.dim_scores.get("effectiveness", 0)
        if topic_score >= 7:
            return content
        if not re.search(r'^\d+\.\s', content, re.MULTILINE):
            content += "\n\n## Quick Reference\n1. Identify the task scope\n2. Execute the core action\n3. Validate the result\n"
        if len(content) < 300:
            content += "\n\n> **Note:** This skill covers the essential patterns. " \
                       "Adapt the steps to your specific context.\n"
        return content

    # --- Logging ---

    def _log_evaluation(self, skill_id: int, round_num: int,
                        eval_result: EvalResult, status: str):
        try:
            self._storage.insert_skill_evaluation(
                skill_id=skill_id,
                version=1,
                total_score=eval_result.total_score,
                dim_scores=eval_result.dim_scores,
                eval_mode="auto",
                round=round_num,
                status=status,
            )
        except Exception as e:
            logger.warning("Failed to log evaluation: %s", e)
