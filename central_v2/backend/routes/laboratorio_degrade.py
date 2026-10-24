"""Isolated experimental Degradê adapter for the Central V2 Laboratory."""
import json
from pathlib import Path
from urllib.parse import urlencode

from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.routes.laboratorio_source import resolve_source
from central_v2.backend.orchestration.textoff_special.artifacts import (
    sha256, contained_file, read_json,
)
from central_v2.backend.orchestration.textoff_special.execution import preview
from central_v2.backend.orchestration.textoff_special.inputs import validate_selections
from central_v2.backend.orchestration.textoff_special.catalog import ROOT
from central_v2.backend.routes.laboratorio_lock import TREATMENT_LOCK
from central_v2.backend.routes.laboratorio_logging import (
    authorization_ready, authorization_unavailable, run_treatment_logged,
    treatment_blocked,
)
from central_v2.backend.orchestration.textoff_special.lab_degrade_authorization import (
    candidate_rows, consume, issue, load_pending, selections_digest,
)

STAGING = ROOT / 'reports/experimentos/textoff_laboratorio'
_LOCK = TREATMENT_LOCK


def _json(body, status=200):
    return RouteResponse(status, json.dumps(body, ensure_ascii=False).encode('utf-8'))


def _field(value, name):
    if not isinstance(value, str) or not value or len(value) > 240:
        raise ValueError(f'{name} inválido.')
    return value


def _resolve(payload, output_root):
    boxes = validate_selections(payload.get('selections'))
    manga, path, chapter, filename = resolve_source(payload, output_root)
    digest = sha256(path)
    source = {'path': str(path), 'sha256': digest, 'level': 'LAB',
              'chapter': chapter, 'filename': filename, 'manga': str(manga),
              'predecessors': []}
    request = {'treatment': 'degrade', 'level': 'LAB', 'chapter': chapter,
               'filename': filename, 'expected_sha256': digest, 'selections': boxes}
    return manga, source, request


def _result(manifest):
    run_id = manifest['run_id']
    url = '/api/textoff/laboratorio/degrade/image?' + urlencode({'run_id': run_id})
    return _json({'run_id': run_id, 'image_url': url,
                  'validation': manifest.get('validation'), 'status': 'succeeded'})


def execute(payload, output_root, on_progress=None):
    if not isinstance(payload, dict):
        return _json({'error': 'Requisição inválida.'}, 400)
    if not _LOCK.acquire(blocking=False):
        treatment_blocked("degrade")
        return _json({'error': 'Há outro tratamento experimental em andamento.'}, 409)
    try:
        manga, source, request = _resolve(payload, output_root)
        manifest = run_treatment_logged("degrade", payload, lambda: preview(
            manga, request, staging=STAGING, resolved_source=source,
            laboratory_experimental=True, on_progress=on_progress))
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
        return _result(manifest)
    except (ValueError, OSError, RuntimeError, TimeoutError) as error:
        return _json({'error': str(error)}, 400)
    finally:
        _LOCK.release()


def authorization_candidates(payload):
    if not isinstance(payload, dict):
        return _json({'error': 'Requisição inválida.'}, 400)
    try:
        run_id = _field(payload.get('run_id'), 'Execução')
        if len(run_id) != 32 or any(c not in '0123456789abcdef' for c in run_id):
            raise ValueError('Execução inválida.')
        folder = (STAGING / run_id).resolve()
        if not folder.is_relative_to(STAGING.resolve()):
            raise ValueError('Execução inválida.')
        manifest, request = read_json(folder / 'manifest.json'), read_json(folder / 'request.json')
        error = manifest.get('error')
        if (manifest.get('run_id') != run_id or request.get('run_id') != run_id
                or request.get('treatment') != 'degrade'
                or manifest.get('execution_status') != 'failed'
                or not isinstance(error, dict) or error.get('error')
                != 'Nenhum componente autorizado intersecta as seleções.'):
            raise ValueError('Execução não oferece autorização assistida.')
        source = request['source']
        if sha256(Path(source['path'])) != source['sha256']:
            raise ValueError('PROPOSTA_OBSOLETA: imagem de origem mudou.')
        report = contained_file(folder, 'treatment/balloon_authorization.json')
        mask = contained_file(folder, 'treatment/cleaner/source_mask_raw.png')
        candidates, binding = candidate_rows(request, report, mask)
        if not candidates:
            authorization_unavailable(run_id)
            return _json({'error': 'Nenhum componente adiado elegível intersecta as ROIs.'}, 422)
        token, record = issue(folder, run_id, request, candidates, binding)
        authorization_ready(run_id, len(candidates))
        return _json({'proposal_run_id': run_id, 'proposal_token': token,
                      'expires_at': record['expires_at'], 'candidates': candidates})
    except (ValueError, OSError, KeyError, TypeError) as error:
        return _json({'error': str(error)}, 409)


def confirm_authorization(payload, output_root, on_progress=None):
    if not isinstance(payload, dict):
        return _json({'error': 'Requisição inválida.'}, 400)
    if not _LOCK.acquire(blocking=False):
        treatment_blocked("degrade")
        return _json({'error': 'Há outro tratamento experimental em andamento.'}, 409)
    source_run_id = payload.get('proposal_run_id')
    try:
        manga, source, request = _resolve(payload, output_root)
        run_id = _field(payload.get('proposal_run_id'), 'Proposta')
        token = _field(payload.get('proposal_token'), 'Confirmação')
        folder = (STAGING / run_id).resolve()
        if (len(run_id) != 32 or not folder.is_relative_to(STAGING.resolve())):
            raise ValueError('Proposta inválida.')
        record = load_pending(folder, token)
        previous = read_json(folder / 'request.json')
        if (record.get('run_id') != run_id or previous.get('source') != source
                or previous.get('selections') != request['selections']
                or record.get('source') != source
                or record.get('selections') != request['selections']
                or record['binding']['selections_sha256']
                != selections_digest(request['selections'])):
            raise ValueError('PROPOSTA_OBSOLETA: imagem ou ROIs mudaram.')
        report = contained_file(folder, 'treatment/balloon_authorization.json')
        mask = contained_file(folder, 'treatment/cleaner/source_mask_raw.png')
        candidates, binding = candidate_rows(previous, report, mask)
        if binding != record.get('binding') or candidates != record.get('candidates'):
            raise ValueError('PROPOSTA_OBSOLETA: classificação experimental mudou.')
        selected = payload.get('component_ids')
        authorization = consume(folder, record, selected)
        manifest = run_treatment_logged("degrade", payload, lambda: preview(
            manga, request, staging=STAGING, resolved_source=source,
            laboratory_authorization=authorization,
            laboratory_experimental=True, on_progress=on_progress), correlation_id=source_run_id)
        if manifest.get('execution_status') != 'succeeded':
            detail = manifest.get('error') or {}
            return _json({'error': 'Degradê assistido não concluiu; consulte o manifesto experimental.',
                          'run_id': manifest['run_id'], 'failure_type': detail.get('type', '')
                          if isinstance(detail, dict) else ''}, 422)
        return _result(manifest)
    except (ValueError, OSError, RuntimeError, TimeoutError, KeyError, TypeError) as error:
        return _json({'error': str(error)}, 409)
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
