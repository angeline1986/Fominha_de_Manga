"""Job bridge for experimental Degradê; preserves 422 assisted authorization."""
import json
from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.laboratorio_degrade import execute, confirm_authorization
from central_v2.backend.routes.response import RouteResponse


def _json(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode("utf-8"))


def start(payload, output_root, assisted=False):
    if not isinstance(payload, dict):
        return _json({"error": "Requisição inválida."}, 400)

    def operation(update, _job_id):
        milestones = {"snapshot": 1, "worker": 2, "validated": 3}

        def checkpoint(event):
            done = milestones.get(event.get("stage"))
            if done is None:
                return
            update(str(payload.get("chapter", "")), {
                "completed": done, "total": 3,
                "percent": min(99, int(done * 100 / 3)),
                "stage": event["stage"], "message": event["message"],
                "countUnit": "etapa(s) verificadas",
            })

        action = confirm_authorization if assisted else execute
        response = action(payload, output_root, on_progress=checkpoint)
        body = json.loads(response.body)
        if response.status != 200:
            return [{"status": "failed", "http_status": response.status,
                     "error": body.get("error", "Degradê não concluído."),
                     "run_id": body.get("run_id"),
                     "failure_type": body.get("failure_type", "")}]
        update(str(payload.get("chapter", "")), {
            "completed": 3, "total": 3, "percent": 100,
            "stage": "complete", "message": "Degradê concluído e validado",
            "countUnit": "etapa(s) verificadas",
        })
        return [{"status": "succeeded", **body}]

    return _json({"job": submit(operation, total=3)}, 202)
