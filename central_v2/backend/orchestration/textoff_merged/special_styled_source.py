"""Resolve the image reviewed by Check for an initial Artístico occurrence."""
import json
from pathlib import Path

from PIL import Image

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from central_v2.backend.orchestration.textoff_special.inputs import resolve_input

from .artifact_paths import artifact_ref
from .auto_cleaner_check_manifest import _read_check_manifest, manifest_path as check_path
from .consolidated import consolidated_is_current
from .consolidated_artifacts import consolidated_image
from .special_treatments_manifest import SCHEMA as SPECIAL_SCHEMA, manifest_path as special_path
from .stages import LEVEL1, LEVEL2, stage_chapter


def detection_input(manga: Path, provider: str, chapter: str, page: str,
                    identity: str, roi: dict) -> dict:
    """Bind an approved identity to the current manifest-backed Check image."""
    manga = Path(manga).resolve()
    if (not provider or not chapter or Path(chapter).name != chapter
            or not page or Path(page).name != page or not identity):
        raise ValueError("Contexto Artístico inválido.")
    special = special_path(manga, chapter)
    special_hash = sha256(special)
    payload = json.loads(special.read_text(encoding="utf-8"))
    check = check_path(manga, chapter)
    check_hash = sha256(check)
    if (payload.get("schema") != SPECIAL_SCHEMA or payload.get("version") != 1
            or payload.get("provider") != provider or payload.get("manga") != manga.name
            or payload.get("chapter") != chapter
            or (payload.get("source_check") or {}).get("path") != str(check.relative_to(manga))
            or (payload.get("source_check") or {}).get("sha256") != check_hash):
        raise ValueError("Check ou manifesto Artístico desatualizado.")
    document = {"provider": provider, "obra": manga.name, "capitulo": chapter}
    decisions = _read_check_manifest(check, document)["approved_occurrences"]
    matches = [row for row in decisions if row.get("page") == page
               and row.get("id") == identity and row.get("tipo") == "balao_estilizado"
               and row.get("box_pixels") == roi]
    if len(matches) != 1:
        raise ValueError("Identidade ou ROI Artístico diverge do Check aprovado.")
    if not consolidated_is_current(manga, chapter):
        raise ValueError("Imagem de revisão do Check indisponível ou obsoleta.")
    folder = stage_chapter(manga, "TO_MERGED_CONSOLIDADO", chapter)
    manifest = (folder / "json/clean-manifest.json").resolve()
    manifest_hash = sha256(manifest)
    selection = [row for row in json.loads(manifest.read_text(encoding="utf-8"))
                 .get("selections", []) if row.get("source") == page]
    if len(selection) != 1:
        raise ValueError("Página ambígua na revisão do Check.")
    item = selection[0]
    stage = item.get("selected_from")
    if stage not in {LEVEL1, LEVEL2}:
        raise ValueError("Origem da revisão do Check inválida.")
    artifact = artifact_ref("clean", Path(page).stem + "_clean" + Path(page).suffix)
    if item.get("artifact") != artifact:
        raise ValueError("Artefato da revisão do Check divergente.")
    image = consolidated_image(manga, chapter, Path(artifact).name)
    if image is None or sha256(image) != item.get("sha256"):
        raise ValueError("Imagem da revisão do Check sem SHA verificável.")
    level = "MERGED_NIVEL_II" if stage == LEVEL2 else "MERGED_NIVEL_I"
    resolved = resolve_input(manga, level, chapter, Path(artifact).name, item["sha256"])
    if Path(resolved["path"]).resolve() != image.resolve():
        raise ValueError("Origem da revisão do Check não corresponde ao estágio.")
    with Image.open(image) as opened:
        width, height = opened.size
    x, y, w, h = (roi.get(key) for key in ("x", "y", "width", "height"))
    if (any(type(value) is not int for value in (x, y, w, h)) or x < 0 or y < 0
            or w <= 0 or h <= 0 or x + w > width or y + h > height):
        raise ValueError("ROI Artístico fora das dimensões naturais da revisão.")
    if sha256(check) != check_hash or sha256(special) != special_hash or sha256(manifest) != manifest_hash:
        raise ValueError("Origem ou autorização Artístico mudou durante a leitura.")
    return {**resolved, "page": page, "filename": page,
            "artifact_filename": Path(artifact).name, "selected_from": stage,
            "consolidated_manifest": str(manifest),
            "consolidated_manifest_sha256": manifest_hash,
            "check_sha256": check_hash, "special_sha256": special_hash,
            "width": width, "height": height}
