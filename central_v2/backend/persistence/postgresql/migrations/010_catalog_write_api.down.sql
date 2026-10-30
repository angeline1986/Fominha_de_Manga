DROP FUNCTION fominha.catalog_stage(text,text,text,text,uuid);
DROP FUNCTION fominha.catalog_segment(uuid,text,uuid);
DROP FUNCTION fominha.catalog_source_page(uuid,text,text,integer,uuid);
DROP FUNCTION fominha.catalog_chapter(uuid,text,integer,uuid);
DROP FUNCTION fominha.catalog_work(uuid,text,text,text,uuid);
DROP FUNCTION fominha.catalog_provider(text,text,uuid);
REVOKE CREATE ON SCHEMA fominha FROM fominha_migrator;
