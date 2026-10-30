SET search_path TO fominha, public;

CREATE FUNCTION guard_approval_batch_scope() RETURNS trigger
LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM artifact_versions v
    JOIN artifact_slots a ON a.artifact_slot_id=v.artifact_slot_id
    JOIN stage_run_scopes s ON s.stage_run_id=NEW.check_run_id
      AND s.chapter_id=NEW.chapter_id
    WHERE v.artifact_version_id=NEW.source_snapshot_version_id
      AND a.chapter_id=NEW.chapter_id
      AND (s.source_page_id IS NULL OR s.source_page_id=a.source_page_id)
      AND (s.segment_id IS NULL OR s.segment_id=a.segment_id)
  ) THEN
    RAISE EXCEPTION 'approval snapshot and check run must cover the declared chapter and page';
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION guard_approval_decision_page() RETURNS trigger
LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM approval_subjects s
    JOIN occurrence_revisions r ON r.occurrence_revision_id=s.occurrence_revision_id
    JOIN occurrences o ON o.occurrence_id=r.occurrence_id
    JOIN artifact_versions v ON v.artifact_version_id=NEW.reviewed_image_version_id
    JOIN artifact_slots a ON a.artifact_slot_id=v.artifact_slot_id
    WHERE s.approval_subject_id=NEW.approval_subject_id
      AND a.subject_type='SOURCE_PAGE' AND a.source_page_id=o.source_page_id
  ) THEN
    RAISE EXCEPTION 'approval decision image must belong to the reviewed occurrence page';
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION guard_approval_subject_snapshot() RETURNS trigger
LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM approval_batches b
    JOIN artifact_versions v ON v.artifact_version_id=b.source_snapshot_version_id
    JOIN artifact_slots a ON a.artifact_slot_id=v.artifact_slot_id
    JOIN occurrence_revisions r ON r.occurrence_revision_id=NEW.occurrence_revision_id
    JOIN occurrences o ON o.occurrence_id=r.occurrence_id
    WHERE b.approval_batch_id=NEW.approval_batch_id
      AND (a.subject_type<>'SOURCE_PAGE' OR a.source_page_id=o.source_page_id)
  ) THEN
    RAISE EXCEPTION 'approval subject must match the snapshot page';
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION guard_legacy_import_item() RETURNS trigger
LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE batch_status text;
BEGIN
  SELECT status INTO batch_status FROM legacy_import_batches
    WHERE import_batch_id=NEW.import_batch_id FOR UPDATE;
  IF batch_status IS DISTINCT FROM 'RUNNING' THEN
    RAISE EXCEPTION 'legacy import batch must be RUNNING to accept items';
  END IF;
  RETURN NEW;
END $$;

CREATE FUNCTION guard_legacy_import_batch() RETURNS trigger
LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF OLD.status<>'RUNNING' OR NEW.status NOT IN ('COMPLETED','PARTIAL','FAILED')
     OR NEW.import_batch_id<>OLD.import_batch_id
     OR NEW.source_root_id<>OLD.source_root_id
     OR NEW.fingerprint<>OLD.fingerprint
     OR NEW.importer_version<>OLD.importer_version
     OR NEW.started_at<>OLD.started_at
     OR NEW.report_object_id IS DISTINCT FROM OLD.report_object_id
     OR NEW.finished_at IS NULL THEN
    RAISE EXCEPTION 'invalid legacy import batch transition';
  END IF;
  RETURN NEW;
END $$;

CREATE TRIGGER approval_batch_scope BEFORE INSERT ON approval_batches
  FOR EACH ROW EXECUTE FUNCTION guard_approval_batch_scope();
CREATE TRIGGER approval_decision_page BEFORE INSERT ON approval_decisions
  FOR EACH ROW EXECUTE FUNCTION guard_approval_decision_page();
CREATE TRIGGER approval_subject_snapshot BEFORE INSERT ON approval_subjects
  FOR EACH ROW EXECUTE FUNCTION guard_approval_subject_snapshot();
CREATE TRIGGER legacy_import_item_open BEFORE INSERT ON legacy_import_items
  FOR EACH ROW EXECUTE FUNCTION guard_legacy_import_item();
CREATE TRIGGER legacy_import_item_append_only BEFORE UPDATE OR DELETE ON legacy_import_items
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER legacy_import_batch_transition BEFORE UPDATE ON legacy_import_batches
  FOR EACH ROW EXECUTE FUNCTION guard_legacy_import_batch();
