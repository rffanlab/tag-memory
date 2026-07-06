# Tag Memory

**Tag-based memory system for AI agents — a cheaper, more controllable alternative to vector databases.**

Instead of embedding everything into vectors and hoping cosine similarity works, this system uses **hierarchical tags** + **LLM relevance filtering** to retrieve memories. Tags are human-readable, debuggable, and precise.

## Why Not Vector DB?

| Vector DB | Tag Memory |
|---|---|
| Semantic drift over time | Tags are explicit, no drift |
| Opaque "why was this retrieved?" | Full tag path traceable |
| Context window bloated by near-misses | Only tag-matched candidates enter AI filter |
| Embedding cost at scale | Tags amortize to near-zero |
| Hard to tune relevance thresholds | LLM filter understands nuance |

## How It Works

```
┌──────────────────────────────────────────────────────────┐
│                      WRITE PATH                          │
│                                                          │
│   Event Text ──→ LLM generates tags + summary ──→ MySQL  │
│                    "角色/张三", "地点/会议室"              │
└──────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│                      READ PATH                           │
│                                                          │
│   Intent ──→ LLM extracts search tags                    │
│       │           ["角色/张三", "概念/Q3目标"]            │
│       ▼                                                  │
│   SQL: SELECT * FROM events JOIN event_tags               │
│       WHERE tag IN (...) GROUP BY event HAVING hits >= 1  │
│       │                                                  │
│       ▼ (candidate events with summaries)                │
│   LLM filter: which of these are actually relevant?       │
│       │                                                  │
│       ▼                                                  │
│   Return full events + context block                     │
└──────────────────────────────────────────────────────────┘
```

## Features

- **Hierarchical tags** — `角色/宋怀真/武器/耳后一寸` with auto-dedup
- **Many-to-many** — one event has many tags, one tag spans many events
- **LLM-powered tagging** — auto-generates tags + summaries from raw text
- **Two-phase retrieval** — SQL pre-filter → LLM relevance check
- **Schema auto-migration** — runs `CREATE TABLE IF NOT EXISTS` on connect
- **Namespace isolation** — one database, multiple projects/agents
- **Async-first** — built on `httpx` + `pymysql`

## Install

```bash
git clone https://github.com/rffanlab/tag-memory.git
cd tag-memory
uv venv
uv pip install -e .
```

Requires Python 3.11+ and MySQL 8.0+.

## Quick Start

### 1. Set up MySQL

```sql
CREATE DATABASE tag_memory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

### 2. Configure

```bash
cp .env.example .env
# edit: OPENAI_API_KEY, OPENAI_BASE_URL, LLM_MODEL, MYSQL_PASSWORD
```

### 3. Use

```python
import asyncio
from dotenv import load_dotenv
load_dotenv()

from tag_memory import TagMemory, OpenAIClient
import os

async def main():
    mem = TagMemory(
        mysql_user="root",
        mysql_password=os.getenv("MYSQL_PASSWORD"),
        mysql_database="tag_memory",
        namespace="my-agent",
        llm=OpenAIClient(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        ),
    )

    # Store memories
    await mem.remember(
        "张三在会议室向李四汇报了Q3项目进展：已完成80%，需要延期两周。",
        event_type="dialogue",
    )
    await mem.remember(
        "李四宣布公司明年Q1战略重点是海外市场拓展。",
        event_type="milestone",
    )

    # Retrieve
    result = await mem.recall("张三的Q3进展怎么样？")
    for event in result.relevant:
        print(f"[{event.title}] {event.summary}")

    # Or get a compact text block for LLM prompts
    context = await mem.recall_text("明年公司的战略方向")
    print(context)

    mem.close()

asyncio.run(main())
```

## API

### TagMemory (high-level)

| Method | Description |
|---|---|
| `remember(content)` | Store event with auto-generated tags |
| `recall(intent)` | Full retrieval: tags → candidates → AI filter → results |
| `recall_text(intent)` | Same as recall, but returns formatted markdown string |

### TagManager (low-level)

| Method | Description |
|---|---|
| `get_or_create(name, parent_id)` | Idempotent tag creation |
| `ensure_path("角色/张三/武器")` | Create all tags along a path |
| `get_by_path(path)` | Resolve a path to a tag |
| `get_tree()` | Full hierarchical tag tree |
| `search(keyword)` | Fuzzy tag name search |

### EventManager (low-level)

| Method | Description |
|---|---|
| `insert(title, summary, tag_ids)` | Insert event with tags |
| `insert_with_paths(title, summary, paths)` | Insert with auto-created tag paths |
| `query_by_tags(tag_ids, min_hits)` | SQL query by tag intersection |
| `get_by_id(id)` | Full event with tag list |
| `get_recent(limit)` | Most recent events |

### Retriever

| Method | Description |
|---|---|
| `retrieve(intent)` | Full pipeline, returns `RetrieveResult` |
| `retrieve_compact(intent)` | Returns formatted markdown for LLM prompts |

## MySQL Schema

```sql
tags (id, name, parent_id, namespace, level, description)
events (id, namespace, event_type, title, summary, full_content, importance, source_ref, occurred_at)
event_tags (event_id, tag_id)  -- many-to-many
```

Tags are hierarchical via `parent_id`. The `namespace` column isolates different projects/agents.

## Supported LLM Providers

Any OpenAI-compatible API works. Tested with:

- **OpenAI** — `base_url=https://api.openai.com/v1`
- **DeepSeek** — `base_url=https://api.deepseek.com`, `model=deepseek-v4-pro`
- **MiniMax** — `base_url=https://api.minimax.chat/v1`

Set `OPENAI_BASE_URL` and `LLM_MODEL` in `.env`.

## License

MIT
