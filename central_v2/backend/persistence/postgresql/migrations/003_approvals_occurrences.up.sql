SET search_path TO fominha, public;
ALTER TABLE stage_run_scopes
  ADD CONSTRAINT stage_scope_page_fk FOREIGN KEY(source_page_id,chapter_id)
  REFERENCES source_pages(source_page_id,chapter_id) ON DELETE RESTRICT;
ALTER TABLE stage_run_scopes
  ADD CONSTRAINT stage_scope_segment_fk FOREIGN KEY(segment_id,chapter_id)
  REFERENCES derived_segments(segment_id,chapter_id) ON DELETE RESTRICT;
ALTER TABLE artifact_slots
  ADD CONSTRAINT artifact_slot_page_fk FOREIGN KEY(source_page_id,chapter_id)
  REFERENCES source_pages(source_page_id,chapter_id) ON DELETE RESTRICT;
ALTER TABLE artifact_slots
  ADD CONSTRAINT artifact_slot_segment_fk FOREIGN KEY(segment_id,chapter_id)
  REFERENCES derived_segments(segment_id,chapter_id) ON DELETE RESTRICT;
CREATE TABLE segment_source_ranges (
  segment_version_id uuid NOT NULL REFERENCES derived_segment_versions ON DELETE RESTRICT,
  ordinal integer NOT NULL CHECK (ordinal >= 0), source_page_id uuid NOT NULL REFERENCES source_pages ON DELETE RESTRICT,
  source_artifact_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  start_offset jsonb NOT NULL, end_offset jsonb NOT NULL, coordinate_space text NOT NULL,
  details_json jsonb NOT NULL DEFAULT '{}'::jsonb, PRIMARY KEY(segment_version_id,ordinal)
);
CREATE TABLE occurrences (
  occurrence_id uuid PRIMARY KEY, source_page_id uuid NOT NULL REFERENCES source_pages ON DELETE RESTRICT,
  first_seen_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  source_occurrence_key text, created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (occurrence_id,source_page_id)
);
CREATE TABLE occurrence_revisions (
  occurrence_revision_id uuid PRIMARY KEY, occurrence_id uuid NOT NULL REFERENCES occurrences ON DELETE RESTRICT,
  revision_no integer NOT NULL CHECK (revision_no > 0), evidence_artifact_version_id uuid REFERENCES artifact_versions ON DELETE RESTRICT,
  reviewed_image_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  source_occurrence_key text, type_code text NOT NULL, origin text NOT NULL, candidate boolean NOT NULL DEFAULT false,
  roi_x double precision NOT NULL, roi_y double precision NOT NULL,
  roi_width double precision NOT NULL CHECK(roi_width > 0), roi_height double precision NOT NULL CHECK(roi_height > 0),
  policy_version text NOT NULL, classification_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (occurrence_id,revision_no), UNIQUE (occurrence_revision_id,occurrence_id),
  CHECK (roi_x >= 0 AND roi_y >= 0 AND roi_x + roi_width <= 1 AND roi_y + roi_height <= 1)
);
CREATE TABLE approval_batches (
  approval_batch_id uuid PRIMARY KEY, chapter_id uuid NOT NULL REFERENCES chapters ON DELETE RESTRICT,
  check_run_id uuid NOT NULL REFERENCES stage_runs ON DELETE RESTRICT,
  source_snapshot_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  status text NOT NULL CHECK(status IN ('OPEN','CLOSED','CANCELLED')),
  created_at timestamptz NOT NULL DEFAULT now(), closed_at timestamptz,
  UNIQUE (approval_batch_id,chapter_id)
);
CREATE TABLE approval_subjects (
  approval_subject_id uuid PRIMARY KEY, approval_batch_id uuid NOT NULL REFERENCES approval_batches ON DELETE RESTRICT,
  occurrence_revision_id uuid NOT NULL REFERENCES occurrence_revisions ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(approval_batch_id,occurrence_revision_id),
  UNIQUE(approval_subject_id,approval_batch_id)
);
CREATE TABLE approval_decisions (
  approval_decision_id uuid PRIMARY KEY, approval_subject_id uuid NOT NULL REFERENCES approval_subjects ON DELETE RESTRICT,
  decision_seq integer NOT NULL CHECK(decision_seq > 0), supersedes_decision_id uuid,
  decision text NOT NULL CHECK(decision IN ('APPROVE','REJECT','EDIT','REVOKE')),
  actor_id text, decided_at timestamptz NOT NULL DEFAULT now(), reason text NOT NULL,
  reviewed_image_version_id uuid NOT NULL REFERENCES artifact_versions ON DELETE RESTRICT,
  policy_version text NOT NULL, source_snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(approval_subject_id,decision_seq), UNIQUE(approval_subject_id,approval_decision_id),
  FOREIGN KEY(approval_subject_id,supersedes_decision_id)
    REFERENCES approval_decisions(approval_subject_id,approval_decision_id) ON DELETE RESTRICT
);
CREATE TABLE current_approval_decisions (
  approval_subject_id uuid PRIMARY KEY REFERENCES approval_subjects ON DELETE RESTRICT,
  approval_decision_id uuid NOT NULL, revision bigint NOT NULL CHECK(revision > 0),
  updated_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY(approval_subject_id,approval_decision_id)
    REFERENCES approval_decisions(approval_subject_id,approval_decision_id) ON DELETE RESTRICT
);
ALTER TABLE approval_dependencies ADD CONSTRAINT approval_dependency_decision_fk
  FOREIGN KEY(approval_subject_id,required_decision_id)
  REFERENCES approval_decisions(approval_subject_id,approval_decision_id) ON DELETE RESTRICT;
ALTER TABLE invalidation_outbox ADD CONSTRAINT invalidation_approval_subject_fk
  FOREIGN KEY(approval_subject_id) REFERENCES approval_subjects ON DELETE RESTRICT;
ALTER TABLE invalidation_outbox ADD CONSTRAINT invalidation_approval_decision_fk
  FOREIGN KEY(approval_subject_id,approval_decision_id)
  REFERENCES approval_decisions(approval_subject_id,approval_decision_id) ON DELETE RESTRICT;
ALTER TABLE invalidation_outbox ADD CONSTRAINT invalidation_previous_approval_fk
  FOREIGN KEY(approval_subject_id,previous_approval_decision_id)
  REFERENCES approval_decisions(approval_subject_id,approval_decision_id) ON DELETE RESTRICT;
ALTER TABLE invalidation_outbox ADD CONSTRAINT invalidation_source_version_fk
  FOREIGN KEY(source_slot_id,source_version_id)
  REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT;
ALTER TABLE invalidation_outbox ADD CONSTRAINT invalidation_previous_version_fk
  FOREIGN KEY(source_slot_id,previous_version_id)
  REFERENCES artifact_versions(artifact_slot_id,artifact_version_id) ON DELETE RESTRICT;
