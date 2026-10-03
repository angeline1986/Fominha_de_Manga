import os
import shutil
import subprocess
import tempfile
from pathlib import Path


PROFILE_IDS = frozenset({"poc_a_v1", "poc_b_v1"})


def central_root() -> Path:
    return Path(__file__).resolve().parents[3]


def runtime_dir() -> Path:
    return central_root() / "runtime" / "bubble_sommelier"


def validate_profile_id(profile_id: object) -> str:
    if not isinstance(profile_id, str) or profile_id not in PROFILE_IDS:
        raise ValueError("profile_id ausente ou inválido.")
    return profile_id


def resolve_runtime() -> tuple[str, Path, Path, Path]:
    root = runtime_dir()
    node = shutil.which("node")
    cli = root / "cli.js"
    runner = root / "runner.js"
    model = root / "models" / "detector.onnx"
    modules = root / "node_modules"
    missing = []

    if not node:
        missing.append("node (executável não encontrado no PATH)")
    for required in (cli, runner, model):
        if not required.is_file():
            missing.append(str(required))
    if not modules.is_dir():
        missing.append(str(modules))

    if missing:
        raise RuntimeError(
            "Runtime próprio do BubbleSommelier não está instalado/configurado "
            "em central_v2/runtime/bubble_sommelier. Ausente: "
            + ", ".join(missing)
        )

    return node, cli, model, modules


def run(source: Path, output_dir: Path, profile_id: str) -> subprocess.CompletedProcess:
    profile_id = validate_profile_id(profile_id)
    node, cli, model, modules = resolve_runtime()
    env = os.environ.copy()
    env["NODE_PATH"] = str(modules)
    command = [
        node,
        str(cli),
        "--input", str(source.resolve()),
        "--output", str(output_dir.resolve()),
        "--model", str(model),
        "--profile", profile_id,
    ]

    with tempfile.TemporaryDirectory(prefix="bubble-sommelier-runtime-") as working_directory:
        completed = subprocess.run(
            command,
            cwd=working_directory,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    if completed.returncode:
        diagnostic = "\n".join(
            part.strip() for part in (completed.stdout, completed.stderr) if part.strip()
        )
        raise RuntimeError(
            f"BubbleSommelier falhou para profile {profile_id}: "
            f"{diagnostic[-4000:]}"
        )
    return completed
