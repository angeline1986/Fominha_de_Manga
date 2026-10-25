CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE SCHEMA IF NOT EXISTS fominha;
SET search_path TO fominha, public;

CREATE TABLE providers (
  provider_id uuid PRIMARY KEY,
  code text NOT NULL UNIQUE,
  display_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE works (
  work_id uuid PRIMARY KEY,
  provider_id uuid NOT NULL REFERENCES providers ON DELETE RESTRICT,
  external_key text NOT NULL,
  display_name text NOT NULL,
  catalog_status text NOT NULL CHECK (catalog_status IN ('ACTIVE','RETIRED','UNVERIFIED')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (provider_id, external_key), UNIQUE (work_id, provider_id)
);
CREATE TABLE work_path_aliases (
  alias_id uuid PRIMARY KEY, work_id uuid NOT NULL REFERENCES works ON DELETE RESTRICT,
  path text NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz,
  source text NOT NULL, CHECK (valid_to IS NULL OR valid_to > valid_from),
  EXCLUDE USING gist (path WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&)
);
CREATE TABLE chapters (
  chapter_id uuid PRIMARY KEY, work_id uuid NOT NULL REFERENCES works ON DELETE RESTRICT,
  chapter_key text NOT NULL, display_order integer, legacy_path text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (work_id, chapter_key), UNIQUE (chapter_id, work_id)
);
CREATE TABLE source_pages (
  source_page_id uuid PRIMARY KEY, chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  source_key text NOT NULL, original_filename text NOT NULL, display_order integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (chapter_id, source_key), UNIQUE (source_page_id, chapter_id)
);
CREATE TABLE source_page_aliases (
  alias_id uuid PRIMARY KEY, source_page_id uuid NOT NULL REFERENCES source_pages ON DELETE RESTRICT,
  alias text NOT NULL, valid_from timestamptz NOT NULL, valid_to timestamptz,
  source text NOT NULL, CHECK (valid_to IS NULL OR valid_to > valid_from),
  EXCLUDE USING gist (source_page_id WITH =, alias WITH =, tstzrange(valid_from, valid_to, '[)') WITH &&)
);
CREATE TABLE pipeline_stages (
  stage_id uuid PRIMARY KEY, stage_code text NOT NULL, contract_version text NOT NULL,
  display_name text NOT NULL, stage_class text NOT NULL,
  active boolean NOT NULL DEFAULT true, UNIQUE (stage_code, contract_version)
);
CREATE TABLE stage_runs (
  stage_run_id uuid PRIMARY KEY, stage_id uuid NOT NULL REFERENCES pipeline_stages ON DELETE RESTRICT,
  run_key text NOT NULL, request_fingerprint text NOT NULL,
  scope_type text NOT NULL CHECK (scope_type IN ('CHAPTER','PAGE','SEGMENT','BATCH')),
  status text NOT NULL CHECK (status IN ('CREATED','RUNNING','SUCCEEDED','FAILED','CANCELLED','INTERRUPTED')),
  started_at timestamptz, finished_at timestamptz, actor_id text,
  algorithm text, algorithm_version text, manifest_schema text,
  parameters_json jsonb NOT NULL DEFAULT '{}'::jsonb, error_code text,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (stage_id, run_key), UNIQUE (stage_run_id, stage_id),
  CHECK ((status IN ('CREATED','RUNNING') AND finished_at IS NULL) OR
         (status IN ('SUCCEEDED','FAILED','CANCELLED','INTERRUPTED') AND finished_at IS NOT NULL))
);
CREATE TABLE stage_run_scopes (
  stage_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  ordinal integer NOT NULL CHECK (ordinal >= 0), chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  source_page_id uuid, segment_id uuid,
  PRIMARY KEY (stage_run_id, ordinal),
  CHECK (num_nonnulls(source_page_id, segment_id) <= 1)
);
CREATE TABLE stage_run_events (
  event_id uuid PRIMARY KEY, stage_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  event_type text NOT NULL, occurred_at timestamptz NOT NULL DEFAULT now(),
  actor_id text, details_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX stage_run_events_run_time_idx ON stage_run_events(stage_run_id, occurred_at);
