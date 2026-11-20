"""Offline matching regression tests; run: python -m unittest -v test_matching.py"""
import unittest
from matching import lexical, score_matches

def report(id,kind,title,description,category,color,location,date):
 return dict(id=id,kind=kind,title=title,description=description,category=category,color=color,location=location,event_date=date)

class MatchingTests(unittest.TestCase):
 def setUp(self):
  self.source=report(1,'lost','سلسلة ذهب','سلسلة ذهب بالقرب من مكتبة الجامعة','مجوهرات','ذهبي','مكتبة','2026-10-25')
 def test_arabic_english_concepts(self):
  self.assertGreater(lexical('سلسلة ذهب','gold necklace'),.95)
 def test_normalization(self):
  self.assertGreater(lexical('سِلْسِلَة ذَهَب','سلسلة ذهب'),.95)
 def test_rank_relevant_above_irrelevant(self):
  good=report(2,'found','gold necklace','gold necklace found at the library','مجوهرات','ذهبي','مكتبة','2026-10-26')
  bad=report(3,'found','موبايل اسود','هاتف اسود عند البوابة','إلكترونيات','اسود','بوابة','2026-09-11')
  ranked,_=score_matches(self.source,[bad,good])
  self.assertEqual(ranked[0]['report']['id'],2)
  self.assertGreater(ranked[0]['score'],ranked[1]['score'])
 def test_results_unique_when_input_unique(self):
  other=report(4,'found','سلسلة ذهب','تم العثور على سلسلة','مجوهرات','ذهبي','مكتبة','2026-10-26')
  ranked,_=score_matches(self.source,[other])
  self.assertEqual(len(ranked),1)
 def test_score_is_bounded(self):
  ranked,_=score_matches(self.source,[self.source])
  self.assertGreaterEqual(ranked[0]['score'],0)
  self.assertLessEqual(ranked[0]['score'],100)

if __name__=='__main__': unittest.main()
