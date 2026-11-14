"""Offline retrieval over a Vietnamese knowledge base (SQLite FTS5 / BM25) to ground the small LLM's answers."""
from .index import KnowledgeBase, build_prompt_context

__all__ = ["KnowledgeBase", "build_prompt_context"]
