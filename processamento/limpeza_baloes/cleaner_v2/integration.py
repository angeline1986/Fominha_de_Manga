"""Integração oficial do Cleaner V2 com o fluxo Texto Off."""
from __future__ import annotations
from pathlib import Path
import json, os, shutil, subprocess, tempfile, uuid
from .launcher import MODULE_DIR, build_command

ALGORITHM = "cleaner_v2_panel_cleaner_2_11_11"
PROFILE_NAME = "outlined-text.ini"

def _single_output(output_dir: Path, stem: str, kind: str) -> Path | None:
    matches = sorted(p for p in output_dir.glob(f"{stem}_{kind}.*") if p.is_file())
    if len(matches) > 1:
        raise RuntimeError(f"Múltiplos artefatos {kind} para {stem}: " + ", ".join(p.name for p in matches))
    return matches[0] if matches else None

def _promote_directory(staged: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.parent / f".{target.name}.backup-cleaner-v2-{uuid.uuid4().hex}"
    had_previous = target.exists()
    try:
        if had_previous:
            os.replace(target, backup)
        os.replace(staged, target)
    except Exception:
        if had_previous and backup.exists() and not target.exists():
            os.replace(backup, target)
        raise
    else:
        if backup.exists():
            shutil.rmtree(backup)

def clean_chapter(source_images, target, *, source_stage: str, timeout: int = 900):
    images = [Path(p).resolve() for p in source_images]
    if not images:
        raise ValueError("Nenhuma imagem foi informada ao Cleaner V2.")
    missing = [str(p) for p in images if not p.is_file()]
    if missing:
        raise FileNotFoundError("Imagem(ns) ausente(s): " + ", ".join(missing))
    names = [p.name for p in images]
    if len(names) != len(set(names)):
        raise ValueError("O lote contém nomes de arquivo duplicados.")
    if int(timeout) != 900:
        raise ValueError("Cleaner V2 oficial está configurado para timeout de 900 segundos.")

    target = Path(target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{target.name}.cleaner-v2-", dir=target.parent))
    input_dir, output_dir, staged = work/'input', work/'output', work/'staged'
    input_dir.mkdir(); output_dir.mkdir(); staged.mkdir()
    try:
        for src in images:
            os.symlink(src, input_dir/src.name)
        command = build_command(input_dir, output_dir, offline=True)
        completed = subprocess.run(command, cwd=MODULE_DIR, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"Cleaner V2 encerrou com código {completed.returncode}. A saída oficial anterior foi preservada.")

        clean_files, mask_files, missing_clean, missing_mask = [], [], [], []
        for src in images:
            clean = _single_output(output_dir, src.stem, 'clean')
            mask = _single_output(output_dir, src.stem, 'mask')
            if clean is None:
                missing_clean.append(src.name)
            else:
                clean_files.append(clean)
            if mask is None:
                missing_mask.append(src.name)
            else:
                mask_files.append(mask)

        if missing_clean:
            raise RuntimeError("Lote incompleto: não foi gerado *_clean para: " + ", ".join(missing_clean))
        if missing_mask:
            raise RuntimeError("Lote incompleto: não foi gerado *_mask para: " + ", ".join(missing_mask))
        if len(clean_files) != len(images):
            raise RuntimeError(f"Lote incompleto: {len(images)} entrada(s), {len(clean_files)} saída(s) limpa(s).")
        if len(mask_files) != len(images):
            raise RuntimeError(f"Lote incompleto: {len(images)} entrada(s), {len(mask_files)} máscara(s).")

        for artifact in sorted(p for p in output_dir.iterdir() if p.is_file()):
            shutil.copy2(artifact, staged/artifact.name)

        manifest = {
            'schema_version': 2,
            'algorithm': ALGORITHM,
            'engine': 'Panel Cleaner',
            'engine_version': '2.11.11',
            'profile': PROFILE_NAME,
            'offline': True,
            'source_stage': str(source_stage).upper(),
            'source_immutable': True,
            'pages_total': len(images),
            'outputs_total': len(clean_files),
            'masks_total': len(mask_files),
            'mask_complete': True,
            'integrity_ok': True,
            'source_artifacts': names,
            'clean_artifacts': [p.name for p in clean_files],
            'mask_artifacts': [p.name for p in mask_files],
            'failures': [],
        }
        (staged/'clean-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        _promote_directory(staged, target)
        return {'status':'ok','pages':len(images),'outputs':len(clean_files),'masks':len(mask_files),'mask_complete':True,'stage_folder':str(target)}
    finally:
        shutil.rmtree(work, ignore_errors=True)
