-- The opt-in adapter has no trusted SQL writer API yet. Keep the runtime role
-- read-only until validation, approval and publication functions are designed.
REVOKE INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER
  ON ALL TABLES IN SCHEMA fominha FROM fominha_app;
REVOKE UPDATE(status,started_at,finished_at,error_code)
  ON fominha.stage_runs FROM fominha_app;
REVOKE UPDATE(status,closed_at) ON fominha.approval_batches FROM fominha_app;
REVOKE UPDATE(approval_decision_id,revision,updated_at)
  ON fominha.current_approval_decisions FROM fominha_app;
REVOKE UPDATE(status,committed_at,reason) ON fominha.publications FROM fominha_app;
REVOKE UPDATE(artifact_version_id,publication_id,revision,updated_at)
  ON fominha.active_artifacts FROM fominha_app;
REVOKE UPDATE(status,attempt_count,last_error,processed_at)
  ON fominha.invalidation_outbox FROM fominha_app;
REVOKE UPDATE(status,finished_at) ON fominha.legacy_import_batches FROM fominha_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA fominha
  REVOKE INSERT ON TABLES FROM fominha_app;
