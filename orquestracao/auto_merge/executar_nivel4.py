"""Execute Level IV over selected, validated Level III residuals."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import threading

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel4 import materialize_level4
from processamento.unificacao_imagens.auto_merge.nivel3 import read_level3
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import write_json_exclusive
from processamento.unificacao_imagens.auto_merge.planejamento_nivel4 import plan_level4
from processamento.unificacao_imagens.auto_merge.promocao_nivel4 import promote_level4
from orquestracao.auto_merge.consulta_nivel4 import query_level4


def validate_level4_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters or len(chapters) > 100:
        raise ValueError("Selecione de 1 a 100 capítulos.")
    if any(not isinstance(name, str) or not name for name in chapters) or len(set(chapters)) != len(chapters):
        raise ValueError("A seleção contém capítulos inválidos ou repetidos.")
    root = manga / "IMG"
    if not root.is_dir():
        raise ValueError("Obra sem diretório IMG.")
    eligible = {row["chapter"] for row in query_level4(manga, [path.name for path in root.iterdir() if path.is_dir()])}
    if any(name not in eligible for name in chapters):
        raise ValueError("A seleção contém capítulos sem residual elegível do Nível III.")
    return chapters


def _run_chapter(manga: Path, name: str, job_id: str, progress, preflight) -> dict:
    chapter = manga / "IMG" / name
    if chapter.resolve().parent != (manga / "IMG").resolve():
        raise ValueError("Capítulo fora do diretório IMG.")
    preflight()
    if v3.merge_output_dir(chapter).exists():
        raise FileExistsError(f"{name}: destino MERGE oficial existente; nada foi alterado.")
    stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL4" / name
    if stage.exists():
        raise FileExistsError(f"{name}: estágio do Nível IV existente; revisar antes de reexecutar.")
    progress(name, {"stage": "analyze_pages", "message": "Validando residual e imagens-fonte"})
    plan = plan_level4(chapter, lambda event: progress(name, event))
    if not plan["artifacts"] and not plan["residuals"]:
        raise ValueError("O Nível IV não recebeu intervalos para processar.")
    progress(name, {"stage": "analyze_residual", "message": "Composição estrutural concluída"})
    level3_path = plan["level3_dir"] / "merge-level3-manifest.json"
    if hashlib.sha256(level3_path.read_bytes()).hexdigest() != plan["level3_sha256"]:
        raise RuntimeError("O manifesto do Nível III mudou durante a execução.")
    progress(name, {"stage": "materialize", "message": "Gravando somente composição SAFE"})
    artifacts = materialize_level4(chapter, plan["infos"], plan["artifacts"], stage)
    payload = {"schema_version": 1, "algorithm": "merge_level4_directed_structural_safe_v1",
               "chapter": name, "job_id": job_id, "source_dir": str(chapter),
               "output_dir": str(stage), "total_height": plan["total_height"],
               "source_level3_manifest": "merge-level3-manifest.json",
               "source_level3_sha256": plan["level3_sha256"],
               "safe_artifacts": artifacts, "residual_pending_segments": plan["residuals"],
               "diagnostics": plan["diagnostics"],
               "safety": {"level3_safe_artifacts_modified": False, "forced_cut": False,
                          "unsafe_candidate_accepted": False, "inconclusive_candidate_accepted": False,
                          "global_safe_composition_only": True}}
    write_json_exclusive(stage / "merge-level4-manifest.json", payload)
    promoted = False
    if not plan["residuals"]:
        progress(name, {"stage": "promote", "message": "Validando composição dos Níveis I a IV"})
        promote_level4(chapter, payload, stage)
        promoted = True
    progress(name, {"stage": "done", "message": "Capítulo finalizado"})
    pending = plan["residuals"]
    pending_files = sorted({source["file"] for row in pending for source in row.get("source_spans", [])},
                           key=lambda value: v3.natural_key(Path(value)))
    return {"chapter": name, "status": "promoted" if promoted else "partial",
            "resolved_segments": len(artifacts), "saved_files": [row["file"] for row in artifacts],
            "pending_segments": len(pending), "pending_files": pending_files,
            "reason_codes": sorted({row["reason"] for row in pending}),
            "next_stage": "Auto-Merge Nível V" if pending else "—"}


def execute_level4(manga: Path, chapters: list[str], job_id: str, progress, preflight=None) -> list[dict]:
    validate_level4_selection(manga, chapters)
    lock, values = threading.Lock(), {name: 0.0 for name in chapters}

    def report(name: str, event: dict) -> None:
        stage = event.get("stage")
        current = max(0, int(event.get("current") or 0))
        total = max(1, int(event.get("total") or 1))
        if stage == "analyze_pages":
            ratio = .02 + .08 * min(current / total, 1)
        elif stage == "analyze_residual":
            ratio = .10 + .72 * min(current / total, 1)
        else:
            ratio = {"materialize": .86, "promote": .97, "done": 1.0}.get(stage, .01)
        with lock:
            values[name] = max(values[name], ratio)
            count = len(chapters)
            progress(name, {**event, "completed": sum(value == 1 for value in values.values()),
                            "total": count, "value": sum(values.values()), "max": count,
                            "percent": round(sum(values.values()) * 100 / count)})

    def run(index: int, name: str) -> dict:
        report(name, {"stage": "analyze", "message": f"Capítulo {index}/{len(chapters)}: iniciando"})
        try:
            return _run_chapter(manga, name, job_id, report, preflight or (lambda: None))
        except Exception as exc:
            report(name, {"stage": "done", "message": "Capítulo finalizado com ocorrência"})
            return {"chapter": name, "status": "failed", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=min(2, len(chapters)), thread_name_prefix="auto-merge-level4") as worker:
        futures = [worker.submit(run, index, name) for index, name in enumerate(chapters, 1)]
        results = [future.result() for future in as_completed(futures)]
    order = {name: index for index, name in enumerate(chapters)}
    return sorted(results, key=lambda row: order[row["chapter"]])
