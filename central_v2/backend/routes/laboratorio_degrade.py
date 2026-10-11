"""Isolated experimental Degradê adapter for the Central V2 Laboratory."""
import json
import threading
from pathlib import Path
from urllib.parse import urlencode

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.laboratorio_pages import _directory, _chapter, _images
from central_v2.backend.orchestration.textoff_special.artifacts import sha256, contained_file, read_json
from central_v2.backend.orchestration.textoff_special.execution import preview
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections
from central_v2.backend.orchestration.textoff_special.catalog import ROOT

STAGING = ROOT / 'reports/experimentos/textoff_laboratorio'
_LOCK = threading.Lock()


def _json(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode('utf-8'))


def _field(value, name):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise ValueError(f'{name} inválido.')
    return value


def execute(payload, output_root):
    if not isinstance(payload, dict):
        return _json({'error': 'Requisição inválida.'}, 400)
    if not _LOCK.acquire(blocking=False):
        return _json({'error': 'Há outro tratamento experimental em andamento.'}, 409)
    try:
        provider = _field(payload.get('provider'), 'Provider')
        manga_name = _field(payload.get('manga'), 'Obra')
        chapter = _field(payload.get('chapter'), 'Capítulo')
        filename = _field(payload.get('page'), 'Página')
        source_kind = payload.get('source')
        if source_kind not in ('img', 'merge'):
            raise ValueError('Origem inválida.')
        boxes = validate_selections(payload.get('selections'))
        image_root = _directory(output_root, provider, manga_name, source_kind)
        chapter_dir = _chapter(image_root, chapter)
        candidates = {p.name: p.resolve() for p in _images(chapter_dir)}
        if filename not in candidates:
            raise ValueError('Página fora do catálogo autorizado.')
        path = candidates[filename]
        manga = image_root.parent if source_kind == 'img' else image_root.parents[1]
        manga = manga.resolve()
        digest = sha256(path)
        source = {'path': str(path), 'sha256': digest, 'level': 'LAB',
                  'chapter': chapter, 'filename': filename, 'manga': str(manga),
                  'predecessors': []}
        request = {'treatment': 'degrade', 'level': 'LAB', 'chapter': chapter,
                   'filename': filename, 'expected_sha256': digest,
                   'selections': boxes}
        manifest = preview(manga, request, staging=STAGING, resolved_source=source)
        if manifest.get('execution_status') != 'succeeded':
            detail = manifest.get('error') or {}
            description = detail.get('error', '') if isinstance(detail, dict) else ''
            public_errors = {
                'Nenhum componente autorizado intersecta as seleções.':
                    'Nenhum componente autorizado intersecta as áreas selecionadas. '
                    'A seleção manual não substitui a autorização automática.',
            }
            return _json({'error': public_errors.get(description,
                          'Degradê não concluiu; consulte o manifesto experimental.'),
                          'run_id': manifest['run_id'], 'failure_type':
                          detail.get('type', '') if isinstance(detail, dict) else ''}, 422)
        run_id = manifest['run_id']
        url = '/api/textoff/laboratorio/degrade/image?' + urlencode({'run_id': run_id})
        return _json({'run_id': run_id, 'image_url': url,
                      'validation': manifest.get('validation'), 'status': 'succeeded'})
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        return _json({'error': str(error)}, 400)
    finally:
        _LOCK.release()


def result_image(query):
    run_id = (query.get('run_id') or [''])[0]
    if len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
        return _json({'error': 'Execução inválida.'}, 400)
    try:
        folder = (STAGING / run_id).resolve()
        if not folder.is_relative_to(STAGING.resolve()):
            raise ValueError('Execução inválida.')
        manifest = read_json(folder / 'manifest.json')
        if manifest.get('run_id') != run_id or manifest.get('execution_status') != 'succeeded':
            raise ValueError('Resultado não aprovado.')
        result = contained_file(folder, manifest['result_file'])
        if sha256(result) != manifest['validation']['result_sha256']:
            raise ValueError('Resultado divergente.')
        return RouteResponse(200, result.read_bytes(), 'image/png')
    except (OSError, ValueError, KeyError, TypeError):
        return _json({'error': 'Resultado indisponível.'}, 404)
