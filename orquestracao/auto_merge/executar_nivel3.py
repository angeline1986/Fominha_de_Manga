"""Coordinate V2 Level III planning, materialization and safe promotion."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import threading

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel3 import materialize_level3
from processamento.unificacao_imagens.auto_merge.nivel2 import read_level2
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import write_json_exclusive
from processamento.unificacao_imagens.auto_merge.planejamento_nivel3 import plan_level3
from processamento.unificacao_imagens.auto_merge.promocao_nivel3 import promote_level3
from orquestracao.auto_merge.consulta_nivel3 import query_level3


def validate_level3_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters or len(chapters) > 100:
        raise ValueError("Selecione de 1 a 100 capítulos.")
    if (any(not isinstance(name, str) or not name for name in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ValueError("A seleção contém capítulos inválidos ou repetidos.")
    root = manga / "IMG"
    if not root.is_dir():
        raise ValueError("Obra sem diretório IMG.")
    available = {row["chapter"] for row in query_level3(
        manga, [path.name for path in root.iterdir() if path.is_dir()]
    )}
    if any(name not in available for name in chapters):
        raise ValueError("A seleção contém capítulos sem residual elegível do Nível II.")
    return chapters


def _pending_files(residuals: list[dict]) -> list[str]:
    return sorted({name for item in residuals for name in item.get("sources", [])},
                  key=lambda value: v3.natural_key(Path(value)))


def _run_chapter(manga: Path, name: str, job_id: str, progress, preflight) -> dict:
    chapter = manga / "IMG" / name
    if chapter.resolve().parent != (manga / "IMG").resolve():
        raise ValueError("Capítulo fora do diretório IMG.")
    preflight()
    if v3.merge_output_dir(chapter).exists():
        raise FileExistsError(f"{name}: destino MERGE oficial existente; nada foi alterado.")
    stage = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL3" / name
    if stage.exists():
        raise FileExistsError(f"{name}: estágio do Nível III existente; revisar antes de reexecutar.")
    progress(name, {"stage": "analyze_pages", "message": "Validando resíduos e imagens-fonte"})
    plan = plan_level3(chapter, progress_callback=lambda event: progress(name, event))
    if not plan["intervals"] and not plan["residuals"]:
        raise ValueError("O Nível III não recebeu intervalos para processar.")
    progress(name, {"stage": "materialize", "message": "Gravando somente trechos estruturalmente seguros"})
    artifacts = materialize_level3(chapter, plan["infos"], plan["intervals"], stage)
    level2_file = plan["level2_dir"] / "merge-level2-manifest.json"
    latest_level2 = read_level2(manga, name)
    if (latest_level2.status != "recorded"
            or hashlib.sha256(level2_file.read_bytes()).hexdigest() != plan["level2_sha256"]):
        raise RuntimeError("O manifesto do Nível II mudou durante a execução; publicação cancelada.")
    config = plan["config"]
    payload = {
        "schema_version": 1, "algorithm": "merge_level3_structural_safe_v1",
        "chapter": name, "job_id": job_id,
        "source_dir": str(chapter), "output_dir": str(stage),
        "total_height": plan["total_height"],
        "source_level2_manifest": "merge-level2-manifest.json",
        "source_level2_sha256": plan["level2_sha256"],
        "safe_artifacts": artifacts,
        "residual_pending_segments": plan["residuals"],
        "diagnostics": plan["diagnostics"],
        "policy": {"max_chunk_height": v3.DEFAULT_MAX_CHUNK_HEIGHT,
                   "analysis_half_window": config.analysis_half_window,
                   "local_search_radius": config.local_search_radius,
                   "local_search_step": config.local_search_step,
                   "continuous_scene_max_height": config.continuous_scene_max_height},
        "safety": {"level2_artifacts_modified": False, "forced_cut": False,
                   "inconclusive_local_search_allowed": False},
    }
    write_json_exclusive(stage / "merge-level3-manifest.json", payload)
    promoted = False
    if not plan["residuals"]:
        progress(name, {"stage": "promote", "message": "Validando composição dos Níveis I, II e III"})
        promote_level3(chapter, payload, stage)
        promoted = True
    residual_files = _pending_files(plan["residuals"])
    progress(name, {"stage": "done", "message": "Capítulo finalizado: " + ("promoted" if promoted else "partial")})
    return {
        "chapter": name, "status": "promoted" if promoted else "partial",
        "resolved_segments": len(artifacts), "saved_files": [item["file"] for item in artifacts],
        "pending_segments": len(plan["residuals"]), "pending_files": residual_files,
        "residuals": [{"global_start": item["global_start"], "global_end": item["global_end"]}
                      for item in plan["residuals"]],
        "reason_codes": sorted({item["reason"] for item in plan["residuals"]}),
        "next_stage": "Auto-Merge Nível IV" if plan["residuals"] else "—",
    }


def execute_level3(manga: Path, chapters: list[str], job_id: str, progress, preflight=None) -> list[dict]:
    validate_level3_selection(manga, chapters)
    lock, values = threading.Lock(), {name: 0.0 for name in chapters}

    def report(name: str, event: dict) -> None:
        stage = event.get("stage")
        current, total = max(0, int(event.get("current") or 0)), max(1, int(event.get("total") or 1))
        ratio = {"analyze_pages": .05 + .20 * min(current / total, 1),
                 "analyze_residual": .28 + .50 * min(current / total, 1),
                 "materialize": .84, "promote": .97, "done": 1.0}.get(stage, .01)
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

    with ThreadPoolExecutor(max_workers=min(2, len(chapters)), thread_name_prefix="auto-merge-level3") as worker:
        futures = [worker.submit(run, index, name) for index, name in enumerate(chapters, 1)]
        results = [future.result() for future in as_completed(futures)]
    order = {name: index for index, name in enumerate(chapters)}
    return sorted(results, key=lambda item: order[item["chapter"]])
