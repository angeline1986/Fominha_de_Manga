"""Experimento isolado para balões semitransparentes.

Algoritmo:
    transparent_balloon_lama_text_mask_v1

Estratégia validada experimentalmente:
    1. selecionar uma página IMG;
    2. selecionar manualmente uma região contendo o texto;
    3. detectar componentes escuros compatíveis com texto;
    4. criar máscara base com dilatação 3x3;
    5. ampliar a autorização com elipse 9x9;
    6. executar LaMa usando contexto ao redor;
    7. promover SOMENTE pixels pertencentes à máscara autorizada.

Não altera IMG, 02_MERGE, 04_TEXTO_OFF nem qualquer saída oficial.
Todos os artefatos são gravados em reports/experimentos.
"""

from __future__ import annotations

from pathlib import Path
import json
import os
import re
import subprocess
import time

import cv2
import numpy as np

from processamento.limpeza_baloes import patch_degrade_experimento as base
from processamento.limpeza_baloes.cleaner_v2.balloon_authorization import apply_balloon_authorization


ALGORITHM = "transparent_balloon_lama_text_mask_v1"

TEST_CHAPTER = "Ch. 3"
TEST_PAGES = (
    "page-036.png",
    "page-037.png",
    "page-040.png",
    "page-084.png",
)

OUT = base.OUT / "transparent_balloon_lama_text_mask_v1"


BASE_DILATION = (3, 3)
AUTHORIZED_DILATION = (9, 9)





LAMA_PADDING = 120


def _available_chapters() -> list[Path]:
    root = Path(base.IMG)

    chapters = [
        path
        for path in root.iterdir()
        if path.is_dir() and path.name.startswith("Ch. ")
    ]

    def sort_key(path: Path):
        match = re.search(r"(\d+)", path.name)
        return (
            int(match.group(1)) if match else 10**9,
            path.name,
        )

    return sorted(chapters, key=sort_key)


def _available_pages(chapter: Path) -> list[Path]:
    pages = [
        path
        for path in chapter.iterdir()
        if path.is_file()
        and path.name.startswith("page-")
        and path.suffix.lower() in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }
    ]

    def sort_key(path: Path):
        match = re.search(r"page-(\d+)", path.stem, re.I)
        return (
            int(match.group(1)) if match else 10**9,
            path.name,
        )

    return sorted(pages, key=sort_key)


def _read_image(path: Path) -> np.ndarray:
    image = cv2.imread(str(path))
    if image is None:
        raise RuntimeError(f"Falha ao ler imagem: {path}")
    return image


def _parse_page_selection(raw: str, total: int) -> list[int]:
    selected = []
    seen = set()

    for token in raw.split(","):
        token = token.strip()

        if not token:
            continue

        try:
            value = int(token)
        except ValueError as exc:
            raise ValueError(
                "Use números separados por vírgula, "
                "por exemplo: 1 ou 1,2,3."
            ) from exc

        if not 1 <= value <= total:
            raise ValueError(
                f"Página {value} fora da lista 1..{total}."
            )

        index = value - 1

        if index not in seen:
            selected.append(index)
            seen.add(index)

    if not selected:
        raise ValueError("Nenhuma página selecionada.")

    return selected


def _mask_components(mask: np.ndarray) -> list[dict]:
    binary = (mask > 0).astype(np.uint8)

    count, _, stats, _ = cv2.connectedComponentsWithStats(
        binary,
        connectivity=8,
    )

    components = []

    for component_id in range(1, count):
        x, y, w, h, area = map(
            int,
            stats[component_id],
        )

        components.append(
            {
                "component": component_id,
                "bbox_page": [x, y, w, h],
                "area": area,
            }
        )

    return components


