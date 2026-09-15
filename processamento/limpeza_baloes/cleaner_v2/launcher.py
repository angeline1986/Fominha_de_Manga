"""Entrada de terminal sem importar as dependências de IA no processo do hub."""
from pathlib import Path
import os
import subprocess

MODULE_DIR = Path(__file__).resolve().parent


def build_command(source: Path, destination: Path, *, offline: bool, progress_file: Path | None = None):
    python = MODULE_DIR / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.is_file():
        raise FileNotFoundError(f'Instale o ambiente do Cleaner V2 conforme {MODULE_DIR / "README.md"}')
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not source.is_dir():
        raise ValueError(f'Pasta de entrada não encontrada: {source}')
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Use pastas de entrada e saída separadas, sem uma estar dentro da outra.')
    command = [str(python), str(MODULE_DIR / 'main.py'), '-i', str(source),
               '-o', str(destination), '--profile', str(MODULE_DIR / 'outlined-text.ini'),
               '--timeout', '900']
    if offline:
        command.append('--offline')
    if progress_file is not None:
        command.extend(['--progress-file', str(Path(progress_file).expanduser().resolve())])
    return command


def run_interactive():
    print('\nCLEANER V2 — limpeza em lote com preservação de cores')
    print('Informe uma pasta de imagens originais ou de merges. Vazio volta ao menu.')
    source = input('Pasta de entrada: ').strip()
    if not source:
        return
    destination = input('Pasta de saída (separada da entrada): ').strip()
    if not destination:
        return
    offline = input('Modelos de OCR já baixados? Usar modo offline [s/N]: ').strip().lower() == 's'
    try:
        command = build_command(Path(source), Path(destination), offline=offline)
        result = subprocess.run(command, cwd=MODULE_DIR, check=False)
        if result.returncode:
            print(f'Cleaner V2 encerrado com código {result.returncode}. Confira os logs acima.')
    except (OSError, ValueError) as exc:
        print(f'Cleaner V2: {exc}')
