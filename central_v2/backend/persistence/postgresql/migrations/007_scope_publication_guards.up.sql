SET search_path TO fominha, public;
CREATE FUNCTION guard_scope_definition() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE kind text;
BEGIN
  SELECT scope_type INTO kind FROM stage_runs WHERE stage_run_id=NEW.stage_run_id FOR KEY SHARE;
  IF kind='CHAPTER' AND num_nonnulls(NEW.source_page_id,NEW.segment_id)<>0 THEN
    RAISE EXCEPTION 'CHAPTER scope cannot name a page or segment'; END IF;
  IF kind='PAGE' AND (NEW.source_page_id IS NULL OR NEW.segment_id IS NOT NULL) THEN
    RAISE EXCEPTION 'PAGE scope requires exactly a source page'; END IF;
  IF kind='SEGMENT' AND (NEW.segment_id IS NULL OR NEW.source_page_id IS NOT NULL) THEN
    RAISE EXCEPTION 'SEGMENT scope requires exactly a derived segment'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_segment_version_scope() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM derived_segments d JOIN stage_run_scopes s
    ON s.stage_run_id=NEW.stage_run_id AND s.chapter_id=d.chapter_id
    WHERE d.segment_id=NEW.segment_id AND (s.segment_id=NEW.segment_id OR
      (s.source_page_id IS NULL AND s.segment_id IS NULL) OR
      (SELECT scope_type FROM stage_runs WHERE stage_run_id=s.stage_run_id)='BATCH')) THEN
    RAISE EXCEPTION 'segment version run does not declare its segment scope'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_publication_run_scope() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM stage_run_scopes WHERE stage_run_id=NEW.stage_run_id
    AND chapter_id=NEW.chapter_id) THEN RAISE EXCEPTION 'publication run does not cover chapter'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_publication_item() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE p publications%ROWTYPE; v artifact_versions%ROWTYPE; cur active_artifacts%ROWTYPE;
BEGIN
  SELECT * INTO p FROM publications WHERE publication_id=NEW.publication_id FOR KEY SHARE;
  SELECT * INTO v FROM artifact_versions WHERE artifact_version_id=NEW.artifact_version_id FOR KEY SHARE;
  IF p.chapter_id<>NEW.chapter_id OR (p.publication_type='PUBLISH' AND v.stage_run_id<>p.stage_run_id) THEN
    RAISE EXCEPTION 'publication item chapter or producer run mismatch'; END IF;
  SELECT * INTO cur FROM active_artifacts WHERE artifact_slot_id=NEW.artifact_slot_id FOR UPDATE;
  IF (cur.revision IS NULL AND NEW.expected_active_revision<>0) OR
     (cur.revision IS NOT NULL AND cur.revision<>NEW.expected_active_revision) OR
     (cur.artifact_version_id IS DISTINCT FROM NEW.previous_version_id) THEN
    RAISE EXCEPTION 'publication item expected revision or previous version mismatch'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_reset_event_scope() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
BEGIN
  IF NEW.source_page_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM source_pages
    WHERE source_page_id=NEW.source_page_id AND chapter_id=NEW.chapter_id) THEN
    RAISE EXCEPTION 'reset source page is outside chapter'; END IF;
  IF NEW.segment_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM derived_segments
    WHERE segment_id=NEW.segment_id AND chapter_id=NEW.chapter_id) THEN
    RAISE EXCEPTION 'reset segment is outside chapter'; END IF;
  RETURN NEW;
END $$;
CREATE FUNCTION guard_reset_item() RETURNS trigger LANGUAGE plpgsql SET search_path=fominha,public AS $$
DECLARE e reset_events%ROWTYPE;
BEGIN
  SELECT * INTO e FROM reset_events WHERE reset_event_id=NEW.reset_event_id FOR KEY SHARE;
  IF NOT EXISTS (SELECT 1 FROM publication_items i JOIN publications p USING(publication_id)
    WHERE p.publication_id=e.publication_id AND p.status='COMMITTED'
      AND i.artifact_slot_id=NEW.artifact_slot_id AND i.artifact_version_id=NEW.to_version_id
      AND i.previous_version_id=NEW.from_version_id) THEN
    RAISE EXCEPTION 'reset item must match committed publication transition'; END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER stage_scope_definition BEFORE INSERT ON stage_run_scopes
  FOR EACH ROW EXECUTE FUNCTION guard_scope_definition();
CREATE TRIGGER segment_version_scope BEFORE INSERT ON derived_segment_versions
  FOR EACH ROW EXECUTE FUNCTION guard_segment_version_scope();
CREATE TRIGGER publication_run_scope BEFORE INSERT ON publications
  FOR EACH ROW EXECUTE FUNCTION guard_publication_run_scope();
CREATE TRIGGER publication_item_guard BEFORE INSERT ON publication_items
  FOR EACH ROW EXECUTE FUNCTION guard_publication_item();
CREATE TRIGGER reset_event_scope BEFORE INSERT ON reset_events
  FOR EACH ROW EXECUTE FUNCTION guard_reset_event_scope();
CREATE TRIGGER reset_item_guard BEFORE INSERT ON reset_items
  FOR EACH ROW EXECUTE FUNCTION guard_reset_item();
