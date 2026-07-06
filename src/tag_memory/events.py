"""Event Manager — store and query memory events with tag associations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from .tags import Tag, TagManager

if TYPE_CHECKING:
    import pymysql


@dataclass
class Event:
    id: int | None = None
    namespace: str = "default"
    event_type: str = "misc"
    title: str = ""
    summary: str = ""
    full_content: str | None = None
    importance: int = 5
    source_ref: str | None = None
    occurred_at: datetime | None = None
    created_at: datetime | None = None

    # populated on retrieval
    tag_ids: list[int] | None = None
    tags: list[Tag] | None = None


class EventManager:
    """Stores and queries events, handling tag associations."""

    def __init__(self, conn: pymysql.Connection, namespace: str = "default"):
        self.conn = conn
        self.namespace = namespace
        self.tags = TagManager(conn, namespace)

    # ── Create ────────────────────────────────────────────

    def insert(
        self,
        title: str,
        summary: str,
        tag_ids: list[int],
        *,
        event_type: str = "misc",
        full_content: str | None = None,
        importance: int = 5,
        source_ref: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Event:
        """Insert an event and associate tags atomically."""
        if occurred_at is None:
            occurred_at = datetime.now()

        with self.conn.cursor() as cur:
            cur.execute(
                """INSERT INTO events
                   (namespace, event_type, title, summary, full_content,
                    importance, source_ref, occurred_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (self.namespace, event_type, title, summary,
                 full_content, importance, source_ref, occurred_at),
            )
            event_id = cur.lastrowid

            if tag_ids:
                cur.executemany(
                    "INSERT INTO event_tags (event_id, tag_id) VALUES (%s, %s)",
                    [(event_id, tid) for tid in tag_ids],
                )

        return Event(
            id=event_id,
            namespace=self.namespace,
            event_type=event_type,
            title=title,
            summary=summary,
            full_content=full_content,
            importance=importance,
            source_ref=source_ref,
            occurred_at=occurred_at,
            tag_ids=tag_ids,
        )

    def insert_with_paths(
        self,
        title: str,
        summary: str,
        tag_paths: list[str],
        *,
        event_type: str = "misc",
        full_content: str | None = None,
        importance: int = 5,
        source_ref: str | None = None,
        occurred_at: datetime | None = None,
    ) -> Event:
        """Insert an event, auto-creating tags from '/' delimited paths."""
        tag_ids = []
        for path in tag_paths:
            tag = self.tags.ensure_path(path)
            if tag.id:
                tag_ids.append(tag.id)

        return self.insert(
            title=title,
            summary=summary,
            tag_ids=tag_ids,
            event_type=event_type,
            full_content=full_content,
            importance=importance,
            source_ref=source_ref,
            occurred_at=occurred_at,
        )

    # ── Query by Tags ─────────────────────────────────────

    def query_by_tags(
        self,
        tag_ids: list[int],
        min_hits: int = 1,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        """
        Find events matching at least `min_hits` of the given tags.
        Results are ordered by (hit_count DESC, importance DESC, occurred_at DESC).
        """
        if not tag_ids:
            return []

        placeholders = ",".join(["%s"] * len(tag_ids))
        with self.conn.cursor() as cur:
            cur.execute(
                f"""SELECT e.*, COUNT(et.tag_id) AS hit_count
                    FROM events e
                    JOIN event_tags et ON e.id = et.event_id
                    WHERE e.namespace = %s AND et.tag_id IN ({placeholders})
                    GROUP BY e.id
                    HAVING hit_count >= %s
                    ORDER BY hit_count DESC, e.importance DESC, e.occurred_at DESC
                    LIMIT %s OFFSET %s""",
                (self.namespace, *tag_ids, min_hits, limit, offset),
            )
            rows = cur.fetchall()

        return [
            Event(
                id=row["id"],
                namespace=row["namespace"],
                event_type=row["event_type"],
                title=row["title"],
                summary=row["summary"],
                full_content=row["full_content"],
                importance=row["importance"],
                source_ref=row["source_ref"],
                occurred_at=row["occurred_at"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def query_by_tag_names(
        self,
        tag_names: list[str],
        min_hits: int = 1,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Event]:
        """Find events by tag names directly (convenience method)."""
        tag_ids: list[int] = []
        for name in tag_names:
            results = self.tags.search(name, limit=10)
            for t in results:
                if t.id and t.id not in tag_ids:
                    tag_ids.append(t.id)
        return self.query_by_tags(tag_ids, min_hits=min_hits, limit=limit, offset=offset)

    # ── Read ──────────────────────────────────────────────

    def get_by_id(self, event_id: int) -> Event | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM events WHERE id = %s AND namespace = %s",
                (event_id, self.namespace),
            )
            row = cur.fetchone()
            if not row:
                return None

            # load tag IDs
            cur.execute(
                "SELECT tag_id FROM event_tags WHERE event_id = %s",
                (event_id,),
            )
            tag_ids = [r["tag_id"] for r in cur.fetchall()]

            return Event(
                id=row["id"],
                namespace=row["namespace"],
                event_type=row["event_type"],
                title=row["title"],
                summary=row["summary"],
                full_content=row["full_content"],
                importance=row["importance"],
                source_ref=row["source_ref"],
                occurred_at=row["occurred_at"],
                created_at=row["created_at"],
                tag_ids=tag_ids,
            )

    def get_recent(self, limit: int = 50) -> list[Event]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM events WHERE namespace = %s
                   ORDER BY occurred_at DESC LIMIT %s""",
                (self.namespace, limit),
            )
            return [
                Event(
                    id=row["id"],
                    namespace=row["namespace"],
                    event_type=row["event_type"],
                    title=row["title"],
                    summary=row["summary"],
                    full_content=row["full_content"],
                    importance=row["importance"],
                    source_ref=row["source_ref"],
                    occurred_at=row["occurred_at"],
                    created_at=row["created_at"],
                )
                for row in cur.fetchall()
            ]

    # ── Tag Association ───────────────────────────────────

    def add_tags(self, event_id: int, tag_ids: list[int]) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                "INSERT IGNORE INTO event_tags (event_id, tag_id) VALUES (%s, %s)",
                [(event_id, tid) for tid in tag_ids],
            )

    def remove_tags(self, event_id: int, tag_ids: list[int]) -> None:
        with self.conn.cursor() as cur:
            cur.executemany(
                "DELETE FROM event_tags WHERE event_id = %s AND tag_id = %s",
                [(event_id, tid) for tid in tag_ids],
            )

    def get_tags(self, event_id: int) -> list[Tag]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT t.* FROM tags t
                   JOIN event_tags et ON t.id = et.tag_id
                   WHERE et.event_id = %s ORDER BY t.name""",
                (event_id,),
            )
            return [Tag(**row) for row in cur.fetchall()]
