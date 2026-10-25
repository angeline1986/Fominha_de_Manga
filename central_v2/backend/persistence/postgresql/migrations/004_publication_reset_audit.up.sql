SET search_path TO fominha, public;
CREATE TABLE publications (
  publication_id uuid PRIMARY KEY, chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  stage_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  publication_type text NOT NULL DEFAULT 'PUBLISH' CHECK(publication_type IN ('PUBLISH','RESET')),
  status text NOT NULL CHECK(status IN ('STAGED','COMMITTED','CONFLICT','ABORTED')),
  expected_active_revision bigint NOT NULL CHECK(expected_active_revision >= 0),
  idempotency_key text NOT NULL, request_fingerprint char(64) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), committed_at timestamptz,
  actor_id text, reason text, manifest_version_id uuid REFERENCES artifact_versions ON DELETE RESTRICT,
  UNIQUE(chapter_id,idempotency_key), UNIQUE(publication_id,chapter_id)
);
CREATE TABLE publication_items (
  publication_id uuid NOT NULL, chapter_id uuid NOT NULL, artifact_slot_id uuid NOT NULL,
  artifact_version_id uuid NOT NULL, previous_version_id uuid,
  expected_active_revision bigint NOT NULL CHECK(expected_active_revision >= 0),
  published_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY(publication_id,artifact_slot_id),
  UNIQUE(publication_id,artifact_slot_id,artifact_version_id),
  FOREIGN KEY(publication_id,chapter_id) REFERENCES publications(publication_id,chapter_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,chapter_id) REFERENCES artifact_slots(artifact_slot_id,chapter_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,artifact_version_id)
    REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,previous_version_id)
    REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT
);
CREATE TABLE active_artifacts (
  artifact_slot_id uuid PRIMARY KEY, artifact_version_id uuid NOT NULL,
  publication_id uuid NOT NULL, revision bigint NOT NULL CHECK(revision > 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY(artifact_slot_id,artifact_version_id)
    REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT,
  FOREIGN KEY(publication_id,artifact_slot_id,artifact_version_id)
    REFERENCES publication_items(publication_id,artifact_slot_id,artifact_version_id) ON DELETE RESTRICT
);
CREATE TABLE reset_events (
  reset_event_id uuid PRIMARY KEY, chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  source_page_id uuid, segment_id uuid,
  reset_type text NOT NULL, actor_id text, reason text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
  source_version_id uuid REFERENCES artifact_versions ON DELETE RESTRICT,
  target_version_id uuid REFERENCES artifact_versions ON DELETE RESTRICT,
  approval_batch_id uuid REFERENCES approval_batches ON DELETE RESTRICT,
  publication_id uuid REFERENCES publications ON DELETE RESTRICT,
  idempotency_key text NOT NULL, UNIQUE(chapter_id,idempotency_key),
  UNIQUE(reset_event_id,chapter_id),
  CHECK(num_nonnulls(source_page_id,segment_id) <= 1)
);
CREATE TABLE reset_items (
  reset_event_id uuid NOT NULL, chapter_id uuid NOT NULL, artifact_slot_id uuid NOT NULL,
  from_version_id uuid NOT NULL, to_version_id uuid NOT NULL, backup_version_id uuid,
  invalidated_run_id uuid REFERENCES stage_runs ON DELETE RESTRICT,
  ordinal integer NOT NULL DEFAULT 0 CHECK(ordinal >= 0), PRIMARY KEY(reset_event_id,artifact_slot_id,ordinal),
  FOREIGN KEY(reset_event_id,chapter_id) REFERENCES reset_events(reset_event_id,chapter_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,chapter_id) REFERENCES artifact_slots(artifact_slot_id,chapter_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,from_version_id) REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,to_version_id) REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT,
  FOREIGN KEY(artifact_slot_id,backup_version_id) REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT
);
CREATE TABLE audit_events (
  audit_event_id uuid PRIMARY KEY, aggregate_type text NOT NULL, aggregate_id uuid NOT NULL,
  event_type text NOT NULL, actor_id text, occurred_at timestamptz NOT NULL DEFAULT now(),
  correlation_id uuid, payload_json jsonb NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX audit_aggregate_time_idx ON audit_events(aggregate_type,aggregate_id,occurred_at);
CREATE TABLE legacy_import_batches (
  import_batch_id uuid PRIMARY KEY, source_root_id text NOT NULL, fingerprint char(64) NOT NULL,
  importer_version text NOT NULL, status text NOT NULL CHECK(status IN ('RUNNING','COMPLETED','PARTIAL','FAILED')),
  started_at timestamptz NOT NULL DEFAULT now(), finished_at timestamptz,
  report_object_id uuid REFERENCES artifact_objects ON DELETE RESTRICT,
  UNIQUE(source_root_id,fingerprint)
);
CREATE TABLE legacy_import_items (
  import_item_id uuid PRIMARY KEY, import_batch_id uuid NOT NULL REFERENCES legacy_import_batches ON DELETE RESTRICT,
  legacy_path text NOT NULL, legacy_sha256 char(64), contract_code text NOT NULL,
  classification text NOT NULL CHECK(classification IN ('VERIFIED','LEGACY_UNVERIFIED','IGNORED_BY_SCOPE','CONFLICT')),
  artifact_version_id uuid REFERENCES artifact_versions ON DELETE RESTRICT,
  issue_code text, details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(import_batch_id,legacy_path,legacy_sha256)
);
