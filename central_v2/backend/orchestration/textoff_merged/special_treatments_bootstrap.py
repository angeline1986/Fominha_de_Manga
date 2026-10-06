"""Explicit one-shot bootstrap of derived special-treatment manifests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .auto_cleaner_check_manifest import CHECK_STAGE, MANIFEST_NAME
from .special_treatments_manifest import rebuild_special_treatments


def bootstrap(output_root: Path) -> list[dict]:
    root = output_root.resolve()
    pattern = f"*/*/FLUXO_SECUNDARIO/04_TEXTO_OFF/{CHECK_STAGE}/*/{MANIFEST_NAME}"
    results = []
    for source in sorted(root.glob(pattern)):
        manga, chapter = source.parents[4], source.parent.name
        if not source.resolve().is_relative_to(root):
            raise ValueError("Manifesto Check fora do output autorizado.")
        raw = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"Manifesto Check inválido: {source}")
        document = {"provider": raw.get("provider"), "obra": raw.get("manga"),
                    "capitulo": chapter}
        if (document["provider"] != manga.parent.name
                or document["obra"] != manga.name or raw.get("chapter") != chapter):
            raise ValueError(f"Identidade do Check diverge do caminho: {source}")
        target, payload, written = rebuild_special_treatments(manga, document, chapter)
        results.append({
            "manifest": str(target), "check": str(source), "written": written,
            "degrade": len(payload["treatments"]["degrade"]),
            "artistico": len(payload["treatments"]["estilizado"]),
            "suave": len(payload["treatments"]["gradiente_suave"]),
            "unclassified": payload["unclassified"],
        })
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_root", type=Path)
    args = parser.parse_args()
    print(json.dumps(bootstrap(args.output_root), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
