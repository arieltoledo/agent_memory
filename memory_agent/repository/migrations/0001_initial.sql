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
    core_version INTEGER PRIMARY KEY,
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE branches (
    branch_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'ARCHIVED')),
    current_revision INTEGER NOT NULL DEFAULT 0 CHECK (current_revision >= 0),
    core_version INTEGER NOT NULL REFERENCES core_snapshots(core_version),
    created_at TEXT NOT NULL
);

CREATE TABLE branch_contracts (
    contract_id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(branch_id),
    version INTEGER NOT NULL,
    content_json TEXT NOT NULL CHECK (json_valid(content_json)),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(branch_id, version)
);

CREATE TABLE policies (
    policy_snapshot_id TEXT PRIMARY KEY,
    policy_version INTEGER NOT NULL UNIQUE,
    policy_hash TEXT NOT NULL UNIQUE,
    source_ref TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 0 CHECK (active IN (0, 1)),
    created_at TEXT NOT NULL
);

CREATE TABLE mount_policies (
    mount_policy_id TEXT PRIMARY KEY,
    version INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('GLOBAL_INTERACTION_PREFERENCE', 'BRANCH_ONLY', 'EXPLICIT_SCOPES', 'EXPLICIT_ONLY')),
    allowed_scopes_json TEXT NOT NULL CHECK (json_valid(allowed_scopes_json)),
    allow_sensitive_operational_mount INTEGER NOT NULL CHECK (allow_sensitive_operational_mount IN (0, 1)),
    policy_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE payload_objects (
    id TEXT PRIMARY KEY,
    purpose TEXT NOT NULL CHECK (purpose IN ('EVIDENCE', 'MEMORY_VALUE', 'PATCH_VALUE')),
    status TEXT NOT NULL CHECK (status IN ('STAGED', 'ACTIVE', 'PURGE_PENDING', 'DESTROYED', 'ABORTED')),
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE')),
    key_handle TEXT,
    ciphertext_location TEXT,
    created_at TEXT NOT NULL,
    activated_at TEXT,
    destroyed_at TEXT,
    CHECK (
        (status IN ('STAGED', 'ACTIVE', 'PURGE_PENDING') AND key_handle IS NOT NULL AND ciphertext_location IS NOT NULL) OR
        (status IN ('DESTROYED', 'ABORTED') AND key_handle IS NULL AND ciphertext_location IS NULL)
    )
);

CREATE TABLE evidence (
    id TEXT PRIMARY KEY,
    scope_type TEXT NOT NULL CHECK (scope_type IN ('BRANCH', 'PERSONAL', 'GLOBAL')),
    branch_id TEXT REFERENCES branches(branch_id),
    source_kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('STAGED', 'ACTIVE', 'ABORTED', 'PURGE_REVOKED', 'PURGED')),
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE', 'PROHIBITED')),
    storage_class TEXT NOT NULL CHECK (storage_class IN ('INLINE_NON_SENSITIVE', 'VAULT_REF')),
    inline_sanitized_text TEXT,
    payload_id TEXT REFERENCES payload_objects(id),
    sanitization_applied BOOLEAN NOT NULL,
    removed_categories_json TEXT CHECK (removed_categories_json IS NULL OR json_valid(removed_categories_json)),
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(policy_snapshot_id),
    created_at TEXT NOT NULL,
    purged_at TEXT,
    CHECK (
        (scope_type = 'BRANCH' AND branch_id IS NOT NULL) OR
        (scope_type != 'BRANCH')
    ),
    CHECK (
        (storage_class = 'INLINE_NON_SENSITIVE' AND inline_sanitized_text IS NOT NULL AND payload_id IS NULL) OR
        (storage_class = 'VAULT_REF' AND payload_id IS NOT NULL AND inline_sanitized_text IS NULL)
    ),
    CHECK (sensitivity != 'PROHIBITED'),
    CHECK (sensitivity != 'SENSITIVE' OR storage_class = 'VAULT_REF')
);

CREATE TABLE patches (
    id TEXT PRIMARY KEY,
    branch_id TEXT REFERENCES branches(branch_id),
    base_revision INTEGER NOT NULL CHECK (base_revision >= 0),
    core_version INTEGER NOT NULL REFERENCES core_snapshots(core_version),
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(policy_snapshot_id),
    status TEXT NOT NULL CHECK (status IN ('PROPOSED', 'VALIDATED', 'AUDIT_ACCEPTED', 'AUDIT_REJECTED', 'DEFERRED', 'STALE', 'COMMITTED', 'ABORTED')),
    patch_hash TEXT NOT NULL,
    generator_model_id TEXT NOT NULL,
    generator_prompt_version TEXT NOT NULL,
    proposed_at TEXT NOT NULL
);

