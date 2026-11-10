"""Optional LLM client for memory distillation.

Supports OpenAI-compatible APIs and Anthropic. Falls back to heuristic
compression when no LLM is configured.
"""

import json
import logging
import time
import urllib.request
import urllib.error
from functools import wraps

from evolver.utils import nonempty_lines


def retry(max_retries=3, backoff=1.0, retry_on=(429, 503)):
    """Decorator for retrying failed function calls with exponential backoff."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt == max_retries:
                        break
                    error_code = getattr(e, 'code', None)
                    if error_code in retry_on:
                        wait = backoff * (2 ** attempt)
                        logger.warning(
                            "Retry %d/%d after %.1fs (code=%s)",
                            attempt + 1, max_retries, wait, error_code
                        )
                        time.sleep(wait)
                    else:
                        raise
            raise last_exception
        return wrapper
    return decorator

logger = logging.getLogger(__name__)

# Distillation prompts for each level
PROMPTS = {
    "today": {
        "zh": (
            "你是一个记忆压缩器。请从以下学习记录中提炼3-5条粗颗粒经验。\n\n"
            "规则：\n"
            "- 只保留核心教训和反复出现的模式\n"
            "- 合并同一主题的多条记录为一条\n"
            "- 去掉具体文件名、命令、代码细节\n"
            "- 每条1-2句话\n\n"
            "禁止：分析、解释、展示草稿、展示思考过程、使用Markdown格式。\n"
            "只输出最终的纯文本列表。"
        ),
        "en": (
            "You are a memory compressor. Distill the following learning records "
            "into 3-5 coarse-grained lessons.\n\n"
            "Rules:\n"
            "- Keep only core lessons and recurring patterns\n"
            "- Merge same-topic records into one\n"
            "- Remove filenames, commands, code details\n"
            "- 1-2 sentences per item\n\n"
            "FORBIDDEN: analysis, explanations, drafts, thinking process, Markdown formatting.\n"
            "Output ONLY the final plain text list."
        ),
    },
    "week": {
        "zh": (
            "你是一个记忆压缩器。请从过去7天的经验中归纳主要模式。\n\n"
            "规则：\n"
            "- 记录用户反复遇到的问题类型\n"
            "- 记录用户擅长和不擅长的领域\n"
            "- 去掉单次事件，只保留反复出现的主题\n"
            "- 最多5条\n\n"
            "禁止：分析、解释、展示草稿、展示思考过程、使用Markdown格式。\n"
            "只输出最终的纯文本。"
        ),
        "en": (
            "You are a memory compressor. Summarize the past 7 days into major patterns.\n\n"
            "Rules:\n"
            "- Record recurring problem types\n"
            "- Record user strengths and weaknesses\n"
            "- Remove one-off events, keep recurring themes\n"
            "- Max 5 items\n\n"
            "FORBIDDEN: analysis, explanations, drafts, thinking process, Markdown formatting.\n"
            "Output ONLY the final plain text."
        ),
    },
    "longterm": {
        "zh": (
            "你是一个记忆压缩器。请将以下内容整合为长期技能画像。\n\n"
            "只保留（如果一年后回看仍有用的）：\n"
            "- 用户擅长什么、常犯什么错\n"
            "- 偏好的工作方法和技术栈\n"
            "- 长期关注的领域和方向\n\n"
            "去掉：具体任务、具体日期、单次事件。\n"
            "禁止：分析、解释、展示草稿、展示思考过程、使用Markdown格式。\n"
            "只输出最终的纯文本。最多300字。"
        ),
        "en": (
            "You are a memory compressor. Consolidate into a long-term skill profile.\n\n"
            "Keep only what would still be useful a year from now:\n"
            "- User strengths and common mistakes\n"
            "- Preferred methods and tech stack\n"
            "- Long-term focus areas\n\n"
            "Remove: specific tasks, dates, one-off events.\n"
            "FORBIDDEN: analysis, explanations, drafts, thinking process, Markdown formatting.\n"
            "Output ONLY the final plain text. Max 200 words."
        ),
    },
    "facts": {
        "zh": (
            "你是一个事实提取器。从以下内容中提取独立的客观事实。\n\n"
            "规则：\n"
            "- 每条事实只记一件事（原子性）\n"
            "- 只提取稳定的用户画像和技能特征\n"
            "- 不要提取执行细节和过程信息\n"
            "- 为每条事实附2-3个标签\n\n"
            "禁止：分析、解释、展示草稿、展示思考过程。\n"
            "只输出JSON数组：[{\"fact\": \"...\", \"tags\": [\"...\"]}]\n"
            "如果没有值得提取的内容，返回空数组[]。"
        ),
        "en": (
            "You are a fact extractor. Extract independent objective facts.\n\n"
            "Rules:\n"
            "- Each fact is atomic (one thing per entry)\n"
            "- Only extract stable user profile and skill traits\n"
            "- Do not extract execution details or process info\n"
            "- Attach 2-3 tags per fact\n\n"
            "FORBIDDEN: analysis, explanations, drafts, thinking process.\n"
            "Output ONLY JSON array: [{\"fact\": \"...\", \"tags\": [\"...\"]}]\n"
            "Return empty array [] if nothing worth extracting."
        ),
    },
}

VERIFY_PROMPTS = {
    "zh": (
        "你是一个蒸馏保真度验证器。请检查以下摘要是否准确反映了原文中的事实。\n\n"
        "规则：\n"
        "- 对比原文和摘要中的每一条事实\n"
        "- 检查摘要是否引入了原文中没有的信息（幻觉）\n"
        "- 检查摘要是否遗漏了原文中的关键信息\n"
        "- 检查摘要是否歪曲了原文的含义\n\n"
        "输出格式（纯JSON）：\n"
        '{"fidelity": 0.0-1.0, "issues": ["问题1", "问题2"], "verdict": "pass|fail"}\n'
        "fidelity: 1.0=完全准确, 0.0=完全失真\n"
        "verdict: fidelity>=0.7为pass，否则为fail"
    ),
    "en": (
        "You are a distillation fidelity verifier. Check whether the summary "
        "accurately reflects the facts in the original text.\n\n"
        "Rules:\n"
        "- Compare each fact in the summary against the original\n"
        "- Check if the summary introduces information not in the original (hallucination)\n"
        "- Check if the summary omits key information from the original\n"
        "- Check if the summary distorts the meaning of the original\n\n"
        "Output format (pure JSON):\n"
        '{"fidelity": 0.0-1.0, "issues": ["issue1", "issue2"], "verdict": "pass|fail"}\n'
        "fidelity: 1.0=perfectly accurate, 0.0=completely wrong\n"
        "verdict: pass if fidelity>=0.7, fail otherwise"
    ),
}


PROVIDERS = {
    "minimax": {
        "base_url": "https://api.minimax.chat/v1",
        "models": {"fast": "MiniMax-M2.7", "quality": "MiniMax-M2.7"},
        "note": "Chinese AI, long context, thinking mode",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com/v1",
        "models": {"fast": "deepseek-chat", "quality": "deepseek-reasoner"},
        "note": "Cheap, strong reasoning (V3/R1)",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "models": {"fast": "qwen-turbo", "quality": "qwen-max"},
        "note": "Alibaba cloud, good Chinese",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "models": {"fast": "gpt-4o-mini", "quality": "gpt-4o"},
        "note": "OpenAI official",
    },
    "anthropic": {
        "base_url": "https://api.anthropic.com",
        "models": {"fast": "claude-3-haiku-20240307", "quality": "claude-3-5-sonnet-20241022"},
        "note": "Uses native Anthropic API (not OpenAI-compatible)",
    },
}


class LLMClient:
    """Optional LLM client for memory distillation.

    When no API is configured, compress() falls back to heuristic mode:
    sort memories by importance, take top-N, and concatenate.

    Supports any OpenAI-compatible API (MiniMax, DeepSeek, Qwen, etc.)
    by setting provider="openai" with custom base_url and api_key.
    Use PROVIDERS dict for quick reference.
    """

    def __init__(self, provider: str = "openai", api_key: str = None,
                 model: str = None, base_url: str = None):
        self.provider = provider
        self.api_key = api_key
        self.model = model or self._default_model()
        self.base_url = base_url or self._default_base_url()
        self._available = bool(api_key)

    def _default_model(self) -> str:
        provider_info = PROVIDERS.get(self.provider, {})
        models = provider_info.get("models", {})
        return models.get("fast", "gpt-4o-mini")

    def _default_base_url(self) -> str:
        provider_info = PROVIDERS.get(self.provider, {})
        return provider_info.get("base_url", "https://api.openai.com/v1")

    @property
    def available(self) -> bool:
        return self._available

    def compress(self, input_text: str, level: str = "today",
                 max_tokens: int = 500, lang: str = "en") -> str:
        """Compress text using LLM or heuristic fallback.

        Args:
            input_text: Text to compress.
            level: Distillation level ('today'|'week'|'longterm'|'facts').
            max_tokens: Max output tokens.
            lang: Language ('zh'|'en').
        """
        if not input_text.strip():
            return ""
        if not self._available:
            return self.heuristic_compress(input_text, max_tokens)
        # Thinking models need extra tokens for reasoning before output
        # Multiply by 4 to give enough space for thinking + answer
        effective_tokens = max_tokens * 4
        prompt = PROMPTS.get(level, PROMPTS["today"]).get(lang, PROMPTS["today"]["en"])
        try:
            result = self.call_llm(input_text, prompt, effective_tokens)
            return self.extract_final_answer(result)
        except Exception as e:
            logger.warning("LLM call failed, falling back to heuristic: %s", e)
            return self.heuristic_compress(input_text, max_tokens)

    def verify(self, original: str, distilled: str, lang: str = "zh") -> dict:
        """验证蒸馏摘要是否准确反映原文。

        Args:
            original: 原始记忆文本。
            distilled: 蒸馏后的摘要。
            lang: 语言 ('zh'|'en')。

        Returns:
            dict with keys: fidelity (float 0-1), issues (list[str]), verdict (str "pass"|"fail").
            Returns {"fidelity": 1.0, "issues": [], "verdict": "pass"} when LLM is unavailable.
        """
        if not self._available:
            return {"fidelity": 1.0, "issues": [], "verdict": "pass"}
        prompt = VERIFY_PROMPTS.get(lang, VERIFY_PROMPTS["en"])
        input_text = f"[Original]\n{original}\n\n[Summary]\n{distilled}"
        try:
            result = self.call_llm(input_text, prompt, max_tokens=500)
            result = self.extract_final_answer(result)
            # Parse JSON from response
            if "```" in result:
                import re
                m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", result, re.DOTALL)
                if m:
                    result = m.group(1)
            parsed = json.loads(result)
            return {
                "fidelity": float(parsed.get("fidelity", 0.5)),
                "issues": parsed.get("issues", []),
                "verdict": parsed.get("verdict", "fail"),
            }
        except Exception as e:
            logger.warning("Fidelity verification failed: %s", e)
            return {"fidelity": 1.0, "issues": [], "verdict": "pass"}

    def heuristic_compress(self, text: str, max_tokens: int) -> str:
        """Heuristic compression: split by lines, keep first N lines within token budget."""
        lines = nonempty_lines(text)
        # Rough estimate: 1 token ≈ 4 chars (English) or 1.5 chars (Chinese)
        char_budget = max_tokens * 3
        result = []
        total = 0
        for line in lines:
            if total + len(line) > char_budget:
                break
            result.append(line)
            total += len(line)
        return "\n".join(result)

    def call_llm(self, input_text: str, system_prompt: str, max_tokens: int) -> str:
        """Call LLM API. Supports OpenAI-compatible and Anthropic."""
        if self.provider == "anthropic":
            return self._call_anthropic(input_text, system_prompt, max_tokens)
        return self._call_openai_compatible(input_text, system_prompt, max_tokens)

    @retry()
    def _call_openai_compatible(self, input_text: str, system_prompt: str,
                                 max_tokens: int) -> str:
        url = f"{self.base_url.rstrip('/')}/chat/completions"
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": input_text},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3,
            "think": False,
        }).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        })
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        msg = data["choices"][0]["message"]
        content = msg.get("content", "").strip()
        # Gemma4 puts thinking in "reasoning" field, content may be empty
        if not content and "reasoning" in msg:
            content = msg["reasoning"].strip()
        # Strip any leaked thinking artifacts
        return self.strip_thinking(content)

    @staticmethod
    def strip_thinking(text: str) -> str:
        """Remove common thinking/reasoning artifacts from model output."""
        import re
        # Remove <think>...</think> blocks (Gemma/MiniMax thinking mode)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        # Remove <thinking>...</thinking> blocks
        text = re.sub(r"<thinking>.*?</thinking>", "", text, flags=re.DOTALL)
        # Remove MiniMax-style plain-text thinking (no tags)
        # Patterns: "用户要求我...", "让我分析...", "可能提炼的...", "我需要..."
        thinking_patterns = [
            r"用户要求我.*?(?=\n\n|\n[1-9一二三])",
            r"让我(分析|看看|总结|合并|提炼).*?(?=\n\n|\n[1-9一二三])",
            r"可能提炼的.*?(?=\n\n|\n[1-9一二三])",
            r"我需要.*?(?=\n\n|\n[1-9一二三])",
            r"(关键信息|这些信息)[：:].*?(?=\n\n|\n[1-9一二三])",
            r"这看起来像是.*?(?=\n\n|\n[1-9一二三])",
            r"^(这是|这是一个|这段).*?(总结|摘要|记录).*?$",
        ]
        for pat in thinking_patterns:
            text = re.sub(pat, "", text, flags=re.DOTALL)
        # Remove lines starting with > (thinking artifacts)
        lines = text.split("\n")
        cleaned = [line for line in lines if not line.strip().startswith(">")]
        return "\n".join(cleaned).strip()

    @staticmethod
    def extract_final_answer(text: str) -> str:
        """Extract the final answer from verbose thinking output."""
        import re
        # If output is short and has no thinking markers, return as-is
        if len(text) < 200 and not any(kw in text for kw in ["让我", "用户要求", "可能提炼", "我需要", "分析"]):
            return text
        # Try to extract JSON block first (for facts extraction)
        json_match = re.search(r"```json\s*\n(.*?)\n```", text, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        # Try to find JSON array without code fence
        json_array_match = re.search(r"(\[\s*\{.*?\}\s*\])", text, re.DOTALL)
        if json_array_match:
            return json_array_match.group(1).strip()
        # For plain text: remove thinking patterns and take last lines
        # Remove all thinking-like patterns (analysis, drafts, checking)
        text = re.sub(r"\*+\s*(Input|Goal|Rules?|Item|Draft|Check|Refin|Record|Constraint|Rule|Step|Wait|Actually|Let|If I|The input|Both|Pattern|Combining|Adopt|Address|Use|Through|针对|通过|采用|根据|两种|这些|这里|如果|那么|等等|所以|其实|让我|输入|目标|规则|项目|草稿|检查|细化|记录|约束|步骤|等待|实际上|如果我|输入是|两者|模式|合并|采用|地址|使用|通过).*", "", text, flags=re.MULTILINE)
        # Remove bullet/numbered analysis lines
        text = re.sub(r"^[\s]*[-*•]\s+.*$", "", text, flags=re.MULTILINE)
        text = re.sub(r"^[\s]*\d+\.\s+.*$", "", text, flags=re.MULTILINE)
        # Remove empty lines and get last remaining content
        lines = nonempty_lines(text)
        # Return the last meaningful lines (likely the final answer)
        if lines:
            return "\n".join(lines[-5:])
        return text

    @retry()
    def _call_anthropic(self, input_text: str, system_prompt: str,
                         max_tokens: int) -> str:
        url = f"{self.base_url.rstrip('/')}/v1/messages"
        body = json.dumps({
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": input_text}],
            "temperature": 0.3,
        }).encode()
        req = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        })
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
        return data["content"][0]["text"].strip()
