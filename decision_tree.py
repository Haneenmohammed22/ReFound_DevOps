"""Advisory Decision Tree classifier for Lost/Found report pairs.

A model trained on synthetic instructional examples is NOT evidence of ownership.
No user reports, images, emails, or chat content are used in training.
"""
from datetime import date
from pathlib import Path
from functools import lru_cache

FEATURE_NAMES = ['description_similarity', 'category_similarity', 'color_similarity',
                 'location_similarity', 'date_proximity']
MODEL_PATH = Path(__file__).resolve().parent / 'models' / 'decision_tree.joblib'


def pair_features(source, target, description_similarity=None):
    from matching import lexical, text_scores
    if description_similarity is None:
        desc, _ = text_scores(source, [target])
        description_similarity = desc[0]
    def field(name):
        return lexical(source.get(name, ''), target.get(name, ''))
    try:
        diff = abs((date.fromisoformat(source['event_date']) -
                    date.fromisoformat(target['event_date'])).days)
        proximity = max(0.0, 1.0 - diff / 30.0)
    except (KeyError, TypeError, ValueError):
        proximity = 0.0
    return [round(float(description_similarity), 6), field('category'), field('color'),
            field('location'), proximity]


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.exists():
        return None
    try:
        from joblib import load
        item = load(MODEL_PATH)
        if item.get('features') != FEATURE_NAMES or item.get('version') != 1:
            return None
        return item['model']
    except Exception:
        return None


def classify_pair(source, target, description_similarity=None):
    """Return a second, explicitly advisory signal; never auto-approve claims."""
    model = load_model()
    if model is None:
        return None
    features = pair_features(source, target, description_similarity)
    prediction = int(model.predict([features])[0])
    return {'label': 'potential_match' if prediction == 1 else 'unlikely_match',
            'algorithm': 'Decision Tree (entropy)', 'training_data': 'synthetic'}
