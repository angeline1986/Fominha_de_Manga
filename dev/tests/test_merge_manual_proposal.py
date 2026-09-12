import tempfile,unittest
from pathlib import Path
from PIL import Image
from processamento.merge_manual.proposal import generate_proposal
class T(unittest.TestCase):
 def test_partial_slice(self):
  with tempfile.TemporaryDirectory() as td:
   manga=Path(td)/"m";ch=manga/"IMG"/"6";ch.mkdir(parents=True)
   Image.new("RGB",(4,10),(255,0,0)).save(ch/"page-001.png");Image.new("RGB",(4,10),(0,255,0)).save(ch/"page-002.png")
   row={"needs_review":True,"merge_state":"pendente_review","merge_level5_detail":{"available":True,"valid":True,"review_pending_segments":[{"global_start":5,"global_end":20}]}}
   p=generate_proposal(manga,ch,review_row=row,block_id="pending-1",start_file="page-001.png",end_file="page-002.png",cuts=[5])
   self.assertEqual(p["source_block"]["height"],15);self.assertEqual([x["height"] for x in p["outputs"]],[5,10]);self.assertFalse(p["safety"]["official_merge_modified"])
if __name__=="__main__":unittest.main()
