GRANT INSERT ON ALL TABLES IN SCHEMA fominha TO fominha_app;
GRANT UPDATE(status,started_at,finished_at,error_code)
  ON fominha.stage_runs TO fominha_app;
GRANT UPDATE(status,closed_at) ON fominha.approval_batches TO fominha_app;
GRANT UPDATE(approval_decision_id,revision,updated_at)
  ON fominha.current_approval_decisions TO fominha_app;
GRANT UPDATE(status,committed_at,reason) ON fominha.publications TO fominha_app;
GRANT UPDATE(artifact_version_id,publication_id,revision,updated_at)
  ON fominha.active_artifacts TO fominha_app;
GRANT UPDATE(status,attempt_count,last_error,processed_at)
  ON fominha.invalidation_outbox TO fominha_app;
GRANT UPDATE(status,finished_at) ON fominha.legacy_import_batches TO fominha_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA fominha
  GRANT SELECT,INSERT ON TABLES TO fominha_app;
