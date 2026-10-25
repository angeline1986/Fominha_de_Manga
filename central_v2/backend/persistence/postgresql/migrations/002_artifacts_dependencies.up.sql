SET search_path TO fominha, public;
CREATE TABLE derived_segments (
  segment_id uuid PRIMARY KEY, chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  segment_key text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(), retired_at timestamptz,
  UNIQUE (chapter_id, segment_key), UNIQUE (segment_id, chapter_id)
);
CREATE TABLE derived_segment_versions (
  segment_version_id uuid PRIMARY KEY, segment_id uuid NOT NULL REFERENCES derived_segments ON DELETE RESTRICT,
  stage_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  version_no integer NOT NULL CHECK (version_no > 0), created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (segment_id, version_no), UNIQUE (segment_version_id, segment_id)
);
CREATE TABLE artifact_objects (
  object_id uuid PRIMARY KEY, sha256 char(64) NOT NULL UNIQUE CHECK (sha256 ~ '^[0-9a-f]{64}$'),
  byte_size bigint NOT NULL CHECK (byte_size >= 0), media_type text NOT NULL,
  storage_key text NOT NULL UNIQUE, created_at timestamptz NOT NULL DEFAULT now(), verified_at timestamptz
);
CREATE TABLE artifact_slots (
  artifact_slot_id uuid PRIMARY KEY, chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  subject_type text NOT NULL CHECK (subject_type IN ('CHAPTER','SOURCE_PAGE','DERIVED_SEGMENT')),
  source_page_id uuid, segment_id uuid, stage_id uuid NOT NULL REFERENCES pipeline_stages ON DELETE RESTRICT,
  role text NOT NULL, context_key text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (artifact_slot_id, chapter_id), UNIQUE (artifact_slot_id, stage_id),
  CHECK ((subject_type='CHAPTER' AND source_page_id IS NULL AND segment_id IS NULL) OR
         (subject_type='SOURCE_PAGE' AND source_page_id IS NOT NULL AND segment_id IS NULL) OR
         (subject_type='DERIVED_SEGMENT' AND segment_id IS NOT NULL AND source_page_id IS NULL))
);
CREATE UNIQUE INDEX artifact_slot_chapter_uq ON artifact_slots(chapter_id,stage_id,role,context_key) WHERE subject_type='CHAPTER';
CREATE UNIQUE INDEX artifact_slot_page_uq ON artifact_slots(source_page_id,stage_id,role,context_key) WHERE subject_type='SOURCE_PAGE';
CREATE UNIQUE INDEX artifact_slot_segment_uq ON artifact_slots(segment_id,stage_id,role,context_key) WHERE subject_type='DERIVED_SEGMENT';
CREATE TABLE artifact_versions (
  artifact_version_id uuid PRIMARY KEY, artifact_slot_id uuid NOT NULL,
  stage_id uuid NOT NULL, stage_run_id uuid, object_id uuid NOT NULL REFERENCES artifact_objects ON DELETE RESTRICT,
  version_no integer NOT NULL CHECK (version_no > 0), created_at timestamptz NOT NULL DEFAULT now(),
  source_legacy_path text, manifest_fields_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (artifact_slot_id,version_no), UNIQUE (artifact_slot_id,artifact_version_id),
  UNIQUE (stage_run_id,artifact_version_id),
  FOREIGN KEY (artifact_slot_id,stage_id) REFERENCES artifact_slots(artifact_slot_id,stage_id) ON DELETE RESTRICT,
  FOREIGN KEY (stage_run_id,stage_id) REFERENCES stage_runs(stage_run_id,stage_id) ON DELETE RESTRICT
);
CREATE TABLE stage_run_artifacts (
  stage_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  scope_ordinal integer NOT NULL, artifact_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  direction text NOT NULL CHECK (direction IN ('INPUT','OUTPUT','EVIDENCE')),
  artifact_role text NOT NULL, ordinal integer NOT NULL DEFAULT 0 CHECK (ordinal >= 0),
  PRIMARY KEY (stage_run_id,artifact_version_id,direction,ordinal),
  FOREIGN KEY (stage_run_id,scope_ordinal) REFERENCES stage_run_scopes(stage_run_id,ordinal) ON DELETE RESTRICT
);
CREATE TABLE artifact_dependencies (
  consumer_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  input_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  dependency_role text NOT NULL, required boolean NOT NULL DEFAULT true,
  observed_sha256 char(64) NOT NULL CHECK (observed_sha256 ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (consumer_version_id,input_version_id,dependency_role),
  CHECK (consumer_version_id <> input_version_id)
);
CREATE INDEX artifact_dependencies_input_idx ON artifact_dependencies(input_version_id);
CREATE TABLE approval_dependencies (
  consumer_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  approval_subject_id uuid NOT NULL, required_decision_id uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(consumer_version_id,approval_subject_id)
);
CREATE INDEX approval_dependencies_subject_idx ON approval_dependencies(approval_subject_id);
CREATE TABLE artifact_validations (
  validation_id uuid PRIMARY KEY, artifact_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  validation_type text NOT NULL, status text NOT NULL CHECK (status IN ('PASS','FAIL','NOT_APPLICABLE','UNVERIFIED')),
  validator_version text NOT NULL, expected_sha256 char(64), observed_sha256 char(64),
  details_json jsonb NOT NULL DEFAULT '{}'::jsonb, checked_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE artifact_state_events (
  state_event_id uuid PRIMARY KEY, artifact_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  sequence_no bigint NOT NULL CHECK (sequence_no > 0), state text NOT NULL CHECK (state IN ('STAGED','VALID','STALE','INVALID','QUARANTINED')),
  cause_event_id uuid, created_at timestamptz NOT NULL DEFAULT now(), details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE (artifact_version_id,sequence_no)
);
CREATE TABLE invalidation_outbox (
  event_id uuid PRIMARY KEY, cause_type text NOT NULL CHECK (cause_type IN ('ARTIFACT_POINTER','APPROVAL_DECISION')),
  source_slot_id uuid, source_version_id uuid, approval_subject_id uuid, approval_decision_id uuid,
  previous_version_id uuid, previous_approval_decision_id uuid,
  new_revision bigint NOT NULL, status text NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING','PROCESSING','DONE','FAILED')),
  attempt_count integer NOT NULL DEFAULT 0 CHECK (attempt_count >= 0), last_error text,
  created_at timestamptz NOT NULL DEFAULT now(), processed_at timestamptz,
  CHECK ((cause_type='ARTIFACT_POINTER' AND source_slot_id IS NOT NULL AND source_version_id IS NOT NULL
          AND approval_subject_id IS NULL AND approval_decision_id IS NULL AND previous_approval_decision_id IS NULL) OR
         (cause_type='APPROVAL_DECISION' AND approval_subject_id IS NOT NULL AND approval_decision_id IS NOT NULL
          AND source_slot_id IS NULL AND source_version_id IS NULL AND previous_version_id IS NULL))
);
CREATE UNIQUE INDEX invalidation_artifact_revision_uq ON invalidation_outbox(source_slot_id,new_revision)
  WHERE cause_type='ARTIFACT_POINTER';
CREATE UNIQUE INDEX invalidation_approval_revision_uq ON invalidation_outbox(approval_subject_id,new_revision)
  WHERE cause_type='APPROVAL_DECISION';
