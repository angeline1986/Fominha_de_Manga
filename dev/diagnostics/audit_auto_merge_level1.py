"""Read-only source audit; all execution artifacts are synthetic and temporary."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from interface_web import processing_web as v1
from processamento.unificacao_imagens import image_stitcher as domain


def hashes(path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.glob('*.png')}


def fixture(root, name, heights, bands=()):
    chapter = root / 'comix' / 'Synthetic' / 'IMG' / name
    chapter.mkdir(parents=True)
    y = 0
    for index, height in enumerate(heights, 1):
        pixels = np.zeros((height, 64, 3), dtype=np.uint8)
        for start, end in bands:
            lo, hi = max(start, y), min(end, y + height)
            if lo < hi:
                pixels[lo-y:hi-y] = 255
        Image.fromarray(pixels).save(chapter / f'page-{index:03d}.png')
        y += height
    return chapter


def inspect(chapter, status, artifact_count, pending, official):
    sources = hashes(chapter)
    job = v1.Job(1, 'merge')
    result = v1.do_merge(job, [chapter])[0]
    assert hashes(chapter) == sources, 'source image modified'
    assert result['status'] == status, result
    assert result['pending_segments_count'] == pending, result
    assert domain.is_chapter_merged(chapter) == official
    directory = v1.amdir(chapter.parent.parent, chapter.name)
    manifest = json.loads((directory / 'auto-merge-manifest.json').read_text())
    assert len(manifest['artifacts']) == artifact_count
    originals = []
    for path in domain.list_pages(chapter):
        with Image.open(path) as image:
            originals.append(np.asarray(image.convert('RGB')))
    original = np.concatenate(originals)
    for item in manifest['artifacts']:
        with Image.open(directory / item['file']) as image:
            actual = np.asarray(image.convert('RGB'))
        expected = original[item['global_start']:item['global_end']]
        assert np.array_equal(actual, expected), 'artifact differs from source interval'
    official_manifest = domain.merge_manifest_path(chapter)
    promoted = json.loads(official_manifest.read_text()) if official_manifest.is_file() else {}
    evidence = {
        'scenario': chapter.name, 'status': result['status'],
        'algorithm': manifest['algorithm'], 'artifacts': artifact_count,
        'auto_merge_saved': result['auto_merge_saved'],
        'pending_segments': pending, 'residuals': result['residuals'],
        'official_merge': official, 'official_algorithm': promoted.get('algorithm'),
        'next_stage': result['next_stage'], 'source_hashes_preserved': True,
        'artifact_pixels_match_source_intervals': True,
    }
    return evidence


report = []
with tempfile.TemporaryDirectory(prefix='fominha-am1-audit-') as tmp:
    root = Path(tmp)
    complete = fixture(root, 'complete', [4000, 4000])
    report.append(inspect(complete, 'ok', 1, 0, True))
    stage_before = hashes(v1.amdir(complete.parent.parent, complete.name))
    v1.set_merge_failure(complete, 'synthetic stale marker')
    report.append(inspect(complete, 'skipped', 1, 0, True))
    assert not v1.merge_status_file(complete).exists()
    assert hashes(v1.amdir(complete.parent.parent, complete.name)) == stage_before
    report[-1]['scenario'] = 'existing_valid_merge'
    partial = fixture(root, 'partial', [7000] * 4, [(6000, 6400), (20000, 20400)])
    report.append(inspect(partial, 'partial', 2, 1, False))
    blocked = fixture(root, 'no_safe_band', [7000, 7000])
    report.append(inspect(blocked, 'error', 0, 1, False))
    occupied = fixture(root, 'occupied_official', [4000, 4000])
    destination = domain.merge_output_dir(occupied)
    destination.mkdir(parents=True)
    sentinel = destination / 'keep.txt'
    sentinel.write_text('must remain')
    report.append(inspect(occupied, 'error', 1, 0, False))
    assert sentinel.read_text() == 'must remain'
    report[-1]['existing_official_preserved'] = True

for item in report:
    print(json.dumps(item, ensure_ascii=False))
