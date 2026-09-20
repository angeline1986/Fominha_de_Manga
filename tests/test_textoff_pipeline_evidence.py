"""M2 measurement tests: synthetic pixels and masks, no golden routing rules."""
import json
from copy import deepcopy

import cv2
import numpy as np
import pytest

from processamento.limpeza_baloes.pipeline.region_evidence import measure_regions, to_merged_bbox
from processamento.limpeza_baloes.pipeline import orchestrator


def scene():
    image = np.zeros((40, 40, 3), np.uint8)
    image[:] = (0, 0, 255)
    mask = np.zeros((40, 40), np.uint8)
    mask[10:30, 10:30] = 255
    image[mask > 0] = 255
    return image, mask


def test_white_surface_is_separate_from_colored_context_and_deterministic():
    image, mask = scene()
    original, original_mask = image.copy(), mask.copy()
    result = measure_regions(image, [mask], [])
    assert result == measure_regions(image, [mask], [])
    zones = result['balloons'][0]['zones']
    assert zones['INTERIOR']['pixel_count'] == 144
    assert zones['INNER_RING']['pixel_count'] == 256
    assert zones['OUTER_CONTEXT']['pixel_count'] == 384
    assert zones['INTERIOR']['metrics']['gray_mean'] == 255
    assert zones['INNER_RING']['metrics']['saturation_mean'] == 0
    assert zones['OUTER_CONTEXT']['metrics']['saturation_mean'] == 255
    assert np.array_equal(image, original) and np.array_equal(mask, original_mask)


def test_colored_surface_statistics():
    image, mask = scene()
    image[mask > 0] = (255, 0, 0)
    zones = measure_regions(image, [mask], [])['balloons'][0]['zones']
    assert zones['INTERIOR']['metrics']['saturation_mean'] == 255
    assert zones['INTERIOR']['metrics']['gray_std'] == 0
    assert zones['INTERIOR']['metrics']['rgb_std_mean'] == 0


def test_gradient_measures_dispersion_without_classification():
    image, mask = scene()
    image[:] = np.arange(40, dtype=np.uint8)[None, :, None] * 5
    result = measure_regions(image, [mask], [])
    metrics = result['balloons'][0]['zones']['INTERIOR']['metrics']
    assert metrics['gray_mean'] == 97.5
    assert metrics['gray_std'] == pytest.approx(np.std(np.arange(14,26)*5), abs=1e-4)
    assert metrics['saturation_mean'] == 0
    assert 'destination' not in json.dumps(result)
    assert 'score' not in json.dumps(result)


def test_border_clipping_is_explicit_and_zones_remain_disjoint():
    image = np.full((20,20,3), 255, np.uint8)
    mask = np.zeros((20,20), np.uint8); mask[:10,:10] = 255
    b = measure_regions(image, [mask], [])['balloons'][0]
    assert b['outer_context_clipping'] == {'left':True,'top':True,'right':False,'bottom':False}
    assert b['zones']['INTERIOR']['geometric_pixel_count'] == 4
    assert b['zones']['INNER_RING']['geometric_pixel_count'] == 96
    assert b['zones']['OUTER_CONTEXT']['geometric_pixel_count'] == 96


def test_neighbor_balloon_is_excluded_from_context():
    image, mask = scene()
    neighbor = np.zeros(mask.shape, np.uint8); neighbor[10:30,31:39] = 255
    image[neighbor > 0] = (0,255,0)
    result = measure_regions(image, [mask,neighbor], [])
    context = result['balloons'][0]['zones']['OUTER_CONTEXT']
    assert context['excluded_other_balloon_pixels'] == 60
    assert context['geometric_pixel_count'] - context['pixel_count'] == 60
    assert context['metrics']['gray_mean'] == 76  # Red scene, green neighbor removed.


def test_full_partial_and_absent_relations_are_not_semantic_membership():
    image, mask = scene()
    candidates = [{'candidate_id':'full','bbox':[15,15,20,20]},
                  {'candidate_id':'touch','bbox':[29,15,39,20]},
                  {'candidate_id':'outside','bbox':[0,0,3,3]}]
    original = deepcopy(candidates)
    r = measure_regions(image,[mask],candidates)
    assert r['candidates']['full']['intersections'][0]['relation'] == 'FULL_CONTAINMENT'
    contact = r['candidates']['touch']['intersections'][0]
    assert contact['relation'] == 'PARTIAL_INTERSECTION'
    assert contact['intersection_pixels'] == 5
    assert contact['candidate_inside_percent'] == 10
    assert contact['center_inside_individual_mask'] is False
    assert r['candidates']['outside']['reason'] == 'NO_INTERSECTING_BALLOON'
    assert r['balloons'][0]['related_candidate_ids'] == ['full','touch']
    assert candidates == original


def test_union_and_best_individual_are_different():
    image = np.zeros((20,20,3),np.uint8)
    left = np.zeros((20,20),np.uint8); left[:,:10] = 255
    right = np.zeros((20,20),np.uint8); right[:,10:] = 255
    r = measure_regions(image,[left,right],[{'candidate_id':'both','bbox':[5,5,15,15]}])
    c = r['candidates']['both']
    assert c['union_inside_percent'] == 100
    assert [i['candidate_inside_percent'] for i in c['intersections']] == [50,50]


