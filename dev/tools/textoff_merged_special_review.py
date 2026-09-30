"""Build a self-contained visual comparison for Merged Levels I–V."""
import argparse
import html
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]


def panel(title: str, path: Path | None, detail: str, images: Path, key: str) -> str:
    if path is None or not path.is_file():
        return f"<figure><figcaption>{html.escape(title)}</figcaption><p>Sem resultado validado.</p></figure>"
    with Image.open(path) as image:
        dimensions = f"{image.width} × {image.height}"
        image.thumbnail((720, 3600))
        thumb = images / f"{key}.jpg"
        image.convert("RGB").save(thumb, format="JPEG", quality=88, optimize=True)
    ref = f"images/{thumb.name}"
    return (f"<figure><figcaption>{html.escape(title)}<small>{html.escape(detail)} · "
            f"{dimensions}</small></figcaption><a href='{ref}' target='_blank'>"
            f"<img src='{ref}' alt='{html.escape(title)}'></a></figure>")


def run_result(report_root: Path, report_name: str, chapter: str) -> tuple[Path | None, str]:
    report = json.loads((report_root / report_name).read_text(encoding="utf-8"))
    item = next(entry for entry in report["results"] if entry["chapter"] == chapter)
    page = item.get("pages", [{}])[0]
    if page.get("status") != "succeeded":
        return None, str((page.get("error") or {}).get("error") or page.get("status"))
    manifest = json.loads((ROOT / page["manifest"]).read_text(encoding="utf-8"))
    result = ROOT / page["run_id"] / manifest["result_file"]
    if not result.is_file():
        result = (ROOT / "reports/experimentos/textoff_especiais_v2" /
                  page["run_id"] / manifest["result_file"])
    validation = manifest.get("validation", {})
    return result, f"alterados {validation.get('changed_pixels', 0)} px; fora da máscara {validation.get('changed_outside_mask', 0)} px"


def stage_image(root: Path, chapter: str, stage: str) -> Path | None:
    folder = root / "FLUXO_SECUNDARIO/04_TEXTO_OFF" / stage / chapter
    manifest_path = folder / "json/clean-manifest.json"
    if not manifest_path.is_file(): manifest_path = folder / "clean-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        artifact = manifest["clean_artifacts"][0]
        parts = Path(artifact).parts
        path = folder.joinpath(*parts) if len(parts) == 2 else folder / "clean" / artifact
        return path if path.is_file() else None
    except (OSError, ValueError, KeyError, IndexError):
        return None


def build(manga: Path, reports: Path, destination: Path) -> None:
    body = ["<h1>TextOff Merged — comparação dos níveis I–V</h1>",
            "<p>Ensaios experimentais em Ch. 1, Ch. 3 e Ch. 4. Nenhum resultado foi promovido. Clique numa imagem para abri-la em tamanho natural.</p>"]
    merge_root = manga / "FLUXO_SECUNDARIO/02_MERGE"
    images = destination.parent / "images"
    images.mkdir(parents=True, exist_ok=True)
    for chapter, filename in (("Ch. 1", "page-024-026.png"),
                              ("Ch. 3", "page-034-038.png"),
                              ("Ch. 4", "page-049-053.png")):
        body.append(f"<h2>{html.escape(chapter)} · {html.escape(filename)}</h2><div class='row'>")
        key = chapter.replace(" ", "-")
        body.append(panel("MERGE", merge_root / chapter / filename, "Entrada original", images, f"{key}-merge"))
        body.append(panel("Nível I", stage_image(manga, chapter, "MERGED_NIVEL_I"), "Base comum", images, f"{key}-i"))
        body.append(panel("Nível II", stage_image(manga, chapter, "MERGED_NIVEL_II"), "Referência atual", images, f"{key}-ii"))
        for level, name in (("III", "level3-protected-test.json"),
                            ("IV", "level4-mask-test.json"),
                            ("V", "level5-mask-test.json")):
            path, detail = run_result(reports, name, chapter)
            body.append(panel(f"Nível {level}", path, detail, images, f"{key}-{level.lower()}"))
        body.append("</div>")
    destination.parent.mkdir(parents=True, exist_ok=True)
    css = "body{background:#171717;color:#eee;font:16px sans-serif;margin:24px} .row{display:flex;overflow:auto;gap:12px} figure{margin:0;padding:12px;background:#242424;min-width:320px} figcaption{font-weight:bold} small{display:block;color:#bbb;margin-top:6px} img{height:680px;width:auto;max-width:44vw;object-fit:contain;background:#111}"
    document = "<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>TextOff I–V</title>"
    document += f"<style>{css}</style><body>{''.join(body)}</body></html>"
    destination.write_text(document, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manga", type=Path, required=True)
    parser.add_argument("--reports", type=Path, default=ROOT / "reports/experimentos/textoff_merged_special_levels")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.manga, args.reports, args.output)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
