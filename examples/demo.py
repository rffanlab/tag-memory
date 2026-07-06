"""
Demo — Tag-based Memory System full pipeline.

Run:
  uv run python examples/demo.py
"""

import asyncio
import os

from dotenv import load_dotenv
load_dotenv()

from tag_memory import TagMemory, OpenAIClient


async def main():
    # 1. Connect
    mem = TagMemory(
        mysql_user="root",
        mysql_password=os.getenv("MYSQL_PASSWORD", ""),
        mysql_database="tag_memory",
        namespace="demo",
        llm=OpenAIClient(
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        ),
    )

    try:
        # 2. Store some memories
        print("📝 存储记忆...")

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

        # 3. Query
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

        # 4. Show tag tree
        print("\n🏷️  标签树:")
        tree = mem.tags.get_tree()
        _print_tree(tree)

    finally:
        mem.close()


def _print_tree(tags, indent=0):
    for tag in tags:
        print("  " * indent + f"├─ {tag.name} ({tag.level})")
        _print_tree(tag.children, indent + 1)


if __name__ == "__main__":
    asyncio.run(main())
