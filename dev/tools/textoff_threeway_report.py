"""Portable comparison of Level II and the two special treatments over Level I."""
import argparse
import base64
import html
from io import BytesIO
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256, write_json
from textoff_special_report import STYLE, VIEWER


def verified(path: Path, expected: str) -> Path:
    if sha256(path) != expected:
        raise ValueError(f"Artefato alterado: {path}")
    return path


def panel(label: str, path: Path | None, detail: str, roi: dict | None) -> str:
    result = f"<figure><figcaption>{html.escape(label)}<small>{html.escape(detail)}</small></figcaption>"
    if path is None:
        return result + "<p class='error'>Sem proposta válida.</p></figure>"
    with Image.open(path) as image:
        if roi:
            x, y, width, height = (roi[key] for key in ("x", "y", "width", "height"))
            image = image.crop((x, y, x + width, y + height))
        stream = BytesIO()
        image.save(stream, format="PNG")
    encoded = base64.b64encode(stream.getvalue()).decode("ascii")
    safe = html.escape(label, quote=True)
    return (result + f"<button class='crop' type='button' aria-label='Ampliar {safe}'>"
            f"<img src='data:image/png;base64,{encoded}' alt='{safe}'></button></figure>")


def candidates(source: dict, inventory: dict, matrix: dict) -> list[tuple]:
    identity = source["chapter"], source["filename"]
    references = {r["kind"]: r for r in inventory["references"]
                  if (r["chapter"], r["filename"]) == identity}
    items = []
    merge = references["merge"]
    items.append(("MERGE original", verified(Path(merge["path"]), merge["sha256"]), "Referência"))
    level1 = Path(inventory["local_work_root"]) / source["path_relative_to_work"]
    items.append(("Nível I", verified(level1, source["sha256"]), "Base comum aos testes"))
    level2 = references["level2"]
    items.append(("Nível II", verified(Path(level2["path"]), level2["sha256"]), "Receita atual da V2"))
    for treatment, label in (("transparente_legacy", "Nível I + Transparência Legado"),
                             ("transparente", "Nível I + Transparência normal")):
        matches = [r for r in matrix["runs"] if (r["chapter"], r["filename"]) == identity
                   and r["level"] == "MERGED_NIVEL_I" and r["treatment"] == treatment]
        if len(matches) != 1:
            raise ValueError(f"Execução ausente ou ambígua: {identity}, {treatment}")
        run_path = ROOT / matches[0]["manifest"]
        run = read_json(run_path)
        if run["source"]["sha256"] != source["sha256"] or run["selections"] != source["selections"]:
            raise ValueError("A execução não usou a entrada e as ROIs da comparação.")
        if run["execution_status"] == "succeeded":
            path = verified(run_path.parent / run["result_file"], run["validation"]["result_sha256"])
            detail = f"{run['duration_seconds']} s; fora da máscara: {run['validation']['changed_outside_mask']} pixels"
        else:
            path, detail = None, run.get("error", {}).get("error", "Falha de execução")
        items.append((label, path, detail))
    return items


def build(inventory_path: Path, matrix_path: Path, output: Path) -> None:
    inventory, matrix = read_json(inventory_path), read_json(matrix_path)
    if matrix["inventory_sha256"] != sha256(inventory_path):
        raise ValueError("Inventário divergente da matriz.")
    output.mkdir(parents=True, exist_ok=True)
    body = [f"<h1>{html.escape(inventory['work'])} — comparação de transparência</h1>",
            "<p>Três opções: Nível II, Transparência Legado sobre Nível I e Transparência normal sobre Nível I.</p>",
            "<p>MERGE e Nível I aparecem como referências. Resultados experimentais; nenhum arquivo oficial substituído.</p>",
            "<p>Role horizontalmente para comparar. Clique em uma imagem para ampliar; Esc fecha a ampliação.</p>"]
    for source in inventory["inputs"]:
        body.append(f"<h2>{html.escape(source['chapter'])} · {html.escape(source['filename'])}</h2>")
        items = candidates(source, inventory, matrix)
        for index, roi in enumerate(source["selections"], 1):
            body.append(f"<h3>Região {index}</h3><div class='row'>")
            body.extend(panel(label, path, detail, roi) for label, path, detail in items)
            body.append("</div>")
        body.append("<details><summary>Comparar página completa</summary><div class='row'>")
        body.extend(panel(label, path, detail, None) for label, path, detail in items)
        body.append("</div></details>")
    document = "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
    document += f"<title>Comparação de transparência</title><style>{STYLE}</style><body>"
    document += "\n".join(body) + VIEWER + "</body></html>"
    (output / "index.html").write_text(document, encoding="utf-8")
    write_json(output / "provenance.json", {"inventory_sha256": sha256(inventory_path),
                                           "matrix_sha256": sha256(matrix_path)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--matrix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build(args.inventory, args.matrix, args.output)
    print(args.output / "index.html")


if __name__ == "__main__":
    main()