CREATE INDEX ix_patches_patch_hash ON patches(patch_hash);

CREATE TABLE audits (
    id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL UNIQUE REFERENCES patches(id),
    patch_hash TEXT NOT NULL,
    branch_id TEXT REFERENCES branches(branch_id),
    base_revision INTEGER NOT NULL,
    core_version INTEGER NOT NULL REFERENCES core_snapshots(core_version),
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(policy_snapshot_id),
    evidence_binding TEXT NOT NULL,
    decision TEXT NOT NULL CHECK (decision IN ('ACCEPT', 'REJECT', 'DEFER')),
    reason_codes_json TEXT NOT NULL CHECK (json_valid(reason_codes_json)),
    auditor_model_id TEXT NOT NULL,
    auditor_prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE audit_evidence (
    audit_id TEXT NOT NULL REFERENCES audits(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    PRIMARY KEY (audit_id, evidence_id)
);

CREATE TABLE commits (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(branch_id),
    revision INTEGER NOT NULL CHECK (revision > 0),
    previous_commit_id TEXT REFERENCES commits(id),
    patch_id TEXT NOT NULL UNIQUE REFERENCES patches(id),
    patch_hash TEXT NOT NULL,
    audit_id TEXT NOT NULL UNIQUE REFERENCES audits(id),
    core_version INTEGER NOT NULL REFERENCES core_snapshots(core_version),
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(policy_snapshot_id),
    committed_at TEXT NOT NULL,
    UNIQUE (branch_id, revision)
);

CREATE TABLE memory_records (
    id TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (domain IN ('PERSONAL', 'OPERATIONAL')),
    branch_id TEXT REFERENCES branches(branch_id),
    semantic_key TEXT NOT NULL,
    kind TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'RETRACTED', 'PURGE_REVOKED', 'PURGED')),
    sensitivity TEXT NOT NULL CHECK (sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE', 'PROHIBITED')),
    storage_class TEXT NOT NULL CHECK (storage_class IN ('INLINE_NON_SENSITIVE', 'VAULT_REF', 'NONE')),
    inline_value_json TEXT CHECK (inline_value_json IS NULL OR json_valid(inline_value_json)),
    payload_id TEXT REFERENCES payload_objects(id),
    lifetime TEXT NOT NULL CHECK (lifetime IN ('TEMPORARY', 'DURABLE')),
    valid_until TEXT,
    timezone TEXT,
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(policy_snapshot_id),
    mount_policy_id TEXT REFERENCES mount_policies(mount_policy_id),
    created_by_commit_id TEXT NOT NULL REFERENCES commits(id),
    supersedes_record_id TEXT REFERENCES memory_records(id),
    created_at TEXT NOT NULL,
    purged_at TEXT,
    CHECK (sensitivity != 'PROHIBITED'),
    CHECK (sensitivity != 'SENSITIVE' OR storage_class = 'VAULT_REF'),
    CHECK (
        (domain = 'PERSONAL' AND storage_class = 'VAULT_REF') OR (domain != 'PERSONAL')
    ),
    CHECK (
        (storage_class = 'INLINE_NON_SENSITIVE' AND inline_value_json IS NOT NULL AND payload_id IS NULL) OR
        (storage_class = 'VAULT_REF' AND payload_id IS NOT NULL AND inline_value_json IS NULL) OR
        (storage_class = 'NONE' AND payload_id IS NULL AND inline_value_json IS NULL)
    ),
    CHECK (
        (status = 'PURGED' AND domain = 'PERSONAL' AND storage_class = 'VAULT_REF' AND inline_value_json IS NULL AND payload_id IS NOT NULL) OR (status != 'PURGED')
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
    relation_type TEXT NOT NULL,
    created_by_commit_id TEXT NOT NULL REFERENCES commits(id),
    UNIQUE(source_record_id, target_record_id, relation_type)
);

CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    branch_id TEXT NOT NULL REFERENCES branches(branch_id),
    semantic_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'RESOLVED')),
    opened_by_commit_id TEXT NOT NULL REFERENCES commits(id),
    resolved_by_commit_id TEXT REFERENCES commits(id),
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE TABLE conflict_records (
    conflict_id TEXT NOT NULL REFERENCES conflicts(id),
    record_id TEXT NOT NULL REFERENCES memory_records(id),
    role TEXT NOT NULL CHECK (role IN ('WINNER', 'LOSER', 'COMPETING')),
    PRIMARY KEY (conflict_id, record_id)
);

