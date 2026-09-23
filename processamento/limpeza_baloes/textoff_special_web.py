from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import cv2

from config.data_paths import OUTPUT_ROOT

ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = ROOT / "reports" / "experimentos" / "textoff_especiais"
ALLOWED = {".png", ".jpg", ".jpeg", ".webp"}
PATCHES = {"degrade", "estilizado", "transparente", "gradiente_suave"}


def _decode_image(payload: dict) -> tuple[Path, Path]:
    name = Path(str(payload.get("filename") or "imagem.png")).name
    suffix = Path(name).suffix.lower()
    if suffix not in ALLOWED:
        raise ValueError("Formato inválido. Use PNG, JPG, JPEG ou WEBP.")

    raw = str(payload.get("content_base64") or "")
    if not raw:
        raise ValueError("Imagem não informada.")
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        content = base64.b64decode(raw, validate=True)
    except Exception as exc:
        raise ValueError("Conteúdo da imagem inválido.") from exc
    if not content:
        raise ValueError("Imagem vazia.")
    if len(content) > 60 * 1024 * 1024:
        raise ValueError("Imagem excede o limite de 60 MB.")

    run_dir = WORK_ROOT / uuid.uuid4().hex
    run_dir.mkdir(parents=True, exist_ok=False)
    source = run_dir / ("source" + suffix)
    source.write_bytes(content)

    probe = cv2.imread(str(source))
    if probe is None:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise ValueError("O arquivo selecionado não pôde ser lido como imagem.")
    return source, run_dir


def _encode_result(path: Path) -> dict:
    if not path.is_file():
        raise RuntimeError(f"Resultado não encontrado: {path}")
    mime = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")
    return {
        "filename": path.name,
        "mime": mime,
        "content_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
    }


def _run_degrade(source: Path, target: Path) -> Path:
    from processamento.limpeza_baloes import patch_degrade_experimento as patch
    patch._run(source.parent, source)
    result=patch.OUT/source.parent.name/source.stem/"01_local_heal.png"
    if not result.is_file(): raise RuntimeError("Backend da opção 7 não gerou resultado.")
    copied=target/result.name; shutil.copy2(result,copied); return copied

def _run_styled(source: Path, target: Path) -> Path:
    from processamento.limpeza_baloes import patch_balao_estilizado_experimento as patch
    patch._run(source.parent, source)
    result=patch.OUT/source.parent.name/source.stem/"01_local_heal.png"
    if not result.is_file(): raise RuntimeError("Backend da opção 8 não gerou resultado.")
    copied=target/result.name; shutil.copy2(result,copied); return copied

def _run_transparent(source: Path, target: Path) -> Path:
    from processamento.limpeza_baloes import patch_balao_transparente_experimento as patch
    result=patch._run_page(source)
    if not result.is_file(): raise RuntimeError("Backend da opção 9 não gerou resultado.")
    copied=target/result.name; shutil.copy2(result,copied); return copied


def _run_smooth_gradient(source: Path, target: Path, selection) -> tuple[Path, dict]:
    from processamento.limpeza_baloes.gradiente_suave.gradiente_suave import reconstruct
    if not isinstance(selection, dict):
        raise ValueError("Selecione a região do texto para aplicar Gradiente Suave.")
    try:
        bbox=tuple(int(round(float(selection[k]))) for k in ("x","y","width","height"))
    except Exception as exc:
        raise ValueError("Seleção do Gradiente Suave inválida.") from exc
    result=target/"gradiente_suave.png"
    meta=reconstruct(source,result,bbox,target/"gradiente_suave_report.json")
    return result,meta

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _validated_original_path(manga_path: Path, raw_path: str) -> Path | None:
    raw = str(raw_path or "").strip()
    if not raw:
        return None
    manga = Path(manga_path).resolve()
    chosen = Path(raw).expanduser().resolve()
    if not chosen.is_file() or chosen.suffix.lower() not in ALLOWED:
        raise ValueError("A imagem original selecionada não é válida.")
    if not chosen.is_relative_to(manga):
        raise ValueError("A imagem precisa pertencer à obra selecionada para ser promovida ao Texto Off.")
    return chosen


