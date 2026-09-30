"""Prepare experimental Level I/II outputs from read-only MERGE chapters."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from central_v2.backend.orchestration.textoff_merged.level1_cleaner import clean_level1_chapter
from central_v2.backend.orchestration.textoff_merged.runtime import python_for
from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256, write_json


def prepare(manga: Path, chapters: list[str], output: Path) -> dict:
    manga, output = manga.resolve(), output.resolve()
    if output.is_relative_to(manga) or manga.is_relative_to(output):
        raise ValueError("Área experimental deve ser separada da obra.")
    output.mkdir(parents=True, exist_ok=False)
    record = {"schema_version": 1, "source_manga": str(manga),
              "created_at": datetime.now(timezone.utc).isoformat(), "chapters": [],
              "experimental_manga": str(output / "work"), "official_files_modified": False}
    write_json(output / "preparation.json", record)
    os.environ.update(HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    for chapter in chapters:
        if Path(chapter).name != chapter or chapter in {".", "..", ""}:
            raise ValueError("Capítulo inválido.")
        source = manga / "FLUXO_SECUNDARIO/02_MERGE" / chapter
        source_manifest = source / "merge-manifest.json"
        manifest_hash = sha256(source_manifest)
        manifest = read_json(source_manifest)
        names = [row["file"] for row in manifest["outputs"]]
        if len(names) != len(set(names)) or any(Path(name).name != name for name in names):
            raise ValueError("Lista de imagens MERGE inválida.")
        images = [source / name for name in names]
        actual = {p.name for p in source.iterdir() if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}}
        if set(names) != actual or not images:
            raise ValueError("Imagens da pasta divergem do manifesto MERGE.")
        hashes = {str(path): sha256(path) for path in [source_manifest, *images]}
        if hashes[str(source_manifest)] != manifest_hash:
            raise ValueError("Manifesto mudou durante a leitura.")
        merge = output / "work/FLUXO_SECUNDARIO/02_MERGE" / chapter
        merge.mkdir(parents=True)
        for path in images:
            shutil.copyfile(path, merge / path.name)
            if sha256(merge / path.name) != hashes[str(path)]:
                raise ValueError("Snapshot de entrada divergente.")
        level1 = output / "work/FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED_NIVEL_I" / chapter
        level2 = output / "work/FLUXO_SECUNDARIO/04_TEXTO_OFF/MERGED_NIVEL_II" / chapter
        print(f"{chapter}: gerando Nível I em staging", flush=True)
        started = time.monotonic()
        result = clean_level1_chapter([merge / name for name in names], level1,
                                     source_stage="MERGE", progress_job=None, chapter_name=chapter)
        duration1 = round(time.monotonic() - started, 3)
        level2.mkdir(parents=True)
        report = level2 / "json/level2-transparent-report.json"
        command = [str(python_for("merged_nivel_ii")), "-m",
                   "central_v2.backend.orchestration.textoff_merged.level2_transparent",
                   "--source-dir", str(merge), "--level1-dir", str(level1),
                   "--output-dir", str(level2), "--report", str(report)]
        print(f"{chapter}: gerando Nível II em staging", flush=True)
        subprocess.run(command, cwd=ROOT, check=True, timeout=1800)
        report_data = read_json(report)
        if not report_data.get("integrity_ok"):
            raise ValueError("Nível II falhou na validação de integridade.")
        if any(sha256(Path(path)) != expected for path, expected in hashes.items()):
            raise ValueError("As entradas oficiais mudaram durante o teste.")
        record["chapters"].append({"chapter": chapter, "source_hashes": hashes,
                                   "source_images": names, "level1": str(level1),
                                   "level2": str(level2), "level1_result": result,
                                   "level1_seconds": duration1, "level2_report": report_data,
                                   "level1_manifest_sha256": sha256(level1 / "json/clean-manifest.json"),
                                   "level2_report_sha256": sha256(report)})
        write_json(output / "preparation.json", record)
    record["inputs_unchanged"] = all(
        sha256(Path(path)) == expected for row in record["chapters"]
        for path, expected in row["source_hashes"].items()
    )
    record["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json(output / "preparation.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manga", type=Path, required=True)
    parser.add_argument("--chapters", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.manga, args.chapters, args.output)


if __name__ == "__main__":
    main()
