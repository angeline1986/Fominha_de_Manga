from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Iterable

from .service import build_read_state


def get_merge_manual_state(
    manga: Path,
    chapter_dirs: Iterable[Path],
    *,
    review_state_loader: Callable[[Path], dict[str, Any]],
) -> dict[str, Any]:
    """Adapter HTTP independente do servidor concreto.

    O servidor só fornece o estado já calculado para a Revisão Merge; nenhuma
    regra de Auto-Merge é duplicada dentro do Merge Manual.
    """
    return build_read_state(
        manga,
        chapter_dirs,
        review_state_loader=review_state_loader,
    )


from .proposal import generate_proposal, latest_proposal

def generate_merge_manual_proposal_job(manga: Path, chapter_dirs: Iterable[Path], *, review_state_loader: Callable[[Path], dict[str, Any]], payload: dict[str, Any]) -> dict[str, Any]:
    chapter=str(payload.get("chapter") or "")
    selected=[item for item in chapter_dirs if str(item.name)==chapter]
    if len(selected)!=1: raise ValueError("A geração exige exatamente um capítulo.")
    return generate_proposal(manga,selected[0],review_row=review_state_loader(selected[0]),block_id=str(payload.get("block_id") or ""),start_file=str(payload.get("start") or ""),end_file=str(payload.get("end") or ""),cuts=list(payload.get("cuts") or []))

def get_latest_merge_manual_proposal(manga: Path, chapter: str) -> dict[str, Any]:
    return {"ok":True,"proposal":latest_proposal(manga,str(chapter))}


from .finalizer import apply_final_composition

def apply_merge_manual_proposal_job(
    manga: Path,
    chapter_dirs: Iterable[Path],
    *,
    review_state_loader: Callable[[Path], dict[str, Any]],
    payload: dict[str, Any],
) -> dict[str, Any]:
    chapter = str(payload.get("chapter") or "")
    proposal_id = str(payload.get("proposal_id") or "")
    if not proposal_id:
        raise ValueError("proposal_id obrigatório.")
    selected = [item for item in chapter_dirs if str(item.name) == chapter]
    if len(selected) != 1:
        raise ValueError("A efetivação exige exatamente um capítulo.")
    ch = selected[0]
    return apply_final_composition(
        manga,
        ch,
        review_row=review_state_loader(ch),
        proposal_id=proposal_id,
    )
