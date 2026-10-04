import json
import os
import shutil
import subprocess
import tempfile
import threading
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


def run(
    source: Path,
    output_dir: Path,
    profile_id: str,
    *,
    on_progress=None,
    progress_context: dict | None = None,
) -> subprocess.CompletedProcess:
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
    for key, value in (progress_context or {}).items():
        if key in {"provider", "manga", "chapter"} and value is not None:
            env[f"BUBBLE_SOMMELIER_{key.upper()}"] = str(value)

    with tempfile.TemporaryDirectory(prefix="bubble-sommelier-runtime-") as working_directory:
        process = subprocess.Popen(
            command,
            cwd=working_directory,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_lines = []
        stderr_lines = []
        stderr_reader = threading.Thread(
            target=lambda: stderr_lines.extend(process.stderr),
            name="bubble-sommelier-stderr",
            daemon=True,
        )
        stderr_reader.start()
        try:
            for line in process.stdout:
                stdout_lines.append(line)
                try:
                    message = json.loads(line)
                except (TypeError, ValueError):
                    continue
                if isinstance(message, dict) and message.get("type") == "progress" and on_progress:
                    on_progress(message.get("payload") or {})
            returncode = process.wait()
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.wait()
            stderr_reader.join()
            raise
        stderr_reader.join()
        completed = subprocess.CompletedProcess(
            command,
            returncode,
            "".join(stdout_lines),
            "".join(stderr_lines),
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
