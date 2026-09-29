"""Run the Merged Level I balloon authorization in its dedicated V2 runtime."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from processamento.limpeza_baloes.cleaner_v2.balloon_authorization import apply_balloon_authorization
from .transparency_artifacts import save_deferred_artifacts


class _Progress:
    def __init__(self, path: Path, chapter: str):
        self.path, self.chapter = path, chapter

    @property
    def progress_detail(self):
        return ""

    @progress_detail.setter
    def progress_detail(self, detail):
        self._write(str(detail))

    @property
    def message(self):
        return ""

    @message.setter
    def message(self, detail):
        self._write(str(detail))

    def _write(self, detail):
        payload = {"chapter": self.chapter, "detail": detail}
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        os.replace(temp, self.path)


def run(request: dict) -> None:
    images = [Path(item).resolve() for item in request["images"]]
    raw_masks = [Path(item).resolve() for item in request["raw_masks"]]
    output_dir = Path(request["output_dir"]).resolve()
    report_path = Path(request["report_path"]).resolve()
    progress_path = Path(request["progress_path"]).resolve()
    report = apply_balloon_authorization(
        images, output_dir, report_path,
        progress_job=_Progress(progress_path, str(request.get("chapter") or "")),
        chapter_name=str(request.get("chapter") or ""),
    )
    if len(images) != len(raw_masks):
        raise ValueError("O lote de máscaras brutas não corresponde às imagens.")
    save_deferred_artifacts(images, raw_masks, output_dir, report)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        run(json.loads(args.request.read_text(encoding="utf-8")))
    except Exception as exc:
        print(f"TextOff Merged Nível I: {exc}", flush=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
