#!/usr/bin/env python3
"""Limpa imagens em lote, preservando o perfil e o progresso do Panel Cleaner."""

import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import threading
import time

SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
COLOR_PROFILE = Path(__file__).resolve().with_name('preserve-colors.ini')
PROGRESS_RE = re.compile(r'(\d{1,3})%\|.*?(\d+)/(\d+)')
_CENTRAL_TQDM_WARNING_PREFIX = re.compile(
    r'^\s*\d{1,3}%\|[^\r\n]*?\b\d+/\d+\s+\[[^\]\r\n]*\]\s*'
    r'(?=\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:\.\d+)?\s+\|\s*'
    r'(?:WARNING|ERROR|CRITICAL)\s*\|)',
    re.IGNORECASE,
)
STAGES = {
    'preparacao': (0.00, 0.10, 'preparando modelos'),
    'deteccao': (0.10, 0.40, 'detectando texto'),
    'ocr': (0.40, 0.55, 'processando OCR'),
    'mascaras': (0.55, 0.75, 'gerando máscaras'),
    'denoise': (0.75, 0.85, 'reduzindo ruído'),
    'exportacao': (0.85, 0.99, 'exportando resultados'),
}

def get_images(folder: Path) -> list[Path]:
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS)

def stop_process(process):
    if os.name == 'posix': os.killpg(process.pid, signal.SIGTERM)
    else: process.terminate()
    try: process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == 'posix': os.killpg(process.pid, signal.SIGKILL)
        else: process.kill()
        process.wait()

def _write_progress(progress_file: Path | None, *, stage: str, stage_progress: float, overall: float, detail: str) -> None:
    if progress_file is None: return
    payload = {
        'stage': stage,
        'stage_progress': max(0.0,min(1.0,float(stage_progress))),
        'overall': max(0.0,min(1.0,float(overall))),
        'detail': detail,
        'updated_at': time.time(),
    }
    progress_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = progress_file.with_name(progress_file.name + '.tmp')
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
    os.replace(tmp, progress_file)

def _stage_from_line(line: str, current: str) -> str:
    if 'Running text detection AI model' in line: return 'deteccao'
    if 'Running box data Preprocessor' in line or 'OCR Analytics' in line: return 'ocr'
    if 'Running Masker' in line: return 'mascaras'
    if 'Running Denoiser' in line: return 'denoise'
    if 'Exporting results' in line: return 'exportacao'
    return current

def _central_event(event: str, **fields) -> None:
    print(json.dumps({'type': 'central_log', 'event': event, **fields},
                     ensure_ascii=False, separators=(',', ':')), flush=True)

def _log_level(line: str) -> str | None:
    match = re.search(r'\b(CRITICAL|ERROR|WARNING)\b', line, re.IGNORECASE)
    return match.group(1).upper() if match else None

def _central_diagnostic_message(line: str) -> str:
    """Remove only a tqdm prefix directly attached to a Pcleaner diagnostic."""
    return _CENTRAL_TQDM_WARNING_PREFIX.sub('', line, count=1).strip()

