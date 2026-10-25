SET search_path TO fominha, public;
CREATE FUNCTION reject_mutation() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME USING ERRCODE='55000'; END $$;
CREATE FUNCTION guard_stage_run_transition() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF OLD.status = NEW.status THEN RETURN NEW; END IF;
  IF OLD.status='CREATED' AND NEW.status IN ('RUNNING','FAILED','CANCELLED') THEN RETURN NEW; END IF;
  IF OLD.status='RUNNING' AND NEW.status IN ('SUCCEEDED','FAILED','CANCELLED','INTERRUPTED') THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'invalid stage run transition: % -> %', OLD.status, NEW.status;
END $$;
CREATE FUNCTION guard_scope_artifact() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE s stage_run_scopes%ROWTYPE; v artifact_versions%ROWTYPE; a artifact_slots%ROWTYPE;
BEGIN
  SELECT * INTO s FROM stage_run_scopes WHERE stage_run_id=NEW.stage_run_id AND ordinal=NEW.scope_ordinal FOR KEY SHARE;
  SELECT * INTO v FROM artifact_versions WHERE artifact_version_id=NEW.artifact_version_id FOR KEY SHARE;
  SELECT * INTO a FROM artifact_slots WHERE artifact_slot_id=v.artifact_slot_id FOR KEY SHARE;
  IF a.chapter_id<>s.chapter_id THEN RAISE EXCEPTION 'artifact is outside declared chapter scope'; END IF;
  IF s.source_page_id IS NOT NULL AND (a.subject_type<>'SOURCE_PAGE' OR a.source_page_id<>s.source_page_id) THEN
    RAISE EXCEPTION 'artifact is outside declared source page scope'; END IF;
  IF s.segment_id IS NOT NULL AND (a.subject_type<>'DERIVED_SEGMENT' OR a.segment_id<>s.segment_id) THEN
    RAISE EXCEPTION 'artifact is outside declared segment scope'; END IF;
  IF NEW.direction='OUTPUT' AND v.stage_run_id IS DISTINCT FROM NEW.stage_run_id THEN
    RAISE EXCEPTION 'output version must be produced by this run'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_segment_source() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE seg derived_segment_versions%ROWTYPE; page source_pages%ROWTYPE; ver artifact_versions%ROWTYPE; slot artifact_slots%ROWTYPE;
BEGIN
  SELECT * INTO seg FROM derived_segment_versions WHERE segment_version_id=NEW.segment_version_id FOR KEY SHARE;
  SELECT * INTO page FROM source_pages WHERE source_page_id=NEW.source_page_id FOR KEY SHARE;
  SELECT * INTO ver FROM artifact_versions WHERE artifact_version_id=NEW.source_artifact_version_id FOR KEY SHARE;
  SELECT * INTO slot FROM artifact_slots WHERE artifact_slot_id=ver.artifact_slot_id FOR KEY SHARE;
  IF slot.subject_type<>'SOURCE_PAGE' OR slot.source_page_id<>page.source_page_id THEN
    RAISE EXCEPTION 'segment source version must belong to declared source page'; END IF;
  IF NOT EXISTS (SELECT 1 FROM derived_segments d WHERE d.segment_id=seg.segment_id AND d.chapter_id=page.chapter_id) THEN
    RAISE EXCEPTION 'segment and source page must belong to same chapter'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_occurrence_revision() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE o occurrences%ROWTYPE; v artifact_versions%ROWTYPE; s artifact_slots%ROWTYPE;
BEGIN
  SELECT * INTO o FROM occurrences WHERE occurrence_id=NEW.occurrence_id FOR KEY SHARE;
  SELECT * INTO v FROM artifact_versions WHERE artifact_version_id=NEW.reviewed_image_version_id FOR KEY SHARE;
  SELECT * INTO s FROM artifact_slots WHERE artifact_slot_id=v.artifact_slot_id FOR KEY SHARE;
  IF s.subject_type<>'SOURCE_PAGE' OR s.source_page_id<>o.source_page_id THEN
    RAISE EXCEPTION 'reviewed image version must belong to occurrence source page'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_approval_subject() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE b approval_batches%ROWTYPE; r occurrence_revisions%ROWTYPE; o occurrences%ROWTYPE;
