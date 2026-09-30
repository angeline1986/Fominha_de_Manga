"""Build a local visual comparison from immutable inputs and recorded previews."""
import argparse
import base64
import html
from pathlib import Path
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from central_v2.backend.orchestration.textoff_special.artifacts import read_json, sha256, write_json

STYLE = """
body { margin: 24px; font: 15px system-ui; color: #ddd; background: #18191b; }
h1 { font-size: 24px; } h2 { margin-top: 36px; }
.row { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 16px; }
figure { flex: 0 0 380px; margin: 0; background: #24262a; padding: 10px; }
img { display: block; width: 380px; height: auto; margin-top: 8px; }
figcaption { min-height: 52px; } small { display: block; margin-top: 6px; }
a { color: #94caff; } .error { color: #ffcf9e; }
.crop { border: 0; padding: 0; background: transparent; cursor: zoom-in; }
dialog { max-width: 95vw; max-height: 95vh; overflow: auto; background: #24262a; color: #ddd; }
dialog::backdrop { background: #000b; }
dialog img { width: auto; max-width: none; }
dialog button { position: sticky; top: 0; cursor: pointer; }
"""

VIEWER = """
<dialog aria-label="Recorte em tamanho natural">
  <form method="dialog"><button>Fechar ampliação (Esc)</button></form>
  <img alt="">
</dialog>
<script>
const viewer = document.querySelector('dialog');
document.querySelectorAll('.crop').forEach(button => {
  button.addEventListener('click', () => {
    const source = button.querySelector('img');
    const target = viewer.querySelector('img');
    target.src = source.src;
    target.alt = source.alt;
    viewer.showModal();
    viewer.scrollTop = 0;
    viewer.scrollLeft = 0;
  });
});
</script>
"""


def build(inventory_path: Path, matrix_path: Path, output: Path) -> None:
    inventory, matrix = read_json(inventory_path), read_json(matrix_path)
    if matrix["inventory_sha256"] != sha256(inventory_path):
        raise ValueError("Inventário divergente da matriz.")
    output.mkdir(parents=True, exist_ok=True)
    root = Path(inventory["local_work_root"])
    body = ["<h1>TextOff — comparação dos casos especiais</h1>",
            "<p>Entradas I e II preservadas. Quatro propostas por página; "
            "sem promoção. Clique em um recorte para vê-lo em tamanho natural.</p>",
            "<p>Revisão visual pendente. Diferença de pixels não mede qualidade.</p>"]
    run_index = {(r["filename"], r["level"], r["treatment"]): r for r in matrix["runs"]}
    sources = {(s["filename"], s["level"]): s for s in inventory["inputs"]}
    for filename in dict.fromkeys(s["filename"] for s in inventory["inputs"]):
        body.append(f"<h2>{html.escape(filename)}</h2>")
        first = sources[(filename, "MERGED_NIVEL_I")]
        candidates = []
        for level in ("MERGED_NIVEL_I", "MERGED_NIVEL_II"):
            source = sources[(filename, level)]
            path = root / source["path_relative_to_work"]
            if sha256(path) != source["sha256"]:
                raise ValueError("Entrada alterada após a matriz.")
            label = f"{level} — entrada" if level.endswith("_I") else f"{level} — referência atual"
            candidates.append((label, path, ""))
        for level in ("MERGED_NIVEL_I", "MERGED_NIVEL_II"):
            for treatment in ("transparente", "transparente_legacy"):
                row = run_index.get((filename, level, treatment))
                label = f"{level} + {treatment}"
                path, detail = None, "Execução pendente."
                if row:
                    manifest_path = ROOT / row["manifest"]
                    run = read_json(manifest_path)
                    if run["execution_status"] == "succeeded":
                        path = manifest_path.parent / run["result_file"]
                        if sha256(path) != run["validation"]["result_sha256"]:
                            raise ValueError("Resultado alterado após a validação.")
                        detail = f"{run['duration_seconds']} s; {run['validation']['changed_pixels']} pixels alterados."
                    else:
                        detail = run.get("error", {}).get("error", "Execução falhou.")
                candidates.append((label, path, detail))
        for index, roi in enumerate(first["selections"], 1):
            body.append(f"<h3>Região {index}</h3><div class='row'>")
            for column, (label, path, detail) in enumerate(candidates):
                body.append(f"<figure><figcaption>{html.escape(label)}<small>{html.escape(detail)}</small></figcaption>")
                if path:
                    crop_name = f"{Path(filename).stem}-roi{index}-{column}.png"
                    with Image.open(path) as image:
                        x, y, w, h = (roi[k] for k in ("x", "y", "width", "height"))
                        image.crop((x, y, x + w, y + h)).save(output / crop_name)
                    encoded = base64.b64encode((output / crop_name).read_bytes()).decode("ascii")
                    alt = html.escape(label, quote=True)
                    body.append(f"<button class='crop' type='button' aria-label='Ampliar {alt}'>"
                                f"<img src='data:image/png;base64,{encoded}' alt='{alt}'></button>")
                else:
                    body.append("<p class='error'>Sem proposta válida.</p>")
                body.append("</figure>")
            body.append("</div>")
    document = "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
    document += f"<title>TextOff — comparação</title><style>{STYLE}</style><body>"
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
