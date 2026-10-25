"""Reset history records written inside a publication transaction."""

from uuid import uuid4

from psycopg import Connection


def record_reset(conn: Connection, publication_id, chapter_id, items: list[dict],
                 reset: dict, actor_id: str | None) -> None:
    rows = conn.execute(
        "SELECT artifact_slot_id,previous_version_id,artifact_version_id "
        "FROM fominha.publication_items WHERE publication_id=%s ORDER BY artifact_slot_id",
        (publication_id,),
    ).fetchall()
    if any(row[1] is None for row in rows):
        raise ValueError("reset requires a prior active version for every slot")
    event_source, event_target = (rows[0][1], rows[0][2]) if len(rows) == 1 else (None, None)
    event_id = uuid4()
    conn.execute(
        "INSERT INTO fominha.reset_events(reset_event_id,chapter_id,source_page_id,segment_id,reset_type,"
        "actor_id,reason,source_version_id,target_version_id,approval_batch_id,publication_id,idempotency_key) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (event_id, chapter_id, reset.get("source_page_id"), reset.get("segment_id"),
         reset.get("reset_type", "RESTORE"), actor_id, reset.get("reason", ""), event_source, event_target,
         reset.get("approval_batch_id"), publication_id, reset.get("idempotency_key", str(publication_id))),
    )
    by_slot = {item["slot_id"]: item for item in items}
    for slot, previous, target in rows:
        invalidated = by_slot[slot].get("invalidated_run_ids") or [None]
        for ordinal, run_id in enumerate(invalidated):
            conn.execute(
                "INSERT INTO fominha.reset_items(reset_event_id,chapter_id,artifact_slot_id,from_version_id,"
                "to_version_id,backup_version_id,invalidated_run_id,ordinal) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",
                (event_id, chapter_id, slot, previous, target,
                 by_slot[slot].get("backup_version_id"), run_id, ordinal),
            )
