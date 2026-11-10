-- IncomeVerify schema. Extracted data, checks and signals are JSONB on the row that owns them;
-- what gets filtered or sorted on (status, verdict, income, FOIR, dates) is a real column.

CREATE TABLE IF NOT EXISTS applications (
    id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    applicant_name           text NOT NULL,
    declared_employer        text NOT NULL DEFAULT '',
    declared_monthly_income  numeric(14, 2),
    status                   text NOT NULL DEFAULT 'draft'
                             CHECK (status IN ('draft', 'processing', 'verified', 'needs_review', 'flagged', 'approved', 'failed')),
    authenticity_score       int,
    verified_monthly_income  numeric(14, 2),
    foir                     numeric(8, 4),
    metrics                  jsonb NOT NULL DEFAULT '{}',
    salary_matches           jsonb NOT NULL DEFAULT '[]',
    cross_checks             jsonb NOT NULL DEFAULT '[]',
    signals                  jsonb NOT NULL DEFAULT '[]',
    reasons                  jsonb NOT NULL DEFAULT '[]',
    summary                  text NOT NULL DEFAULT '',
    summary_by               text NOT NULL DEFAULT '',
    progress                 jsonb NOT NULL DEFAULT '{}',
    usage                    jsonb NOT NULL DEFAULT '{}',
    is_sample                boolean NOT NULL DEFAULT false,
    error                    text NOT NULL DEFAULT '',
    approved_at              timestamptz,
    analyzed_at              timestamptz,
    created_at               timestamptz NOT NULL DEFAULT now(),
    updated_at               timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS applications_created_idx ON applications (created_at DESC);
CREATE INDEX IF NOT EXISTS applications_status_idx ON applications (status);

CREATE TABLE IF NOT EXISTS documents (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id     uuid NOT NULL REFERENCES applications (id) ON DELETE CASCADE,
    filename           text NOT NULL,
    storage_key        text NOT NULL,
    mime               text NOT NULL,
    size_bytes         int NOT NULL,
    status             text NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'processing', 'completed', 'failed')),
    doc_type           text NOT NULL DEFAULT 'unknown',
    classified_by      text NOT NULL DEFAULT '',
    pages              int NOT NULL DEFAULT 0,
    low_quality_pages  jsonb NOT NULL DEFAULT '[]',
    raw                jsonb NOT NULL DEFAULT '{}',
    fields             jsonb NOT NULL DEFAULT '{}',
    checks             jsonb NOT NULL DEFAULT '[]',
    signals            jsonb NOT NULL DEFAULT '[]',
    confidence         jsonb NOT NULL DEFAULT '{"fields": {}, "low": []}',
    reread             jsonb,
    progress           jsonb NOT NULL DEFAULT '{}',
    usage              jsonb NOT NULL DEFAULT '{}',
    error              text NOT NULL DEFAULT '',
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS documents_application_idx ON documents (application_id);
CREATE INDEX IF NOT EXISTS documents_created_idx ON documents (created_at);

-- Every human correction, so it can be audited and later turned into a golden-set case.
CREATE TABLE IF NOT EXISTS field_edits (
    id           bigserial PRIMARY KEY,
    document_id  uuid NOT NULL REFERENCES documents (id) ON DELETE CASCADE,
    field_path   text NOT NULL,
    old_value    jsonb,
    new_value    jsonb,
    edited_by    text NOT NULL DEFAULT 'reviewer',
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS field_edits_document_idx ON field_edits (document_id);

-- One row per task run: what it cost and how long it took.
CREATE TABLE IF NOT EXISTS usage_log (
    id                 bigserial PRIMARY KEY,
    ref_kind           text NOT NULL,
    ref_id             uuid NOT NULL,
    task               text NOT NULL,
    status             text NOT NULL,
    calls              int NOT NULL DEFAULT 0,
    prompt_tokens      int NOT NULL DEFAULT 0,
    completion_tokens  int NOT NULL DEFAULT 0,
    ocr_pages          int NOT NULL DEFAULT 0,
    cost_usd           numeric(12, 6) NOT NULL DEFAULT 0,
    duration_s         numeric(10, 1) NOT NULL DEFAULT 0,
    by_model           jsonb NOT NULL DEFAULT '{}',
    error              text NOT NULL DEFAULT '',
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS usage_log_created_idx ON usage_log (created_at DESC);