def clean_images(images: list[Path], output_folder: Path, timeout: int,
                 offline: bool=False, profile: Path=COLOR_PROFILE,
                 progress_file: Path|None=None, central_mode: bool=False) -> int:
    command=[sys.executable,'-u','-m','pcleaner.main','clean',*map(str,images),'-o',str(output_folder),'--profile',str(profile)]
    environment=os.environ.copy()
    if offline:
        environment['HF_HUB_OFFLINE']='1'; environment['TRANSFORMERS_OFFLINE']='1'
    started=time.monotonic()
    _write_progress(progress_file,stage='preparacao',stage_progress=0.0,overall=0.01,detail='preparando Cleaner V2')
    process=subprocess.Popen(command,env=environment,start_new_session=(os.name=='posix'),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,errors='replace')
    state={'stage':'preparacao', 'stage_started':time.monotonic(), 'last_line':''}
    def pump_output():
        buffer=''; stream=process.stdout
        if stream is None: return
        while True:
            chunk=stream.read(1)
            if chunk=='': break
            if not central_mode:
                sys.stdout.write(chunk); sys.stdout.flush()
            if chunk in '\r\n':
                line=buffer; buffer=''
                if not line: continue
                state['last_line']=line
                stage=_stage_from_line(line,state['stage'])
                if stage!=state['stage']:
                    now=time.monotonic()
                    if central_mode:
                        _central_event('stage_completed', stage=state['stage'],
                                       duration_seconds=round(now-state['stage_started'], 3))
                    state['stage']=stage; start,_,detail=STAGES[stage]
                    state['stage_started']=now
                    if central_mode:
                        _central_event('stage_started', stage=stage)
                    _write_progress(progress_file,stage=stage,stage_progress=0.0,overall=start,detail=detail)
                level=_log_level(line)
                if central_mode and level:
                    message=_central_diagnostic_message(line)
                    _central_event('diagnostic', level=level, message=message[-1000:])
                m=PROGRESS_RE.search(line)
                if m:
                    pct=max(0.0,min(1.0,int(m.group(1))/100.0))
                    start,end,detail=STAGES[state['stage']]
                    _write_progress(progress_file,stage=state['stage'],stage_progress=pct,overall=start+((end-start)*pct),detail=detail)
            else:
                buffer+=chunk
        if buffer:
            level=_log_level(buffer)
            if central_mode and level:
                message=_central_diagnostic_message(buffer)
                _central_event('diagnostic', level=level, message=message[-1000:])
    reader=threading.Thread(target=pump_output,name='cleaner-v2-output',daemon=True); reader.start()
    last_heartbeat=-1
    try:
        while True:
            remaining=timeout-(time.monotonic()-started)
            if remaining<=0:
                stop_process(process); reader.join(timeout=2)
                _write_progress(progress_file,stage='erro',stage_progress=0.0,overall=0.0,detail=f'limite de {timeout}s atingido')
                if central_mode: _central_event('failed', error=f'Limite de {timeout}s atingido; o lote foi interrompido.')
                else: print(f'\nLimite de {timeout}s atingido; o lote foi interrompido.',flush=True)
                return 1
            code=process.poll()
            if code is not None:
                reader.join(timeout=2)
                if code==0:
                    _write_progress(progress_file,stage='concluido',stage_progress=1.0,overall=1.0,detail='Cleaner V2 concluído')
                    if central_mode:
                        _central_event('stage_completed', stage=state['stage'],
                                       duration_seconds=round(time.monotonic()-state['stage_started'], 3))
                else: _write_progress(progress_file,stage='erro',stage_progress=0.0,overall=0.0,detail=f'Cleaner V2 encerrou com código {code}')
                if central_mode and code != 0: _central_event('failed', error=f'Cleaner V2 encerrou com código {code}', diagnostic=state['last_line'][-1000:])
                return code
            elapsed=int(time.monotonic()-started)
            if elapsed>0 and elapsed//15!=last_heartbeat:
                last_heartbeat=elapsed//15
                if not central_mode: print(f'\n[Em execução há {elapsed}s; acompanhe a etapa e os logs acima.]',flush=True)
            time.sleep(0.2)
    except KeyboardInterrupt:
        stop_process(process); reader.join(timeout=2)
        _write_progress(progress_file,stage='cancelado',stage_progress=0.0,overall=0.0,detail='processamento cancelado')
        if central_mode: _central_event('failed', error='Processamento cancelado.')
        else: print('\nProcessamento cancelado.',flush=True)
        return 130

def main():
    parser=argparse.ArgumentParser(description='Limpa balões de mangá em lote')
    parser.add_argument('-i','--input',default='./input',help='Pasta de entrada')
    parser.add_argument('-o','--output',default='./output',help='Pasta de saída')
    parser.add_argument('--timeout',type=int,default=900,help='Limite TOTAL do lote em segundos (padrão: 900)')
    parser.add_argument('--offline',action='store_true',help='Usa o OCR já baixado, sem consultas ao Hugging Face')
    parser.add_argument('--profile',type=Path,default=COLOR_PROFILE,help='Perfil de limpeza (padrão: preserve-colors.ini)')
    parser.add_argument('--progress-file',type=Path,default=None,help='Arquivo JSON opcional para progresso estruturado')
    parser.add_argument('--central-mode',action='store_true',help=argparse.SUPPRESS)
    parser.add_argument('--chapter-name',default='',help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.timeout<=0: parser.error('--timeout deve ser maior que zero')
    if not args.profile.is_file(): parser.error(f'Perfil não encontrado: {args.profile}')
    input_folder=Path(args.input).resolve(); output_folder=Path(args.output).resolve()
    progress_file=args.progress_file.resolve() if args.progress_file else None
    if not input_folder.is_dir(): parser.error(f'Pasta de entrada não encontrada: {input_folder}')
    images=get_images(input_folder)
    if not images:
        print('Nenhuma imagem encontrada na pasta de entrada.'); return 0
    output_folder.mkdir(parents=True,exist_ok=True)
    if not args.central_mode:
        print(f'MANGA CLEANER\nEntrada: {input_folder}\nSaída: {output_folder}',flush=True)
        print(f'{len(images)} imagem(ns) em um único lote. Limite total: {args.timeout}s.',flush=True)
        print('Etapas: preparação dos modelos → detecção → OCR → máscaras → redução de ruído → exportação.',flush=True)
        print('As barras abaixo pertencem a cada etapa, não ao tempo total.\nO primeiro uso pode baixar modelos antes de iniciar as barras.',flush=True)
    started=time.monotonic()
    if args.central_mode: _central_event('started', pages=len(images), chapter=args.chapter_name)
    result=clean_images(images,output_folder,args.timeout,args.offline,args.profile.resolve(),progress_file,args.central_mode)
    elapsed=time.monotonic()-started
    if args.central_mode: _central_event('finished' if result==0 else 'failed', result=result, duration_seconds=round(elapsed, 3))
    elif result==0: print(f'\nProcessamento encerrado em {elapsed:.1f}s. Resultados: {output_folder}')
    else: print(f'\nLote não concluído (código {result}, {elapsed:.1f}s). Veja os logs acima.')
    return result

if __name__=='__main__':
    sys.exit(main())
