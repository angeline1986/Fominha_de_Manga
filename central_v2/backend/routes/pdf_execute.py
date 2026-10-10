"""PDF V2 job submission with conservative skip-existing policy."""
import json
from pathlib import Path

from central_v2.backend.jobs.manager import submit
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.catalog import build_catalog
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.pdf_service import generate
from orquestracao.central_session import legacy_server_active


def execute_pdf_response(payload: object, output_root: Path) -> RouteResponse:
    try:
        if not isinstance(payload, dict):
            raise ValueError('Solicitação inválida.')
        provider, manga_name, source = (payload.get(k) for k in ('provider', 'manga', 'source'))
        chapters = payload.get('chapters')
        quality = payload.get('quality', 93)
        if source not in ('original', 'merged') or type(quality) is not int or quality not in (88, 93):
            raise ValueError('Origem ou perfil inválido.')
        if not isinstance(provider, str) or not isinstance(manga_name, str) or manga_name not in build_catalog(output_root).get(provider, []):
            raise ValueError('Obra fora do catálogo.')
        if (not isinstance(chapters, list) or not 1 <= len(chapters) <= 200 or
                any(not isinstance(ch, str) or not ch or ch in ('.', '..') or
                    Path(ch).name != ch or '\\' in ch for ch in chapters) or
                len(set(chapters)) != len(chapters)):
            raise ValueError('Seleção de capítulos inválida.')
        if payload.get('existing_policy', 'skip') != 'skip':
            raise ValueError('Sobrescrita não disponível nesta versão.')
        if legacy_server_active():
            raise ValueError('Feche a Central V1 antes de executar a geração na V2.')
        manga = resolve_manga(output_root, provider, manga_name)
        missing = [ch for ch in chapters if not (manga / 'IMG' / ch).is_dir()]
        if missing:
            raise ValueError('Capítulos não encontrados: ' + ', '.join(missing[:5]))

        def operation(update, job_id):
            results = []
            total = len(chapters)
            for i, ch in enumerate(chapters, 1):
                if legacy_server_active():
                    raise RuntimeError('Central V1 foi iniciada durante a execução.')
                update(ch, {'stage': 'pdf', 'message': f'Gerando PDF do capítulo {ch}…',
                            'completed': i-1, 'total': total, 'percent': int(100*(i-1)/total)})
                try:
                    result = generate(manga, ch, source, quality)
                except (ValueError, OSError, RuntimeError) as exc:
                    result = {'chapter': ch, 'status': 'failed', 'error': str(exc)}
                results.append(result)
                update(ch, {'stage': 'pdf', 'message': f'Capítulo {ch}: {result["status"]}',
                            'completed': i, 'total': total, 'percent': int(100*i/total)})
            return results
        job = submit(operation, total=len(chapters))
        return _response(202, {'job': job})
    except (ValueError, OSError) as exc:
        return _response(400, {'error': str(exc)})


def _response(status, obj):
    return RouteResponse(status, json.dumps(obj, ensure_ascii=False).encode('utf-8'))
