"""Tag-based Memory System for AI Agents.

Usage:
    from tag_memory import TagMemory

    mem = TagMemory(mysql_config={...}, llm_client=client)
    await mem.remember("张三在会议室向李四汇报了Q3进展...")
    results = await mem.recall("张三的Q3进展如何？")
"""

from .db import create_pool
from .tags import Tag, TagManager
from .events import Event, EventManager
from .generator import (
    TagGenerator,
    OpenAIClient,
    GeneratedTag,
    TagResult,
    tag_and_store,
)
from .retriever import Retriever, RetrieveResult


class TagMemory:
    """High-level API for the tag-based memory system."""

    def __init__(
        self,
        *,
        mysql_host: str = "localhost",
        mysql_port: int = 3306,
        mysql_user: str = "root",
        mysql_password: str = "",
        mysql_database: str = "tag_memory",
        namespace: str = "default",
        llm: "LLMClient | None" = None,
        llm_api_key: str | None = None,
        llm_base_url: str = "https://api.openai.com/v1",
        llm_model: str = "gpt-4o-mini",
    ):
        self.conn = create_pool(
            host=mysql_host,
            port=mysql_port,
            user=mysql_user,
            password=mysql_password,
            database=mysql_database,
        )
        self.tags = TagManager(self.conn, namespace)
        self.events = EventManager(self.conn, namespace)

        if llm is None:
            llm = OpenAIClient(
                api_key=llm_api_key,
                base_url=llm_base_url,
                model=llm_model,
            )
        self.generator = TagGenerator(llm)
        self.retriever = Retriever(
            self.events, self.tags, self.generator, llm,
        )

    async def remember(
        self,
        content: str,
        *,
        event_type: str = "misc",
        source_ref: str | None = None,
    ) -> Event:
        """Store a memory event with auto-generated tags."""
        from datetime import datetime
        return await tag_and_store(
            content=content,
            event_manager=self.events,  # type: ignore[arg-type]
            tag_manager=self.tags,
            generator=self.generator,
            event_type=event_type,
            source_ref=source_ref,
        )

    async def recall(
        self,
        intent: str,
        *,
        candidate_limit: int = 15,
        min_hits: int = 1,
    ) -> RetrieveResult:
        """Retrieve relevant memories for an intent."""
        return await self.retriever.retrieve(
            intent,
            candidate_limit=candidate_limit,
            min_hits=min_hits,
        )

    async def recall_text(
        self,
        intent: str,
        *,
        candidate_limit: int = 15,
    ) -> str:
        """Retrieve and format as text block for LLM prompts."""
        return await self.retriever.retrieve_compact(
            intent,
            candidate_limit=candidate_limit,
        )

    def close(self):
        self.conn.close()


__all__ = [
    "TagMemory",
    "TagManager",
    "EventManager",
    "TagGenerator",
    "Retriever",
    "OpenAIClient",
    "Tag",
    "Event",
    "GeneratedTag",
    "TagResult",
    "RetrieveResult",
    "tag_and_store",
    "create_pool",
]