BEGIN
  SELECT * INTO b FROM approval_batches WHERE approval_batch_id=NEW.approval_batch_id FOR KEY SHARE;
  SELECT * INTO r FROM occurrence_revisions WHERE occurrence_revision_id=NEW.occurrence_revision_id FOR KEY SHARE;
  SELECT * INTO o FROM occurrences WHERE occurrence_id=r.occurrence_id FOR KEY SHARE;
  IF NOT EXISTS (SELECT 1 FROM source_pages p WHERE p.source_page_id=o.source_page_id AND p.chapter_id=b.chapter_id) THEN
    RAISE EXCEPTION 'approval batch and occurrence must belong to same chapter'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_approval_pointer() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE d approval_decisions%ROWTYPE; prev approval_decisions%ROWTYPE;
BEGIN
  SELECT * INTO d FROM approval_decisions WHERE approval_subject_id=NEW.approval_subject_id
    AND approval_decision_id=NEW.approval_decision_id FOR KEY SHARE;
  IF TG_OP='INSERT' THEN
    IF NEW.revision<>1 OR d.decision_seq<>1 THEN RAISE EXCEPTION 'initial approval revision and sequence must be 1'; END IF;
    RETURN NEW;
  END IF;
  IF NEW.revision<>OLD.revision+1 OR d.decision_seq<>NEW.revision THEN RAISE EXCEPTION 'approval CAS revision mismatch'; END IF;
  SELECT * INTO prev FROM approval_decisions WHERE approval_subject_id=OLD.approval_subject_id
    AND approval_decision_id=OLD.approval_decision_id FOR KEY SHARE;
  IF d.supersedes_decision_id IS DISTINCT FROM prev.approval_decision_id THEN
    RAISE EXCEPTION 'new decision must supersede current decision'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_active_pointer() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF TG_OP='INSERT' THEN
    IF NEW.revision<>1 THEN RAISE EXCEPTION 'initial active revision must be 1'; END IF;
  ELSIF NEW.revision<>OLD.revision+1 THEN RAISE EXCEPTION 'active pointer CAS revision mismatch';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM publications p WHERE p.publication_id=NEW.publication_id AND p.status='COMMITTED') THEN
    RAISE EXCEPTION 'active pointer requires committed publication'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION enqueue_active_invalidation() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  INSERT INTO invalidation_outbox(event_id,cause_type,source_slot_id,source_version_id,
    previous_version_id,new_revision)
  VALUES(gen_random_uuid(),'ARTIFACT_POINTER',NEW.artifact_slot_id,NEW.artifact_version_id,
    CASE WHEN TG_OP='UPDATE' THEN OLD.artifact_version_id ELSE NULL END,NEW.revision);
  RETURN NEW;
END $$;
CREATE FUNCTION enqueue_approval_invalidation() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  INSERT INTO invalidation_outbox(event_id,cause_type,approval_subject_id,approval_decision_id,
    previous_approval_decision_id,new_revision)
  VALUES(gen_random_uuid(),'APPROVAL_DECISION',NEW.approval_subject_id,NEW.approval_decision_id,
    CASE WHEN TG_OP='UPDATE' THEN OLD.approval_decision_id ELSE NULL END,NEW.revision);
  RETURN NEW;
END $$;
CREATE FUNCTION guard_publication_transition() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF OLD.status=NEW.status THEN RETURN NEW; END IF;
  IF OLD.status='STAGED' AND NEW.status IN ('COMMITTED','CONFLICT','ABORTED') THEN RETURN NEW; END IF;
  RAISE EXCEPTION 'invalid publication transition: % -> %', OLD.status, NEW.status;
