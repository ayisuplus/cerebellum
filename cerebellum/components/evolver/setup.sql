CREATE DATABASE IF NOT EXISTS evolver_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE evolver_db;

CREATE TABLE IF NOT EXISTS memories (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    content     TEXT NOT NULL,
    category    VARCHAR(50),
    tags        JSON,
    embedding   BLOB,
    source      VARCHAR(100),
    importance  FLOAT DEFAULT 0.5,
    access_count INT DEFAULT 0,
    content_hash VARCHAR(32),
    lifecycle   VARCHAR(20) DEFAULT 'seed',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_memories_hash (content_hash),
    -- Embedder identity tag; rows written before tagging are NULL.
    -- Existing deployments: ALTER TABLE memories ADD COLUMN embedder VARCHAR(160) NULL;
    embedder    VARCHAR(160) NULL
);

CREATE TABLE IF NOT EXISTS graph_nodes (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    label       VARCHAR(200) NOT NULL,
    node_type   VARCHAR(50),
    properties  JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_label_type (label, node_type),
    INDEX idx_graph_nodes_label (label)
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_id   BIGINT NOT NULL,
    target_id   BIGINT NOT NULL,
    relation    VARCHAR(50) NOT NULL,
    weight      FLOAT DEFAULT 1.0,
    properties  JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES graph_nodes(id) ON DELETE CASCADE,
    UNIQUE KEY uk_edge (source_id, target_id, relation)
);

CREATE TABLE IF NOT EXISTS skills (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    file_path   VARCHAR(500),
    content     TEXT,
    version     INT DEFAULT 1,
    status      VARCHAR(20) DEFAULT 'draft',
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS interactions (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    task        TEXT NOT NULL,
    outcome     VARCHAR(20),
    context     TEXT,
    solution    TEXT,
    lessons     TEXT,
    memory_ids  JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evolution_log (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type  VARCHAR(50) NOT NULL,
    details     JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS vector_sync_outbox (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    memory_id   BIGINT NOT NULL,
    operation   VARCHAR(16) NOT NULL,
    attempts    INT NOT NULL DEFAULT 0,
    last_error  TEXT,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_vector_sync_memory (memory_id),
    INDEX idx_vector_sync_pending (id, attempts)
);

CREATE TABLE IF NOT EXISTS links (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    source_type   VARCHAR(50) NOT NULL,
    source_id     BIGINT NOT NULL,
    target_type   VARCHAR(50) NOT NULL,
    target_id     BIGINT NOT NULL,
    link_type     VARCHAR(50) NOT NULL,
    weight        FLOAT DEFAULT 1.0,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_links (source_type, source_id, target_type, target_id),
    INDEX idx_links_source (source_type, source_id),
    INDEX idx_links_target (target_type, target_id)
);

CREATE TABLE IF NOT EXISTS skill_evaluations (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    skill_id      BIGINT NOT NULL,
    version       INT NOT NULL,
    total_score   FLOAT,
    dim_scores    JSON,
    eval_mode     VARCHAR(20) DEFAULT 'auto',
    round         INT DEFAULT 1,
    status        VARCHAR(20) DEFAULT 'pass',
    diff_summary  TEXT,
    created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);

CREATE TABLE IF NOT EXISTS facts (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    fact        TEXT NOT NULL,
    tags        JSON,
    time        VARCHAR(50),
    session_id  VARCHAR(100),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_facts_time (time),
    INDEX idx_facts_session (session_id)
);

CREATE TABLE IF NOT EXISTS distill_runs (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    level       VARCHAR(20) NOT NULL,
    fingerprint VARCHAR(64) NOT NULL,
    output      TEXT,
    token_count INT DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_distill_lookup (level, created_at)
);
