"""Run the V2 Level II use case using the authoritative Level I manifest."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import threading
from datetime import datetime, timezone

from processamento.unificacao_imagens import image_stitcher as v3
from processamento.unificacao_imagens.auto_merge.materializacao_nivel2 import materialize_level2
from processamento.unificacao_imagens.auto_merge.nivel1 import read_level1
from processamento.unificacao_imagens.auto_merge.persistencia_nivel1 import write_json_exclusive
from processamento.unificacao_imagens.auto_merge.planejamento_nivel2 import plan_level2
from processamento.unificacao_imagens.auto_merge.promocao_nivel2 import promote_level2


def validate_level2_selection(manga: Path, chapters: object) -> list[str]:
    if not isinstance(chapters, list) or not chapters or len(chapters) > 100:
        raise ValueError("Selecione de 1 a 100 capítulos.")
    if any(not isinstance(name, str) or not name for name in chapters) or len(set(chapters)) != len(chapters):
        raise ValueError("A seleção contém capítulos inválidos ou repetidos.")
    root = manga / "IMG"
    if not root.is_dir():
        raise ValueError("Obra sem diretório IMG.")
    from orquestracao.auto_merge.consulta_nivel2 import query_level2
    available = {row["chapter"] for row in query_level2(
        manga, [path.name for path in root.iterdir() if path.is_dir()]
    )}
    if any(name not in available for name in chapters):
        raise ValueError("A seleção contém capítulos sem residual elegível do Nível I.")
    return chapters


def _pending(plans: list) -> list[dict]:
    result = []
    for entry in plans:
        interval = entry["plan"].get("residual_interval")
        if interval:
            result.append({
                "id": entry["segment_id"],
                "global_start": int(interval[0]),
                "global_end": int(interval[1]),
                "reason": "level2_no_complete_safe_path",
            })
    return result


def _manifest(chapter: Path, plan: dict, artifacts: list, pending: list, job_id: str) -> dict:
    config = plan["config"]
    return {
        "schema_version": 3,
        "algorithm": "merge_level2_bounded_safe_path_v1",
        "chapter": chapter.name,
        "job_id": job_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_height": plan["total_height"],
        "source_auto_merge_manifest": "auto-merge-manifest.json",
        "source_level1_sha256": plan["manifest_sha256"],
        "artifacts": artifacts,
        "pending_segments": pending,
        "coverage": {"level2_segments": [[x["global_start"], x["global_end"]] for x in artifacts]},
        "diagnostics": [
            {"segment_id": x["segment_id"], "source": x["source"], **x["plan"]}
            for x in plan["plans"]
        ],
        "policy": {
            "target_height": config.target_height,
            "min_chunk_height": config.min_chunk_height,
            "max_chunk_height": config.max_chunk_height,
            "preferred_source_files_per_merge": config.preferred_source_files,
            "preferred_source_files_is_safety_rule": False,
            "edge_chunk_scope": "residual_start_or_end_only",
            "edge_chunk_is_last_fallback": True,
        },
        "safety": {
            "level1_artifacts_modified": False,
            "v3_thresholds_relaxed": False,
            "forced_cut": False,
        },
    }


def _run_chapter(manga: Path, name: str, job_id: str, progress, preflight) -> dict:
    chapter = manga / "IMG" / name
    if chapter.resolve().parent != (manga / "IMG").resolve():
        raise ValueError("Capítulo fora do diretório IMG.")
    preflight()
    official = v3.merge_output_dir(chapter)
    if official.exists():
        raise FileExistsError(f"{name}: destino MERGE oficial existente; nada foi alterado.")
    root = manga / "FLUXO_SECUNDARIO" / "01_MERGE_PROCESSAMENTO" / "MERGE_LEVEL2"
    stage = root / name
    if stage.exists():
        raise FileExistsError(f"{name}: estágio do Nível II existente; revisar antes de reexecutar.")
    progress(name, {"stage": "analyze_pages", "message": "Validando residual e analisando fontes"})
    plan = plan_level2(chapter, progress_callback=lambda event: progress(name, event))
    pending = _pending(plan["plans"])
    pending_files = sorted({
        info.path.name for segment in pending for info in plan["infos"]
        if min(segment["global_end"], info.global_end)
        > max(segment["global_start"], info.global_start)
    }, key=lambda name: v3.natural_key(Path(name)))
    root.mkdir(parents=True, exist_ok=True)
    progress(name, {"stage": "materialize", "message": "Gravando apenas intervalos seguros"})
    artifacts = materialize_level2(chapter, plan["infos"], plan["plans"], stage)
    source_manifest = plan["level1_dir"] / "auto-merge-manifest.json"
    if hashlib.sha256(source_manifest.read_bytes()).hexdigest() != plan["manifest_sha256"]:
        raise RuntimeError("O manifesto do Nível I mudou durante a execução; publicação cancelada.")
    payload = _manifest(chapter, plan, artifacts, pending, job_id)
    write_json_exclusive(stage / "merge-level2-manifest.json", payload)
    status = "partial" if pending else "resolved"
    if not pending:
        progress(name, {"stage": "promote", "message": "Validando e promovendo composição I + II"})
        promote_level2(chapter, plan["manifest"], plan["level1_dir"], payload, stage)
        status = "promoted"
    progress(name, {"stage": "done", "message": f"Capítulo finalizado: {status}"})
    return {
        "chapter": name, "status": status, "artifacts": len(artifacts),
        "saved_files": [item["file"] for item in artifacts],
        "pending_files": pending_files,
        "resolved_segments": len(artifacts),
        "pending_segments": len(pending),
        "residuals": [{"global_start": item["global_start"], "global_end": item["global_end"]}
                      for item in pending],
        "reason_codes": ["level2_no_complete_safe_path"] if pending else [],
        "next_stage": "Auto-Merge Nível III" if pending else "—",
    }


def execute_level2(manga: Path, chapters: list[str], job_id: str, progress, preflight=None) -> list[dict]:
    validate_level2_selection(manga, chapters)
    lock = threading.Lock()
    values = {name: 0.0 for name in chapters}

    def report(name: str, event: dict) -> None:
        stage = event.get("stage")
        current = max(0, int(event.get("current") or 0))
        total = max(1, int(event.get("total") or 1))
        ratio = {
            "analyze_pages": .05 + .62 * min(current / total, 1),
            "uniform_bands": .75 if current == 0 else .78,
            "plan": .80 + .04 * min(current / total, 1),
            "materialize": .88, "promote": .97, "done": 1.0,
        }.get(stage, .01)
        with lock:
            values[name] = max(values[name], ratio)
            total = max(1, len(chapters))
            progress(name, {**event, "total": len(chapters), "completed": sum(x == 1 for x in values.values()),
                            "value": sum(values.values()), "max": total,
                            "percent": round(sum(values.values()) * 100 / total)})

    def run(index: int, name: str) -> dict:
        report(name, {"stage": "analyze", "message": f"Capítulo {index}/{len(chapters)}: iniciando"})
        try:
            return _run_chapter(manga, name, job_id, report, preflight or (lambda: None))
        except Exception as exc:
            report(name, {"stage": "done", "message": "Capítulo finalizado com ocorrência"})
            return {"chapter": name, "status": "failed", "error": str(exc)}

    with ThreadPoolExecutor(max_workers=min(2, len(chapters)), thread_name_prefix="auto-merge-level2") as worker:
        futures = [worker.submit(run, i, name) for i, name in enumerate(chapters, 1)]
        results = [future.result() for future in as_completed(futures)]
    order = {name: index for index, name in enumerate(chapters)}
    return sorted(results, key=lambda item: order[item["chapter"]])
