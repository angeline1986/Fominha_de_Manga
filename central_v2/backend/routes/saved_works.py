"""Read/write the downloader's provider-specific saved work catalogs."""
import json
import os
from pathlib import Path
import tempfile
import threading
from urllib.parse import urlsplit

from central_v2.backend.routes.response import RouteResponse

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / 'download' / 'mangago_downloader' / 'data' / 'saved_works'
PROVIDERS = {'comix': 'comix.to', 'mangago': 'mangago.me', 'ridi': 'ridibooks.com', 'lezhinus': 'lezhinus.com'}
_LOCK = threading.RLock()


def _reply(status, data):
    return RouteResponse(status, json.dumps(data, ensure_ascii=False).encode('utf-8'))


def _provider(value):
    if value not in PROVIDERS:
        raise ValueError('Provider inválido.')
    return value


def _path(provider):
    return CATALOG / (_provider(provider) + '.json')


def _read(provider):
    path = _path(provider)
    content = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(content, dict) or not isinstance(content.get('works'), list):
        raise ValueError('Catálogo com estrutura inválida.')
    if any(not isinstance(row, dict) or not isinstance(row.get('name'), str)
           or not isinstance(row.get('url'), str) for row in content['works']):
        raise ValueError('Registros inválidos no catálogo.')
    return content


def _validated(name, url, provider):
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 240):
        raise ValueError('Informe um nome de até 240 caracteres.')
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('URL inválida.')
    url = url.strip()
    parsed = urlsplit(url)
    host = (parsed.hostname or '').lower()
    domain = PROVIDERS[provider]
    if (parsed.scheme != 'https' or parsed.username or parsed.password
            or parsed.port is not None or host not in ({domain, 'www.' + domain, 'lezhin.com', 'www.lezhin.com'} if provider == 'lezhinus' else {domain, 'www.' + domain})
            or not parsed.path or any(ord(c) < 32 for c in url)):
        raise ValueError('Informe um link HTTPS válido do provider selecionado.')
    return name.strip(), url


def _write(provider, content):
    path = _path(provider)
    fd, temp = tempfile.mkstemp(prefix=f'.{provider}-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(content, handle, ensure_ascii=False, indent=4)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def list_response(query):
    try:
        provider = _provider((query.get('provider') or ['comix'])[0])
        with _LOCK:
            content = _read(provider)
        return _reply(200, {'provider': provider, 'works': content['works']})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _reply(400, {'error': str(exc)})


def change_response(payload):
    try:
        if not isinstance(payload, dict):
            raise ValueError('Solicitação inválida.')
        provider = _provider(payload.get('provider'))
        action = payload.get('action')
        if action not in {'add', 'edit', 'delete'}:
            raise ValueError('Ação inválida.')
        with _LOCK:
            content = _read(provider)
            works = content['works']
            if action == 'add':
                name, url = _validated(payload.get('name'), payload.get('url'), provider)
                if any(r['name'].casefold() == name.casefold() or r['url'] == url for r in works):
                    raise ValueError('Nome ou URL já cadastrados neste provider.')
                works.append({'name': name, 'url': url})
            else:
                original = payload.get('original_url')
                matches = [i for i, r in enumerate(works) if r['url'] == original]
                if len(matches) != 1:
                    raise ValueError('Registro não encontrado ou alterado. Atualize a lista.')
                index = matches[0]
                if action == 'delete':
                    works.pop(index)
                else:
                    name, url = _validated(payload.get('name'), payload.get('url'), provider)
                    if any(i != index and (r['name'].casefold() == name.casefold()
                           or r['url'] == url) for i, r in enumerate(works)):
                        raise ValueError('Nome ou URL já cadastrados neste provider.')
                    works[index] = {**works[index], 'name': name, 'url': url}
            _write(provider, content)
            return _reply(200, {'provider': provider, 'works': works})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        return _reply(400, {'error': str(exc)})
