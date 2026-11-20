"""Train an explanatory entropy-based decision tree on synthetic labeled report PAIRS.
Run: python train_decision_tree.py
IMPORTANT: Demonstration data; evaluate on real confirmed claims before deployment.
"""
import csv
import json
from pathlib import Path
import numpy as np
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
from sklearn.model_selection import GroupShuffleSplit
from sklearn.tree import DecisionTreeClassifier, plot_tree, export_text
from joblib import dump
from decision_tree import FEATURE_NAMES, MODEL_PATH, pair_features
from matching import lexical

BASE = Path(__file__).resolve().parent
# Distinct *item families*. These are purpose-written examples, not real verified user claims.
CASES = [
 ('necklace', 'سلسلة ذهب', 'gold necklace', 'مجوهرات', 'ذهبي', 'مكتبة', 'library', '2026-10-25'),
 ('earbuds', 'سماعة بلوتوث سوداء', 'black wireless earbuds', 'إلكترونيات', 'اسود', 'مدرج', 'hall', '2026-10-18'),
 ('wallet', 'محفظة سوداء', 'black wallet', 'اكسسوارات', 'اسود', 'مكتبة', 'library', '2026-10-19'),
 ('phone', 'موبايل ازرق', 'blue phone', 'إلكترونيات', 'ازرق', 'معمل', 'lab', '2026-10-20'),
 ('keys', 'مفاتيح عربية', 'car keys', 'اكسسوارات', 'فضي', 'بوابة', 'gate', '2026-10-23'),
 ('ring', 'خاتم ذهب', 'gold ring', 'مجوهرات', 'ذهبي', 'كافتيريا', 'cafeteria', '2026-10-24'),
 ('laptop', 'لاب توب اسود', 'black laptop', 'إلكترونيات', 'اسود', 'معمل', 'lab', '2026-10-16'),
 ('bag', 'شنطة زرقاء', 'blue bag', 'اكسسوارات', 'ازرق', 'بوابة', 'gate', '2026-10-28'),
 ('card', 'كارنيه الجامعة', 'university ID card', 'وثائق', 'ابيض', 'مدرج', 'hall', '2026-10-21'),
 ('watch', 'ساعة سوداء', 'black watch', 'اكسسوارات', 'اسود', 'كافتيريا', 'cafeteria', '2026-10-12'),
 ('charger', 'شاحن موبايل ابيض', 'white phone charger', 'إلكترونيات', 'ابيض', 'مكتبة', 'library', '2026-10-14'),
 ('glasses', 'نظارة سوداء', 'black glasses', 'اكسسوارات', 'اسود', 'مدرج', 'hall', '2026-10-26'),
]


def make_report(case, english=False, location=None, color=None, date=None, description=None):
    _, ar, en, category, base_color, ar_place, en_place, day = case
    title = en if english else ar
    return {'title': title, 'description': description or title,
            'category': category, 'color': color or base_color,
            'location': location or (en_place if english else ar_place),
            'event_date': date or day}


def examples():
    rows = []
    for i, case in enumerate(CASES):
        src = make_report(case)
        # Positive examples: same reported item, paraphrasing and varying location/date.
        positive = [
            make_report(case, True),
            make_report(case, True, description='found ' + case[2] + ' near ' + case[6]),
            make_report(case, False, description='لقيت ' + case[1]),
            make_report(case, True, location=case[5]),
        ]
        # Negative examples include unrelated items, and harder same-category distractors.
        other = [CASES[(i+1)%len(CASES)], CASES[(i+3)%len(CASES)],
                 CASES[(i+5)%len(CASES)], CASES[(i+7)%len(CASES)]]
        negative = [
            make_report(other[0], True),
            make_report(other[1], False, location=case[5]),
            make_report(other[2], True, color=case[4], location=case[6]),
            make_report(other[3], False, location=case[5], color=case[4], date=case[7]),
        ]
        for label, group in ((1, positive), (0, negative)):
            for target in group:
                # Use the SAME lexical description feature as the offline inference mode.
                description = lexical(src['title']+' '+src['description'],
                                      target['title']+' '+target['description'])
                rows.append({'group': case[0], 'label':label,
                             'features':pair_features(src,target,description)})
    return rows


def train():
    rows = examples()
    X=np.array([r['features'] for r in rows], dtype=float)
    y=np.array([r['label'] for r in rows], dtype=int)
    groups=[r['group'] for r in rows]
    # Group split keeps an item family out of both train and validation simultaneously.
    tr,te=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=42).split(X,y,groups))
    model=DecisionTreeClassifier(criterion='entropy',max_depth=4,min_samples_leaf=3,random_state=42,
                                 class_weight='balanced')
    model.fit(X[tr],y[tr]); predictions=model.predict(X[te])
    metrics={'data_provenance':'synthetic illustrative examples, NOT verified real-world item matches',
             'classifier':'sklearn DecisionTreeClassifier (CART splits using entropy; not strict ID3)',
             'total_pairs':len(rows),'training_pairs':len(tr),'held_out_pairs':len(te),
             'held_out_families':sorted(set(groups[i] for i in te)),
             'accuracy':float(accuracy_score(y[te],predictions)),
             'precision':float(precision_score(y[te],predictions,zero_division=0)),
             'recall':float(recall_score(y[te],predictions,zero_division=0)),
             'f1':float(f1_score(y[te],predictions,zero_division=0)),
             'confusion_matrix':confusion_matrix(y[te],predictions,labels=[0,1]).tolist(),
             'limitations':'Only synthetic pairs; metrics do not estimate accuracy on student reports. No claim is approved automatically.'}
    MODEL_PATH.parent.mkdir(exist_ok=True)
    # Trained model on all instructional examples after measuring held-out scores.
    model.fit(X,y)
    dump({'model':model,'features':FEATURE_NAMES,'version':1,'provenance':'synthetic'},MODEL_PATH)
    (BASE/'decision_tree_metrics.json').write_text(json.dumps(metrics,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    with (BASE/'decision_tree_training_pairs.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f); writer.writerow(['group','label']+FEATURE_NAMES)
        for row in rows: writer.writerow([row['group'],row['label']]+row['features'])
    (BASE/'decision_tree_rules.txt').write_text(export_text(model,feature_names=FEATURE_NAMES),encoding='utf-8')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.figure(figsize=(17,9)); plot_tree(model,feature_names=FEATURE_NAMES,class_names=['Unlikely','Potential'],
                                             filled=True,rounded=True,fontsize=8)
        plt.tight_layout(); plt.savefig(BASE/'decision_tree_visualization.png',dpi=140,bbox_inches='tight')
        plt.close()
    except ImportError:
        print('matplotlib unavailable; text tree rules saved instead')
    print(json.dumps(metrics,ensure_ascii=False,indent=2))

if __name__=='__main__':train()
