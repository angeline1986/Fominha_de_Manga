"""Job bridge for Degradê with one-click ROI authorization in Laboratory V2."""
import json
from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.laboratorio_degrade import (
    execute, confirm_authorization, authorization_candidates,
)
from central_v2.backend.routes.response import RouteResponse


def _json(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode("utf-8"))


def _parse(response):
    return json.loads(response.body)


def start(payload, output_root, assisted=False):
    if not isinstance(payload, dict):
        return _json({"error": "Requisição inválida."}, 400)

    def operation(update, _job_id):
        chapter = str(payload.get("chapter", ""))
        stage_numbers = {"snapshot": 1, "worker": 2, "validated": 3}
        last_percent = 0

        def report(stage, percent, message):
            nonlocal last_percent
            last_percent = max(last_percent, percent)
            update(chapter, {"completed": last_percent, "total": 100,
                "percent": last_percent, "stage": stage, "message": message,
                "countUnit": "percentual verificado"})

        def checkpoints(auto_phase):
            def checkpoint(event):
                done = stage_numbers.get(event.get("stage"))
                if done is None:
                    return
                if auto_phase:
                    percent = (14, 28, 40)[done - 1]
                    label = "Classificação: "
                else:
                    percent = (60, 80, 99)[done - 1]
                    label = "Tratamento autorizado: "
                report(event["stage"], percent, label + event["message"])
            return checkpoint

        # Existing explicit endpoint is kept compatible, but V2's main button
        # now grants consent for eligible components within the selected ROIs.
        if assisted:
            response = confirm_authorization(payload, output_root,
                                            on_progress=checkpoints(False))
        else:
            response = execute(payload, output_root, on_progress=checkpoints(True))
            if response.status == 422:
                failure = _parse(response)
                run_id = failure.get("run_id")
                if run_id:
                    proposal = authorization_candidates({**payload, "run_id": run_id}, output_root)
                    if proposal.status == 200:
                        offer = _parse(proposal)
                        rows = offer.get("candidates") or []
                        if rows:
                            report("authorization", 40,
                                   "Componentes elegíveis nas ROIs validados")
                            authorized = {**payload,
                                "proposal_run_id": offer["proposal_run_id"],
                                "proposal_token": offer["proposal_token"],
                                "component_ids": [row["id"] for row in rows]}
                            response = confirm_authorization(
                                authorized, output_root, on_progress=checkpoints(False))
                        # No eligible candidate: return original failure.
                    elif proposal.status != 422:
                        response = proposal
        body = _parse(response)
        if response.status != 200:
            return [{"status": "failed", "http_status": response.status,
                     "error": body.get("error", "Degradê não concluído."),
                     "run_id": body.get("run_id"),
                     "failure_type": body.get("failure_type", "")}]
        report("complete", 100, "Degradê concluído e validado")
        return [{"status": "succeeded", **body}]

    return _json({"job": submit(operation, total=1)}, 202)
