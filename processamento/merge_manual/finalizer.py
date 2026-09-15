from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from .proposal import MANIFEST_NAME, _fp, _hash, _selection, proposal_dir


_LOCKS_GUARD = threading.Lock()
_CHAPTER_LOCKS: dict[str, threading.Lock] = {}


def _chapter_lock(chapter_dir: Path) -> threading.Lock:
    key = str(Path(chapter_dir).resolve())
    with _LOCKS_GUARD:
        return _CHAPTER_LOCKS.setdefault(key, threading.Lock())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"Manifesto ilegível: {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"Manifesto inválido: {path.name}.")
    return payload


def _image_geometry(path: Path) -> tuple[int, int]:
    try:
        with Image.open(path) as image:
            image.load()
            return int(image.width), int(image.height)
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError(f"Imagem ilegível: {path.name}: {exc}") from exc


def _source_geometry(chapter_dir: Path, v3) -> tuple[list[dict[str, Any]], int, int]:
    pages = list(v3.list_pages(chapter_dir))
    if not pages:
        raise ValueError("Nenhuma imagem fonte page-NNN foi encontrada.")
    spans: list[dict[str, Any]] = []
    total = 0
    width: int | None = None
    for path in pages:
        w, h = _image_geometry(path)
        if width is None:
            width = w
        elif w != width:
            raise ValueError(f"Largura divergente na fonte {path.name}: {w}px; esperado {width}px.")
        spans.append({
            "file": path.name,
            "global_start": total,
            "global_end": total + h,
            "source_y_start": 0,
            "source_y_end": h,
        })
        total += h
    return spans, total, int(width or 0)


def _piece_from_item(stage_dir: Path, item: Any, stage: str) -> dict[str, Any] | None:
    if not isinstance(item, dict) or not item.get("file"):
        return None
    if item.get("global_start") is None or item.get("global_end") is None:
        return None
    start, end = int(item["global_start"]), int(item["global_end"])
    if end <= start:
        raise ValueError(f"Intervalo inválido em {stage}: {item.get('file')}.")
    path = stage_dir / str(item["file"])
    return {
        "source": path,
        "source_file": str(item["file"]),
        "global_start": start,
        "global_end": end,
        "source_stage": stage,
    }


def _collect_manifest_pieces(stage_dir: Path, manifest_name: str, keys: tuple[str, ...], stage: str) -> list[dict[str, Any]]:
    path = stage_dir / manifest_name
    if not path.is_file():
        return []
    payload = _read_json(path)
    pieces: list[dict[str, Any]] = []
    for key in keys:
        for item in payload.get(key) or []:
            piece = _piece_from_item(stage_dir, item, stage)
            if piece:
                pieces.append(piece)
    return pieces


def _collect_review_pieces(review_dir: Path) -> list[dict[str, Any]]:
    path = review_dir / "merge-review.json"
    if not path.is_file():
        return []
    payload = _read_json(path)
    pieces: list[dict[str, Any]] = []

    # Formatos com artefatos explícitos.
    for key in ("artifacts", "safe_artifacts"):
        for item in payload.get(key) or []:
            piece = _piece_from_item(review_dir, item, "review")
            if piece:
                pieces.append(piece)

    # Formato scoped: regions + boundaries + outputs.
    for region in payload.get("regions") or []:
        if not isinstance(region, dict):
            continue
        try:
            rstart = int(region["global_start"])
            rend = int(region["global_end"])
        except Exception:
            continue
        bounds = [int(v) for v in (region.get("boundaries") or [])]
        if not bounds or bounds[0] != rstart:
            bounds = [rstart, *bounds]
        if bounds[-1] != rend:
            bounds.append(rend)
        names = [str(v) for v in (region.get("outputs") or [])]
        if len(names) != len(bounds) - 1:
            continue
        for name, start, end in zip(names, bounds, bounds[1:]):
            if end <= start:
                raise ValueError("Região Review possui bloco vazio.")
            pieces.append({
                "source": review_dir / name,
                "source_file": name,
                "global_start": start,
                "global_end": end,
                "source_stage": "review",
            })
    return pieces