def _detect_text_mask(
    page: Path,
    target: Path,
) -> tuple[np.ndarray, list[dict]]:
    """Obtém automaticamente a máscara detectada pelo Cleaner."""

    cleaner_target = target / "cleaner_stage"

    if cleaner_target.exists():
        import shutil
        shutil.rmtree(cleaner_target)

    cleaner_target.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("1/4 Cleaner: detectando texto e gerando máscara...")

    _, mask_path = base._run_cleaner(
        page,
        cleaner_target,
    )

    cleaner_mask = cv2.imread(
        str(mask_path),
        cv2.IMREAD_GRAYSCALE,
    )

    if cleaner_mask is None:
        raise RuntimeError(
            f"Falha ao ler máscara do Cleaner: {mask_path}"
        )

    original = _read_image(page)

    if cleaner_mask.shape != original.shape[:2]:
        raise RuntimeError(
            "Dimensões divergentes entre IMG e máscara do Cleaner: "
            f"IMG={original.shape[:2]} "
            f"mask={cleaner_mask.shape}"
        )

    raw_components = _mask_components(cleaner_mask)

    if not raw_components:
        raise RuntimeError(
            "Cleaner não detectou componentes de texto."
        )

    raw_pixels = int(np.count_nonzero(cleaner_mask))
    print(f"    componentes Cleaner: {len(raw_components)}")
    print("    pixels Cleaner:", raw_pixels)

    print("2/5 Balloon Authorization: filtrando texto fora de balões...")
    authorization_path = target / "balloon_authorization.json"
    authorization = apply_balloon_authorization(
        [page], mask_path.parent, authorization_path
    )

    authorized_cleaner_mask = cv2.imread(
        str(mask_path), cv2.IMREAD_GRAYSCALE
    )
    if authorized_cleaner_mask is None:
        raise RuntimeError(
            f"Falha ao reler máscara autorizada: {mask_path}"
        )

    components = _mask_components(authorized_cleaner_mask)
    authorized_cleaner_pixels = int(np.count_nonzero(authorized_cleaner_mask))
    authorized_component_count = sum(
        int(p.get("components_authorized", 0))
        for p in authorization.get("pages", [])
    )
    print("    componentes autorizados:", authorized_component_count)
    print("    pixels após Balloon Authorization:", authorized_cleaner_pixels)

    if authorized_cleaner_pixels == 0:
        raise RuntimeError(
            "Balloon Authorization não autorizou nenhum componente; nenhuma reconstrução será executada."
        )

    print("3/5 Máscara de texto: dilatação base 3x3...")

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        BASE_DILATION,
    )

    base_mask = cv2.dilate(
        authorized_cleaner_mask,
        kernel,
        iterations=1,
    )

    authorization_summary = {
        "report": authorization_path.name,
        "algorithm": authorization.get("algorithm"),
        "policy": authorization.get("policy"),
        "cleaner_components": len(raw_components),
        "authorized_components": authorized_component_count,
        "cleaner_mask_pixels": raw_pixels,
        "authorized_cleaner_mask_pixels": authorized_cleaner_pixels,
        "authorized_percent": authorization.get("authorized_percent", 0.0),
        "pages": authorization.get("pages", []),
    }

    return base_mask, components, authorization_summary


def _authorize_mask(base_mask: np.ndarray) -> np.ndarray:
    """Ampliação 9x9 validada no P3C/P16-B/P20."""

    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        AUTHORIZED_DILATION,
    )

    return cv2.dilate(
        base_mask,
        kernel,
        iterations=1,
    )


def _write_mask_overlay(
    image: np.ndarray,
    mask: np.ndarray,
    target: Path,
) -> None:
    overlay = image.copy()

    visible = mask > 0

    if np.any(visible):
        highlighted = overlay.copy()
        highlighted[visible] = (255, 255, 255)

        overlay = cv2.addWeighted(
            overlay,
            0.70,
            highlighted,
            0.30,
            0,
        )

    if not cv2.imwrite(str(target), overlay):
        raise RuntimeError(
            f"Falha ao gravar overlay: {target}"
        )


