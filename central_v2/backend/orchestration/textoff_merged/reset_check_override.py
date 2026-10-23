"""Per-page Check-only manual MERGE replacement; originals never modified."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import tempfile
from uuid import uuid4

from .auto_cleaner_check_manifest import manifest_path
from .manifests import _listing_merge_artifacts
from .special_styled_transaction import transaction_lock

SCHEMA = 'check_manual_merge_reset_v1'
NAME = 'reset-merge-manifest.json'


def digest(path):
    h = sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _paths(manga, chapter, page):
    root = Path(manga).resolve()
    if (not isinstance(chapter, str) or chapter in ('', '.', '..')
            or Path(chapter).name != chapter or '\\' in chapter
            or not isinstance(page, str) or Path(page).name != page
            or not page.lower().endswith('.png') or '\\' in page):
        raise ValueError('Capítulo ou página inválida.')
    folder = manifest_path(root, chapter).parent.resolve()
    if not folder.is_relative_to(root):
        raise ValueError('Check fora da obra.')
    source = next((p for p in _listing_merge_artifacts(root/'IMG'/chapter)
                   if p.name == page), None)
    if source is None or not source.resolve().is_relative_to(root):
        raise ValueError('MERGE original não verificado.')
    return folder, source


def _read(folder):
    path = folder/NAME
    if not path.exists():
        return {'schema': SCHEMA, 'version': 1, 'pages': {}, 'history': []}
    data = json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(data, dict) or data.get('schema') != SCHEMA
            or data.get('version') != 1 or not isinstance(data.get('pages'), dict)
            or not isinstance(data.get('history'), list)):
        raise ValueError('Manifesto de Reset inválido.')
    return data


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.reset-manifest-',dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(payload,out,indent=2,ensure_ascii=False)
            out.write('\n');out.flush();os.fsync(out.fileno())
        os.replace(tmp,path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def effective(manga,chapter,page,fallback):
    """Validate Check-local override integrity or use existing Check image."""
    folder, _ = _paths(manga,chapter,page)
    row = _read(folder)['pages'].get(page)
    if row is None:
        return fallback
    path = (folder/'reset_merge'/page).resolve()
    if (not isinstance(row,dict) or row.get('source') != 'MERGE'
            or not path.is_relative_to(folder) or not path.is_file()
            or digest(path) != row.get('sha256')):
        raise ValueError('Reset do Check corrompido ou ausente.')
    return path


def current_reset_base(manga, chapter, page):
    """Return the current Check Reset image authority for a page, if present."""
    root = Path(manga).resolve()
    folder = manifest_path(root, chapter).parent
    row = _read(folder)['pages'].get(page)
    if row is None:
        return None
    path = effective(manga, chapter, page, None)
    ident = row.get('id')
    if not isinstance(ident, str) or not ident:
        raise ValueError('Identificador do Reset do Check inválido.')
    return {'kind': 'CHECK_RESET', 'path': str(path.relative_to(root)),
            'sha256': digest(path), 'reset_id': ident, 'source': 'MERGE'}


def inspect(manga,chapter,page):
    from .comparison import comparison_pairs
    folder, source = _paths(manga,chapter,page)
    pair = next((p for p in comparison_pairs(manga,chapter,'1',check=True)
                 if p['name']==page),None)
    if pair is None:
        raise ValueError('Página não disponível no Auto-Cleaner Check.')
    current = pair['after']
    return {'chapter':chapter,'page':page,'merge_sha256':digest(source),
            'check_sha256':digest(current), 'already_restored':digest(source)==digest(current),
            'version':sha256((digest(source)+digest(current)).encode()).hexdigest(),
            'can_apply':True}


def restore(manga,chapter,page,version):
    with transaction_lock(manga):
        info = inspect(manga,chapter,page)
        if info['version'] != version:
            raise ValueError('Página mudou. Atualize a pré-validação.')
        if info['already_restored']:
            return {'status':'already_restored','page':page}
        folder, source = _paths(manga,chapter,page)
        from .comparison import comparison_pairs
        pair = next(p for p in comparison_pairs(manga,chapter,'1',check=True)
                    if p['name']==page)
        prior = pair['after']
        record = _read(folder)
        token = uuid4().hex
        archive = folder/'reset_merge'/'backups'/token
        target = folder/'reset_merge'/page
        archive.mkdir(parents=True,exist_ok=False)
        shutil.copyfile(prior,archive/page)
        if digest(archive/page)!=info['check_sha256']:
            raise ValueError('Backup divergente; Reset cancelado.')
        fd,tmp=tempfile.mkstemp(prefix='.reset-image-',dir=target.parent)
        try:
            with os.fdopen(fd,'wb') as out,source.open('rb') as inp:
                shutil.copyfileobj(inp,out);out.flush();os.fsync(out.fileno())
            if digest(tmp)!=info['merge_sha256']:
                raise ValueError('Cópia MERGE divergente.')
            os.replace(tmp,target)
        finally:
            Path(tmp).unlink(missing_ok=True)
        previous=record['pages'].get(page)
        event={'id':token,'page':page,'action':'manual_reset','source':'MERGE',
               'previous_sha256':info['check_sha256'],'sha256':info['merge_sha256'],
               'previous_override':previous,'at':datetime.now(timezone.utc).isoformat()}
        record['pages'][page]={'source':'MERGE','sha256':info['merge_sha256'],
                               'backup':f'reset_merge/backups/{token}/{page}', 'id':token}
        record['history'].append(event)
        _write(folder/NAME,record)
        return {'status':'restored','page':page,'sha256':info['merge_sha256'], 'id':token}
