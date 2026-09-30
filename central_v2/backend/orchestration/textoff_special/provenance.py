"""Record the exact code, configuration and packages used by a preview."""
from importlib import metadata
from pathlib import Path
import platform
import subprocess
import sys

from .artifacts import sha256
from .catalog import ROOT, runtime_folder


def collect(key: str) -> dict:
    lock = runtime_folder(key) / "requirements.lock.txt"
    packages = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.split("==", 1)
        actual = metadata.version(name)
        if actual != expected:
            raise RuntimeError(f"Runtime divergente do lock: {name}={actual}, esperado {expected}.")
        packages[name] = actual
    domain = ROOT / "processamento/limpeza_baloes"
    files = list(Path(__file__).parent.glob("*.py"))
    files.extend(domain.glob("textoff_special_transparent*roi.py"))
    files.extend(domain / name for name in (
        "patch_degrade_experimento.py", "patch_balao_transparente_experimento.py",
        "patch_balao_estilizado_experimento.py", "textoff_special_roi.py",
        "textoff_special_styled_roi.py", "gradiente_suave/gradiente_suave.py",
        "cleaner_v2/preserve-colors.ini",
    ))
    files.extend((domain / "cleaner_v2").glob("*.py"))
    files.append(ROOT / "central_v2/backend/orchestration/textoff_merged/manual_specials.py")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout.strip()
    return {"python": sys.version, "executable": sys.executable, "prefix": sys.prefix,
            "platform": platform.platform(), "lock_sha256": sha256(lock),
            "packages": packages, "commit": revision,
            "code_and_configuration": {str(p.relative_to(ROOT)): sha256(p) for p in sorted(files)}}


def model_records(treatment: dict) -> list[dict]:
    paths = []
    lama = treatment.get("lama", {}).get("model")
    if lama:
        paths.append(Path(lama))
        detector = Path(lama).with_name("comictextdetector.pt")
        if detector.is_file():
            paths.append(detector)
    model = treatment.get("balloon_authorization", {}).get("model")
    if model:
        from huggingface_hub import hf_hub_download
        paths.append(Path(hf_hub_download(repo_id=model["repo"], filename=model["file"],
                                        revision=model["revision"], local_files_only=True)))
    return [{"path": str(path), "sha256": sha256(path)} for path in paths]
