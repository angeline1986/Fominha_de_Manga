"""Integração oficial do Cleaner V2 com o fluxo Texto Off."""
from __future__ import annotations
from pathlib import Path
import json, os, shutil, subprocess, tempfile, time, uuid
from .launcher import MODULE_DIR, build_command
from .balloon_authorization import apply_balloon_authorization

LEVEL2_SCRIPT = MODULE_DIR / 'level2.py'

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

def clean_chapter(source_images, target, *, source_stage: str, timeout: int = 900, progress_job=None, progress_base: float = 0.0, progress_span: float = 1.0, chapter_name: str | None = None):
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
        progress_file = work/'progress.json'
        command = build_command(input_dir, output_dir, offline=True, progress_file=progress_file)
        process = subprocess.Popen(command, cwd=MODULE_DIR)
        last_stamp = None
        while True:
            code = process.poll()
            if progress_job is not None and progress_file.is_file():
                try:
                    payload = json.loads(progress_file.read_text(encoding='utf-8'))
                    stamp = payload.get('updated_at')
                    if stamp != last_stamp:
                        last_stamp = stamp
                        overall = max(0.0, min(1.0, float(payload.get('overall') or 0.0)))
                        progress_job.progress_value = float(progress_base) + (float(progress_span) * overall)
                        detail = str(payload.get('detail') or 'Cleaner V2 processando...')
                        prefix = f"Cap. {chapter_name}: " if chapter_name else ''
                        progress_job.progress_detail = prefix + detail
                        progress_job.message = progress_job.progress_detail
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    pass
            if code is not None:
                break
            time.sleep(0.25)
        if code != 0:
            raise RuntimeError(f"Cleaner V2 encerrou com código {code}. A saída oficial anterior foi preservada.")
        if progress_job is not None:
            progress_job.progress_value = float(progress_base) + float(progress_span)
            prefix = f"Cap. {chapter_name}: " if chapter_name else ''
            progress_job.progress_detail = prefix + 'Cleaner V2 concluído'
            progress_job.message = progress_job.progress_detail

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

        # Nível I: Cleaner V2 intacto; máscara autorizada somente dentro de balões reais.
        level1_report_path = work/'level1-balloon-report.json'
        level1_report = apply_balloon_authorization(
            images, output_dir, level1_report_path,
            progress_job=progress_job, chapter_name=chapter_name,
        )
        if int(level1_report.get('pages_total') or 0) != len(images):
            raise RuntimeError('Texto Off — Nível I não analisou todas as imagens do lote.')

        # Nível II é pós-processamento cirúrgico: usa os originais + máscaras reais
        # do Nível I e altera somente componentes classificados pelo Detector V3.
        level2_report_path = work/'level2-report.json'
        level2_command = [
            str(MODULE_DIR/'.venv'/('Scripts/python.exe' if os.name == 'nt' else 'bin/python')),
            str(LEVEL2_SCRIPT),
            '--source-dir', str(input_dir),
            '--output-dir', str(output_dir),
            '--report', str(level2_report_path),
        ]
        if progress_job is not None:
            prefix = f"Cap. {chapter_name}: " if chapter_name else ''
            progress_job.progress_detail = prefix + 'validando Texto Off — Nível II...'
            progress_job.message = progress_job.progress_detail
        try:
            level2_process = subprocess.run(level2_command, cwd=MODULE_DIR, check=False, timeout=900)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Texto Off — Nível II excedeu o limite de 900 segundos. A saída oficial anterior foi preservada.') from exc
        if level2_process.returncode != 0:
            raise RuntimeError(
                f"Texto Off — Nível II encerrou com código {level2_process.returncode}. "
                "A saída oficial anterior foi preservada."
            )
        if not level2_report_path.is_file():
            raise RuntimeError('Texto Off — Nível II não gerou relatório de validação.')
        level2_report = json.loads(level2_report_path.read_text(encoding='utf-8'))
        if int(level2_report.get('pages_analyzed') or 0) != len(images):
            raise RuntimeError('Texto Off — Nível II não analisou todas as imagens do lote.')

        for artifact in sorted(p for p in output_dir.iterdir() if p.is_file()):
            shutil.copy2(artifact, staged/artifact.name)
        shutil.copy2(level1_report_path, staged/'level1-balloon-report.json')
        shutil.copy2(level2_report_path, staged/'level2-report.json')

        manifest = {
            'schema_version': 3,
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
            'authorization': {
            },
            'level1': {
                'algorithm': level1_report.get('algorithm'),
                'policy': level1_report.get('policy'),
                'fail_closed': level1_report.get('fail_closed'),
                'model': level1_report.get('model'),
                'pages_total': level1_report.get('pages_total'),
                'cleaner_mask_pixels': level1_report.get('cleaner_mask_pixels'),
                'authorized_mask_pixels': level1_report.get('authorized_mask_pixels'),
                'authorized_percent': level1_report.get('authorized_percent'),
                'report': 'level1-balloon-report.json',
            },
            'level2': {
                'algorithm': level2_report.get('algorithm'),
                'detector': level2_report.get('detector'),
                'inpainter': level2_report.get('inpainter'),
                'pages_analyzed': level2_report.get('pages_analyzed'),
                'pages_level2': level2_report.get('pages_level2'),
                'components_level2': level2_report.get('components_level2'),
                'type_counts': level2_report.get('type_counts'),
                'report': 'level2-report.json',
            },
            'failures': [],
        }
        (staged/'clean-manifest.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
        _promote_directory(staged, target)
        return {'status':'ok','pages':len(images),'outputs':len(clean_files),'masks':len(mask_files),'mask_complete':True,'level2_pages':int(level2_report.get('pages_level2') or 0),'level2_components':int(level2_report.get('components_level2') or 0),'stage_folder':str(target)}
    finally:
        shutil.rmtree(work, ignore_errors=True)
