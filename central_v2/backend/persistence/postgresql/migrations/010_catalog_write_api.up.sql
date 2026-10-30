-- Catalog metadata is the first restricted write slice. No table grants.
GRANT CREATE ON SCHEMA fominha TO fominha_migrator;
CREATE FUNCTION fominha.catalog_provider(p_code text, p_name text, p_id uuid)
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path=pg_catalog,fominha,pg_temp AS $$
  INSERT INTO providers(provider_id,code,display_name) VALUES(p_id,p_code,p_name)
  ON CONFLICT(code) DO UPDATE SET code=EXCLUDED.code RETURNING provider_id;
$$;

CREATE FUNCTION fominha.catalog_work(p_provider uuid, p_key text, p_name text,
  p_status text, p_id uuid)
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path=pg_catalog,fominha,pg_temp AS $$
  INSERT INTO works(work_id,provider_id,external_key,display_name,catalog_status)
  VALUES(p_id,p_provider,p_key,p_name,p_status)
  ON CONFLICT(provider_id,external_key) DO UPDATE SET external_key=EXCLUDED.external_key
  RETURNING work_id;
$$;

CREATE FUNCTION fominha.catalog_chapter(p_work uuid, p_key text, p_order integer,
  p_id uuid)
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path=pg_catalog,fominha,pg_temp AS $$
  INSERT INTO chapters(chapter_id,work_id,chapter_key,display_order)
  VALUES(p_id,p_work,p_key,p_order)
  ON CONFLICT(work_id,chapter_key) DO UPDATE SET chapter_key=EXCLUDED.chapter_key
  RETURNING chapter_id;
$$;

CREATE FUNCTION fominha.catalog_source_page(p_chapter uuid, p_key text,
  p_filename text, p_order integer, p_id uuid)
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path=pg_catalog,fominha,pg_temp AS $$
  INSERT INTO source_pages(source_page_id,chapter_id,source_key,original_filename,display_order)
  VALUES(p_id,p_chapter,p_key,p_filename,p_order)
  ON CONFLICT(chapter_id,source_key) DO UPDATE SET source_key=EXCLUDED.source_key
  RETURNING source_page_id;
$$;

CREATE FUNCTION fominha.catalog_segment(p_chapter uuid, p_key text, p_id uuid)
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path=pg_catalog,fominha,pg_temp AS $$
  INSERT INTO derived_segments(segment_id,chapter_id,segment_key)
  VALUES(p_id,p_chapter,p_key)
  ON CONFLICT(chapter_id,segment_key) DO UPDATE SET segment_key=EXCLUDED.segment_key
  RETURNING segment_id;
$$;

CREATE FUNCTION fominha.catalog_stage(p_code text, p_version text, p_name text,
  p_class text, p_id uuid)
RETURNS uuid LANGUAGE sql SECURITY DEFINER
SET search_path=pg_catalog,fominha,pg_temp AS $$
  INSERT INTO pipeline_stages(stage_id,stage_code,contract_version,display_name,stage_class)
  VALUES(p_id,p_code,p_version,p_name,p_class)
  ON CONFLICT(stage_code,contract_version) DO UPDATE SET stage_code=EXCLUDED.stage_code
  RETURNING stage_id;
$$;

ALTER FUNCTION fominha.catalog_provider(text,text,uuid) OWNER TO fominha_migrator;
ALTER FUNCTION fominha.catalog_work(uuid,text,text,text,uuid) OWNER TO fominha_migrator;
ALTER FUNCTION fominha.catalog_chapter(uuid,text,integer,uuid) OWNER TO fominha_migrator;
ALTER FUNCTION fominha.catalog_source_page(uuid,text,text,integer,uuid) OWNER TO fominha_migrator;
ALTER FUNCTION fominha.catalog_segment(uuid,text,uuid) OWNER TO fominha_migrator;
ALTER FUNCTION fominha.catalog_stage(text,text,text,text,uuid) OWNER TO fominha_migrator;

REVOKE ALL ON FUNCTION fominha.catalog_provider(text,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION fominha.catalog_work(uuid,text,text,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION fominha.catalog_chapter(uuid,text,integer,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION fominha.catalog_source_page(uuid,text,text,integer,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION fominha.catalog_segment(uuid,text,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION fominha.catalog_stage(text,text,text,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION fominha.catalog_provider(text,text,uuid) TO fominha_app;
GRANT EXECUTE ON FUNCTION fominha.catalog_work(uuid,text,text,text,uuid) TO fominha_app;
GRANT EXECUTE ON FUNCTION fominha.catalog_chapter(uuid,text,integer,uuid) TO fominha_app;
GRANT EXECUTE ON FUNCTION fominha.catalog_source_page(uuid,text,text,integer,uuid) TO fominha_app;
GRANT EXECUTE ON FUNCTION fominha.catalog_segment(uuid,text,uuid) TO fominha_app;
GRANT EXECUTE ON FUNCTION fominha.catalog_stage(text,text,text,text,uuid) TO fominha_app;
REVOKE CREATE ON SCHEMA fominha FROM fominha_migrator;
