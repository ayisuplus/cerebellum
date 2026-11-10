class EvolverError(Exception):
    """Base exception for all evolver errors."""

class EvolverConnectionError(EvolverError):
    """MySQL connection failed."""

class EmbeddingError(EvolverError):
    """Embedding generation failed."""

class StorageError(EvolverError):
    """Database operation failed."""

class SkillGenerationError(EvolverError):
    """Skill.md generation failed."""

class GitHubConnectorError(EvolverError):
    """GitHub API operation failed."""

class NotionConnectorError(EvolverError):
    """Notion API operation failed."""
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code