def _run_lama_worker(
    source: Path,
    mask_path: Path,
    result_path: Path,
    metadata_path: Path,
) -> None:
    """Executa LaMa no Python isolado já existente do Cleaner V2."""

    worker = result_path.parent / "_lama_worker.py"

    worker.write_text(
        r'''
from pathlib import Path
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image
import torch

source = Path(sys.argv[1])
mask_path = Path(sys.argv[2])
result_path = Path(sys.argv[3])
metadata_path = Path(sys.argv[4])
cleaner_dir = Path(sys.argv[5])
padding = int(sys.argv[6])

sys.path.insert(0, str(cleaner_dir.parent))

import cleaner_v2.level2 as level2

image = cv2.imread(str(source))
mask = cv2.imread(str(mask_path), cv2.IMREAD_GRAYSCALE)

if image is None:
    raise RuntimeError(f"Falha ao ler imagem: {source}")

if mask is None:
    raise RuntimeError(f"Falha ao ler máscara: {mask_path}")

if mask.shape != image.shape[:2]:
    raise RuntimeError(
        f"Dimensões divergentes: image={image.shape[:2]} mask={mask.shape}"
    )

ys, xs = np.where(mask > 0)

if len(xs) == 0:
    raise RuntimeError("Máscara autorizada vazia.")

model_path = level2._find_model()

os.environ["LAMA_MODEL"] = str(model_path)

device = (
    torch.device("mps")
    if torch.backends.mps.is_available()
    else torch.device("cpu")
)

model = level2.SimpleLama(device=device)

x1 = max(0, int(xs.min()) - padding)
y1 = max(0, int(ys.min()) - padding)
x2 = min(image.shape[1], int(xs.max()) + padding + 1)
y2 = min(image.shape[0], int(ys.max()) + padding + 1)

crop = image[y1:y2, x1:x2]
crop_mask = mask[y1:y2, x1:x2]

crop_rgb = cv2.cvtColor(
    crop,
    cv2.COLOR_BGR2RGB,
)

pil_image = Image.fromarray(crop_rgb)
pil_mask = Image.fromarray(crop_mask)

lama = model(
    pil_image,
    pil_mask,
)

if lama.size != pil_image.size:
    lama = lama.crop(
        (
            0,
            0,
            pil_image.width,
            pil_image.height,
        )
    )

lama_np = cv2.cvtColor(
    np.asarray(lama),
    cv2.COLOR_RGB2BGR,
)

final = image.copy()

target = final[y1:y2, x1:x2]
authorized = crop_mask > 0

target[authorized] = lama_np[authorized]

final[y1:y2, x1:x2] = target

difference = cv2.absdiff(
    image,
    final,
)

changed = np.any(
    difference != 0,
    axis=2,
)

outside = changed & ~(mask > 0)

outside_count = int(
    np.count_nonzero(outside)
)

if outside_count:
    raise RuntimeError(
        "Falha de segurança: "
        f"{outside_count} pixel(s) alterado(s) fora da máscara."
    )

if not cv2.imwrite(str(result_path), final):
    raise RuntimeError(
        f"Falha ao gravar resultado: {result_path}"
    )

metadata = {
    "model": str(model_path),
    "device": str(device),
    "padding": padding,
    "mask_pixels": int(
        np.count_nonzero(mask)
    ),
    "changed_pixels": int(
        np.count_nonzero(changed)
    ),
    "changed_outside_mask": outside_count,
    "crop": [x1, y1, x2, y2],
}

metadata_path.write_text(
    json.dumps(
        metadata,
        indent=2,
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
'''.lstrip(),
        encoding="utf-8",
    )

    command = [
        str(base.CLEANER_PY),
        str(worker),
        str(source),
        str(mask_path),
        str(result_path),
        str(metadata_path),
        str(base.CLEANER_DIR),
        str(LAMA_PADDING),
    ]

    proc = subprocess.run(
        command,
        cwd=str(base.CLEANER_DIR),
        check=False,
    )

    if proc.returncode:
        raise RuntimeError(
            "LaMa experimental falhou com código "
            f"{proc.returncode}. "
            "O ambiente do Cleaner não foi modificado."
        )