def _official_target(manga_path: Path, source_path: Path) -> tuple[str, str, Path]:
    manga = Path(manga_path).resolve()
    source = Path(source_path).resolve()
    img_root = (manga / "IMG").resolve()
    merge_root = (manga / "FLUXO_SECUNDARIO" / "02_MERGE").resolve()

    if source.is_relative_to(img_root):
        rel = source.relative_to(img_root)
        stage = "ORIGINAL"
    elif source.is_relative_to(merge_root):
        rel = source.relative_to(merge_root)
        stage = "MERGED"
    else:
        raise ValueError("Promoção oficial aceita imagens vindas de IMG ou FLUXO_SECUNDARIO/02_MERGE.")

    if len(rel.parts) != 2:
        raise ValueError("Não foi possível identificar o capítulo da imagem selecionada.")

    chapter = rel.parts[0]
    target_dir = (manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF" / stage / chapter).resolve()
    textoff_root = (manga / "FLUXO_SECUNDARIO" / "04_TEXTO_OFF").resolve()
    if not target_dir.is_relative_to(textoff_root):
        raise ValueError("Destino Texto Off inválido.")
    return stage, chapter, target_dir / f"{source.stem}_clean.png"


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def _append_special_manifest(target_dir: Path, *, patch: str, run_id: str,
                             source_path: Path, target: Path, stage: str,
                             replaced_existing: bool, backup: Path | None) -> Path:
    manifest_path = target_dir / "special-patches-manifest.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"Manifesto de patches especiais inválido: {manifest_path}") from exc
        if int(manifest.get("schema_version") or 0) != 1:
            raise RuntimeError("Versão não suportada de special-patches-manifest.json.")
        entries = manifest.get("applications")
        if not isinstance(entries, list):
            raise RuntimeError("special-patches-manifest.json não possui applications válido.")
    else:
        manifest = {"schema_version": 1, "manifest": "textoff_special_patches", "applications": []}
        entries = manifest["applications"]

    entry = {
        "application_id": uuid.uuid4().hex,
        "applied_at": _now_iso(),
        "patch": patch,
        "backend": {
            "degrade": "patch_degrade_experimento",
            "estilizado": "patch_balao_estilizado_experimento",
            "transparente": "patch_balao_transparente_experimento",
            "gradiente_suave": "gradiente_suave_v1",
        }[patch],
        "run_id": run_id,
        "source_stage": stage,
        "official_stage": stage,
        "source_file": source_path.name,
        "source_sha256": _sha256(source_path),
        "output_file": target.name,
        "output_sha256": _sha256(target),
        "replaced_existing_output": bool(replaced_existing),
        "backup_file": backup.name if backup else None,
    }
    entries.append(entry)
    manifest["updated_at"] = entry["applied_at"]
    _atomic_json(manifest_path, manifest)
    return manifest_path


def process_special_image(payload: dict, manga_path: Path) -> dict:
    patch = str(payload.get("patch") or "").strip().lower()
    if patch not in PATCHES:
        raise ValueError("Tratamento especial inválido.")

    original_path = _validated_original_path(manga_path, str(payload.get("source_path") or ""))

    # Snapshot da base oficial no momento em que a proposta é gerada.
    # A promoção só será permitida se essa mesma base continuar vigente.
    base_state = None
    base_sha256 = None
    base_official_path = None
    if original_path is not None:
        _base_stage, _base_chapter, base_official = _official_target(manga_path, original_path)
        base_official_path = str(base_official)
        if base_official.is_file():
            base_state = "EXISTS"
            base_sha256 = _sha256(base_official)
        else:
            base_state = "ABSENT"

    source, run_dir = _decode_image(payload)
    target = run_dir / patch
    target.mkdir(parents=True, exist_ok=True)

    treatment_meta = None
    if patch == "degrade":
        result = _run_degrade(source, target)
    elif patch == "estilizado":
        result = _run_styled(source, target)
    elif patch == "transparente":
        result = _run_transparent(source, target)
    else:
        result, treatment_meta = _run_smooth_gradient(source, target, payload.get("selection"))

    run_meta = {
        "schema_version": 1,
        "run_id": run_dir.name,
        "created_at": _now_iso(),
        "patch": patch,
        "source_name": str(payload.get("filename") or source.name),
        "source_path": str(original_path) if original_path else None,
        "source_sha256": _sha256(source),
        "base_state": base_state,
        "base_sha256": base_sha256,
        "base_official_path": base_official_path,
        "result_file": str(result.relative_to(run_dir)),
        "result_sha256": _sha256(result),
        "official_files_modified": False,
        "treatment": treatment_meta,
    }
    _atomic_json(run_dir / "run.json", run_meta)

    encoded = _encode_result(result)
    return {
        "ok": True,
        "patch": patch,
        "source_name": str(payload.get("filename") or source.name),
        "source_path": str(original_path) if original_path else None,
        "result_name": encoded["filename"],
        "mime": encoded["mime"],
        "content_base64": encoded["content_base64"],
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "official_files_modified": False,
        "can_promote": original_path is not None,
    }


def promote_special_result(payload: dict, manga_path: Path) -> dict:
    run_id = str(payload.get("run_id") or "").strip()
    if not run_id or not run_id.isalnum():
        raise ValueError("Execução do tratamento especial inválida.")

    run_dir = (WORK_ROOT / run_id).resolve()
    if not run_dir.is_relative_to(WORK_ROOT.resolve()) or not run_dir.is_dir():
        raise ValueError("Execução do tratamento especial não encontrada.")

    meta_path = run_dir / "run.json"
    if not meta_path.is_file():
        raise ValueError("A execução não possui metadados para promoção oficial.")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    patch = str(meta.get("patch") or "").lower()
    if patch not in PATCHES:
        raise ValueError("Tratamento especial inválido nos metadados da execução.")

    source_path = _validated_original_path(manga_path, str(meta.get("source_path") or ""))
    if source_path is None:
        raise ValueError("Esta execução não preservou o caminho original.")

    result = (run_dir / Path(str(meta.get("result_file") or ""))).resolve()
    if not result.is_relative_to(run_dir) or not result.is_file():
        raise ValueError("Resultado da execução não encontrado.")

    expected_result_sha = str(meta.get("result_sha256") or "")
    if not expected_result_sha or _sha256(result) != expected_result_sha:
        raise RuntimeError("Integridade do resultado processado não confere.")

    stage, chapter, official = _official_target(manga_path, source_path)

    # Controle de concorrência otimista:
    # a proposta só pode substituir exatamente a base oficial sobre a qual
    # foi gerada.
    expected_base_state = str(meta.get("base_state") or "")
    expected_base_sha = str(meta.get("base_sha256") or "")
    expected_base_path = str(meta.get("base_official_path") or "")

    if expected_base_state not in {"EXISTS", "ABSENT"}:
        raise RuntimeError(
            "PROPOSTA_OBSOLETA: a execução não possui snapshot válido da base oficial."
        )

    if expected_base_path and Path(expected_base_path).expanduser().resolve() != official.resolve():
        raise RuntimeError(
            "PROPOSTA_OBSOLETA: o destino oficial da execução mudou."
        )

    if expected_base_state == "EXISTS":
        if not official.is_file():
            raise RuntimeError(
                "PROPOSTA_OBSOLETA: o resultado oficial usado como base não existe mais."
            )
        if not expected_base_sha or _sha256(official) != expected_base_sha:
            raise RuntimeError(
                "PROPOSTA_OBSOLETA: o resultado oficial mudou após a geração da prévia."
            )
    else:
        if official.exists():
            raise RuntimeError(
                "PROPOSTA_OBSOLETA: surgiu um resultado oficial após a geração da prévia."
            )

    official.parent.mkdir(parents=True, exist_ok=True)

    replaced = official.is_file()
    backup = None
    if replaced:
        backup_dir = official.parent / ".special_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = backup_dir / f"{official.stem}.before-{patch}-{stamp}{official.suffix}"
        shutil.copy2(official, backup)

    tmp = official.parent / f".{official.name}.special-{uuid.uuid4().hex}.tmp"
    try:
        shutil.copy2(result, tmp)
        if _sha256(tmp) != expected_result_sha:
            raise RuntimeError("Falha de integridade durante a promoção do resultado.")
        os.replace(tmp, official)
    finally:
        if tmp.exists():
            tmp.unlink()

    manifest_path = _append_special_manifest(
        official.parent, patch=patch, run_id=run_id, source_path=source_path,
        target=official, stage=stage,
        replaced_existing=replaced, backup=backup,
    )

    meta["official_files_modified"] = True
    meta["promoted_at"] = _now_iso()
    meta["official_stage"] = stage
    meta["official_chapter"] = chapter
    meta["official_output"] = str(official)
    meta["official_output_sha256"] = _sha256(official)
    meta["special_manifest"] = str(manifest_path)
    _atomic_json(meta_path, meta)

    return {
        "ok": True,
        "message": f"Resultado salvo em Texto Off — {stage} / {chapter}.",
        "patch": patch, "stage": stage, "chapter": chapter,
        "output": str(official), "output_name": official.name,
        "output_sha256": _sha256(official),
        "replaced_existing_output": replaced,
        "backup": str(backup) if backup else None,
        "manifest": str(manifest_path),
    }


def select_special_image(manga_path: Path) -> dict:
    import subprocess
    manga=Path(manga_path).resolve()
    start=manga if manga.is_dir() else manga.parent
    if not start.is_dir(): start=OUTPUT_ROOT
    if not start.is_dir(): start=ROOT
    apple='on run argv\nset startFolder to POSIX file (item 1 of argv) as alias\nset chosenFile to choose file with prompt (item 2 of argv) default location startFolder of type {\"public.image\"}\nreturn POSIX path of chosenFile\nend run'
    proc=subprocess.run(['osascript','-e',apple,str(start),'Escolha a imagem para aplicar o tratamento especial'],capture_output=True,text=True,check=False)
    if proc.returncode:
        msg=(proc.stderr or '').strip()
        if 'User canceled' in msg or '-128' in msg: return {'ok':True,'cancelled':True}
        raise RuntimeError(msg or 'Não foi possível abrir o seletor de imagem.')
    chosen=Path(proc.stdout.strip()).resolve()
    if not chosen.is_file() or chosen.suffix.lower() not in ALLOWED: raise ValueError('Selecione uma imagem PNG, JPG, JPEG ou WEBP.')
    raw=chosen.read_bytes()
    if len(raw)>60*1024*1024: raise ValueError('Imagem excede o limite de 60 MB.')
    mime={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp'}.get(chosen.suffix.lower(),'image/png')
    return {'ok':True,'cancelled':False,'filename':chosen.name,'path':str(chosen),'mime':mime,'content_base64':base64.b64encode(raw).decode('ascii'),'start_directory':str(start)}
