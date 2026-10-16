"""Check-only preflight and confirmed reset HTTP handlers."""
import json
from pathlib import Path
from urllib.parse import parse_qs
from central_v2.backend.routes.response import RouteResponse
from central_v2.backend.state.manga_state import resolve_manga
from central_v2.backend.orchestration.textoff_merged.reset_check_override import inspect, restore

def _one(data,key):
    val=data.get(key)
    if isinstance(val,list):val=val[0] if len(val)==1 else None
    if not isinstance(val,str) or not val:
        raise ValueError(f'Campo inválido: {key}')
    return val

def _respond(callback):
    try:
        return RouteResponse(200,json.dumps(callback(),ensure_ascii=False).encode('utf-8'))
    except (ValueError,OSError,TypeError,KeyError,json.JSONDecodeError) as err:
        return RouteResponse(400,json.dumps({'error':str(err)},ensure_ascii=False).encode('utf-8'))

def preflight(query,output_root):
    def run():
        data=parse_qs(query,keep_blank_values=True)
        manga=resolve_manga(output_root,_one(data,'provider'),_one(data,'manga'))
        return inspect(manga,_one(data,'chapter'),_one(data,'page'))
    return _respond(run)

def post(payload,output_root):
    def run():
        if not isinstance(payload,dict) or set(payload)!={'provider','manga','chapter','page','version','confirmed'}:
            raise ValueError('Contrato de Reset inválido.')
        if payload['confirmed'] is not True:
            raise ValueError('Confirmação explícita necessária.')
        manga=resolve_manga(output_root,_one(payload,'provider'),_one(payload,'manga'))
        return restore(manga,_one(payload,'chapter'),_one(payload,'page'),_one(payload,'version'))
    return _respond(run)
