#!/usr/bin/env python3
"""Limpa imagens em lote, preservando o perfil e o progresso do Panel Cleaner."""

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

SUPPORTED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp'}
COLOR_PROFILE = Path(__file__).resolve().with_name('preserve-colors.ini')


def get_images(folder: Path) -> list[Path]:
    return sorted(f for f in folder.iterdir()
                  if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS)


def stop_process(process):
    """Encerra também os trabalhadores do lote ao cancelar ou atingir o limite."""
    if os.name == 'posix':
        os.killpg(process.pid, signal.SIGTERM)
    else:
        process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == 'posix':
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.wait()


def clean_images(images: list[Path], output_folder: Path, timeout: int,
                 offline: bool = False, profile: Path = COLOR_PROFILE) -> int:
    command = [sys.executable, '-u', '-m', 'pcleaner.main', 'clean',
               *map(str, images), '-o', str(output_folder), '--profile', str(profile)]
    environment = os.environ.copy()
    if offline:
        environment['HF_HUB_OFFLINE'] = '1'
        environment['TRANSFORMERS_OFFLINE'] = '1'
    started = time.monotonic()
    # Herdar o terminal preserva as barras, inclusive atualizações com retorno de carro.
    with subprocess.Popen(command, env=environment, start_new_session=(os.name == 'posix')) as process:
        try:
            while True:
                remaining = timeout - (time.monotonic() - started)
                if remaining <= 0:
                    stop_process(process)
                    print(f'\nLimite de {timeout}s atingido; o lote foi interrompido.', flush=True)
                    return 1
                try:
                    return process.wait(timeout=min(15, remaining))
                except subprocess.TimeoutExpired:
                    elapsed = int(time.monotonic() - started)
                    print(f'\n[Em execução há {elapsed}s; acompanhe a etapa e os logs acima.]', flush=True)
        except KeyboardInterrupt:
            stop_process(process)
            print('\nProcessamento cancelado.', flush=True)
            return 130


def main():
    parser = argparse.ArgumentParser(description='Limpa balões de mangá em lote')
    parser.add_argument('-i', '--input', default='./input', help='Pasta de entrada')
    parser.add_argument('-o', '--output', default='./output', help='Pasta de saída')
    parser.add_argument('--timeout', type=int, default=900,
                        help='Limite TOTAL do lote em segundos (padrão: 900)')
    parser.add_argument('--offline', action='store_true',
                        help='Usa o OCR já baixado, sem consultas ao Hugging Face')
    parser.add_argument('--profile', type=Path, default=COLOR_PROFILE,
                        help='Perfil de limpeza (padrão: preserve-colors.ini)')
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error('--timeout deve ser maior que zero')
    if not args.profile.is_file():
        parser.error(f'Perfil não encontrado: {args.profile}')
    input_folder = Path(args.input).resolve()
    output_folder = Path(args.output).resolve()
    if not input_folder.is_dir():
        parser.error(f'Pasta de entrada não encontrada: {input_folder}')
    images = get_images(input_folder)
    if not images:
        print('Nenhuma imagem encontrada na pasta de entrada.')
        return 0
    output_folder.mkdir(parents=True, exist_ok=True)
    print(f'MANGA CLEANER\nEntrada: {input_folder}\nSaída: {output_folder}', flush=True)
    print(f'{len(images)} imagem(ns) em um único lote. Limite total: {args.timeout}s.', flush=True)
    print('Etapas: preparação dos modelos → detecção → OCR → máscaras → redução de ruído → exportação.', flush=True)
    print('As barras abaixo pertencem a cada etapa, não ao tempo total.\n'
          'O primeiro uso pode baixar modelos antes de iniciar as barras.', flush=True)
    started = time.monotonic()
    result = clean_images(images, output_folder, args.timeout, args.offline, args.profile.resolve())
    elapsed = time.monotonic() - started
    if result == 0:
        print(f'\nProcessamento encerrado em {elapsed:.1f}s. Resultados: {output_folder}')
    else:
        print(f'\nLote não concluído (código {result}, {elapsed:.1f}s). Veja os logs acima.')
    return result


if __name__ == '__main__':
    sys.exit(main())
