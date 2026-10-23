"""Page-scoped Check Reset inputs for the direct Level II execution."""
from pathlib import Path

from central_v2.backend.orchestration.textoff_special.artifacts import sha256
from .reset_check_override import current_reset_base

RESET_BASE_CONTRACT = "check_reset_v1"


def capture_reset_bases(manga, chapter, pages):
    """Capture reset authority for candidates; None entries detect mid-run edits."""
    root = Path(manga).resolve()
    captured = {}
    for page in sorted(pages):
        source = current_reset_base(root, chapter, page)
        captured[page] = ({"path": str(root / source["path"]),
                           "sha256": source["sha256"], "source": source}
                          if source else None)
    return captured


def assert_reset_bases_current(manga, chapter, captured):
    """Reject publication when a candidate's Check Reset changed during Glass."""
    for page, saved in captured.items():
        current = current_reset_base(manga, chapter, page)
        expected = saved.get("source") if isinstance(saved, dict) else None
        if current != expected:
            raise ValueError(f"Reset do Check mudou durante o Nível II: {page}.")
        if saved:
            path = Path(saved["path"]).resolve()
            if (sha256(path) != saved.get("sha256")
                    or saved["sha256"] != current.get("sha256")):
                raise ValueError(f"Imagem de Reset mudou durante o Nível II: {page}.")


def reset_base_contract_current(manga, chapter, manifest, pages):
    """Check the direct Level II Reset contract without affecting legacy consumers."""
    if manifest.get("reset_base_contract") != RESET_BASE_CONTRACT:
        return not any(current_reset_base(manga, chapter, page) for page in pages)
    rows = {row.get("source"): row for row in manifest.get("page_results", [])
            if isinstance(row, dict)}
    return all(rows.get(page, {}).get("reset_base_source")
               == current_reset_base(manga, chapter, page) for page in pages)


def assert_execution_authorities_current(manga, job):
    """Recheck protection and page-reset authorities before Level II publication."""
    source = job["protection_source"]
    assert_protection_source_current(manga, source)
    assert_reset_bases_current(manga, job["chapter"], job.get("reset_bases", {}))


def assert_protection_source_current(manga, source):
    """Retain the original Check protection authority validator."""
    path = Path(manga) / source["path"] if source.get("path") else None
    current = sha256(path) if path and path.is_file() else None
    if current != source.get("sha256"):
        raise ValueError("A fonte de proteções mudou durante a execução do Nível II.")


def load_reset_base(page, reset_bases):
    """Load a captured Check Reset image and its provenance, if the page has one."""
    if reset_bases is not None and page not in reset_bases:
        raise ValueError(f"Snapshot do Reset ausente no Nível II: {page}.")
    saved = (reset_bases or {}).get(page)
    if saved is None:
        return None, None, None
    if (not isinstance(saved, dict) or not isinstance(saved.get("source"), dict)
            or not isinstance(saved.get("path"), str)):
        raise ValueError(f"Fonte de Reset inválida no Nível II: {page}.")
    path = Path(saved["path"]).resolve()
    source = saved["source"]
    if (source.get("kind") != "CHECK_RESET" or Path(source.get("path", "")).name != page
            or source.get("sha256") != saved.get("sha256")
            or sha256(path) != saved.get("sha256")):
        raise ValueError(f"Imagem de Reset inválida no Nível II: {page}.")
    return path, saved["sha256"], source