CREATE TABLE patch_operations (
    operation_id TEXT PRIMARY KEY,
    patch_id TEXT NOT NULL REFERENCES patches(id) ON DELETE CASCADE,
    op_index INTEGER NOT NULL,
    op_type TEXT NOT NULL CHECK (op_type IN ('ADD', 'SUPERSEDE', 'RETRACT', 'LINK', 'FLAG_CONFLICT', 'RESOLVE_CONFLICT', 'PURGE_REQUEST')),
    domain TEXT CHECK (domain IS NULL OR domain IN ('PERSONAL', 'OPERATIONAL')),
    semantic_key TEXT,
    sensitivity TEXT CHECK (sensitivity IS NULL OR sensitivity IN ('ORDINARY', 'PERSONAL', 'SENSITIVE')),
    target_record_id TEXT REFERENCES memory_records(id),
    value_storage_class TEXT CHECK (value_storage_class IS NULL OR value_storage_class IN ('INLINE_NON_SENSITIVE', 'VAULT_REF', 'NONE')),
    inline_value_json TEXT CHECK (inline_value_json IS NULL OR json_valid(inline_value_json)),
    payload_id TEXT REFERENCES payload_objects(id),
    relation_type TEXT,
    conflict_id TEXT REFERENCES conflicts(id),
    reason_code TEXT,
    UNIQUE(patch_id, op_index),
    CHECK (sensitivity != 'SENSITIVE' OR value_storage_class = 'VAULT_REF'),
    CHECK (
        (value_storage_class IS NULL AND inline_value_json IS NULL AND payload_id IS NULL) OR
        (value_storage_class = 'NONE' AND inline_value_json IS NULL AND payload_id IS NULL) OR
        (value_storage_class = 'INLINE_NON_SENSITIVE' AND inline_value_json IS NOT NULL AND payload_id IS NULL) OR
        (value_storage_class = 'VAULT_REF' AND payload_id IS NOT NULL AND inline_value_json IS NULL)
    )
);

CREATE TABLE patch_evidence (
    patch_id TEXT NOT NULL REFERENCES patches(id),
    evidence_id TEXT NOT NULL REFERENCES evidence(id),
    PRIMARY KEY (patch_id, evidence_id)
);

CREATE TABLE access_leases (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES memory_records(id),
    requested_scope TEXT NOT NULL,
    active_branch_id TEXT REFERENCES branches(branch_id),
    policy_snapshot_id TEXT NOT NULL REFERENCES policies(policy_snapshot_id),
    status TEXT NOT NULL CHECK (status IN ('VALID', 'REVOKED', 'EXPIRED')),
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE purge_jobs (
    id TEXT PRIMARY KEY,
    record_id TEXT NOT NULL REFERENCES memory_records(id),
    status TEXT NOT NULL CHECK (status IN ('PURGE_REQUESTED', 'PURGE_IN_PROGRESS', 'PURGE_COMPLETE', 'PURGE_FAILED')),
    requested_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    failure_code TEXT
);

CREATE TABLE purge_target_results (
    purge_id TEXT NOT NULL REFERENCES purge_jobs(id),
    target_id TEXT NOT NULL,
    purge_attempted INTEGER NOT NULL CHECK (purge_attempted IN (0, 1)),
    purge_succeeded INTEGER NOT NULL CHECK (purge_succeeded IN (0, 1)),
    verify_absent INTEGER NOT NULL CHECK (verify_absent IN (0, 1)),
    last_checked_at TEXT NOT NULL,
    failure_code TEXT,
    PRIMARY KEY (purge_id, target_id)
);

CREATE TABLE detection_events (
    id TEXT PRIMARY KEY,
    run_id TEXT,
    threat_type TEXT NOT NULL,
    expected_detection_layer TEXT,
    actual_detection_layer TEXT,
    security_outcome TEXT NOT NULL CHECK (security_outcome IN ('PASS', 'FAIL', 'NOT_APPLICABLE')),
    architectural_outcome TEXT NOT NULL CHECK (architectural_outcome IN ('PASS', 'DEGRADED', 'FAIL', 'UNDEFINED')),
    policy_bypass BOOLEAN NOT NULL,
    category TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE test_runs (
    id TEXT PRIMARY KEY,
    test_id TEXT NOT NULL,
    run_kind TEXT NOT NULL,
    spec_version TEXT NOT NULL,
    technical_design_version TEXT NOT NULL,
    git_commit TEXT NOT NULL,
    policy_snapshot_id TEXT REFERENCES policies(policy_snapshot_id),
    analyzer_model_id TEXT,
    generator_model_id TEXT,
    auditor_model_id TEXT,
    analyzer_prompt_version TEXT,
    generator_prompt_version TEXT,
    auditor_prompt_version TEXT,
    temperature REAL,
    seed INTEGER,
    result TEXT NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    started_at TEXT NOT NULL,
    ended_at TEXT
);
