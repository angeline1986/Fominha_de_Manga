"""Fluxo independente de Merge Manual.

O módulo não promove artefatos para 02_MERGE no Patch 1. A responsabilidade
inicial é somente expor/validar a faixa residual autoritativa encaminhada pela
Revisão Merge.
"""

from .service import build_read_state

__all__ = ["build_read_state"]
