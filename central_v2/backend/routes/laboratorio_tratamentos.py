"""Experimental previews for treatments shown in Laboratory result cards."""
import json
from pathlib import Path
from urllib.parse import urlencode

from central_v2.backend.orchestration.textoff_special.artifacts import (
    contained_file, read_json, sha256,
)
from central_v2.backend.orchestration.textoff_special.catalog import ROOT
from central_v2.backend.orchestration.textoff_special.execution import preview
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections
from central_v2.backend.routes.laboratorio_source import resolve_source
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.laboratorio_lock import TREATMENT_LOCK
from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.laboratorio_logging import (
    run_treatment_logged, treatment_blocked,
)

STAGING = ROOT / "reports/experimentos/textoff_laboratorio"
_LOCK = TREATMENT_LOCK


def _json(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode("utf-8"))


def _execute(payload, output_root, treatment, on_progress=None):
    if not isinstance(payload, dict):
        return _json({"error": "Requisição inválida."}, 400)
    if not _LOCK.acquire(blocking=False):
        treatment_blocked(treatment)
        return _json({"error": "Há um tratamento experimental em andamento."}, 409)
    try:
        boxes = validate_selections(payload.get("selections"))
        manga, path, chapter, filename = resolve_source(payload, output_root)
        digest = sha256(path)
        source = {"path": str(path), "sha256": digest, "level": "LAB",
                  "chapter": chapter, "filename": filename, "manga": str(manga),
                  "predecessors": []}
        request = {"treatment": treatment, "level": "LAB", "chapter": chapter,
                   "filename": filename, "expected_sha256": digest, "selections": boxes}
        manifest = run_treatment_logged(treatment, payload, lambda: preview(
            manga, request, staging=STAGING, resolved_source=source,
            on_progress=on_progress))
        if manifest.get("execution_status") != "succeeded":
            detail = manifest.get("error") or {}
            error = detail.get("error", "") if isinstance(detail, dict) else ""
            label = "Artístico" if treatment == "estilizado" else "Suave"
            message = (f"Nenhum componente elegível para {label} intersecta as áreas selecionadas."
                       if "Nenhum componente" in error and "intersect" in error.lower() else
                       f"{label} não concluiu; consulte o manifesto experimental.")
            return _json({"error": message, "run_id": manifest["run_id"],
                          "failure_type": detail.get("type", "")
                          if isinstance(detail, dict) else ""}, 422)
        run_id = manifest["run_id"]
        image_url = f"/api/textoff/laboratorio/{treatment}/image?" + urlencode({"run_id": run_id})
        return _json({"run_id": run_id, "image_url": image_url,
                      "validation": manifest.get("validation"), "status": "succeeded"})
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        return _json({"error": str(error)}, 400)
    finally:
        _LOCK.release()



def start_stylized_job(payload, output_root):
    """Asynchronous experimental preview with verified lifecycle milestones."""
    if not isinstance(payload, dict):
        return _json({"error": "Requisição inválida."}, 400)
    def operation(update, _job_id):
        milestone = {"snapshot": 1, "worker": 2, "validated": 3}
        def checkpoint(event):
            completed = milestone.get(event.get("stage"))
            if completed is None:
                return
            update(str(payload.get("chapter", "")), {
                "completed": completed, "total": 3,
                "percent": min(99, int(completed * 100 / 3)),
                "stage": event["stage"], "message": event["message"],
                "countUnit": "etapa(s) verificadas",
            })
        response = _execute(payload, output_root, "estilizado", checkpoint)
        body = json.loads(response.body)
        if response.status != 200:
            return [{"status": "failed", "error": body.get("error", "Falha experimental.")}]
        update(str(payload.get("chapter", "")), {
            "completed": 3, "total": 3, "percent": 100,
            "stage": "complete", "message": "Artístico concluído e validado",
            "countUnit": "etapa(s) verificadas",
        })
        return [{"status": "succeeded", **body}]
    return _json({"job": submit(operation, total=3)}, 202)


def execute_stylized(payload, output_root):
    return _execute(payload, output_root, "estilizado")



def start_smooth_job(payload, output_root):
    """Suave: three observed checkpoints, without simulated worker progress."""
    if not isinstance(payload, dict):
        return _json({"error": "Requisição inválida."}, 400)

    def operation(update, _job_id):
        milestone = {"snapshot": 1, "worker": 2, "validated": 3}

        def checkpoint(event):
            completed = milestone.get(event.get("stage"))
            if completed is None:
                return
            update(str(payload.get("chapter", "")), {
                "completed": completed, "total": 3,
                "percent": min(99, int(completed * 100 / 3)),
                "stage": event["stage"], "message": event["message"],
                "countUnit": "etapa(s) verificadas",
            })

        response = _execute(payload, output_root, "gradiente_suave", checkpoint)
        body = json.loads(response.body)
        if response.status != 200:
            return [{"status": "failed", "error": body.get("error", "Falha experimental.")}]
        update(str(payload.get("chapter", "")), {
            "completed": 3, "total": 3, "percent": 100,
            "stage": "complete", "message": "Suave concluído e validado",
            "countUnit": "etapa(s) verificadas",
        })
        return [{"status": "succeeded", **body}]

    return _json({"job": submit(operation, total=3)}, 202)

def execute_smooth(payload, output_root):
    return _execute(payload, output_root, "gradiente_suave")


def result_image(query, treatment="estilizado"):
    run_id = (query.get("run_id") or [""])[0]
    if len(run_id) != 32 or any(char not in "0123456789abcdef" for char in run_id):
        return _json({"error": "Execução inválida."}, 400)
    try:
        folder = (STAGING / run_id).resolve()
        if not folder.is_relative_to(STAGING.resolve()):
            raise ValueError("Execução inválida.")
        manifest = read_json(folder / "manifest.json")
        request = read_json(folder / "request.json")
        if (manifest.get("run_id") != run_id
                or request.get("run_id") != run_id
                or request.get("treatment") != treatment
                or manifest.get("execution_status") != "succeeded"):
            raise ValueError("Resultado não aprovado.")
        result = contained_file(folder, manifest["result_file"])
        if sha256(result) != manifest["validation"]["result_sha256"]:
            raise ValueError("Resultado divergente.")
        return RouteResponse(200, result.read_bytes(), "image/png")
    except (OSError, ValueError, KeyError, TypeError):
        return _json({"error": "Resultado indisponível."}, 404)
