"""Unit tests for Decision Tree integration."""
import unittest
from matching import score_matches
from decision_tree import pair_features, classify_pair, load_model, FEATURE_NAMES


def item(id,kind,title,category,color,location,day):
    return dict(id=id,kind=kind,title=title,description=title,category=category,
                color=color,location=location,event_date=day)

class DecisionTreeTests(unittest.TestCase):
    def test_model_artifact(self):
        self.assertIsNotNone(load_model())
        self.assertEqual(len(FEATURE_NAMES),5)
    def test_predictions_and_features(self):
        a=item(1,'lost','سلسلة ذهب','مجوهرات','ذهبي','مكتبة','2026-10-25')
        b=item(2,'found','gold necklace','مجوهرات','ذهبي','library','2026-10-26')
        self.assertEqual(len(pair_features(a,b)),5)
        prediction=classify_pair(a,b)
        self.assertIn(prediction['label'], ('potential_match','unlikely_match'))
    def test_matching_response_has_tree_signal(self):
        a=item(1,'lost','سلسلة ذهب','مجوهرات','ذهبي','مكتبة','2026-10-25')
        b=item(2,'found','gold necklace','مجوهرات','ذهبي','library','2026-10-26')
        result,_=score_matches(a,[b]);self.assertIn('decision_tree',result[0])
        self.assertEqual(result[0]['report']['id'],2)
    def test_score_unaffected_by_tree(self):
        a=item(1,'lost','سلسلة ذهب','مجوهرات','ذهبي','مكتبة','2026-10-25')
        b=item(2,'found','gold necklace','مجوهرات','ذهبي','library','2026-10-26')
        result,_=score_matches(a,[b]);self.assertGreaterEqual(result[0]['score'],0)
        self.assertLessEqual(result[0]['score'],100)

if __name__ == '__main__':unittest.main()
