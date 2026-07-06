"""Tag Manager — hierarchical tag CRUD with deduplication."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pymysql


@dataclass
class Tag:
    id: int | None = None
    name: str = ""
    parent_id: int | None = None
    namespace: str = "default"
    level: str = "misc"
    description: str | None = None

    # populated on demand
    children: list[Tag] = field(default_factory=list)
    path: str = ""  # "角色/宋怀真/武器"


class TagManager:
    """Manages hierarchical tags with auto-dedup and path-based lookup."""

    def __init__(self, conn: pymysql.Connection, namespace: str = "default"):
        self.conn = conn
        self.namespace = namespace

    # ── CRUD ──────────────────────────────────────────────

    def get_or_create(
        self,
        name: str,
        parent_id: int | None = None,
        level: str = "misc",
        description: str | None = None,
    ) -> Tag:
        """Get existing tag or create a new one. Idempotent."""
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, parent_id, namespace, level, description
                   FROM tags
                   WHERE namespace = %s AND name = %s
                   AND (parent_id = %s OR (parent_id IS NULL AND %s IS NULL))""",
                (self.namespace, name, parent_id, parent_id),
            )
            row = cur.fetchone()
            if row:
                return Tag(**row)

            cur.execute(
                """INSERT INTO tags (name, parent_id, namespace, level, description)
                   VALUES (%s, %s, %s, %s, %s)""",
                (name, parent_id, self.namespace, level, description),
            )
            return Tag(
                id=cur.lastrowid,
                name=name,
                parent_id=parent_id,
                namespace=self.namespace,
                level=level,
                description=description,
            )

    def get_by_id(self, tag_id: int) -> Tag | None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, parent_id, namespace, level, description FROM tags WHERE id = %s",
                (tag_id,),
            )
            row = cur.fetchone()
            return Tag(**row) if row else None

    def get_by_path(self, path: str) -> Tag | None:
        """Resolve '角色/宋怀真/武器' to a tag (must exist)."""
        parts = [p.strip() for p in path.split("/") if p.strip()]
        if not parts:
            return None

        parent_id: int | None = None
        tag = None
        for part in parts:
            with self.conn.cursor() as cur:
                cur.execute(
                    """SELECT id, name, parent_id, namespace, level, description
                       FROM tags
                       WHERE namespace = %s AND name = %s
                       AND (parent_id = %s OR (parent_id IS NULL AND %s IS NULL))""",
                    (self.namespace, part, parent_id, parent_id),
                )
                row = cur.fetchone()
                if not row:
                    return None
                tag = Tag(**row)
                parent_id = tag.id
        return tag

    def ensure_path(self, path: str, level: str = "misc") -> Tag:
        """Create all missing tags along a path. Returns the leaf tag."""
        parts = [p.strip() for p in path.split("/") if p.strip()]
        if not parts:
            raise ValueError("Path must not be empty")

        parent_id: int | None = None
        tag = None
        for part in parts:
            tag = self.get_or_create(name=part, parent_id=parent_id, level=level)
            parent_id = tag.id
        return tag  # type: ignore[return-value]

    # ── Query ─────────────────────────────────────────────

    def get_children(self, parent_id: int | None = None) -> list[Tag]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, parent_id, namespace, level, description
                   FROM tags WHERE namespace = %s
                   AND (parent_id = %s OR (parent_id IS NULL AND %s IS NULL))
                   ORDER BY name""",
                (self.namespace, parent_id, parent_id),
            )
            return [Tag(**row) for row in cur.fetchall()]

    def search(self, keyword: str, limit: int = 20) -> list[Tag]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT id, name, parent_id, namespace, level, description
                   FROM tags WHERE namespace = %s AND name LIKE %s
                   ORDER BY name LIMIT %s""",
                (self.namespace, f"%{keyword}%", limit),
            )
            return [Tag(**row) for row in cur.fetchall()]

    def get_tree(self, parent_id: int | None = None) -> list[Tag]:
        """Recursively build the full tag tree."""
        children = self.get_children(parent_id)
        for child in children:
            child.children = self.get_tree(child.id)
            child.path = self._build_path(child)
        return children

    def _build_path(self, tag: Tag) -> str:
        parts = [tag.name]
        current_id = tag.parent_id
        while current_id is not None:
            parent = self.get_by_id(current_id)
            if parent is None:
                break
            parts.insert(0, parent.name)
            current_id = parent.parent_id
        return "/".join(parts)

    # ── Bulk ──────────────────────────────────────────────

    def get_by_ids(self, ids: list[int]) -> list[Tag]:
        if not ids:
            return []
        placeholders = ",".join(["%s"] * len(ids))
        with self.conn.cursor() as cur:
            cur.execute(
                f"""SELECT id, name, parent_id, namespace, level, description
                    FROM tags WHERE id IN ({placeholders})""",
                ids,
            )
            return [Tag(**row) for row in cur.fetchall()]