def _run_page(
    page: Path,
) -> Path:
    chapter_name = page.parent.name
    target = OUT / chapter_name / page.stem

    target.mkdir(
        parents=True,
        exist_ok=True,
    )

    started = time.monotonic()
    original = _read_image(page)

    base_mask, components, balloon_authorization = _detect_text_mask(
        page,
        target,
    )

    print("4/5 Autorização: ampliando máscara com elipse 9x9...")

    authorized_mask = _authorize_mask(
        base_mask,
    )

    base_pixels = int(
        np.count_nonzero(base_mask)
    )

    authorized_pixels = int(
        np.count_nonzero(authorized_mask)
    )

    if base_pixels == 0:
        raise RuntimeError(
            "Máscara de texto vazia após o Cleaner."
        )

    base_mask_path = target / "01_text_mask.png"
    authorized_mask_path = target / "02_authorized_mask_9x9.png"
    overlay_path = target / "03_authorized_mask_overlay.png"
    result_path = target / "04_lama_text_only.png"
    worker_metadata_path = target / "lama_metadata.json"

    if not cv2.imwrite(
        str(base_mask_path),
        base_mask,
    ):
        raise RuntimeError(
            f"Falha ao gravar {base_mask_path}"
        )

    if not cv2.imwrite(
        str(authorized_mask_path),
        authorized_mask,
    ):
        raise RuntimeError(
            f"Falha ao gravar {authorized_mask_path}"
        )

    _write_mask_overlay(
        original,
        authorized_mask,
        overlay_path,
    )

    print()
    print("Máscara:")
    print(
        f"  componentes detectados . {len(components)}"
    )
    print(
        f"  pixels base ............. {base_pixels}"
    )
    print(
        f"  pixels autorizados ...... {authorized_pixels}"
    )

    print()
    print(
        "5/5 LaMa: reconstruindo somente "
        "a região autorizada..."
    )

    _run_lama_worker(
        page,
        authorized_mask_path,
        result_path,
        worker_metadata_path,
    )

    worker_metadata = json.loads(
        worker_metadata_path.read_text(
            encoding="utf-8",
        )
    )

    run = {
        "schema_version": 1,
        "algorithm": ALGORITHM,
        "experimental": True,
        "official_files_modified": False,
        "source": str(page),
        "chapter": chapter_name,
        "selection_mode": "automatic_cleaner_mask_balloon_authorized",
        "balloon_authorization": balloon_authorization,
        "base_dilation": list(BASE_DILATION),
        "authorized_dilation": list(AUTHORIZED_DILATION),
        "lama_padding": LAMA_PADDING,
        "components": components,
        "base_mask_pixels": base_pixels,
        "authorized_mask_pixels": authorized_pixels,
        "lama": worker_metadata,
        "artifacts": {
            "text_mask": base_mask_path.name,
            "authorized_mask": authorized_mask_path.name,
            "overlay": overlay_path.name,
            "result": result_path.name,
        },
        "elapsed_seconds": round(
            time.monotonic() - started,
            3,
        ),
    }

    report_path = target / "run.json"

    report_path.write_text(
        json.dumps(
            run,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print("Resultado:")
    print(result_path)

    print()
    print("Overlay da máscara:")
    print(overlay_path)

    print()
    print("Relatório:")
    print(report_path)

    print()
    print(
        "Alterações fora da máscara:",
        worker_metadata["changed_outside_mask"],
    )

    print("Nenhum arquivo oficial foi alterado.")

    return result_path


def run() -> None:
    print()
    print("PATCH BALÃO TRANSPARENTE · EXPERIMENTO ISOLADO")
    print()
    print("Obra: Candy YumYum (Yaoi)")
    print(
        "Pipeline: IMG → Cleaner temporário → Balloon Authorization → "
        "máscara 3x3 → autorização 9x9 → LaMa"
    )
    print(
        "A página IMG original é somente leitura. "
        "Os resultados ficam em reports/experimentos."
    )

    chapters = _available_chapters()

    if not chapters:
        print()
        print(
            f"Nenhum capítulo encontrado em {Path(base.IMG)}"
        )
        return

    print()
    print("Selecione o capítulo:")
    print()

    for index, chapter in enumerate(
        chapters,
        start=1,
    ):
        print(
            f"[{index}] {chapter.name}"
        )

    print("[0] Voltar")

    raw = input(
        "\nCapítulo › "
    ).strip()

    if raw == "0":
        return

    try:
        chapter = chapters[int(raw) - 1]
    except (ValueError, IndexError):
        print("Seleção inválida.")
        return

    pages = _available_pages(chapter)

    if not pages:
        print()
        print(
            f"Nenhuma página encontrada em {chapter}"
        )
        return

    print()
    print(chapter.name)
    print()

    for index, page in enumerate(
        pages,
        start=1,
    ):
        print(
            f"[{index}] {page.name}"
        )

    print()

    raw = input(
        "Páginas (ex.: 1 ou 1,2,3; 0=Voltar) › "
    ).strip()

    if raw == "0":
        return

    try:
        indexes = _parse_page_selection(
            raw,
            len(pages),
        )
    except ValueError as exc:
        print()
        print(
            f"Seleção inválida: {exc}"
        )
        return

    selected = [
        pages[index]
        for index in indexes
    ]

    completed = 0
    failures = []

    for page in selected:
        print()
        print(
            f"--- {chapter.name} · {page.name} ---"
        )

        try:
            _run_page(page)
            completed += 1
        except Exception as exc:
            failures.append(
                (page.name, str(exc))
            )

            print()
            print(
                f"Falha em {page.name}: {exc}"
            )

    print()
    print(
        "Processamento concluído: "
        f"{completed}/{len(selected)} página(s)."
    )

    if failures:
        print()
        print("Falhas:")

        for page_name, error in failures:
            print(
                f"  - {page_name}: {error}"
            )

    print()
    print("Nenhum arquivo oficial foi alterado.")


def run_transparent_balloon_experiment():
    return run()
