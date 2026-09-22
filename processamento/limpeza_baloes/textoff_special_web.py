from __future__ import annotations

import base64
import json
import shutil
import uuid
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[2]
WORK_ROOT = ROOT / "reports" / "experimentos" / "textoff_especiais"
ALLOWED = {".png", ".jpg", ".jpeg", ".webp"}
PATCHES = {"degrade", "estilizado", "transparente"}


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


def process_special_image(payload: dict) -> dict:
    patch = str(payload.get("patch") or "").strip().lower()
    if patch not in PATCHES:
        raise ValueError("Tratamento especial inválido.")

    source, run_dir = _decode_image(payload)
    target = run_dir / patch
    target.mkdir(parents=True, exist_ok=True)

    if patch == "degrade":
        result = _run_degrade(source, target)
    elif patch == "estilizado":
        result = _run_styled(source, target)
    else:
        result = _run_transparent(source, target)

    encoded = _encode_result(result)
    return {
        "ok": True,
        "patch": patch,
        "source_name": str(payload.get("filename") or source.name),
        "result_name": encoded["filename"],
        "mime": encoded["mime"],
        "content_base64": encoded["content_base64"],
        "run_dir": str(run_dir),
        "official_files_modified": False,
    }


def select_special_image(manga_path: Path) -> dict:
    import subprocess
    manga=Path(manga_path).resolve()
    start=manga if manga.is_dir() else manga.parent
    if not start.is_dir(): start=ROOT/'download'/'mangago_downloader'/'output'
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
