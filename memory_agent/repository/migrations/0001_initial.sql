PRAGMA foreign_keys = ON;
PRAGMA journal_mode = DELETE;
PRAGMA synchronous = FULL;
PRAGMA secure_delete = ON;
PRAGMA trusted_schema = OFF;

CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE core_snapshots (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE branches (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE branch_contracts (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE policies (
    id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    policy_hash TEXT NOT NULL,
    activated_at TEXT NOT NULL
);

CREATE TABLE mount_policies (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies(id),
    scope TEXT NOT NULL,
    decision TEXT NOT NULL
);

CREATE TABLE payload_objects (
    id TEXT PRIMARY KEY,
    purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    key_handle TEXT,
    ciphertext_location TEXT,
    created_at TEXT NOT NULL,
    activated_at TEXT,
    destroyed_at TEXT
);

CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL,
    branch_id TEXT REFERENCES branches(id),
    source_kind TEXT NOT NULL,
    status TEXT NOT NULL,
    sensitivity TEXT NOT NULL,
    storage_class TEXT NOT NULL,
    inline_sanitized_text TEXT,
    payload_id TEXT REFERENCES payload_objects(id),
    sanitization_applied BOOLEAN NOT NULL,
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(id),
    created_at TEXT NOT NULL,
    CHECK (
        NOT (sensitivity = 'PERSONAL' AND storage_class = 'INLINE_NON_SENSITIVE')
    )
);

CREATE TABLE patches (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    base_revision INTEGER NOT NULL,
    status TEXT NOT NULL,
    patch_hash TEXT NOT NULL,
    proposed_at TEXT NOT NULL
);

CREATE INDEX ix_patches_patch_hash ON patches(patch_hash);

CREATE TABLE patch_operations (
    id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL REFERENCES patches(id),
    operation_type TEXT NOT NULL,
    target_id TEXT,
    semantic_key TEXT,
    domain TEXT,
    storage_class TEXT,
    inline_value TEXT,
    payload_id TEXT REFERENCES payload_objects(id),
    CHECK (
        NOT (domain = 'PERSONAL' AND storage_class = 'INLINE_NON_SENSITIVE')
    )
);

CREATE TABLE patch_evidence (
    patch_id TEXT NOT NULL REFERENCES patches(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    PRIMARY KEY (patch_id, evidence_id)
);

CREATE TABLE audits (
    id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL REFERENCES patches(id),
    decision TEXT NOT NULL,
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(id),
    audited_at TEXT NOT NULL
);

CREATE TABLE audit_evidence (
    audit_id TEXT NOT NULL REFERENCES audits(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    PRIMARY KEY (audit_id, evidence_id)
);

CREATE TABLE commits (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    revision INTEGER NOT NULL,
    patch_id TEXT NOT NULL UNIQUE REFERENCES patches(id),
    audit_id TEXT NOT NULL UNIQUE REFERENCES audits(id),
    committed_at TEXT NOT NULL,
    UNIQUE (branch_id, revision)
);

CREATE TABLE memory_records (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL,
    semantic_key TEXT NOT NULL,
    status TEXT NOT NULL,
    storage_class TEXT NOT NULL,
    inline_value TEXT,
    payload_id TEXT REFERENCES payload_objects(id),
    branch_id TEXT REFERENCES branches(id),
    created_by_commit_id TEXT NOT NULL REFERENCES commits(id),
    superseded_by_commit_id TEXT REFERENCES commits(id),
    created_at TEXT NOT NULL,
    CHECK (
        NOT (domain = 'PERSONAL' AND storage_class = 'INLINE_NON_SENSITIVE')
    )
);

CREATE UNIQUE INDEX ix_mem_records_active_operational 
ON memory_records(branch_id, semantic_key) 
WHERE status = 'ACTIVE' AND domain = 'OPERATIONAL';

CREATE UNIQUE INDEX ix_mem_records_active_personal 
ON memory_records(semantic_key) 
WHERE status = 'ACTIVE' AND domain = 'PERSONAL';

CREATE TABLE record_links (
    id TEXT PRIMARY KEY,
    source_record_id TEXT NOT NULL REFERENCES memory_records(id),
    target_record_id TEXT NOT NULL REFERENCES memory_records(id),
    relationship TEXT NOT NULL,
    created_by_commit_id TEXT NOT NULL REFERENCES commits(id)
);

CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(id),
    status TEXT NOT NULL,
    opened_by_commit_id TEXT NOT NULL REFERENCES commits(id),
    resolved_by_commit_id TEXT REFERENCES commits(id)
);

CREATE TABLE conflict_records (
    conflict_id TEXT NOT NULL REFERENCES conflicts(id),
    record_id TEXT NOT NULL REFERENCES memory_records(id),
    PRIMARY KEY (conflict_id, record_id)
);

CREATE TABLE access_leases (
    id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL REFERENCES policies(id),
    status TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);

CREATE TABLE purge_jobs (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    completed_at TEXT
);

CREATE TABLE purge_target_results (
    id TEXT PRIMARY KEY,
    job_id TEXT NOT NULL REFERENCES purge_jobs(id),
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    status TEXT NOT NULL
);

CREATE TABLE detection_events (
    id TEXT PRIMARY KEY,
    layer TEXT NOT NULL,
    outcome TEXT NOT NULL,
    event_time TEXT NOT NULL
);

CREATE TABLE test_runs (
    id TEXT PRIMARY KEY,
    suite_version TEXT NOT NULL,
    run_at TEXT NOT NULL
);
