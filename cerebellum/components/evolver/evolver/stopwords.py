"""Shared stopword sets for both memory and graph modules.

Single source of truth to prevent drift between modules.
"""

# English stopwords
_ENGLISH_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "through", "during",
    "before", "after", "above", "below", "between", "and", "but", "or",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "every", "all", "any", "few", "more", "most", "other", "some", "such",
    "than", "too", "very", "just", "also", "now", "then", "here", "there",
    "when", "where", "why", "how", "what", "which", "who", "whom", "this",
    "that", "these", "those", "i", "me", "my", "we", "our", "you", "your",
    "he", "him", "his", "she", "her", "it", "its", "they", "them", "their",
}

# Chinese stopwords
_CHINESE_STOPWORDS = {
    "的", "了", "在", "是", "和", "与", "或", "但", "不", "有",
    "这", "那", "我", "你", "他", "她", "它", "们", "就", "都",
    "而", "及", "等", "个", "上", "下", "中", "里", "到", "把",
    "被", "让", "给", "从", "向", "又", "也", "还", "已", "正在",
}

# Combined set
STOPWORDS = _ENGLISH_STOPWORDS | _CHINESE_STOPWORDS

# Common tech terms for node type inference in graph module
TOOL_KEYWORDS = {
    "git", "docker", "nginx", "redis", "mysql", "postgres", "python",
    "javascript", "node", "npm", "pip", "cargo", "ssh", "curl", "aws",
    "kubernetes", "k8s", "terraform", "ansible", "linux", "bash",
    "vim", "vscode", "pytest", "unittest", "mypy", "ruff", "uv",
    "react", "vue", "angular", "typescript", "rust", "go", "java",
    "spring", "django", "flask", "fastapi", "tensorflow", "pytorch",
}

TECHNIQUE_KEYWORDS = {
    "merge", "rebase", "deploy", "test", "debug", "refactor",
    "optimize", "cache", "retry", "fallback", "rollback", "iterate",
    "traverse", "search", "sort", "filter", "map", "reduce",
    "embed", "tokenize", "normalize", "validate", "migrate",
}
