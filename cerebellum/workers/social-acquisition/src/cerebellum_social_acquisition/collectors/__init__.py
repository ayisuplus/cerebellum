"""Paper collector providers (OpenAlex / arXiv / journal RSS)."""

from __future__ import annotations

from .arxiv import ArxivProvider
from .journal import JournalProvider
from .openalex import OpenAlexProvider

COLLECTOR_PROVIDERS = {
    provider.kind: provider
    for provider in (
        OpenAlexProvider(),
        ArxivProvider(),
        JournalProvider(),
    )
}

__all__ = ["COLLECTOR_PROVIDERS"]