def _automatic_pieces(manga: Path, chapter: str) -> list[dict[str, Any]]:
    root = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO"
    specs = (
        ("AUTO_MERGE", "auto-merge-manifest.json", ("artifacts",), "auto_merge"),
        ("MERGE_LEVEL2", "merge-level2-manifest.json", ("artifacts",), "level2"),
        ("MERGE_LEVEL3", "merge-level3-manifest.json", ("safe_artifacts",), "level3"),
        ("MERGE_LEVEL4", "merge-level4-manifest.json", ("safe_artifacts",), "level4"),
        ("MERGE_LEVEL5", "merge-level5-manifest.json", ("safe_artifacts",), "level5"),
    )
    result: list[dict[str, Any]] = []
    for folder, manifest, keys, stage in specs:
        result.extend(_collect_manifest_pieces(root / folder / chapter, manifest, keys, stage))
    result.extend(_collect_review_pieces(root / "MERGE_REVIEW" / chapter))
    return result


def _validate_current_review(
    chapter_dir: Path,
    review_row: dict[str, Any],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    source_block = manifest.get("source_block") or {}
    current, selected, _pages = _selection(
        chapter_dir,
        review_row,
        str(source_block.get("block_id") or ""),
        str(source_block.get("start") or ""),
        str(source_block.get("end") or ""),
    )
    snapshot = {
        "source": current.get("source"),
        "block_id": str(source_block.get("block_id") or ""),
        "global_start": int(selected["global_start"]),
        "global_end": int(selected["global_end"]),
        "pending_segments": current.get("pending_segments") or [],
    }
    expected = str((manifest.get("review_source") or {}).get("review_fingerprint") or "")
    actual = _fp(snapshot)
    if not expected or actual != expected:
        raise ValueError("Proposta obsoleta: o estado autoritativo da Revisão Merge mudou.")
    if (
        int(source_block.get("global_start") or -1) != int(selected["global_start"])
        or int(source_block.get("global_end") or -1) != int(selected["global_end"])
    ):
        raise ValueError("Proposta obsoleta: a faixa residual mudou.")
    return current, selected


def _validate_sources(chapter_dir: Path, manifest: dict[str, Any]) -> None:
    current: list[dict[str, Any]] = []
    for item in manifest.get("source_files") or []:
        if not isinstance(item, dict):
            raise ValueError("Manifesto da proposta possui source_files inválido.")
        path = chapter_dir / str(item.get("name") or "")
        if not path.is_file():
            raise ValueError(f"Proposta obsoleta: fonte ausente: {path.name}.")
        st = path.stat()
        now = {
            "name": path.name,
            "size": st.st_size,
            "mtime_ns": st.st_mtime_ns,
            "sha256": _hash(path),
            "source_y_start": int(item.get("source_y_start") or 0),
            "source_y_end": int(item.get("source_y_end") or 0),
            "pending_height": int(item.get("pending_height") or 0),
        }
        current.append(now)
    if _fp(current) != str(manifest.get("source_fingerprint") or ""):
        raise ValueError("Proposta obsoleta: uma ou mais imagens fonte foram alteradas.")


def _pending_intervals(current: dict[str, Any]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for seg in current.get("pending_segments") or []:
        if not isinstance(seg, dict):
            continue
        if seg.get("global_start") is None or seg.get("global_end") is None:
            continue
        a, b = int(seg["global_start"]), int(seg["global_end"])
        if b > a:
            out.append((a, b))
    return sorted(out)


def _proposal_pieces(manga: Path, chapter: str, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    folder = proposal_dir(manga, chapter, str(manifest["proposal_id"]))
    pieces: list[dict[str, Any]] = []
    for item in manifest.get("outputs") or []:
        if not isinstance(item, dict) or not item.get("file"):
            raise ValueError("Proposta possui saída inválida.")
        pieces.append({
            "source": folder / str(item["file"]),
            "source_file": str(item["file"]),
            "global_start": int(item["global_start"]),
            "global_end": int(item["global_end"]),
            "source_stage": "merge_manual",
        })
    if not pieces:
        raise ValueError("Proposta não possui blocos candidatos.")
    return pieces


def _overlap(a: int, b: int, c: int, d: int) -> bool:
    return min(b, d) > max(a, c)


def _build_candidate(
    *,
    automatic: list[dict[str, Any]],
    manual: list[dict[str, Any]],
    selected_start: int,
    selected_end: int,
    pending: list[tuple[int, int]],
    total_height: int,
) -> list[dict[str, Any]]:
    # A promoção final só é permitida quando a proposta resolve todo o residual
    # autoritativo ainda pendente. Não mascara pendências fora da faixa manual.
    outside = [
        (a, b) for a, b in pending
        if a < selected_start or b > selected_end
    ]
    if outside:
        raise ValueError(
            "Ainda existem resíduos pendentes fora da faixa desta proposta. "
            "Resolva-os antes de aplicar a composição final."
        )

    pieces: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for piece in automatic:
        a, b = int(piece["global_start"]), int(piece["global_end"])
        if _overlap(a, b, selected_start, selected_end):
            continue
        key = (a, b)
        if key in seen:
            continue
        seen.add(key)
        pieces.append(piece)

    for piece in manual:
        a, b = int(piece["global_start"]), int(piece["global_end"])
        if a < selected_start or b > selected_end:
            raise ValueError("Bloco manual saiu da faixa residual declarada.")
        key = (a, b)
        if key in seen:
            raise ValueError("Bloco manual colide com composição automática.")
        seen.add(key)
        pieces.append(piece)

    pieces.sort(key=lambda x: (int(x["global_start"]), int(x["global_end"])))
    cursor = 0
    for piece in pieces:
        a, b = int(piece["global_start"]), int(piece["global_end"])
        if a != cursor:
            kind = "GAP" if a > cursor else "OVERLAP"
            raise ValueError(f"Composição final inválida ({kind}) em Y={cursor}; próximo bloco inicia em {a}.")
        if b <= a:
            raise ValueError("Composição final contém bloco vazio.")
        cursor = b
    if cursor != total_height:
        raise ValueError(
            f"Composição final incompleta: terminou em Y={cursor}; esperado {total_height}."
        )
    return pieces


def _canonical_output_name(v3, spans: list[dict[str, Any]], start: int, end: int, output_dir: Path) -> Path:
    fn = getattr(v3, "page_range_output_name_from_spans", None)
    unique = getattr(v3, "ensure_unique_output_path", None)
    if not callable(fn) or not callable(unique):
        raise ValueError(
            "Contrato canônico de nomes indisponível no image_stitcher atual "
            "(page_range_output_name_from_spans/ensure_unique_output_path)."
        )
    name = fn(spans, start, end)
    return unique(output_dir, name)


def _validate_piece_file(piece: dict[str, Any], expected_width: int) -> None:
    path = Path(piece["source"])
    if not path.is_file():
        raise ValueError(f"Artefato ausente: {piece['source_stage']}/{piece['source_file']}.")
    width, height = _image_geometry(path)
    expected_height = int(piece["global_end"]) - int(piece["global_start"])
    if width != expected_width:
        raise ValueError(
            f"Largura divergente em {piece['source_file']}: {width}px; esperado {expected_width}px."
        )
    if height != expected_height:
        raise ValueError(
            f"Altura divergente em {piece['source_file']}: {height}px; esperado {expected_height}px."
        )


def _write_candidate(
    *,
    staging: Path,
    pieces: list[dict[str, Any]],
    spans: list[dict[str, Any]],
    total_height: int,
    width: int,
    chapter_dir: Path,
    proposal_manifest: dict[str, Any],
    v3,
) -> dict[str, Any]:
    staging.mkdir(parents=True, exist_ok=False)
    outputs: list[dict[str, Any]] = []

    for piece in pieces:
        _validate_piece_file(piece, width)
        start, end = int(piece["global_start"]), int(piece["global_end"])
        dest = _canonical_output_name(v3, spans, start, end, staging)
        shutil.copy2(piece["source"], dest)
        # Reabre a cópia candidata: valida o que será promovido, não apenas a origem.
        dw, dh = _image_geometry(dest)
        if (dw, dh) != (width, end - start):
            raise ValueError(f"Cópia candidata inválida: {dest.name}.")
        outputs.append({
            "file": dest.name,
            "global_start": start,
            "global_end": end,
            "width": width,
            "height": end - start,
            "sources": [],
            "source_stage": piece["source_stage"],
            "source_file": piece["source_file"],
        })

    cursor = 0
    for item in outputs:
        if int(item["global_start"]) != cursor:
            raise ValueError("Validação candidata detectou GAP/OVERLAP.")
        cursor = int(item["global_end"])
    if cursor != total_height:
        raise ValueError("Validação candidata detectou cobertura incompleta.")

    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": 1,
        "algorithm": "merge_manual_final_composition_v1",
        "status": "approved",
        "approved_at": now,
        "chapter": chapter_dir.name,
        "source_dir": str(chapter_dir),
        "output_dir": str(v3.merge_output_dir(chapter_dir)),
        "source_width": width,
        "source_total_height": total_height,
        "merged_images": len(outputs),
        "outputs": outputs,
        "validation": {
            "ok": True,
            "errors": [],
            "coverage_start": 0,
            "coverage_end": total_height,
        },
        "safety": {
            "source_files_modified": False,
            "automatic_artifacts_rerendered": False,
            "manual_proposal_rerendered": False,
            "all_source_pixels_preserved_in_order": True,
            "transactional_promotion": True,
            "stale_proposal_revalidated": True,
        },
        "composition": {
            "manual_proposal_id": proposal_manifest["proposal_id"],
            "manual_range": [
                int((proposal_manifest.get("source_block") or {})["global_start"]),
                int((proposal_manifest.get("source_block") or {})["global_end"]),
            ],
            "manual_manifest": MANIFEST_NAME,
            "scope": "authoritative_review_residual",
        },
    }
    (staging / "merge-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _merge_status_path(manga: Path, chapter: str) -> Path:
    return (
        manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO"
        / "MERGE_STATUS" / chapter / "merge-attempt.json"
    )


def _restore_status(path: Path, original: bytes | None) -> None:
    if original is None:
        if path.is_file():
            path.unlink()
        if path.parent.is_dir() and not any(path.parent.iterdir()):
            path.parent.rmdir()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(original)


def apply_final_composition(
    manga: Path,
    chapter_dir: Path,
    *,
    review_row: dict[str, Any],
    proposal_id: str,
) -> dict[str, Any]:
    chapter_dir = Path(chapter_dir)
    chapter = chapter_dir.name

    with _chapter_lock(chapter_dir):
        from processamento.unificacao_imagens import image_stitcher as v3

        pdir = proposal_dir(manga, chapter, proposal_id)
        manifest_path = pdir / MANIFEST_NAME
        if not manifest_path.is_file():
            raise ValueError("Manifesto da proposta não encontrado.")
        proposal = _read_json(manifest_path)

        if str(proposal.get("proposal_id") or "") != str(proposal_id):
            raise ValueError("proposal_id não corresponde ao manifesto.")
        if str(proposal.get("chapter") or "") != chapter:
            raise ValueError("Proposta pertence a outro capítulo.")

        official_dir = Path(v3.merge_output_dir(chapter_dir))
        official_manifest_path = official_dir / "merge-manifest.json"

        # Idempotência: a mesma proposta já foi promovida e o MERGE segue válido.
        if proposal.get("status") == "EFETIVADO" and official_manifest_path.is_file():
            try:
                official_payload = _read_json(official_manifest_path)
            except ValueError:
                official_payload = {}
            if (
                str((official_payload.get("composition") or {}).get("manual_proposal_id") or "")
                == str(proposal_id)
                and v3.is_chapter_merged(chapter_dir)
            ):
                return {
                    "ok": True,
                    "status": "EFETIVADO",
                    "already_applied": True,
                    "proposal_id": proposal_id,
                    "chapter": chapter,
                    "merged_images": int(official_payload.get("merged_images") or 0),
                    "message": "Esta proposta já foi aplicada anteriormente.",
                }

        if proposal.get("status") != "PROPOSTA_GERADA":
            raise ValueError(f"Status da proposta não permite efetivação: {proposal.get('status')}.")

        current, selected = _validate_current_review(chapter_dir, review_row, proposal)
        _validate_sources(chapter_dir, proposal)

        source_spans, total_height, width = _source_geometry(chapter_dir, v3)
        if total_height <= 0 or width <= 0:
            raise ValueError("Geometria fonte inválida.")

        source_block = proposal.get("source_block") or {}
        selected_start = int(source_block["global_start"])
        selected_end = int(source_block["global_end"])
        if selected_end <= selected_start:
            raise ValueError("Faixa manual inválida.")

        automatic = _automatic_pieces(manga, chapter)
        manual = _proposal_pieces(manga, chapter, proposal)
        pieces = _build_candidate(
            automatic=automatic,
            manual=manual,
            selected_start=selected_start,
            selected_end=selected_end,
            pending=_pending_intervals(current),
            total_height=total_height,
        )

        parent = official_dir.parent
        parent.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=f".merge-manual-{chapter}-{proposal_id}-", dir=str(parent)))
        # tempfile criou a pasta; _write_candidate exige criação exclusiva.
        staging.rmdir()

        backup = parent / f".{official_dir.name}.backup-{proposal_id}"
        if backup.exists():
            shutil.rmtree(backup)

        status_path = _merge_status_path(manga, chapter)
        status_original = status_path.read_bytes() if status_path.is_file() else None
        proposal_original = manifest_path.read_bytes()
        had_official = official_dir.exists()
        promoted = False

        try:
            official_manifest = _write_candidate(
                staging=staging,
                pieces=pieces,
                spans=source_spans,
                total_height=total_height,
                width=width,
                chapter_dir=chapter_dir,
                proposal_manifest=proposal,
                v3=v3,
            )

            if had_official:
                os.replace(official_dir, backup)
            os.replace(staging, official_dir)
            promoted = True

            if not v3.is_chapter_merged(chapter_dir):
                raise ValueError("MERGE promovido não passou em is_chapter_merged().")

            # O MERGE oficial válido passa a ser a autoridade do capítulo.
            if status_path.is_file():
                status_path.unlink()
            if status_path.parent.is_dir() and not any(status_path.parent.iterdir()):
                status_path.parent.rmdir()

            updated = dict(proposal)
            updated["status"] = "EFETIVADO"
            updated["applied_at"] = datetime.now(timezone.utc).isoformat()
            updated["official_merge"] = {
                "output_dir": str(official_dir),
                "manifest": "merge-manifest.json",
                "merged_images": len(official_manifest["outputs"]),
                "algorithm": official_manifest["algorithm"],
            }
            updated.setdefault("safety", {})["official_merge_modified"] = True
            manifest_path.write_text(
                json.dumps(updated, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            if backup.exists():
                shutil.rmtree(backup)

            return {
                "ok": True,
                "status": "EFETIVADO",
                "already_applied": False,
                "proposal_id": proposal_id,
                "chapter": chapter,
                "merged_images": len(official_manifest["outputs"]),
                "output_dir": str(official_dir),
                "message": "Composição final aplicada e validada.",
            }

        except Exception:
            # Rollback integral do MERGE, estado de Review e manifesto da proposta.
            try:
                manifest_path.write_bytes(proposal_original)
            except Exception:
                pass
            try:
                _restore_status(status_path, status_original)
            except Exception:
                pass
            if promoted and official_dir.exists():
                shutil.rmtree(official_dir, ignore_errors=True)
            if backup.exists():
                os.replace(backup, official_dir)
            shutil.rmtree(staging, ignore_errors=True)
            raise
