"""
Retriever — the core AI retrieval flow.

Flow:
  1. intent → LLM extracts search tags
  2. search tags → SQL query by tags (min_hits=1, limit=15)
  3. candidate summaries → LLM filters for relevance
  4. relevant event IDs → fetch full events with tags
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .events import Event, EventManager
    from .generator import TagGenerator
    from .tags import TagManager


# ── LLM Client Protocol ──────────────────────────────────

class LLMClient(Protocol):
    async def chat(self, system: str, user: str) -> str: ...


# ── Types ────────────────────────────────────────────────

@dataclass
class RetrieveResult:
    intent: str
    search_tags: list[str]
    candidates: list[Event]
    relevant: list[Event]
    filtered_out: int


# ── Prompts ───────────────────────────────────────────────

_FILTER_SYSTEM = """你是一个记忆过滤器。给定一个查询意图和一批候选事件摘要，判断哪些事件与查询相关。

规则：
- 只保留与查询意图直接相关的事件
- 如果事件提供了背景信息或上下文，也算相关
- 如果事件完全不相关，排除
- 当不确定时，保留（宁可多留不要漏）

输出严格 JSON:
{
  "relevant_ids": [3, 7, 12],
  "reasoning": "简要说明为什么选了这些"
}"""

# ── Retriever ─────────────────────────────────────────────

class Retriever:
    """Full retrieval pipeline: intent → tags → candidates → AI filter → results."""

    def __init__(
        self,
        event_manager: EventManager,
        tag_manager: TagManager,
        tag_generator: TagGenerator,
        llm: LLMClient,
    ):
        self.events = event_manager
        self.tags = tag_manager
        self.generator = tag_generator
        self.llm = llm

    async def retrieve(
        self,
        intent: str,
        *,
        candidate_limit: int = 15,
        min_hits: int = 1,
    ) -> RetrieveResult:
        """Full retrieval pipeline."""

        # ── Phase 1: intent → search tags ─────────────────
        search_paths = await self.generator.extract_tags(intent)

        # ── Phase 2: resolve tag paths to IDs ─────────────
        tag_ids: list[int] = []
        for path in search_paths:
            tag = self.tags.get_by_path(path)
            if tag and tag.id:
                tag_ids.append(tag.id)

        # Fallback: try partial match on tag names
        if not tag_ids:
            for path in search_paths:
                leaf = path.rsplit("/", 1)[-1]
                for tag in self.tags.search(leaf, limit=5):
                    if tag.id and tag.id not in tag_ids:
                        tag_ids.append(tag.id)

        # ── Phase 3: SQL query by tags ───────────────────
        candidates = self.events.query_by_tags(
            tag_ids,
            min_hits=min_hits,
            limit=candidate_limit,
        )

        if not candidates:
            return RetrieveResult(
                intent=intent,
                search_tags=search_paths,
                candidates=[],
                relevant=[],
                filtered_out=0,
            )

        # ── Phase 4: AI relevance filter ──────────────────
        candidate_items = "\n".join(
            f"[ID:{e.id}] {e.title}: {e.summary}"
            for e in candidates
            if e.id is not None
        )

        filter_user = f"""查询意图：{intent}

候选事件（共 {len(candidates)} 条）：
{candidate_items}"""

        response = await self.llm.chat(_FILTER_SYSTEM, filter_user)
        data = json.loads(response)
        relevant_ids = set(data.get("relevant_ids", []))

        # ── Phase 5: fetch full events ────────────────────
        relevant = [
            e for e in candidates
            if e.id in relevant_ids
        ]

        # enrich with tags
        for event in relevant:
            if event.id:
                event.tags = self.events.get_tags(event.id)

        return RetrieveResult(
            intent=intent,
            search_tags=search_paths,
            candidates=candidates,
            relevant=relevant,
            filtered_out=len(candidates) - len(relevant),
        )

    async def retrieve_compact(
        self,
        intent: str,
        *,
        candidate_limit: int = 15,
        min_hits: int = 1,
    ) -> str:
        """Retrieve and format as a compact context block for LLM prompts."""
        result = await self.retrieve(
            intent,
            candidate_limit=candidate_limit,
            min_hits=min_hits,
        )

        if not result.relevant:
            return f"[无相关记忆] 查询: {intent}"

        blocks = [f"## 相关记忆 ({len(result.relevant)} 条)\n"]
        for i, event in enumerate(result.relevant, 1):
            tag_paths = []
            if event.tags:
                for t in event.tags:
                    path = t.name
                    current_id = t.parent_id
                    depth = 0
                    while current_id and depth < 10:
                        parent = self.tags.get_by_id(current_id)
                        if parent:
                            path = f"{parent.name}/{path}"
                            current_id = parent.parent_id
                        else:
                            break
                        depth += 1
                    tag_paths.append(path)

            blocks.append(
                f"### 记忆 {i}: {event.title}\n"
                f"标签: {', '.join(tag_paths[:5])}\n"
                f"摘要: {event.summary}\n"
            )
            if event.full_content:
                blocks.append(f"详情: {event.full_content}\n")

        return "\n".join(blocks)
