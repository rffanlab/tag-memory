"""
Demo — Tag-based Memory System full pipeline.

Run (auto-config from .env or TAG_MEMORY_* env vars):
  cd tag-memory && uv run python examples/demo.py

Or with explicit config:
  TAG_MEMORY_MYSQL_PASSWORD=secret uv run python examples/demo.py
"""

import asyncio

from tag_memory import TagMemory, Config


async def main():
    # ── Mode 1: Zero-config (reads .env + TAG_MEMORY_* env vars) ──
    print("=" * 50)
    print("Mode 1 — 零配置，自动读取 .env / TAG_MEMORY_* 环境变量")
    print("=" * 50)

    cfg = Config.from_env()
    print(f"  MySQL → {cfg.mysql.user}@{cfg.mysql.host}:{cfg.mysql.port}/{cfg.mysql.database}")
    print(f"  LLM   → {cfg.llm.model} @ {cfg.llm.base_url}")

    mem = TagMemory(namespace="demo")

    try:
        # Store some memories
        print("\n📝 存储记忆...")

        await mem.remember(
            "张三在会议室向李四汇报了Q3项目进展：已完成80%，但需要延期两周。"
            "李四表示理解，但要求下周一前给出具体的补救计划。",
            event_type="dialogue",
            source_ref="session-1/msg-3",
        )

        await mem.remember(
            "王五在代码仓库提交了用户认证模块的重构代码，修复了3个安全漏洞。"
            "PR #452，等待张三 review。",
            event_type="action",
            source_ref="session-1/msg-7",
        )

        await mem.remember(
            "李四宣布公司明年Q1的战略重点是海外市场拓展，"
            "要求各部门在月底前提交海外业务计划。",
            event_type="milestone",
            source_ref="session-2/msg-1",
        )

        await mem.remember(
            "张三和赵六讨论用户认证模块的技术方案，"
            "决定采用 OAuth 2.0 + JWT，放弃之前的 Session 方案。",
            event_type="dialogue",
            source_ref="session-2/msg-5",
        )

        print("   ✅ 4 条记忆已存储")

        # Query
        print("\n🔍 检索: '张三的Q3进展怎么样了？'")
        result = await mem.recall("张三的Q3进展怎么样了？")
        print(f"   标签: {result.search_tags}")
        print(f"   候选: {len(result.candidates)} 条, 相关: {len(result.relevant)} 条, 过滤: {result.filtered_out} 条")
        for e in result.relevant:
            tag_names = [t.name for t in (e.tags or [])]
            print(f"   → [{e.id}] {e.title} | 标签: {tag_names}")

        print("\n🔍 检索: '用户认证模块的最近进展'")
        result = await mem.recall("用户认证模块的最近进展")
        for e in result.relevant:
            print(f"   → [{e.id}] {e.title}: {e.summary}")

        print("\n🔍 检索: '公司明年的战略方向是什么'")
        result = await mem.recall("公司明年的战略方向是什么")
        for e in result.relevant:
            print(f"   → [{e.id}] {e.title}: {e.summary}")

        print("\n🔍 检索 (compact): '张三最近在忙什么'")
        text = await mem.recall_text("张三最近在忙什么")
        print(text[:500])

        # Show tag tree
        print("\n🏷️  标签树:")
        tree = mem.tags.get_tree()
        _print_tree(tree)

    finally:
        mem.close()

    # ── Mode 2: Explicit override ──
    print("\n" + "=" * 50)
    print("Mode 2 — 显式覆盖（最高优先级，忽略 env/.env）")
    print("=" * 50)

    # If you need to override, pass keyword args (they win over env/.env)
    # mem2 = TagMemory(
    #     mysql_host="192.168.1.100",
    #     mysql_password="prod-secret",
    #     llm_model="gpt-4o",
    #     namespace="production",
    # )
    print("   mem = TagMemory(mysql_host='...', llm_model='gpt-4o')")
    print("   显式参数优先级最高，覆盖 .env 和系统环境变量")


def _print_tree(tags, indent=0):
    for tag in tags:
        print("  " * indent + f"├─ {tag.name} ({tag.level})")
        _print_tree(tag.children, indent + 1)


if __name__ == "__main__":
    asyncio.run(main())
