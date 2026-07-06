"""
Tag-based Memory System — MySQL Schema.

Architecture:
  tags        — hierarchical tags (entity / place / event / attribute)
  events      — discrete memory events with summaries
  event_tags  — many-to-many bridge

AI retrieval flow:
  intent → LLM extracts tags → SQL query by tags → AI filters by summary → fetch events
"""

SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS tags (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL COMMENT '标签名，如 宋怀真 / 突破 / 青云宗',
    parent_id   INT          NULL     COMMENT '上级标签，根节点为 NULL',
    namespace   VARCHAR(50)  NOT NULL DEFAULT 'default' COMMENT '命名空间，用于多项目隔离',
    level       ENUM('category','entity','attribute','action','place','item','misc')
                               NOT NULL DEFAULT 'misc',
    description VARCHAR(500)  NULL     COMMENT '标签说明，供 LLM 理解',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_id) REFERENCES tags(id) ON DELETE CASCADE,
    UNIQUE INDEX uq_tag (namespace, name, parent_id),
    INDEX idx_namespace (namespace),
    INDEX idx_parent   (parent_id),
    INDEX idx_level    (level)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='层级标签';


CREATE TABLE IF NOT EXISTS events (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    namespace       VARCHAR(50)  NOT NULL DEFAULT 'default',
    event_type      ENUM('action','dialogue','thought','plot','world','relation',
                         'item','hook','milestone','misc')
                                 NOT NULL DEFAULT 'misc',
    title           VARCHAR(200) NOT NULL COMMENT '事件标题',
    summary         TEXT         NOT NULL COMMENT '事件摘要，供 AI 相关性判断',
    full_content    MEDIUMTEXT   NULL     COMMENT '完整事件描述',
    importance      TINYINT      NOT NULL DEFAULT 5 COMMENT '1-10 重要性',
    source_ref      VARCHAR(500) NULL     COMMENT '来源引用，如 chapter-3/para-12',
    occurred_at     DATETIME     NOT NULL COMMENT '事件发生时间',
    created_at      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_namespace   (namespace),
    INDEX idx_type        (event_type),
    INDEX idx_occurred    (occurred_at),
    INDEX idx_importance  (importance),
    FULLTEXT INDEX ft_summary (summary)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='记忆事件';


CREATE TABLE IF NOT EXISTS event_tags (
    event_id    INT NOT NULL,
    tag_id      INT NOT NULL,

    PRIMARY KEY (event_id, tag_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id)   REFERENCES tags(id)   ON DELETE CASCADE,
    INDEX idx_tag_event (tag_id, event_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='事件-标签关联';
"""
