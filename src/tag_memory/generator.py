"""
LLM Tag Generator — auto-generate hierarchical tags from text content.

Two modes:
  1. tag_event()      — tag a single event (for storing memories)
  2. extract_tags()   — extract tags from an agent's intent/query (for retrieval)

Uses structured JSON output from the LLM for reliable parsing.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

import httpx

if TYPE_CHECKING:
    from .tags import TagManager


# ── Types ────────────────────────────────────────────────

@dataclass
class GeneratedTag:
    """A tag suggested by the LLM, not yet persisted."""
    path: str       # e.g. "角色/师父" or "地点/藏经阁"
    level: str      # entity / place / action / item / misc
    description: str | None = None


@dataclass
class TagResult:
    tags: list[GeneratedTag]
    summary: str    # short summary of the event (for storage)
    title: str      # short title of the event
    importance: int   # 1-10


# ── LLM Client Protocol ──────────────────────────────────

class LLMClient(Protocol):
    """Protocol for LLM clients. Implement with any provider."""
    async def chat(self, system: str, user: str) -> str: ...


# ── OpenAI-compatible client ──────────────────────────────

class OpenAIClient:
    """Minimal OpenAI-compatible client. Works with DeepSeek, OpenAI, etc."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or ""
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(self, system: str, user: str) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]


# ── Prompts ───────────────────────────────────────────────

_EVENT_TAG_SYSTEM = """你是一个记忆标签系统。给定一段事件描述，你需要：

1. 提取层级标签。每个标签是一个 '/' 分隔的路径。尽量复用已有类别：
   - 角色/<名称>[/<子属性>]    如: 角色/张三, 角色/张三/武器
   - 地点/<名称>[/<子地点>]    如: 地点/公司/会议室
   - 事件/<类型>              如: 事件/会议, 事件/冲突
   - 物品/<名称>              如: 物品/合同
   - 概念/<名称>              如: 概念/季度目标
   - 时间/<节点>              如: 时间/2024-Q3

2. 为事件写一个简短标题（10字内）和一句话摘要（50字内）。
3. 评估事件重要性（1-10）。关键决策=8+，日常记录=3-5，里程碑=9-10。

输出严格 JSON:
{
  "tags": [
    {"path": "角色/张三", "level": "entity", "description": "项目负责人"},
    {"path": "地点/公司/会议室", "level": "place"}
  ],
  "title": "张三汇报Q3进展",
  "summary": "张三在周会上汇报Q3项目已完成80%，提出需要延期两周",
  "importance": 7
}"""


_QUERY_TAG_SYSTEM = """你是一个意图标签提取器。给定一个 agent 的查询意图，提取用于检索的关键标签路径。

规则：
- 只提取对检索有用的标签（实体、地点、事件类型、关键概念）
- 不要提取泛化词（如"所有""最近""什么"）
- 每个标签用 '/' 分隔层级
- 如果有不确定的标签，也列出来（系统会自动模糊匹配）

输出严格 JSON:
{
  "tags": ["角色/张三", "地点/公司", "概念/Q3目标"],
  "intent_type": "query"  或 "action"  或 "recall"
}"""


# ── Generator ─────────────────────────────────────────────

class TagGenerator:
    """Generate tags and summaries from text using an LLM."""

    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def tag_event(self, content: str) -> TagResult:
        """Analyze an event and produce tags + metadata."""
        response = await self.llm.chat(_EVENT_TAG_SYSTEM, content)
        data = json.loads(response)
        return TagResult(
            tags=[GeneratedTag(**t) for t in data.get("tags", [])],
            title=data.get("title", ""),
            summary=data.get("summary", content[:100]),
            importance=data.get("importance", 5),
        )

    async def extract_tags(self, intent: str) -> list[str]:
        """Extract search tags from an agent's intent/query."""
        response = await self.llm.chat(_QUERY_TAG_SYSTEM, intent)
        data = json.loads(response)
        return data.get("tags", [])


# ── Pipeline ──────────────────────────────────────────────

async def tag_and_store(
    content: str,
    event_manager,
    tag_manager: TagManager,
    generator: TagGenerator,
    *,
    event_type: str = "misc",
    source_ref: str | None = None,
) -> Event:
    """Full pipeline: tag an event and persist it.

    Usage:
        event = await tag_and_store(
            "张三在会议室向李四汇报了Q3进展...",
            event_mgr, tag_mgr, generator,
            event_type="dialogue",
            source_ref="session-42/msg-7",
        )
    """
    from datetime import datetime

    result = await generator.tag_event(content)

    # persist tags (auto-create missing)
    tag_ids = []
    for gt in result.tags:
        tag = tag_manager.ensure_path(gt.path, level=gt.level)
        if tag.id:
            tag_ids.append(tag.id)

    # persist event
    event = event_manager.insert(
        title=result.title,
        summary=result.summary,
        tag_ids=tag_ids,
        event_type=event_type,
        full_content=content,
        importance=result.importance,
        source_ref=source_ref,
        occurred_at=datetime.now(),
    )

    # Import here to avoid circular dependency
    from .events import Event
    event.tags = tag_manager.get_by_ids(tag_ids)
    return event