def test_empty_and_small_zones_do_not_fabricate_zero_metrics():
    image = np.zeros((12,12,3),np.uint8)
    mask = np.zeros((12,12),np.uint8); mask[5,5] = 255
    b = measure_regions(image,[mask],[])['balloons'][0]
    for zone in ['INTERIOR','INNER_RING']:
        assert b['zones'][zone]['available'] is False
        assert b['zones'][zone]['reason'] == 'INSUFFICIENT_PIXELS'
        assert b['zones'][zone]['metrics'] is None
    assert b['differences']['INTERIOR_MINUS_OUTER_CONTEXT']['metrics'] is None
    empty = measure_regions(image,[np.zeros((12,12),np.uint8)],[])['balloons'][0]
    assert empty['reason'] == 'EMPTY_MASK'


def test_ctd_boxes_excluded_with_counts_and_unknown_completeness():
    image, mask = scene(); image[15:20,15:20] = 0
    c = [{'candidate_id':'text','bbox':[15,15,20,20]}]
    result = measure_regions(image,[mask],c)
    z = result['balloons'][0]['zones']['INTERIOR']
    assert z['excluded_ctd_bbox_pixels'] == 25
    assert z['pixel_count'] == 119
    assert z['metrics']['gray_mean'] == 255
    assert result['text_exclusion_complete'] == 'UNKNOWN'
    assert measure_regions(image,[mask],None)['ctd_available'] is False


def test_candidate_clipping_is_recorded():
    image, mask = scene()
    c = measure_regions(image,[mask],[{'candidate_id':'clipped','bbox':[-2,10,15,15]}])['candidates']['clipped']
    assert c['clipped'] and c['bbox'] == [0,10,15,15]


def test_split_conversion_scale_and_input_preservation():
    r = to_merged_bbox([2,4,10,12],split_size=(20,20),merged_size=(20,50),offset=(0,25),scale=2)
    assert r['bbox'] == [1,27,5,31]
    assert r['input_bbox'] == [2,4,10,12]
    assert r['scale'] == 2 and not r['clipped']
    c = to_merged_bbox([-1,2,21,12],split_size=(20,20),merged_size=(20,50),offset=(0,25))
    assert c['clipped'] and c['bbox'] == [0,27,20,37]


@pytest.mark.parametrize('offset', [(-1,0),(0,31),(0,0.5)])
def test_invalid_offset_rejected(offset):
    with pytest.raises(ValueError,match='[Oo]ffset'):
        to_merged_bbox([1,1,5,5],split_size=(20,20),merged_size=(20,50),offset=offset)


def test_incompatible_dimensions_rejected():
    image, mask = scene()
    with pytest.raises(ValueError,match='dimensions'):
        measure_regions(image,[mask[:10]],[])
    with pytest.raises(ValueError,match='dimensions'):
        to_merged_bbox([1,1,5,5],split_size=(21,20),merged_size=(20,20))


def make_split(tmp_path, source, name, offset, box):
    split = tmp_path / f'{name}.png'
    cv2.imwrite(str(split),source[offset:offset+20])
    raw = tmp_path / f'{name}#raw.json'
    raw.write_text(json.dumps({'original_path':str(split),'image_path':str(split),
                              'scale':1.0,'blk_list':[{'xyxy':box,'lines':[]}]}))
    return {'raw_json':raw,'offset':[0,offset]}


def test_merged_orchestrator_single_segmentation_and_no_cross_split_label_grouping(tmp_path,monkeypatch):
    source = np.full((40,20,3),255,np.uint8)
    path = tmp_path/'merged.png'; cv2.imwrite(str(path),source)
    entries = [make_split(tmp_path,source,'first',0,[5,5,10,10]),
               make_split(tmp_path,source,'second',20,[5,5,10,10])]
    calls = []
    def segment(raw,original,base,candidates):
        calls.append(candidates)
        mask = np.ones(source.shape[:2],np.uint8)
        return {'candidates':{c['candidate_id']:{} for c in candidates}, 'model':{},
                'region_evidence':measure_regions(source,[mask],candidates)}
    monkeypatch.setattr(orchestrator,'analyze_page',segment)
    report = orchestrator.build_merged_audit(path,entries)
    assert len(calls) == 1
    candidates = report['level1']['candidates']
    assert [c['bbox'] for c in candidates] == [[5,5,10,10],[5,25,10,30]]
    assert all(c['routing']['destination']=='REVIEW' for c in candidates)
    assert all('visual_evidence' in c for c in candidates)
    assert all('visual_group_id' not in c for c in candidates)
    assert len(report['region_evidence']['balloons'][0]['related_candidate_ids']) == 2


def test_merged_orchestrator_rejects_unrelated_split_before_segmentation(tmp_path,monkeypatch):
    source = np.full((40,20,3),255,np.uint8)
    path = tmp_path/'merged.png'; cv2.imwrite(str(path),source)
    entry = make_split(tmp_path,np.zeros_like(source),'wrong',0,[5,5,10,10])
    def forbidden(*args):
        pytest.fail('Segmentation must not run on incompatible sources')
    monkeypatch.setattr(orchestrator,'analyze_page',forbidden)
    with pytest.raises(ValueError,match='pixels'):
        orchestrator.build_merged_audit(path,[entry])
