"""Safe request identity, PLAN_ONLY summaries, and short-lived plan tokens."""
import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

from central_v2.backend.orchestration.combo_turbo.orchestrator import run_combo
from central_v2.backend.orchestration.combo_turbo.execution import source_signature
from central_v2.backend.orchestration.combo_turbo.models import valid_chapter_id
from central_v2.backend.orchestration.combo_turbo.orchestrator_workspace import _reject_links
from central_v2.backend.state.catalog import CATALOG_PROVIDERS
from central_v2.backend.state.manga_state import build_structural_state, resolve_manga

MAX_CHAPTERS = 40
_TOKEN_SECRET = os.urandom(32)
_TOKEN_TTL = 1800


class PlanConflictError(ValueError):
    """The signed plan is expired or no longer matches the selected inputs."""


def request_context(payload, output_root, *, fields):
    if not isinstance(payload, dict) or set(payload) != set(fields):
        raise ValueError("Campos da solicitação Combo Turbo inválidos.")
    provider, name, chapters = payload.get("provider"), payload.get("manga"), payload.get("chapters")
    if provider not in CATALOG_PROVIDERS:
        raise ValueError("Provider inválido.")
    if (not isinstance(name, str) or not name or name in {".", ".."}
            or Path(name).name != name or "/" in name or "\\" in name):
        raise ValueError("Obra inválida.")
    if (not isinstance(chapters, list) or not chapters or len(chapters) > MAX_CHAPTERS
            or any(not valid_chapter_id(chapter) for chapter in chapters)
            or len(set(chapters)) != len(chapters)):
        raise ValueError("Seleção de capítulos inválida.")
    root = Path(output_root).resolve()
    provider_path = Path(output_root) / provider
    if provider_path.is_symlink():
        raise ValueError("Provider aponta por link simbólico.")
    manga_path = provider_path / name
    if manga_path.is_symlink():
        raise ValueError("Obra aponta por link simbólico.")
    manga = resolve_manga(root, provider, name)
    if not manga.is_relative_to(root):
        raise ValueError("Obra fora da raiz de dados autorizada.")
    available = set(build_structural_state(root, provider, name)["chapters"])
    if any(chapter not in available for chapter in chapters):
        raise ValueError("Seleção contém capítulo ausente da obra.")
    _reject_links(manga)
    signature = source_signature(manga, provider, chapters)
    return {"provider": provider, "manga_name": name, "chapters": list(chapters),
            "manga": manga, "signature": signature}


def plan_request(context):
    result = run_combo(context["manga"], context["provider"], context["chapters"], None,
                       mode="PLAN_ONLY")
    result["summary"] = summarize_plan(result.get("plan") or {})
    result["plan_token"] = _issue_token(context)
    return result


def verify_plan_token(token, context):
    if not isinstance(token, str) or len(token) > 4096:
        raise PlanConflictError("Plano expirado ou incompatível; execute PLAN_ONLY novamente.")
    try:
        encoded, signed = token.split(".", 1)
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        expected = hmac.new(_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
        payload = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError):
        raise PlanConflictError("Plano expirado ou incompatível; execute PLAN_ONLY novamente.")
    if (not hmac.compare_digest(expected, signed) or not isinstance(payload, dict)
            or payload.get("expires", 0) < time.time()
            or any(payload.get(key) != context.get(source) for key, source in (
                ("provider", "provider"), ("manga", "manga_name"),
                ("chapters", "chapters"), ("signature", "signature")))):
        raise PlanConflictError("Fontes ou identidade mudaram desde PLAN_ONLY.")


def summarize_plan(plan):
    chapters = plan.get("chapters", [])
    result = {"chapters_total": len(chapters), "planned": 0, "blocked": 0,
              "no_work": 0,
              "pages_total": 0, "solids_candidates": 0, "glass_candidates": 0,
              "solids_reusable": 0, "glass_reusable": 0, "dependencies": []}
    for chapter in chapters:
        state = chapter.get("status")
        result["blocked" if state == "BLOCKED" else
               "no_work" if state == "NO_WORK" else "planned"] += 1
        if chapter.get("status") == "BLOCKED" and not chapter.get("pages"):
            result["dependencies"].append({"chapter": chapter.get("chapter"),
                "page": None, "stage": None,
                "reasons": chapter.get("reasons") or ["CHAPTER_BLOCKED"],
                "detail": chapter.get("error")})
        result["pages_total"] += len(chapter.get("pages", []))
        for page in chapter.get("pages", []):
            for key, stage in (("solids", "SOLIDOS"), ("glass", "GLASS")):
                row = page.get("stages", {}).get(stage, {})
                result[f"{key}_candidates"] += int(page.get("eligible", {}).get(stage, False))
                result[f"{key}_reusable"] += int(row.get("status") == "REUSED")
                if row.get("status") == "BLOCKED":
                    result["dependencies"].append({"chapter": chapter.get("chapter"),
                        "page": page.get("page"), "stage": stage,
                        "reasons": list(row.get("reasons", []))})
    result["eligible"] = result["planned"] > 0
    result["status"] = ("BLOCKED" if result["blocked"] else
                        "NO_WORK" if result["no_work"] == result["chapters_total"]
                        else "PLANNED")
    return result


def _issue_token(context):
    payload = {"provider": context["provider"], "manga": context["manga_name"],
               "chapters": context["chapters"], "signature": context["signature"],
               "expires": int(time.time() + _TOKEN_TTL)}
    encoded = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True,
        separators=(",", ":")).encode()).decode().rstrip("=")
    signed = hmac.new(_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    return encoded + "." + signed
