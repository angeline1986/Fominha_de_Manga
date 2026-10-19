"""Consolidacao de fontes, sem alterar algoritmos de limpeza."""
from __future__ import annotations

from .auto_cleaner_check_geometry import _merge_source_data

SOLID = "residuo_balao_solido_branco"
TRANSPARENT = "balao_transparente"


def _overlap(a, b):
    x = max(0., min(a['left']+a['width'], b['left']+b['width'])-max(a['left'], b['left']))
    y = max(0., min(a['top']+a['height'], b['top']+b['height'])-max(a['top'], b['top']))
    return x*y


def _area(a):
    return a['width']*a['height']


def _contains(a, b, epsilon=1e-8):
    return (a['left'] <= b['left']+epsilon and a['top'] <= b['top']+epsilon
            and a['left']+a['width']+epsilon >= b['left']+b['width']
            and a['top']+a['height']+epsilon >= b['top']+b['height'])


def _similar(a, b):
    intersection = _overlap(a, b)
    union = _area(a)+_area(b)-intersection
    return union > 0 and intersection/union >= .78


def consolidate_transparent(rows, transparent):
    """Evita envelope duplicado somente se os alvos sao bem definidos."""
    output = list(rows)
    for candidate in transparent:
        if not candidate.get('page'):
            continue
        matches = [row for row in output if row['page'] == candidate['page']
                   and _overlap(row['box'], candidate['box']) > 0]
        strong = [row for row in matches if _similar(row['box'], candidate['box'])
                  or _contains(row['box'], candidate['box'])
                  or _contains(candidate['box'], row['box'])]
        if len(matches) == len(strong) == 1:
            base = strong[0]
            previous = base.get('type')
            _merge_source_data(base, candidate)
            if not previous or previous == SOLID:
                base['type'] = TRANSPARENT
            continue
        # Um detector retornou envelope envolvendo varios baloes separados.
        # Preserva as caixas menores, associando a proveniencia a cada uma.
        if (len(matches) >= 2 and len(strong) == len(matches)
                and all(_contains(candidate['box'], row['box']) for row in matches)
                and all(_overlap(a['box'], b['box']) / min(_area(a['box']), _area(b['box'])) < .2
                        for i, a in enumerate(matches) for b in matches[i+1:])):
            for base in matches:
                previous = base.get('type')
                _merge_source_data(base, candidate)
                # Um envelope multiplo nao comprova transparencia individual.
                base['type'] = previous or SOLID
            continue
        output.append(candidate)
    return consolidate_near_duplicates(output)


def consolidate_near_duplicates(rows):
    """Agrupa deteccoes muito semelhantes, sem fundir baloes adjacentes."""
    result = []
    for item in rows:
        hits = [r for r in result if r['page'] == item['page']
                and _similar(r['box'], item['box'])]
        if len(hits) == 1:
            existing = hits[0]
            before = existing.get('type')
            _merge_source_data(existing, item)
            if before:
                existing['type'] = before
        else:
            result.append(item)
    return result


def default_sommelier_solid(rows):
    """Fallback somente se ainda nao existe classificacao especifica."""
    for row in rows:
        if row.get('candidate') is not True or row.get('type'):
            continue
        origins = set(row.get('origins', [row.get('origin')]))
        classifications = {str(r.get('candidate_type', '')).lower()
                           for r in row.get('source_references', [])}
        if (origins & {'SOMMELIER', 'MAPEAR'}
                and not (classifications & {'soft_gradient', 'gradient', 'degrade'})):
            row['type'] = SOLID
    return rows
