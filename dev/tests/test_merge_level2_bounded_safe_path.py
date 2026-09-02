import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from processamento.unificacao_imagens.image_stitcher import WhiteBand
from processamento.unificacao_imagens.image_stitcher_level2 import (
    Level2Config,
    UniformColorBand,
    analyze_uniform_color_bands,
    solve_pending_region,
)


class MergeLevel2BoundedSafePathTests(unittest.TestCase):
    def _band(self, center, height=200, ratio=0.995):
        half=height//2
        return WhiteBand(center-half, center+half, height, ratio)

    def _uniform(self, center, height=300, rgb=(223,218,210), std=0.2):
        half=height//2
        return UniformColorBand(
            center-half,center+half,height,rgb,std,std,0.1,
        )

    def test_finds_path_using_safe_band_outside_level1_target_window(self):
        result=solve_pending_region(
            0,16_731,
            [self._band(4_396),self._band(12_500)],
        )
        self.assertEqual(result['status'],'resolved')
        self.assertEqual(result['resolved_intervals'],[[0,4_396],[4_396,12_500],[12_500,16_731]])
        self.assertEqual([x['center'] for x in result['selected_cuts']],[4_396,12_500])

    def test_never_relaxes_minimum_white_band(self):
        cfg=Level2Config(min_white_band=150)
        result=solve_pending_region(0,16_731,[self._band(5_000,height=149)],cfg)
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(result['resolved_intervals'],[])
        self.assertEqual(result['rejected_candidates'][0]['reason'],'white_band_too_short')

    def test_can_make_safe_partial_progress(self):
        result=solve_pending_region(0,25_000,[self._band(5_000)])
        self.assertEqual(result['status'],'partial')
        self.assertEqual(result['resolved_intervals'],[[0,5_000]])
        self.assertEqual(result['residual_interval'],[5_000,25_000])

    def test_does_not_force_cut_without_reachable_safe_band(self):
        result=solve_pending_region(0,16_731,[])
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(result['selected_cuts'],[])
        self.assertEqual(result['residual_interval'],[0,16_731])

    def test_allows_safe_small_edge_chunk_only_after_strict_path_fails(self):
        result=solve_pending_region(
            42_252,55_042,
            [self._band(43_827,height=427,ratio=0.99997)],
        )
        self.assertEqual(result['status'],'resolved')
        self.assertEqual(result['resolved_intervals'],[[42_252,43_827],[43_827,55_042]])
        self.assertEqual(result['strategy'],'bounded_safe_balanced_path_with_edge_chunk')
        self.assertEqual(result['path_mode'],'safe_edge_chunk_last_fallback')
        self.assertTrue(result['edge_chunk_relaxation_used'])
        self.assertEqual(result['edge_chunks'][0]['position'],'start')
        self.assertEqual(result['edge_chunks'][0]['height'],1_575)

    def test_allows_safe_small_final_edge_chunk(self):
        result=solve_pending_region(
            0,12_790,
            [self._band(11_215,height=427,ratio=0.99997)],
        )
        self.assertEqual(result['status'],'resolved')
        self.assertEqual(result['resolved_intervals'],[[0,11_215],[11_215,12_790]])
        self.assertEqual(result['edge_chunks'][0]['position'],'end')
        self.assertEqual(result['edge_chunks'][0]['height'],1_575)

    def test_does_not_allow_small_internal_chunk(self):
        cfg=Level2Config(min_chunk_height=3_000,max_chunk_height=12_000,target_height=7_000)
        result=solve_pending_region(
            0,20_000,
            [self._band(5_000),self._band(6_000),self._band(15_000)],
            cfg,
        )
        self.assertEqual(result['status'],'resolved')
        intervals=result['resolved_intervals']
        self.assertTrue(all((b-a)>=3_000 for a,b in intervals[1:-1]))
        self.assertNotIn([5_000,6_000],intervals)
        self.assertFalse(result['edge_chunk_relaxation_used'])

    def test_edge_fallback_does_not_relax_white_band_requirement(self):
        cfg=Level2Config(min_white_band=150)
        result=solve_pending_region(
            42_252,55_042,
            [self._band(43_827,height=149,ratio=0.99999)],
            cfg,
        )
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(result['selected_cuts'],[])
        self.assertEqual(result['rejected_candidates'][0]['reason'],'white_band_too_short')

    def test_accepts_wide_uniform_band_without_requiring_white(self):
        # #dfdad2: o candidato é seguro pela baixa variação espacial, não por
        # ser branco. A posição central produz dois chunks equilibrados.
        result=solve_pending_region(
            42_252,55_042,
            [
                self._band(43_827,height=427,ratio=0.99997),
                self._uniform(48_647,height=900,rgb=(223,218,210)),
            ],
        )
        self.assertEqual(result['status'],'resolved')
        self.assertFalse(result['edge_chunk_relaxation_used'])
        self.assertEqual(result['selected_cuts'][0]['candidate_type'],'uniform_color_band')
        self.assertEqual(result['selected_cuts'][0]['color_hex'],'#dfdad2')
        self.assertEqual(result['resolved_intervals'],[[42_252,48_647],[48_647,55_042]])

    def test_uniform_band_detector_is_color_agnostic_and_rejects_content_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'page-001.png'
            image=Image.new('RGB',(240,1200),(255,255,255))
            draw=ImageDraw.Draw(image)
            # Conteúdo escuro acima e abaixo; gutter bege sólido no meio.
            draw.rectangle((0,0,239,349),fill=(70,60,50))
            draw.rectangle((30,100,210,250),fill=(220,30,30))
            draw.rectangle((0,350,239,799),fill=(223,218,210))
            draw.rectangle((0,800,239,1199),fill=(40,50,60))
            draw.rectangle((20,900,220,1050),fill=(20,220,60))
            image.save(path)
            bands=analyze_uniform_color_bands(
                [path],sample_width=120,max_channel_std=4.0,max_row_delta=3.0
            )
        beige=[b for b in bands if b.color_hex=='#dfdad2' and b.height>=400]
        self.assertTrue(beige,[(b.start,b.end,b.color_hex,b.height) for b in bands])

    def test_balance_score_prefers_four_source_files_as_soft_preference(self):
        # As duas opções são SAFE. O corte em 6.400 atravessa quatro fontes de
        # cada lado; o corte em 4.000 deixaria um merge curto com só duas.
        sources=[(0,2_000),(2_000,4_000),(4_000,6_000),(6_000,8_000),
                 (8_000,10_000),(10_000,12_000),(12_000,14_000)]
        result=solve_pending_region(
            0,14_000,
            [self._uniform(4_000,height=300),self._uniform(6_400,height=300)],
            source_intervals=sources,
        )
        self.assertEqual(result['status'],'resolved')
        self.assertEqual(result['selected_cuts'][0]['center'],6_400)
        self.assertTrue(result['balance']['preference_is_not_safety_rule'])

    def test_balance_preference_never_makes_unsafe_candidate_eligible(self):
        cfg=Level2Config(min_uniform_band=150,preferred_source_files=4)
        sources=[(0,2_000),(2_000,4_000),(4_000,6_000),(6_000,8_000),
                 (8_000,10_000),(10_000,12_000),(12_000,14_000)]
        result=solve_pending_region(
            0,14_000,
            [self._uniform(7_000,height=149)],
            cfg,source_intervals=sources,
        )
        self.assertEqual(result['status'],'unresolved')
        self.assertEqual(result['selected_cuts'],[])
        self.assertEqual(result['rejected_candidates'][0]['reason'],'uniform_band_too_short')


if __name__=='__main__':
    unittest.main()