END $$;
CREATE FUNCTION guard_artifact_state_transition() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE previous text;
BEGIN
  SELECT state INTO previous FROM artifact_state_events WHERE artifact_version_id=NEW.artifact_version_id
    ORDER BY sequence_no DESC LIMIT 1;
  IF previous IS NULL AND NEW.state<>'STAGED' THEN RAISE EXCEPTION 'artifact must start STAGED'; END IF;
  IF previous='STAGED' AND NEW.state NOT IN ('VALID','STALE','INVALID','QUARANTINED') THEN
    RAISE EXCEPTION 'invalid artifact state transition'; END IF;
  IF previous='VALID' AND NEW.state NOT IN ('STALE','INVALID','QUARANTINED') THEN
    RAISE EXCEPTION 'invalid artifact state transition'; END IF;
  IF previous='STALE' AND (NEW.state<>'VALID' OR NEW.details_json->>'revalidated'<>'true') THEN
    RAISE EXCEPTION 'STALE can become VALID only after explicit revalidation'; END IF;
  IF previous IN ('INVALID','QUARANTINED') THEN RAISE EXCEPTION 'terminal artifact state'; END IF;
  IF NEW.state='STALE' AND NEW.cause_event_id IS NULL THEN RAISE EXCEPTION 'STALE requires a cause event'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER stage_run_transition BEFORE UPDATE OF status ON stage_runs
  FOR EACH ROW EXECUTE FUNCTION guard_stage_run_transition();
CREATE TRIGGER stage_scope_artifact BEFORE INSERT ON stage_run_artifacts
  FOR EACH ROW EXECUTE FUNCTION guard_scope_artifact();
CREATE TRIGGER segment_source_guard BEFORE INSERT ON segment_source_ranges
  FOR EACH ROW EXECUTE FUNCTION guard_segment_source();
CREATE TRIGGER occurrence_revision_guard BEFORE INSERT ON occurrence_revisions
  FOR EACH ROW EXECUTE FUNCTION guard_occurrence_revision();
CREATE TRIGGER approval_subject_guard BEFORE INSERT ON approval_subjects
  FOR EACH ROW EXECUTE FUNCTION guard_approval_subject();
CREATE TRIGGER approval_pointer_guard BEFORE INSERT OR UPDATE ON current_approval_decisions
  FOR EACH ROW EXECUTE FUNCTION guard_approval_pointer();
CREATE TRIGGER active_pointer_guard BEFORE INSERT OR UPDATE ON active_artifacts
  FOR EACH ROW EXECUTE FUNCTION guard_active_pointer();
CREATE TRIGGER active_pointer_invalidation AFTER INSERT OR UPDATE ON active_artifacts
  FOR EACH ROW EXECUTE FUNCTION enqueue_active_invalidation();
CREATE TRIGGER approval_pointer_invalidation AFTER INSERT OR UPDATE ON current_approval_decisions
  FOR EACH ROW EXECUTE FUNCTION enqueue_approval_invalidation();
CREATE TRIGGER publication_transition BEFORE UPDATE OF status ON publications
  FOR EACH ROW EXECUTE FUNCTION guard_publication_transition();
CREATE TRIGGER artifact_state_transition BEFORE INSERT ON artifact_state_events
  FOR EACH ROW EXECUTE FUNCTION guard_artifact_state_transition();
CREATE TRIGGER artifact_versions_append_only BEFORE UPDATE OR DELETE ON artifact_versions
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER artifact_objects_append_only BEFORE UPDATE OR DELETE ON artifact_objects
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER artifact_dependencies_append_only BEFORE UPDATE OR DELETE ON artifact_dependencies
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER approval_dependencies_append_only BEFORE UPDATE OR DELETE ON approval_dependencies
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER approval_decisions_append_only BEFORE UPDATE OR DELETE ON approval_decisions
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER publication_items_append_only BEFORE UPDATE OR DELETE ON publication_items
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER reset_events_append_only BEFORE UPDATE OR DELETE ON reset_events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER reset_items_append_only BEFORE UPDATE OR DELETE ON reset_items
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER audit_events_append_only BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER stage_run_events_append_only BEFORE UPDATE OR DELETE ON stage_run_events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER artifact_state_events_append_only BEFORE UPDATE OR DELETE ON artifact_state_events
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
CREATE TRIGGER artifact_validations_append_only BEFORE UPDATE OR DELETE ON artifact_validations
  FOR EACH ROW EXECUTE FUNCTION reject_mutation();
