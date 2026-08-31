import unittest
from processamento.pdf_original.pdf_divergence_review import build_analysis
class TestReview(unittest.TestCase):
    def test_image(self):
        d={"chapter":"28","issue_type":"image_validation_failed","pdf_generated":False,"images":{"expected":1,"found":1,"errors":["x page-001.png"],"metadata":[{"file":"page-001.png","width":1280,"height":3,"pdf_width":960,"pdf_height":2.25}]}}
        t="\n".join(build_analysis(d)); self.assertIn("1 de 1",t); self.assertIn("1280x3",t); self.assertIn("960.00x2.25",t); self.assertIn("Revisar visualmente a página 1",t)
if __name__=="__main__": unittest.main()
